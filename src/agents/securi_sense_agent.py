# NOVAGUARD-AI/src/agents/securi_sense_agent.py
import json
import logging
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent
from ..core.shared_context import ChangedFile
from ..core.config_loader import Config
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# Define SEVERITY_MAP or import from a central location
SEVERITY_MAP: Dict[str, str] = {
    "critical": "error", "error": "error", "high": "error", 
    "warning": "warning", "medium": "warning",             
    "note": "note", "information": "note", "info": "note", "low": "note", 
    "none": "none",
}
DEFAULT_SECURITY_LEVEL = "warning"

class SecuriSenseAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("SecuriSense", config, ollama_client, prompt_manager)
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "csharp", "go",
            "ruby", "php", "c", "cpp", "rust", "kotlin", "swift"
        ]
        self.default_prompt_name = "security_scan_general"
        self.language_specific_prompt_prefix = "security_scan_"

    def _get_relevant_sast_findings(
        self, file_path: str, tier1_tool_results: Optional[Dict[str, Any]]
    ) -> List[str]:
        sast_messages: List[str] = []
        if not tier1_tool_results: return sast_messages
        sast_category_results = tier1_tool_results.get("sast", {})
        if not isinstance(sast_category_results, dict):
            logger.warning(f"<{self.agent_name}> Expected 'sast' key in tier1_tool_results to be a dict, got {type(sast_category_results)}")
            return sast_messages
        for tool_key, findings_list in sast_category_results.items():
            if not isinstance(findings_list, list): continue
            for finding in findings_list:
                if not isinstance(finding, dict): continue
                if finding.get("file_path") == file_path:
                    msg = (f"- SAST Tool ({finding.get('tool_name', tool_key)} - Rule: {finding.get('rule_id', 'N/A')}) at line {finding.get('line_start', 'N/A')}: {finding.get('message_text', 'N/A')} (Severity: {finding.get('level', 'N/A')})")
                    sast_messages.append(msg)
        if sast_messages: logger.debug(f"Found {len(sast_messages)} SAST issues for {file_path} to include in prompt.")
        return sast_messages

    def review(
        self,
        files_data: List[ChangedFile],
        tier1_tool_results: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        logger.info(f"<{self.agent_name}> Starting security scan for {len(files_data)} files.")
        all_findings: List[Dict[str, Any]] = []
        relevant_files = self._filter_files_by_language(files_data, self.supported_languages)
        if not relevant_files:
            logger.info(f"<{self.agent_name}> No files match supported languages for security scan. Skipping.")
            return all_findings

        for file_data in relevant_files:
            logger.debug(f"<{self.agent_name}> Scanning file: {file_data.path} (Language: {file_data.language})")
            sast_issues_for_prompt = self._get_relevant_sast_findings(file_data.path, tier1_tool_results)
            sast_context_str = "\n".join(sast_issues_for_prompt) if sast_issues_for_prompt else "No specific findings reported for this file by SAST tools in Tier 1."
            prompt_template_name = f"{self.language_specific_prompt_prefix}{file_data.language}"
            if not self.config.get_prompt_template(prompt_template_name):
                logger.debug(f"<{self.agent_name}> Specific prompt '{prompt_template_name}' not found in config. Using default '{self.default_prompt_name}'.")
                prompt_template_name = self.default_prompt_name

            prompt_variables = {
                "agent_name": self.agent_name,
                "file_path": file_data.path,
                "file_content": file_data.content,
                "language": file_data.language,
                "sast_tool_feedback": sast_context_str,
                "output_format_instructions": """Please provide your findings as a JSON list... (instructions as before)"""
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
                logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for security scan of {file_data.path}.")
                system_msg = (f"You are {self.agent_name}, an AI assistant specialized in identifying security vulnerabilities... in {file_data.language} code...")
                response_text = self.ollama_client.invoke(
                    model_name=model_name, prompt=rendered_prompt,
                    system_message_content=system_msg, is_json_mode=True, temperature=0.3
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
                                possible_keys = ["findings", "results", "vulnerabilities", "security_issues"]
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
                        logger.warning(f"<{self.agent_name}> Invalid finding format for {file_data.path}: {llm_finding}")
                        continue
                    level_from_llm = str(llm_finding.get("severity", DEFAULT_SECURITY_LEVEL)).lower()
                    internal_level = SEVERITY_MAP.get(level_from_llm, DEFAULT_SECURITY_LEVEL)
                    vuln_type = llm_finding.get("vulnerability_type", "generic_security").replace(" ", "_").lower()
                    finding_message = llm_finding.get("message", "LLM provided no specific message for this vulnerability.")
                    if "explanation" in llm_finding and llm_finding["explanation"] not in finding_message:
                        finding_message += f" (Explanation: {llm_finding['explanation']})"
                    finding = self._format_finding(
                        file_path=file_data.path,
                        line_start=int(llm_finding.get("line_start", 1)),
                        message=finding_message,
                        rule_id_suffix=f"llm_sec_{vuln_type}",
                        level=internal_level,
                        suggestion=llm_finding.get("suggested_fix"),
                    )
                    if "line_end" in llm_finding: finding["line_end"] = llm_finding["line_end"]
                    if "cvss_score_v3" in llm_finding: finding["cvss_v3"] = llm_finding["cvss_score_v3"]
                    if "confidence" in llm_finding: finding["confidence"] = llm_finding["confidence"]
                    all_findings.append(finding)
                    processed_count += 1
                logger.info(f"<{self.agent_name}> LLM processing yielded {processed_count} potential security issues in {file_data.path}.")
            except Exception as e:
                logger.error(f"<{self.agent_name}> Error during LLM interaction or processing for {file_data.path}: {e}", exc_info=True)
        logger.info(f"<{self.agent_name}> Security scan completed. Total potential vulnerabilities found: {len(all_findings)}.")
        return all_findings