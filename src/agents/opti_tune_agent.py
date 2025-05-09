# NOVAGUARD-AI/src/agents/opti_tune_agent.py
import json
import logging
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent
from ..core.shared_context import ChangedFile, SharedReviewContext
from ..core.config_loader import Config
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# Define SEVERITY_MAP or import from a central location if available
SEVERITY_MAP: Dict[str, str] = {
    "critical_impact": "warning", "high_impact": "warning",
    "medium_impact": "note", "low_impact": "note",
    "suggestion": "note", "note": "note",
    "error": "warning", "warning": "warning", "none": "none",
}
DEFAULT_OPTIMIZATION_LEVEL = "note"

class OptiTuneAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("OptiTune", config, ollama_client, prompt_manager)
        self.supported_languages = [
            "python", "java", "csharp", "go", "cpp", "c", "rust",
            "javascript", "typescript", "kotlin", "swift"
        ]
        self.default_prompt_name = "optimize_code_general"
        self.language_specific_prompt_prefix = "optimize_code_"

    def review(
        self,
        files_data: List[ChangedFile],
        tier1_tool_results: Optional[Dict[str, Any]] = None,
        pr_context: Optional[SharedReviewContext] = None
    ) -> List[Dict[str, Any]]:
        logger.info(f"<{self.agent_name}> Starting performance optimization review for {len(files_data)} files.")
        all_findings: List[Dict[str, Any]] = []
        relevant_files = self._filter_files_by_language(files_data, self.supported_languages)
        if not relevant_files:
            logger.info(f"<{self.agent_name}> No files match supported languages for optimization review. Skipping.")
            return all_findings
        
        # Lấy thông tin PR từ pr_context
        pr_title_for_prompt = pr_context.pr_title if pr_context and pr_context.pr_title else "Not available"
        pr_description_for_prompt = pr_context.pr_body if pr_context and pr_context.pr_body else "Not available"

        for file_data in relevant_files:
            logger.debug(f"<{self.agent_name}> Optimizing file: {file_data.path} (Language: {file_data.language})")
            prompt_template_name = f"{self.language_specific_prompt_prefix}{file_data.language}"
            if not self.config.get_prompt_template(prompt_template_name):
                logger.debug(f"<{self.agent_name}> Specific prompt '{prompt_template_name}' not found in config. Using default '{self.default_prompt_name}'.")
                prompt_template_name = self.default_prompt_name

            prompt_variables = {
                "agent_name": self.agent_name,
                "file_path": file_data.path,
                "file_content": file_data.content,
                "language": file_data.language,
                "pr_title": pr_title_for_prompt,           
                "pr_description": pr_description_for_prompt,
                "optimization_goals": ( 
                    "Identify potential performance bottlenecks related to CPU usage, memory allocation/management, "
                    "I/O operations, or inefficient algorithms and data structures. "
                    "Suggest specific, actionable improvements. These could include using more efficient library functions, "
                    "optimizing loops, choosing better data structures, applying concurrency/parallelism patterns where "
                    "appropriate (and safe), reducing redundant computations, or leveraging modern language features for "
                    "better performance. Clearly explain *why* the suggestion improves performance and what trade-offs "
                    "might exist (e.g., memory vs. speed, readability vs. performance)."
                ),
                "output_format_instructions": """Please provide your findings STRICTLY as a JSON list.
- If multiple optimization opportunities are found, return a list of JSON objects.
- If only one opportunity is found, return a list containing a single JSON object.
- If no clear optimization opportunities are found, return an empty JSON list: [].
Each JSON object in the list should represent a single optimization suggestion and have AT LEAST the following keys:
- "line_start": integer (the primary line number related to the optimization opportunity)
- "message": string (a concise description of the optimization opportunity and its potential benefit)
- "optimization_type": string (e.g., "AlgorithmRefinement", "DataStructureChoice", "ConcurrencyParallelism", "MemoryManagement", "IOBoundOptimization", "LanguageFeatureAdoption", "LoopOptimization", "CachingStrategy", "RedundantComputation")
- "explanation_steps": list_of_strings (your step-by-step reasoning explaining why the current code might be suboptimal and how the suggestion improves performance, including any relevant trade-offs)
- "suggested_change": string (a concrete suggestion, ideally with a small code snippet illustrating the 'before' and 'after', or a clear description of the change required)
- "estimated_impact": string (your assessment of potential performance gain: "low", "medium", "high", "significant")
You MAY also include these OPTIONAL keys if applicable:
- "line_end": integer (optional, the end line number of the relevant code block)
- "implementation_difficulty": string (optional, your assessment of how difficult it is to implement: "low", "medium", "high")
- "confidence": string (optional, your confidence in this suggestion: "high", "medium", "low")
"""
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
                logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for optimization review of {file_data.path}.")
                system_msg = (f"You are {self.agent_name}, an AI expert in code performance optimization... for the {file_data.language} language...")
                response_text = self.ollama_client.invoke(
                    model_name=model_name, prompt=rendered_prompt,
                    system_message_content=system_msg, is_json_mode=True, temperature=0.5
                )
                # --- DEBUG LOG ---
                logger.info(f"<{self.agent_name}>:\n>>> START PROMP <<<\n{rendered_prompt.strip()}\n>>> END PROMPT <<<")
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
                                possible_keys = ["findings", "results", "suggestions", "optimizations"]
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
                    impact_level = str(llm_finding.get("estimated_impact", "low_impact")).lower()
                    internal_level = SEVERITY_MAP.get(impact_level, DEFAULT_OPTIMIZATION_LEVEL)
                    opt_type = llm_finding.get("optimization_type", "general_opt").replace(" ", "_").lower()
                    finding_message = llm_finding.get("message", "LLM provided no specific message for this optimization.")
                    if "explanation" in llm_finding and llm_finding["explanation"] not in finding_message:
                        finding_message += f" (Reason: {llm_finding['explanation']})"
                    finding = self._format_finding(
                        file_path=file_data.path,
                        line_start=int(llm_finding.get("line_start", 1)),
                        message=finding_message,
                        rule_id_suffix=f"llm_opt_{opt_type}",
                        level=internal_level,
                        suggestion=llm_finding.get("suggested_change"),
                    )
                    if "line_end" in llm_finding: finding["line_end"] = llm_finding["line_end"]
                    if "estimated_impact" in llm_finding: finding["estimated_impact"] = llm_finding["estimated_impact"]
                    if "implementation_difficulty" in llm_finding: finding["implementation_difficulty"] = llm_finding["implementation_difficulty"]
                    if "confidence" in llm_finding: finding["confidence"] = llm_finding["confidence"]
                    all_findings.append(finding)
                    processed_count += 1
                logger.info(f"<{self.agent_name}> LLM processing yielded {processed_count} optimization opportunities in {file_data.path}.")
            except Exception as e:
                logger.error(f"<{self.agent_name}> Error during LLM interaction or processing for {file_data.path}: {e}", exc_info=True)
        logger.info(f"<{self.agent_name}> Optimization review completed. Total suggestions: {len(all_findings)}.")
        return all_findings