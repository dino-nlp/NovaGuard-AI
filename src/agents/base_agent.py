# NOVAGUARD-AI/src/agents/base_agent.py
import logging
from typing import List, Dict, Any, Optional
from ..core.config_loader import Config
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager
from ..core.shared_context import ChangedFile

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, agent_name: str, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        self.agent_name = agent_name
        self.config = config
        self.ollama_client = ollama_client
        self.prompt_manager = prompt_manager
        logger.info(f"{self.agent_name} initialized.")

    def review(self, files_data: List[ChangedFile], additional_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # This method should be overridden by subclasses
        raise NotImplementedError(f"Review method not implemented for {self.agent_name}")

    def _filter_files_by_language(self, files_data: List[ChangedFile], supported_languages: List[str]) -> List[ChangedFile]:
        """Helper to filter files based on supported languages."""
        filtered_files = [
            file for file in files_data
            if file.language and file.language.lower() in [lang.lower() for lang in supported_languages]
        ]
        if len(filtered_files) < len(files_data):
            logger.debug(f"{self.agent_name} filtered {len(files_data) - len(filtered_files)} files not matching supported languages: {supported_languages}")
        return filtered_files

    def _format_finding(self, file_path: str, line_start: int, message: str, rule_id_suffix:str, level:str, suggestion: Optional[str]=None, code_snippet: Optional[str]=None) -> Dict[str, Any]:
        return {
            "file_path": file_path,
            "line_start": line_start,
            "message_text": message,
            "rule_id": f"{self.agent_name}.{rule_id_suffix}",
            "level": level,
            "tool_name": self.agent_name,
            "suggestion": suggestion,
            "code_snippet": code_snippet
        }