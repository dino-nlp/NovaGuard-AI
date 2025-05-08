# NOVAGUARD-AI/src/agents/meta_reviewer_agent.py
import json
import logging
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent
from ..core.shared_context import ChangedFile # For context, though primary input is findings
from ..core.config_loader import Config
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# SEVERITY_MAP might be needed if the MetaReviewer adjusts severities
SEVERITY_MAP: Dict[str, str] = {
    "critical": "error", "error": "error", "high": "error",
    "warning": "warning", "medium": "warning",
    "note": "note", "information": "note", "info": "note", "low": "note",
    "none": "none",
}
DEFAULT_META_REVIEW_LEVEL = "note"

class MetaReviewerAgent(BaseAgent):
    def __init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager):
        super().__init__("MetaReviewer", config, ollama_client, prompt_manager)
        # MetaReviewer doesn't have "supported_languages" in the same way, it processes findings text.
        self.prompt_name = "meta_review_findings" # A single, primary prompt for this agent

    def _format_findings_for_llm(self, findings: List[Dict[str, Any]]) -> str:
        """
        Formats a list of finding dictionaries into a string suitable for an LLM prompt.
        """
        formatted_texts: List[str] = []
        for i, finding in enumerate(findings):
            text = (
                f"Finding {i+1}:\n"
                f"  File: {finding.get('file_path', 'N/A')}\n"
                f"  Line: {finding.get('line_start', 'N/A')}\n"
                f"  Agent: {finding.get('tool_name', 'N/A')}\n" # 'tool_name' field from _format_finding in BaseAgent
                f"  Rule ID: {finding.get('rule_id', 'N/A')}\n"
                f"  Severity: {finding.get('level', 'N/A')}\n"
                f"  Message: {finding.get('message_text', 'N/A')}\n"
                f"  Suggestion: {finding.get('suggestion', 'N/A')}\n"
            )
            formatted_texts.append(text)
        return "\n---\n".join(formatted_texts) if formatted_texts else "No findings were provided by other agents."

    def review(
        self,
        all_agent_findings: List[Dict[str, Any]], # Primary input: list of findings from other agents
        files_data: List[ChangedFile] # Provides context about the files involved if needed by LLM
    ) -> List[Dict[str, Any]]:
        """
        Reviews, de-duplicates, prioritizes, and potentially refines findings from other agents.

        Args:
            all_agent_findings: A list of all finding dictionaries from previous LLM agents.
            files_data: List of ChangedFile objects for broader context (e.g., list of all files reviewed).

        Returns:
            A potentially refined list of finding dictionaries. If processing fails,
            it might return the original list or an empty list with errors.
        """
        logger.info(f"<{self.agent_name}> Starting meta-review of {len(all_agent_findings)} findings.")

        if not all_agent_findings:
            logger.info(f"<{self.agent_name}> No agent findings to meta-review. Returning empty list.")
            return []

        formatted_findings_str = self._format_findings_for_llm(all_agent_findings)
        
        # Context about files can be simple, e.g., just paths, or more detailed if needed
        file_paths_involved = sorted(list(set(f.path for f in files_data)))
        files_context_str = "The review involved the following files:\n" + "\n".join([f"- {fp}" for fp in file_paths_involved])

        prompt_variables = {
            "agent_name": self.agent_name,
            "raw_findings_text": formatted_findings_str,
            "num_findings_from_agents": len(all_agent_findings),
            "files_context": files_context_str,
            "meta_review_goals": (
                "1. **De-duplicate & Consolidate:** Identify and merge substantially similar or redundant findings, especially if they originate from different specialized agents but point to the same root cause or code location. Choose the most accurate and descriptive representation for merged findings.\n"
                "2. **Validate & Filter:** Critically assess the plausibility of each finding. If a finding seems to be a likely false positive or is too vague to be actionable, it may be omitted. Provide a brief justification if a significant finding is dropped.\n"
                "3. **Prioritize & Refine:** Evaluate the overall importance and potential impact of the remaining findings. You may suggest a priority order or highlight the most critical ones. Rephrase messages for clarity, conciseness, and a consistent tone if necessary. Ensure technical accuracy.\n"
                "4. **Maintain Structure:** The output must be a list of findings, where each finding is a JSON object preserving the original key structure (e.g., 'file_path', 'line_start', 'message_text', 'rule_id', 'level', 'tool_name', 'suggestion') as much as possible. If you merge findings, populate these fields from the most representative source or synthesize appropriately."
            ),
            "output_format_instructions": """Please return your output as a single JSON list, where each element is an object representing a refined finding. The structure of each finding object should mirror the input findings' structure. Example keys: "file_path", "line_start", "line_end" (optional), "message_text", "rule_id" (can be refined or kept), "level" (can be adjusted), "tool_name" (can indicate 'MetaReviewer' or the originating agent if preserved), "suggestion" (can be refined).
If, after your review, no findings are deemed valid or actionable, return an empty list []."""
        }

        rendered_prompt = self.prompt_manager.get_prompt(self.prompt_name, prompt_variables)
        if not rendered_prompt:
            logger.error(f"<{self.agent_name}> Could not render prompt for meta-review. Returning original findings.")
            return all_agent_findings # Fallback

        model_name = self.config.get_model_for_agent(self.agent_name) # e.g., "mistral:7b-instruct-v0.2-q5_K_M"
        if not model_name:
            logger.error(f"<{self.agent_name}> Model name not configured. Returning original findings.")
            return all_agent_findings # Fallback

        try:
            logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for meta-review.")
            system_msg = (
                f"You are {self.agent_name}, an AI Lead Code Reviewer. Your task is to process a list of findings "
                f"generated by other specialized AI agents. Your goal is to improve the overall quality, "
                f"accuracy, and actionability of the final set of reported issues by de-duplicating, validating, "
                f"prioritizing, and refining them. Adhere strictly to the output format requested."
            )
            
            # This prompt can be very long. Consider models with large context windows.
            # A potential issue: if formatted_findings_str is huge, this might fail.
            # TODO: Implement chunking or summarization for very large numbers of findings if needed.
            if len(formatted_findings_str) > 20000: # Arbitrary limit, adjust based on model
                logger.warning(f"<{self.agent_name}> Formatted findings string is very long ({len(formatted_findings_str)} chars). May exceed context window.")


            response_text = self.ollama_client.invoke(
                model_name=model_name,
                prompt=rendered_prompt,
                system_message_content=system_msg,
                is_json_mode=True,
                temperature=0.2 # Meta-review should be more analytical and less creative
            )

            # --- DEBUG LOG ---
            logger.info(f"<{self.agent_name}> RAW LLM RESPONSE \n>>> START LLM RESPONSE <<<\n{response_text.strip()}\n>>> END LLM RESPONSE <<<")
            
            refined_llm_findings = json.loads(response_text)
            if not isinstance(refined_llm_findings, list):
                logger.warning(f"<{self.agent_name}> LLM response for meta-review was not a JSON list. Got: {type(refined_llm_findings)}. Returning original findings.")
                return all_agent_findings # Fallback

            # Validate and re-format LLM output to ensure consistency
            final_refined_findings: List[Dict[str, Any]] = []
            for llm_finding in refined_llm_findings:
                if not isinstance(llm_finding, dict):
                    logger.warning(f"<{self.agent_name}> Invalid item in refined findings list: {llm_finding}")
                    continue
                
                # Ensure essential keys are present, using defaults from original if possible or sensible fallbacks
                # This step is crucial to ensure the output is still processable by the SARIF generator.
                # The LLM is asked to preserve structure, but we should verify.
                file_path = llm_finding.get("file_path")
                line_start = llm_finding.get("line_start")
                message = llm_finding.get("message_text", llm_finding.get("message")) # Accept 'message' or 'message_text'

                if not all([file_path, line_start is not None, message]):
                    logger.warning(f"<{self.agent_name}> Refined finding missing essential fields (file_path, line_start, message): {llm_finding}")
                    continue

                # Re-apply our standard formatting, potentially updating fields based on LLM's refinement
                refined_finding = self._format_finding(
                    file_path=str(file_path),
                    line_start=int(line_start),
                    line_end=llm_finding.get("line_end"), # Optional
                    message=str(message),
                    rule_id_suffix=str(llm_finding.get("rule_id", "meta.refined").split('.')[-1]), # Try to keep or adapt rule_id
                    level=SEVERITY_MAP.get(str(llm_finding.get("level", DEFAULT_META_REVIEW_LEVEL)).lower(), DEFAULT_META_REVIEW_LEVEL),
                    suggestion=llm_finding.get("suggestion"),
                    # The tool_name could be set to "MetaReviewer" or preserve original if distinct.
                    # For simplicity, _format_finding uses self.agent_name.
                )
                # If LLM explicitly provides the original tool_name, or if we want to track it:
                if "tool_name" in llm_finding:
                    refined_finding["original_tool_name"] = llm_finding["tool_name"]
                
                final_refined_findings.append(refined_finding)
            
            logger.info(f"<{self.agent_name}> Meta-review resulted in {len(final_refined_findings)} refined findings.")
            return final_refined_findings

        except json.JSONDecodeError as e:
            logger.error(f"<{self.agent_name}> Failed to parse LLM JSON response for meta-review: {e}. Response: {response_text[:500]}. Returning original findings.")
            return all_agent_findings # Fallback
        except Exception as e:
            logger.error(f"<{self.agent_name}> Error during LLM interaction for meta-review: {e}", exc_info=True)
            return all_agent_findings # Fallback
        
        logger.info(f"<{self.agent_name}> Meta-review completed. Original: {len(all_agent_findings)}, Refined: {len(all_agent_findings)} (fallback).")
        return all_agent_findings # Fallback if any unhandled path