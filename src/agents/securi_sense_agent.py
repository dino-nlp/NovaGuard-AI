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
    "critical": "error", "error": "error", "high": "error", # SARIF 'error' maps to high/critical
    "warning": "warning", "medium": "warning",             # SARIF 'warning' maps to medium
    "note": "note", "information": "note", "info": "note", "low": "note", # SARIF 'note' maps to low/info
    "none": "none",
}
DEFAULT_SECURITY_LEVEL = "warning" # Default if LLM doesn't specify or map fails

class SecuriSenseAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("SecuriSense", config, ollama_client, prompt_manager)
        self.supported_languages = [ # Languages where SAST tools and LLM security analysis are common
            "python", "javascript", "typescript", "java", "csharp", "go",
            "ruby", "php", "c", "cpp", "rust", "kotlin", "swift"
        ]
        self.default_prompt_name = "security_scan_general"
        self.language_specific_prompt_prefix = "security_scan_" # e.g., security_scan_python

    def _get_relevant_sast_findings(
        self,
        file_path: str,
        tier1_tool_results: Optional[Dict[str, Any]] # Expects structure like {"sast": {"tool_key": [findings...]}}
    ) -> List[str]:
        """
        Extracts relevant SAST findings for the current file from tier1_tool_results.
        """
        sast_messages: List[str] = []
        if not tier1_tool_results:
            return sast_messages

        sast_category_results = tier1_tool_results.get("sast", {}) # "sast" is the category
        
        # Iterate through all tools configured under "sast" (e.g., "generic_semgrep_project")
        for tool_key, findings_list in sast_category_results.items():
            if not isinstance(findings_list, list): continue

            for finding in findings_list:
                if not isinstance(finding, dict): continue
                if finding.get("file_path") == file_path:
                    msg = (
                        f"- SAST Tool ({finding.get('tool_name', tool_key)} - Rule: {finding.get('rule_id', 'N/A')}) "
                        f"at line {finding.get('line_start', 'N/A')}: {finding.get('message_text', 'N/A')} "
                        f"(Severity: {finding.get('level', 'N/A')})"
                    )
                    sast_messages.append(msg)
        
        if sast_messages:
            logger.debug(f"Found {len(sast_messages)} SAST issues for {file_path} to include in prompt.")
        return sast_messages

    def review(
        self,
        files_data: List[ChangedFile],
        tier1_tool_results: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs security review on the provided files, potentially using SAST tool outputs.

        Args:
            files_data: List of ChangedFile objects to review.
            tier1_tool_results: Results from Tier 1 tools, especially SAST scanners.
                                Example structure: {"sast": {"semgrep": [findings...]}}

        Returns:
            A list of dictionaries, each representing a potential security vulnerability.
        """
        logger.info(f"<{self.agent_name}> Starting security scan for {len(files_data)} files.")
        all_findings: List[Dict[str, Any]] = []

        relevant_files = self._filter_files_by_language(files_data, self.supported_languages)
        if not relevant_files:
            logger.info(f"<{self.agent_name}> No files match supported languages for security scan. Skipping.")
            return all_findings

        for file_data in relevant_files:
            logger.debug(f"<{self.agent_name}> Scanning file: {file_data.path} (Language: {file_data.language})")

            sast_issues_for_prompt = self._get_relevant_sast_findings(file_data.path, tier1_tool_results)
            sast_context_str = "\n".join(sast_issues_for_prompt) if sast_issues_for_prompt \
                               else "No specific findings reported for this file by SAST tools in Tier 1."

            prompt_template_name = f"{self.language_specific_prompt_prefix}{file_data.language}"
            if not self.prompt_manager.get_prompt_template(prompt_template_name):
                prompt_template_name = self.default_prompt_name
            
            prompt_variables = {
                "file_path": file_data.path,
                "file_content": file_data.content,
                "language": file_data.language,
                "sast_tool_feedback": sast_context_str,
                "output_format_instructions": """Please provide your findings as a JSON list. Each object in the list should represent a single potential security vulnerability and have the following keys:
- "line_start": integer (the line number where the vulnerability starts or is most evident)
- "line_end": integer (optional, the line number where the scope of the vulnerability ends)
- "message": string (a concise description of the vulnerability and its potential impact)
- "vulnerability_type": string (e.g., "SQLInjection", "XSS", "PathTraversal", "InsecureDeserialization", "CWE-ID_if_known" like "CWE-79" for XSS, "CWE-89" for SQLi)
- "explanation": string (a brief explanation of why this is a potential vulnerability and how it could be exploited)
- "suggested_fix": string (a concrete suggestion on how to remediate the vulnerability, including code examples if possible)
- "severity": string (your assessment of severity: "critical", "high", "medium", "low")
- "confidence": string (optional, your confidence in this finding: "high", "medium", "low")
- "cvss_score_v3": string (optional, if you can estimate a CVSS v3.1 score, e.g., "7.5")
If no security vulnerabilities are found, or if SAST findings appear to be false positives upon your deeper analysis, return an empty list []. If confirming a SAST finding, please enrich it with your explanation and fix suggestion."""
            }

            rendered_prompt = self.prompt_manager.get_prompt(prompt_template_name, prompt_variables)
            if not rendered_prompt:
                logger.error(f"<{self.agent_name}> Could not render prompt for {file_data.path}. Skipping.")
                continue

            model_name = self.config.get_model_for_agent(self.agent_name)
            if not model_name:
                logger.error(f"<{self.agent_name}> Model name not configured. Skipping file {file_data.path}.")
                continue

            try:
                logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for security scan of {file_data.path}.")
                system_msg = (
                    f"You are {self.agent_name}, an AI assistant specialized in identifying security vulnerabilities "
                    f"in {file_data.language} code. Analyze the provided code and any SAST tool feedback. "
                    f"Focus on identifying common weaknesses (CWEs), potential attack vectors, and insecure coding practices. "
                    f"If SAST feedback is provided, critically evaluate it: confirm true positives, identify false positives with explanation, "
                    f"and enrich true positives with detailed explanations and remediation advice."
                )
                
                response_text = self.ollama_client.invoke(
                    model_name=model_name,
                    prompt=rendered_prompt,
                    system_message_content=system_msg,
                    is_json_mode=True,
                    temperature=0.3 # Security analysis should be precise
                )

                logger.debug(f"<{self.agent_name}> LLM raw response for {file_data.path}: {response_text[:500]}...")
                
                llm_findings = json.loads(response_text)
                if not isinstance(llm_findings, list):
                    logger.warning(f"<{self.agent_name}> LLM response for {file_data.path} was not a JSON list. Got: {type(llm_findings)}")
                    llm_findings = []

                for llm_finding in llm_findings:
                    if not isinstance(llm_finding, dict):
                        logger.warning(f"<{self.agent_name}> Invalid finding format for {file_data.path}: {llm_finding}")
                        continue
                    
                    level_from_llm = str(llm_finding.get("severity", DEFAULT_SECURITY_LEVEL)).lower()
                    internal_level = SEVERITY_MAP.get(level_from_llm, DEFAULT_SECURITY_LEVEL)
                    vuln_type = llm_finding.get("vulnerability_type", "generic_security_issue").replace(" ", "_").lower()

                    finding_message = llm_finding.get("message", "LLM provided no specific message for this vulnerability.")
                    if "explanation" in llm_finding and llm_finding["explanation"] not in finding_message:
                        finding_message += f" (Explanation: {llm_finding['explanation']})"

                    finding = self._format_finding(
                        file_path=file_data.path,
                        line_start=int(llm_finding.get("line_start", 1)),
                        line_end=llm_finding.get("line_end"),
                        message=finding_message,
                        rule_id_suffix=f"llm_sec_{vuln_type}",
                        level=internal_level,
                        suggestion=llm_finding.get("suggested_fix"),
                    )
                    # Add custom fields if needed, e.g., for SARIF properties
                    if "cvss_score_v3" in llm_finding:
                        finding["cvss_v3"] = llm_finding["cvss_score_v3"]
                    if "confidence" in llm_finding:
                        finding["confidence"] = llm_finding["confidence"]
                    
                    all_findings.append(finding)
                
                logger.info(f"<{self.agent_name}> LLM identified {len(llm_findings)} potential security issues in {file_data.path}.")

            except json.JSONDecodeError as e:
                logger.error(f"<{self.agent_name}> Failed to parse LLM JSON response for {file_data.path}: {e}. Response: {response_text[:500]}")
            except Exception as e:
                logger.error(f"<{self.agent_name}> Error during LLM interaction for {file_data.path}: {e}", exc_info=True)
        
        logger.info(f"<{self.agent_name}> Security scan completed. Total potential vulnerabilities found: {len(all_findings)}.")
        return all_findings