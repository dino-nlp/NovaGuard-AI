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
DEFAULT_BUG_LEVEL = "warning" # Default severity for bugs if LLM doesn't specify clearly

class BugHunterAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("BugHunter", config, ollama_client, prompt_manager)
        # Supported languages for bug hunting can be quite broad
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "csharp", "go",
            "c", "cpp", "rust", "ruby", "php", "kotlin", "swift"
        ]
        self.default_prompt_name = "bug_hunt_general"
        self.language_specific_prompt_prefix = "bug_hunt_" # e.g., bug_hunt_python

    def review(
        self,
        files_data: List[ChangedFile],
        tier1_tool_results: Optional[Dict[str, Any]] = None # BugHunter might not use Tier1 results directly as much
    ) -> List[Dict[str, Any]]:
        """
        Analyzes code for potential bugs, logical errors, and runtime issues.

        Args:
            files_data: List of ChangedFile objects to review.
            tier1_tool_results: Optional results from Tier 1 tools (might be used for context).

        Returns:
            A list of dictionaries, each representing a potential bug finding.
        """
        logger.info(f"<{self.agent_name}> Starting bug hunt for {len(files_data)} files.")
        all_findings: List[Dict[str, Any]] = []

        relevant_files = self._filter_files_by_language(files_data, self.supported_languages)
        if not relevant_files:
            logger.info(f"<{self.agent_name}> No files match supported languages for bug hunting. Skipping.")
            return all_findings

        for file_data in relevant_files:
            logger.debug(f"<{self.agent_name}> Hunting for bugs in file: {file_data.path} (Language: {file_data.language})")

            # Prepare context from Tier 1 tools if relevant (e.g., warnings about complexity)
            # For now, we'll keep it simple and not deeply integrate tier1_tool_results for BugHunter.
            additional_context_from_tools = "No specific warnings from other tools were provided for initial bug assessment."
            if tier1_tool_results:
                # Potentially summarize any critical warnings or complexity metrics if available
                pass


            prompt_template_name = f"{self.language_specific_prompt_prefix}{file_data.language}"
            if not self.prompt_manager.get_prompt_template(prompt_template_name):
                prompt_template_name = self.default_prompt_name
            
            prompt_variables = {
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
                logger.error(f"<{self.agent_name}> Could not render prompt for {file_data.path}. Skipping.")
                continue

            model_name = self.config.get_model_for_agent(self.agent_name) # Expects e.g., "deepseek-coder:33b..."
            if not model_name:
                logger.error(f"<{self.agent_name}> Model name not configured for agent {self.agent_name}. Skipping file {file_data.path}.")
                continue

            try:
                logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for bug hunt in {file_data.path}.")
                system_msg = (
                    f"You are {self.agent_name}, an AI assistant highly skilled in identifying potential bugs, "
                    f"logical errors, race conditions, resource leaks, null pointer issues, and other runtime vulnerabilities "
                    f"in {file_data.language} code. Focus on correctness and potential for failure. "
                    "Do not comment on code style unless it directly contributes to a bug."
                )
                
                response_text = self.ollama_client.invoke(
                    model_name=model_name,
                    prompt=rendered_prompt,
                    system_message_content=system_msg,
                    is_json_mode=True,
                    temperature=0.4 # Moderate temperature for bug finding
                )

                logger.debug(f"<{self.agent_name}> LLM raw response for {file_data.path}: {response_text[:500]}...")
                
                llm_findings = json.loads(response_text)
                if not isinstance(llm_findings, list):
                    logger.warning(f"<{self.agent_name}> LLM response for {file_data.path} was not a JSON list. Got: {type(llm_findings)}")
                    llm_findings = []

                for llm_finding in llm_findings:
                    if not isinstance(llm_finding, dict):
                        logger.warning(f"<{self.agent_name}> Invalid finding format in LLM response for {file_data.path}: {llm_finding}")
                        continue
                    
                    level_from_llm = str(llm_finding.get("severity", DEFAULT_BUG_LEVEL)).lower()
                    internal_level = SEVERITY_MAP.get(level_from_llm, DEFAULT_BUG_LEVEL)
                    bug_type = llm_finding.get("bug_type", "general_bug").replace(" ", "_").lower()

                    finding = self._format_finding(
                        file_path=file_data.path,
                        line_start=int(llm_finding.get("line_start", 1)),
                        line_end=llm_finding.get("line_end"), # Optional
                        message=llm_finding.get("message", "LLM provided no specific message for this bug."),
                        # rule_id should be more specific based on the bug type if possible
                        rule_id_suffix=f"llm_bug_{bug_type}",
                        level=internal_level,
                        suggestion=llm_finding.get("suggestion"),
                        # 'explanation' from LLM can be added to the message or a custom field if SARIF supports it well
                        # For now, let's ensure the message contains the essence of the explanation.
                    )
                    # Add explanation to message if not already part of it
                    if "explanation" in llm_finding and llm_finding["explanation"] not in finding["message_text"]:
                        finding["message_text"] += f" (Explanation: {llm_finding['explanation']})"
                    
                    all_findings.append(finding)
                
                logger.info(f"<{self.agent_name}> LLM identified {len(llm_findings)} potential bugs in {file_data.path}.")

            except json.JSONDecodeError as e:
                logger.error(f"<{self.agent_name}> Failed to parse LLM JSON response for {file_data.path}: {e}. Response: {response_text[:500]}")
            except Exception as e:
                logger.error(f"<{self.agent_name}> Error during LLM interaction for {file_data.path}: {e}", exc_info=True)
        
        logger.info(f"<{self.agent_name}> Bug hunt completed. Total potential bugs found: {len(all_findings)}.")
        return all_findings