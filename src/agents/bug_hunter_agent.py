# NOVAGUARD-AI/src/agents/bug_hunter_agent.py
import json
import logging
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent
from ..core.shared_context import ChangedFile
from ..core.config_loader import Config
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# Define SEVERITY_MAP or import from a central location if available
SEVERITY_MAP: Dict[str, str] = {
    "critical": "error", "error": "error", "high": "error",
    "warning": "warning", "medium": "warning",
    "note": "note", "information": "note", "info": "note", "low": "note",
    "none": "none",
}
DEFAULT_BUG_LEVEL = "warning"

class BugHunterAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("BugHunter", config, ollama_client, prompt_manager)
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "csharp", "go",
            "c", "cpp", "rust", "ruby", "php", "kotlin", "swift"
        ]
        self.default_prompt_name = "bug_hunter_generic" # Changed to match filename
        self.language_specific_prompt_prefix = "bug_hunt_"

    def review(
        self,
        files_data: List[ChangedFile],
        tier1_tool_results: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        logger.info(f"<{self.agent_name}> Starting bug hunt for {len(files_data)} files.")
        all_findings: List[Dict[str, Any]] = []
        relevant_files = self._filter_files_by_language(files_data, self.supported_languages)
        if not relevant_files:
            logger.info(f"<{self.agent_name}> No files match supported languages for bug hunting. Skipping.")
            return all_findings

        for file_data in relevant_files:
            logger.debug(f"<{self.agent_name}> Hunting for bugs in file: {file_data.path} (Language: {file_data.language})")
            additional_context_from_tools = "No specific warnings from other tools were provided for initial bug assessment."
            if tier1_tool_results: pass # Add logic if needed
            prompt_template_name = f"{self.language_specific_prompt_prefix}{file_data.language}"
            if not self.config.get_prompt_template(prompt_template_name):
                logger.debug(f"<{self.agent_name}> Specific prompt '{prompt_template_name}' not found in config. Using default '{self.default_prompt_name}'.")
                prompt_template_name = self.default_prompt_name

            prompt_variables = {
                "agent_name": self.agent_name,
                "file_path": file_data.path,
                "file_content": file_data.content,
                "language": file_data.language,
                "additional_context": additional_context_from_tools,
                "output_format_instructions": """Please provide your findings as a JSON list. Each object in the list should represent a single potential bug and have the following keys:
- "line_start": integer (the line number where the potential bug starts or is most evident)
- "line_end": integer (optional, the line number where the scope of the bug ends)
- "message": string (a concise description of the potential bug and its impact)
- "bug_type": string (e.g., "NullPointerException", "ResourceLeak", "OffByOneError", "LogicError", "RaceCondition", "DataCorruption", "SecurityVulnerability_ CWE-ID_IF_APPLICABLE")
- "explanation": string (a brief explanation of why this is a potential bug)
- "suggestion": string (optional, a brief suggestion on how to fix or further investigate it)
- "severity": string (your assessment of severity: "critical", "high", "medium", "low", or "info"/"note")
- "confidence": string (optional, your confidence in this finding: "high", "medium", "low")
If no potential bugs are found, return an empty list []."""
            }
            rendered_prompt = self.prompt_manager.get_prompt(prompt_template_name, prompt_variables)
            if not rendered_prompt:
                logger.error(f"<{self.agent_name}> Could not render prompt '{prompt_template_name}' for {file_data.path}. Skipping.")
                continue
            model_name = self.config.get_model_for_agent(self.agent_name)
            if not model_name:
                logger.error(f"<{self.agent_name}> Model name not configured. Skipping file {file_data.path}.")
                continue

            try:
                logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for bug hunt in {file_data.path}.")
                system_msg = (f"You are {self.agent_name}, an AI assistant highly skilled in identifying potential bugs... in {file_data.language} code...")
                response_text = self.ollama_client.invoke(
                    model_name=model_name, prompt=rendered_prompt,
                    system_message_content=system_msg, is_json_mode=True, temperature=0.4
                )
                # --- DEBUG LOG ---
                logger.info(f"<{self.agent_name}> RAW LLM RESPONSE for {file_data.path}:\n>>> START LLM RESPONSE <<<\n{response_text.strip()}\n>>> END LLM RESPONSE <<<")

                llm_findings_list: List[Dict] = []
                try:
                    # --- START Updated Parsing Logic ---
                    stripped_response_text = response_text.strip()
                    if not stripped_response_text:
                        logger.warning(f"<{self.agent_name}> LLM returned empty or whitespace-only response for {file_data.path}.")
                    else:
                        parsed_response = json.loads(stripped_response_text)
                        if isinstance(parsed_response, list):
                            llm_findings_list = parsed_response
                            logger.debug(f"<{self.agent_name}> LLM returned a JSON list with {len(llm_findings_list)} items.")
                        elif isinstance(parsed_response, dict):
                            is_single_finding = "line_start" in parsed_response and ("message" in parsed_response or "message_text" in parsed_response)
                            if is_single_finding:
                                logger.debug(f"<{self.agent_name}> LLM returned a single JSON object, treating it as one finding.")
                                llm_findings_list = [parsed_response]
                            else: # Fallback: Check for nested list
                                possible_keys = ["findings", "results", "bugs", "potential_bugs"]
                                found = False
                                for key in possible_keys:
                                    if key in parsed_response and isinstance(parsed_response.get(key), list):
                                        llm_findings_list = parsed_response[key]
                                        logger.debug(f"<{self.agent_name}> LLM returned a dict, extracted list from key '{key}'.")
                                        found = True; break
                                if not found:
                                    logger.warning(f"<{self.agent_name}> LLM response was a JSON dict, but no known key contained a list, and it didn't look like a single finding object. Got dict keys: {list(parsed_response.keys())}")
                        else:
                            logger.warning(f"<{self.agent_name}> LLM response parsed but was not a JSON list or dict. Got: {type(parsed_response)}")
                    # --- END Updated Parsing Logic ---
                except json.JSONDecodeError as e:
                    logger.error(f"<{self.agent_name}> Failed to parse LLM JSON response for {file_data.path}: {e}. Response: '{response_text[:500]}...'")

                processed_count = 0
                for llm_finding in llm_findings_list:
                    if not isinstance(llm_finding, dict):
                        logger.warning(f"<{self.agent_name}> Invalid finding format in LLM findings list for {file_data.path}: {llm_finding}")
                        continue
                    level_from_llm = str(llm_finding.get("severity", DEFAULT_BUG_LEVEL)).lower()
                    internal_level = SEVERITY_MAP.get(level_from_llm, DEFAULT_BUG_LEVEL)
                    bug_type = llm_finding.get("bug_type", "general_bug").replace(" ", "_").lower()
                    finding = self._format_finding(
                        file_path=file_data.path,
                        line_start=int(llm_finding.get("line_start", 1)),
                        message=llm_finding.get("message", "LLM provided no specific message for this bug."),
                        rule_id_suffix=f"llm_bug_{bug_type}",
                        level=internal_level,
                        suggestion=llm_finding.get("suggestion"),
                    )
                    if "explanation" in llm_finding and llm_finding["explanation"] not in finding["message_text"]:
                        finding["message_text"] += f" (Explanation: {llm_finding['explanation']})"
                    if "line_end" in llm_finding: finding["line_end"] = llm_finding["line_end"]
                    if "confidence" in llm_finding: finding["confidence"] = llm_finding["confidence"]
                    all_findings.append(finding)
                    processed_count += 1
                logger.info(f"<{self.agent_name}> LLM processing yielded {processed_count} potential bugs in {file_data.path}.")
            except Exception as e:
                logger.error(f"<{self.agent_name}> Error during LLM interaction or processing for {file_data.path}: {e}", exc_info=True)
        logger.info(f"<{self.agent_name}> Bug hunt completed. Total potential bugs found: {len(all_findings)}.")
        return all_findings