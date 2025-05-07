# NOVAGUARD-AI/src/agents/style_guardian_agent.py
import json
import logging
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent
from ..core.shared_context import ChangedFile
from ..core.config_loader import Config
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class StyleGuardianAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("StyleGuardian", config, ollama_client, prompt_manager)
        # Ngôn ngữ được hỗ trợ (có thể lấy từ config nếu muốn linh hoạt hơn)
        self.supported_languages = ["python", "javascript", "typescript", "java", "csharp", "go"]
        # Tên các prompt template mặc định
        self.default_prompt_name = "style_review_general"
        self.language_specific_prompt_prefix = "style_review_" # e.g., style_review_python

    def _get_relevant_linter_findings(
        self,
        file_path: str,
        language: Optional[str],
        tier1_tool_results: Optional[Dict[str, List[Dict[str, Any]]]]
    ) -> List[str]:
        """
        Trích xuất các phát hiện linter có liên quan cho file hiện tại.
        """
        linter_messages: List[str] = []
        if not tier1_tool_results or not language:
            return linter_messages

        # Cấu trúc của tier1_tool_results có thể là:
        # {"linters": {"python": [{"file_path": "...", "message_text": ...}]}}
        # Hoặc một cấu trúc phẳng hơn tùy thuộc vào run_tier1_tools_node
        # Ví dụ này giả định cấu trúc trên
        linter_category_results = tier1_tool_results.get("linters", {})
        
        # Tìm linter output cho ngôn ngữ cụ thể
        # tool_key cho linter có thể là tên ngôn ngữ (ví dụ: 'python' cho pylint)
        # Hoặc một tool_key cụ thể hơn. Phải khớp với cách run_tier1_tools_node lưu trữ.
        # Ví dụ: nếu pylint được lưu dưới key 'python' trong 'linters'
        specific_linter_findings = linter_category_results.get(language.lower(), [])

        for finding in specific_linter_findings:
            if finding.get("file_path") == file_path:
                # Format a descriptive message for the LLM
                msg = f"- Linter ({finding.get('tool_name', 'linter')}.{finding.get('rule_id', 'N/A')}) " \
                    f"at line {finding.get('line_start', 'N/A')}: {finding.get('message_text', 'N/A')}"
                linter_messages.append(msg)
        
        if linter_messages:
            logger.debug(f"Found {len(linter_messages)} linter issues for {file_path} to include in prompt.")
        return linter_messages

    def review(
        self,
        files_data: List[ChangedFile], # Từ GraphState.files_to_review
        tier1_tool_results: Optional[Dict[str, Any]] = None # Từ GraphState.tier1_tool_results
    ) -> List[Dict[str, Any]]:
        """
        Thực hiện review về style cho các file được cung cấp.

        Args:
            files_data: Danh sách các đối tượng ChangedFile cần review.
            tier1_tool_results: Kết quả từ các tool ở Tier 1 (ví dụ: Pylint, ESLint).
                                Cấu trúc ví dụ: {"linters": {"python": [findings...]}}

        Returns:
            Một danh sách các dictionary, mỗi dict là một "phát hiện" (finding).
        """
        logger.info(f"<{self.agent_name}> Starting style review for {len(files_data)} files.")
        all_findings: List[Dict[str, Any]] = []

        relevant_files = self._filter_files_by_language(files_data, self.supported_languages)
        if not relevant_files:
            logger.info(f"<{self.agent_name}> No files match supported languages. Skipping review.")
            return all_findings

        for file_data in relevant_files:
            logger.debug(f"<{self.agent_name}> Reviewing file: {file_data.path} (Language: {file_data.language})")

            linter_issues_for_prompt = self._get_relevant_linter_findings(
                file_data.path, file_data.language, tier1_tool_results
            )
            linter_context_str = "\n".join(linter_issues_for_prompt) if linter_issues_for_prompt else "No specific linter issues reported for this file by Tier 1 tools."

            prompt_template_name = f"{self.language_specific_prompt_prefix}{file_data.language}"
            if not self.prompt_manager.get_prompt_template(prompt_template_name): # Check if specific template exists
                prompt_template_name = self.default_prompt_name
            
            # Các coding standards có thể được lấy từ self.config nếu có
            # project_coding_standards = self.config.get_project_standards(file_data.language)

            prompt_variables = {
                "file_path": file_data.path,
                "file_content": file_data.content,
                "language": file_data.language,
                "linter_feedback": linter_context_str,
                # "coding_standards": project_coding_standards, # Nếu có
                "output_format_instructions": """Please provide your findings as a JSON list. Each object in the list should represent a single style issue and have the following keys:
- "line_start": integer (the line number where the issue starts)
- "line_end": integer (optional, the line number where the issue ends, defaults to line_start)
- "message": string (a concise description of the style issue)
- "suggestion": string (optional, a brief suggestion on how to fix it or improve)
- "severity": string (your assessment of severity, e.g., "low", "medium", "high", or "info", "warning", "error")
- "confidence": string (optional, e.g. "high", "medium", "low" - your confidence in this finding)
If no style issues are found, return an empty list []."""
            }

            rendered_prompt = self.prompt_manager.get_prompt(prompt_template_name, prompt_variables)
            if not rendered_prompt:
                logger.error(f"<{self.agent_name}> Could not render prompt for {file_data.path}. Skipping.")
                continue

            model_name = self.config.get_model_for_agent(self.agent_name)
            if not model_name:
                logger.error(f"<{self.agent_name}> Model name not configured for agent {self.agent_name}. Skipping file {file_data.path}.")
                continue # Or add to error_messages in state if agent could return them

            try:
                logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for style review of {file_data.path}.")
                # TODO: Define system message, perhaps in config or per-agent
                system_msg = f"You are {self.agent_name}, an AI assistant specialized in reviewing code for style, formatting, and conventions for {file_data.language} language. Analyze the provided code and linter feedback."
                
                response_text = self.ollama_client.invoke(
                    model_name=model_name,
                    prompt=rendered_prompt,
                    system_message_content=system_msg,
                    is_json_mode=True, # Critical for parsing
                    temperature=0.2 # Style review should be more deterministic
                )

                logger.debug(f"<{self.agent_name}> LLM raw response for {file_data.path}: {response_text[:500]}...")
                
                # Parse LLM response (expected to be JSON)
                llm_findings = json.loads(response_text)
                if not isinstance(llm_findings, list):
                    logger.warning(f"<{self.agent_name}> LLM response for {file_data.path} was not a JSON list. Got: {type(llm_findings)}")
                    llm_findings = [] # Treat as no findings if format is wrong

                for llm_finding in llm_findings:
                    if not isinstance(llm_finding, dict):
                        logger.warning(f"<{self.agent_name}> Invalid finding format in LLM response for {file_data.path}: {llm_finding}")
                        continue
                    
                    # Map LLM severity to our internal levels
                    level_from_llm = str(llm_finding.get("severity", "note")).lower()
                    internal_level = SEVERITY_MAP.get(level_from_llm, "note") # Use SEVERITY_MAP from sarif_generator or define one

                    finding = self._format_finding(
                        file_path=file_data.path,
                        line_start=int(llm_finding.get("line_start", 1)), # Ensure type conversion
                        message=llm_finding.get("message", "LLM provided no message."),
                        rule_id_suffix=f"llm_style_{llm_finding.get('code_issue_category', 'general').replace(' ', '_').lower()}", # Example rule_id
                        level=internal_level,
                        suggestion=llm_finding.get("suggestion"),
                        # code_snippet can be added if LLM provides it or if we extract it
                    )
                    all_findings.append(finding)
                
                logger.info(f"<{self.agent_name}> LLM found {len(llm_findings)} style issues in {file_data.path}.")

            except json.JSONDecodeError as e:
                logger.error(f"<{self.agent_name}> Failed to parse LLM JSON response for {file_data.path}: {e}. Response: {response_text[:500]}")
            except Exception as e:
                logger.error(f"<{self.agent_name}> Error during LLM interaction for {file_data.path}: {e}", exc_info=True)
        
        logger.info(f"<{self.agent_name}> Review completed. Total style findings: {len(all_findings)}.")
        return all_findings

# You would also need the SEVERITY_MAP here or import it if it's defined centrally
# For now, let's assume it's available or defined in BaseAgent, or we can redefine it.
SEVERITY_MAP: Dict[str, str] = {
    "error": "error", "critical": "error", "high": "error",
    "warning": "warning", "medium": "warning",
    "note": "note", "information": "note", "info": "note", "low": "note",
    "none": "none",
}