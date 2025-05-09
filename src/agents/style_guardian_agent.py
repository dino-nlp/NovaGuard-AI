# NOVAGUARD-AI/src/agents/style_guardian_agent.py
import json
import logging
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent
from ..core.shared_context import ChangedFile,SharedReviewContext
from ..core.config_loader import Config
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# Define SEVERITY_MAP or import from a central location if available
SEVERITY_MAP: Dict[str, str] = {
    "error": "error", "critical": "error", "high": "error",
    "warning": "warning", "medium": "warning",
    "note": "note", "information": "note", "info": "note", "low": "note",
    "none": "none",
}
DEFAULT_STYLE_LEVEL = "note" # Default level for style issues

class StyleGuardianAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("StyleGuardian", config, ollama_client, prompt_manager)
        self.supported_languages = ["python", "javascript", "typescript", "java", "csharp", "go"]
        self.default_prompt_name = "style_review_general"
        self.language_specific_prompt_prefix = "style_review_"

    def _get_relevant_linter_findings(
        self,
        file_path: str,
        language: Optional[str],
        tier1_tool_results: Optional[Dict[str, Any]]
    ) -> List[str]:
        linter_messages: List[str] = []
        if not tier1_tool_results or not language: return linter_messages
        linter_category_results = tier1_tool_results.get("linters", {})
        if not isinstance(linter_category_results, dict):
            logger.warning(f"<{self.agent_name}> Expected 'linters' key in tier1_tool_results to be a dict, got {type(linter_category_results)}")
            return linter_messages
        specific_linter_findings = linter_category_results.get(language.lower(), [])
        if not isinstance(specific_linter_findings, list):
            logger.warning(f"<{self.agent_name}> Expected findings for language '{language.lower()}' under 'linters' to be a list, got {type(specific_linter_findings)}")
            return linter_messages
        for finding in specific_linter_findings:
            if isinstance(finding, dict) and finding.get("file_path") == file_path:
                msg = f"- Linter ({finding.get('tool_name', 'linter')}.{finding.get('rule_id', 'N/A')}) at line {finding.get('line_start', 'N/A')}: {finding.get('message_text', 'N/A')}"
                linter_messages.append(msg)
        if linter_messages: logger.debug(f"Found {len(linter_messages)} linter issues for {file_path} to include in prompt.")
        return linter_messages

    def review(
        self,
        files_data: List[ChangedFile],
        tier1_tool_results: Optional[Dict[str, Any]] = None, 
        pr_context: Optional[SharedReviewContext] = None
    ) -> List[Dict[str, Any]]:
        logger.info(f"<{self.agent_name}> Starting style review for {len(files_data)} files.")
        all_findings: List[Dict[str, Any]] = []
        relevant_files = self._filter_files_by_language(files_data, self.supported_languages)
        if not relevant_files:
            logger.info(f"<{self.agent_name}> No files match supported languages. Skipping review.")
            return all_findings
        
        # Lấy thông tin PR từ pr_context
        pr_title_for_prompt = pr_context.pr_title if pr_context and pr_context.pr_title else "Not available"
        pr_description_for_prompt = pr_context.pr_body if pr_context and pr_context.pr_body else "Not available"

        for file_data in relevant_files:
            logger.debug(f"<{self.agent_name}> Reviewing file: {file_data.path} (Language: {file_data.language})")
            linter_issues_for_prompt = self._get_relevant_linter_findings(file_data.path, file_data.language, tier1_tool_results)
            linter_context_str = "\n".join(linter_issues_for_prompt) if linter_issues_for_prompt else "No specific linter issues reported for this file by Tier 1 tools."
            prompt_template_name = f"{self.language_specific_prompt_prefix}{file_data.language}"
            if not self.config.get_prompt_template(prompt_template_name):
                logger.debug(f"<{self.agent_name}> Specific prompt '{prompt_template_name}' not found in config. Using default '{self.default_prompt_name}'.")
                prompt_template_name = self.default_prompt_name

            prompt_variables = {
                "agent_name": self.agent_name,
                "file_path": file_data.path,
                "file_content": file_data.content,
                "language": file_data.language,
                "linter_feedback": linter_context_str,
                "pr_title": pr_title_for_prompt,           
                "pr_description": pr_description_for_prompt,
                "output_format_instructions": """Please provide your findings STRICTLY as a JSON list.
- If multiple issues are found, return a list of JSON objects. Example: [{"line_start": ..., "message": ...}, {"line_start": ..., "message": ...}]
- If only one issue is found, return a list containing a single JSON object. Example: [{"line_start": ..., "message": ...}]
- If no style issues are found, return an empty JSON list. Example: []
Each JSON object in the list should represent a single style issue and have AT LEAST the following keys:
- "line_start": integer (the line number where the issue starts)
- "message": string (a concise description of the style issue)
- "suggestion": string (optional, a brief suggestion on how to fix it or improve)
- "severity": string (your assessment of severity: "low", "medium", "high")
You MAY also include these OPTIONAL keys if applicable:
- "line_end": integer (the line number where the issue ends, defaults to line_start)
- "confidence": string (e.g. "high", "medium", "low" - your confidence in this finding)
- "explanation_steps": list_of_strings (optional, brief step-by-step reasoning for your finding)"""
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
                logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for style review of {file_data.path}.")
                system_msg = f"You are {self.agent_name}, an AI assistant specialized in reviewing code for style, formatting, and conventions for {file_data.language} language. Analyze the provided code and linter feedback."
                response_text = self.ollama_client.invoke(
                    model_name=model_name, prompt=rendered_prompt,
                    system_message_content=system_msg, is_json_mode=True, temperature=0.2
                )
                # --- DEBUG LOG ---
                logger.info(f"<{self.agent_name}>:\n>>> START PROMPT <<<\n{rendered_prompt.strip()}\n>>> END PROMPT <<<")
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
                            # Heuristic check for single finding object
                            is_single_finding = "line_start" in parsed_response and ("message" in parsed_response or "message_text" in parsed_response)
                            if is_single_finding:
                                logger.debug(f"<{self.agent_name}> LLM returned a single JSON object, treating it as one finding.")
                                llm_findings_list = [parsed_response] # Wrap the dict in a list
                            else: # Fallback: Check for nested list
                                possible_keys = ["findings", "results", "suggestions", "issues", "style_issues"]
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
                    level_from_llm = str(llm_finding.get("severity", DEFAULT_STYLE_LEVEL)).lower()
                    internal_level = SEVERITY_MAP.get(level_from_llm, DEFAULT_STYLE_LEVEL)
                    finding = self._format_finding(
                        file_path=file_data.path,
                        line_start=int(llm_finding.get("line_start", 1)),
                        message=llm_finding.get("message", "LLM provided no message."), # Use 'message' key from LLM output
                        rule_id_suffix=f"llm_style_{llm_finding.get('code_issue_category', 'general').replace(' ', '_').lower()}",
                        level=internal_level,
                        suggestion=llm_finding.get("suggestion"),
                    )
                    if "line_end" in llm_finding: finding["line_end"] = llm_finding["line_end"]
                    if "confidence" in llm_finding: finding["confidence"] = llm_finding["confidence"]
                    all_findings.append(finding)
                    processed_count += 1
                logger.info(f"<{self.agent_name}> LLM processing yielded {processed_count} findings for {file_data.path}.")
            except Exception as e:
                logger.error(f"<{self.agent_name}> Error during LLM interaction or processing for {file_data.path}: {e}", exc_info=True)
        logger.info(f"<{self.agent_name}> Review completed. Total style findings: {len(all_findings)}.")
        return all_findings