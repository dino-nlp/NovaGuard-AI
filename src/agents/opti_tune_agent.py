# NOVAGUARD-AI/src/agents/opti_tune_agent.py
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
# For OptiTune, findings are usually 'note' or 'warning' if it's a significant known bottleneck pattern
SEVERITY_MAP: Dict[str, str] = {
    "critical_impact": "warning", # A severe performance issue might be a warning
    "high_impact": "warning",
    "medium_impact": "note",
    "low_impact": "note",
    "suggestion": "note",
    "note": "note",
    # Map LLM's severity words if they differ
    "error": "warning", # Unlikely for optimization, but map it
    "warning": "warning",
    "none": "none",
}
DEFAULT_OPTIMIZATION_LEVEL = "note"

class OptiTuneAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("OptiTune", config, ollama_client, prompt_manager)
        # Languages where performance discussions and LLM knowledge are common
        self.supported_languages = [
            "python", "java", "csharp", "go", "cpp", "c", "rust",
            "javascript", "typescript", # Especially for Node.js or heavy client-side logic
            "kotlin", "swift"
        ]
        self.default_prompt_name = "optimize_code_general"
        self.language_specific_prompt_prefix = "optimize_code_" # e.g., optimize_code_python

    def review(
        self,
        files_data: List[ChangedFile],
        tier1_tool_results: Optional[Dict[str, Any]] = None # OptiTune typically doesn't rely on Tier1 tools
    ) -> List[Dict[str, Any]]:
        """
        Analyzes code for performance optimization opportunities.

        Args:
            files_data: List of ChangedFile objects to review.
            tier1_tool_results: Optional results from Tier 1 tools (generally not used by this agent).

        Returns:
            A list of dictionaries, each representing a performance optimization suggestion.
        """
        logger.info(f"<{self.agent_name}> Starting performance optimization review for {len(files_data)} files.")
        all_findings: List[Dict[str, Any]] = []

        relevant_files = self._filter_files_by_language(files_data, self.supported_languages)
        if not relevant_files:
            logger.info(f"<{self.agent_name}> No files match supported languages for optimization review. Skipping.")
            return all_findings

        for file_data in relevant_files:
            logger.debug(f"<{self.agent_name}> Optimizing file: {file_data.path} (Language: {file_data.language})")

            prompt_template_name = f"{self.language_specific_prompt_prefix}{file_data.language}"
            if not self.prompt_manager.get_prompt_template(prompt_template_name):
                prompt_template_name = self.default_prompt_name
            
            prompt_variables = {
                "file_path": file_data.path,
                "file_content": file_data.content,
                "language": file_data.language,
                "optimization_goals": (
                    "Identify potential performance bottlenecks related to CPU usage, memory allocation, I/O operations, "
                    "or inefficient algorithms and data structures. Suggest specific, actionable improvements. "
                    "These could include using more efficient library functions, optimizing loops, choosing better data structures, "
                    "applying concurrency patterns where appropriate, or leveraging modern language features for better performance. "
                    "Explain why the suggestion improves performance."
                ),
                "output_format_instructions": """Please provide your findings as a JSON list. Each object in the list should represent a single optimization suggestion and have the following keys:
- "line_start": integer (the primary line number related to the optimization opportunity)
- "line_end": integer (optional, the end line number of the relevant code block)
- "message": string (a concise description of the optimization opportunity)
- "optimization_type": string (e.g., "Algorithm", "DataStructure", "Concurrency", "MemoryManagement", "IOBound", "LanguageFeature", "LoopOptimization", "Caching")
- "explanation": string (a clear explanation of why the current code might be suboptimal and how the suggestion improves performance)
- "suggested_change": string (a concrete suggestion, ideally with a small code snippet illustrating the before and after, or a clear description of the change)
- "estimated_impact": string (your assessment of potential performance gain: "low", "medium", "high")
- "implementation_difficulty": string (optional, your assessment of how difficult it is to implement: "low", "medium", "high")
- "confidence": string (optional, your confidence in this suggestion: "high", "medium", "low")
If no clear optimization opportunities are found, return an empty list []."""
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
                logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for optimization review of {file_data.path}.")
                system_msg = (
                    f"You are {self.agent_name}, an AI expert in code performance optimization for the {file_data.language} language. "
                    f"Your goal is to identify areas in the provided code that could be made more efficient in terms of speed, "
                    f"memory usage, or resource consumption. Provide actionable and specific advice."
                )
                
                response_text = self.ollama_client.invoke(
                    model_name=model_name,
                    prompt=rendered_prompt,
                    system_message_content=system_msg,
                    is_json_mode=True,
                    temperature=0.5 # Allow for some creativity in finding optimization patterns
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
                    
                    # Use 'estimated_impact' for severity mapping, or a default.
                    impact_level = str(llm_finding.get("estimated_impact", "low_impact")).lower()
                    internal_level = SEVERITY_MAP.get(impact_level, DEFAULT_OPTIMIZATION_LEVEL)
                    opt_type = llm_finding.get("optimization_type", "general_optimization").replace(" ", "_").lower()

                    finding_message = llm_finding.get("message", "LLM provided no specific message for this optimization.")
                    if "explanation" in llm_finding and llm_finding["explanation"] not in finding_message:
                        finding_message += f" (Reason: {llm_finding['explanation']})"

                    finding = self._format_finding(
                        file_path=file_data.path,
                        line_start=int(llm_finding.get("line_start", 1)),
                        line_end=llm_finding.get("line_end"),
                        message=finding_message,
                        rule_id_suffix=f"llm_opt_{opt_type}",
                        level=internal_level, # Optimizations are usually 'note' or 'warning'
                        suggestion=llm_finding.get("suggested_change"),
                    )
                    # Add custom fields if useful for reporting
                    if "estimated_impact" in llm_finding:
                        finding["estimated_impact"] = llm_finding["estimated_impact"]
                    if "implementation_difficulty" in llm_finding:
                        finding["implementation_difficulty"] = llm_finding["implementation_difficulty"]
                    if "confidence" in llm_finding:
                        finding["confidence"] = llm_finding["confidence"]
                    
                    all_findings.append(finding)
                
                logger.info(f"<{self.agent_name}> LLM identified {len(llm_findings)} optimization opportunities in {file_data.path}.")

            except json.JSONDecodeError as e:
                logger.error(f"<{self.agent_name}> Failed to parse LLM JSON response for {file_data.path}: {e}. Response: {response_text[:500]}")
            except Exception as e:
                logger.error(f"<{self.agent_name}> Error during LLM interaction for {file_data.path}: {e}", exc_info=True)
        
        logger.info(f"<{self.agent_name}> Optimization review completed. Total suggestions: {len(all_findings)}.")
        return all_findings