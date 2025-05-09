# NOVAGUARD-AI/src/agents/meta_reviewer_agent.py
import json
import logging
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent
from ..core.shared_context import ChangedFile, SharedReviewContext # For context, though primary input is findings
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
        all_agent_findings: List[Dict[str, Any]],
        files_data: List[ChangedFile], # Cung cấp context về các file liên quan
        pr_context: Optional[SharedReviewContext] = None # Thêm context của PR
    ) -> List[Dict[str, Any]]:
        """
        Review, loại bỏ trùng lặp, ưu tiên, và có thể tinh chỉnh các finding từ các agent khác.

        Args:
            all_agent_findings: Danh sách tất cả các finding (dạng dict) từ các agent LLM trước đó.
            files_data: Danh sách các đối tượng ChangedFile cho context rộng hơn.
            pr_context: Context của Pull Request (title, body).

        Returns:
            Một danh sách các dictionary finding đã được tinh chỉnh (hoặc danh sách gốc nếu lỗi).
        """
        logger.info(f"<{self.agent_name}> Starting meta-review of {len(all_agent_findings)} findings.")

        if not all_agent_findings:
            logger.info(f"<{self.agent_name}> No agent findings to meta-review. Returning empty list.")
            return []

        formatted_findings_str = self._format_findings_for_llm(all_agent_findings)
        
        file_paths_involved = sorted(list(set(f.path for f in files_data)))
        files_context_str = "The review involved the following files (relative to repository root):\n" + "\n".join([f"- {fp}" for fp in file_paths_involved])

        pr_title_for_prompt = pr_context.pr_title if pr_context and pr_context.pr_title else "Not available"
        pr_description_for_prompt = pr_context.pr_body if pr_context and pr_context.pr_body else "Not available"

        prompt_variables = {
            "agent_name": self.agent_name,
            "num_findings_from_agents": len(all_agent_findings),
            "raw_findings_text": formatted_findings_str,
            "files_context": files_context_str,
            "pr_title": pr_title_for_prompt,
            "pr_description": pr_description_for_prompt,
            "meta_review_goals": (
                "1. **De-duplicate & Consolidate:** Identify and merge substantially similar or redundant findings, especially if they originate from different specialized agents but point to the same root cause or code location. Choose the most accurate and descriptive representation for merged findings.\n"
                "2. **Validate & Filter:** Critically assess the plausibility of each finding. If a finding seems to be a likely false positive or is too vague to be actionable, it may be omitted. Provide a brief justification if a significant finding is dropped.\n"
                "3. **Prioritize & Refine:** Evaluate the overall importance and potential impact of the remaining findings. You may suggest a priority order or highlight the most critical ones. Rephrase messages for clarity, conciseness, and a consistent tone if necessary. Ensure technical accuracy.\n"
                "4. **Maintain Structure:** The output must be a list of findings, where each finding is a JSON object preserving the original key structure (e.g., 'file_path', 'line_start', 'message_text', 'rule_id', 'level', 'tool_name', 'suggestion') as much as possible. If you merge findings, populate these fields from the most representative source or synthesize appropriately.\n"
                "5. **Explain Changes:** For any significant changes you make (merging multiple findings, or dropping a high/medium severity finding reported by an agent), briefly explain your reasoning. This reasoning can be included within the 'message_text' of a merged finding, or as a separate 'meta_comment' field within the finding object."
            ),
            "output_format_instructions": """Please return your output STRICTLY as a single JSON list, where each element is an object representing a refined finding.
- If multiple findings remain after your review, return a list of JSON objects.
- If only one finding remains, return a list containing that single JSON object.
- If, after your review, no findings are deemed valid or actionable, return an empty JSON list: [].
Each JSON object in the list should aim to mirror the input findings' structure, including AT LEAST the following keys:
- "file_path": string
- "line_start": integer
- "message": string (this can be the refined message, and can include your reasoning for merging/dropping if applicable. Use "message" as the key for the main descriptive text.)
- "rule_id": string (can be refined, kept from original, or a new 'MetaReviewer.Consolidated' ID)
- "level": string (your final assessment: "error", "warning", "note")
- "tool_name": string (can indicate 'MetaReviewer' or the originating agent if preserved or relevant)
You MAY also include these OPTIONAL keys if applicable:
- "line_end": integer
- "suggestion": string (refined suggestion)
- "confidence": string
- "meta_comment": string (optional, for specific notes about the meta-review decision on this finding, if not included in message_text)
- "original_rule_ids": list_of_strings (optional, if merging findings, list the original rule_ids that were merged into this one)
- "explanation_steps": list_of_strings (optional, if you performed a chain-of-thought for a specific finding, list those steps here)
"""
        }

        rendered_prompt = self.prompt_manager.get_prompt(self.prompt_name, prompt_variables)
        if not rendered_prompt:
            logger.error(f"<{self.agent_name}> Could not render prompt for meta-review. Returning original findings.")
            return all_agent_findings

        model_name = self.config.get_model_for_agent(self.agent_name)
        if not model_name:
            logger.error(f"<{self.agent_name}> Model name not configured for {self.agent_name}. Returning original findings.")
            return all_agent_findings

        final_refined_findings: List[Dict[str, Any]] = []
        try:
            logger.info(f"<{self.agent_name}> Invoking LLM '{model_name}' for meta-review on {len(all_agent_findings)} findings.")
            system_msg = (
                f"You are {self.agent_name}, an AI Lead Code Reviewer. Your task is to process a list of findings "
                f"generated by other specialized AI agents. Your goal is to improve the overall quality, "
                f"accuracy, and actionability of the final set of reported issues by de-duplicating, validating, "
                f"prioritizing, and refining them according to the provided goals. Adhere strictly to the JSON list output format requested."
            )
            
            if len(formatted_findings_str) > 20000: # Ngưỡng cảnh báo, tùy chỉnh
                logger.warning(f"<{self.agent_name}> Formatted findings string is very long ({len(formatted_findings_str)} chars). May approach context window limits for model '{model_name}'.")

            response_text = self.ollama_client.invoke(
                model_name=model_name,
                prompt=rendered_prompt,
                system_message_content=system_msg,
                is_json_mode=True,
                temperature=0.1 # Meta-review nên chính xác và ít sáng tạo
            )
            logger.info(f"<{self.agent_name}>:\n>>> START PROMP <<<\n{rendered_prompt.strip()}\n>>> END PROMPT <<<")
            logger.info(f"<{self.agent_name}> RAW LLM RESPONSE for meta-review:\n>>> START LLM RESPONSE <<<\n{response_text}\n>>> END LLM RESPONSE <<<")

            llm_output_list: List[Dict] = []
            try:
                stripped_response_text = response_text.strip()
                if not stripped_response_text:
                    logger.warning(f"<{self.agent_name}> LLM returned empty or whitespace-only response for meta-review.")
                else:
                    parsed_response = json.loads(stripped_response_text)
                    if isinstance(parsed_response, list):
                        llm_output_list = parsed_response
                        logger.debug(f"<{self.agent_name}> Meta-reviewer LLM returned a JSON list with {len(llm_output_list)} items.")
                    elif isinstance(parsed_response, dict):
                        # MetaReviewer nên luôn trả về list, nhưng nếu nó trả về dict (có thể là 1 finding duy nhất)
                        is_single_finding = "line_start" in parsed_response and ("message" in parsed_response or "message_text" in parsed_response)
                        if is_single_finding:
                            logger.debug(f"<{self.agent_name}> Meta-reviewer LLM returned a single JSON object, treating it as one finding.")
                            llm_output_list = [parsed_response]
                        else: # Thử tìm trong các key phổ biến nếu là dict chứa list
                            possible_keys = ["findings", "results", "refined_findings"]
                            found = False
                            for key in possible_keys:
                                if key in parsed_response and isinstance(parsed_response.get(key), list):
                                    llm_output_list = parsed_response[key]
                                    logger.debug(f"<{self.agent_name}> Meta-reviewer LLM returned a dict, extracted list from key '{key}'.")
                                    found = True; break
                            if not found:
                                logger.warning(f"<{self.agent_name}> Meta-reviewer LLM response was a JSON dict, but no known key contained a list, and it didn't look like a single finding object. Got dict keys: {list(parsed_response.keys())}")
                    else:
                        logger.warning(f"<{self.agent_name}> Meta-reviewer LLM response parsed but was not a JSON list or dict. Got: {type(parsed_response)}")
            
            except json.JSONDecodeError as e:
                logger.error(f"<{self.agent_name}> Failed to parse LLM JSON response for meta-review: {e}. Response: '{response_text[:500]}...'. Returning original findings.")
                return all_agent_findings # Fallback

            # Xử lý và chuẩn hóa output từ LLM
            for llm_finding in llm_output_list:
                if not isinstance(llm_finding, dict):
                    logger.warning(f"<{self.agent_name}> Invalid item in refined findings list (not a dict): {llm_finding}")
                    continue
                
                file_path = llm_finding.get("file_path")
                line_start_any = llm_finding.get("line_start")
                # LLM có thể trả về "message" hoặc "message_text"
                message = llm_finding.get("message", llm_finding.get("message_text")) 

                if not all([file_path, line_start_any is not None, message]):
                    logger.warning(f"<{self.agent_name}> Refined finding missing essential fields (file_path, line_start, message): {llm_finding}")
                    continue
                try:
                    line_start = int(line_start_any)
                except ValueError:
                    logger.warning(f"<{self.agent_name}> Invalid line_start value in refined finding: {line_start_any}. Skipping.")
                    continue

                # Giữ lại rule_id từ LLM nếu nó cung cấp, nếu không, tạo một rule_id chung chung
                rule_id_from_llm = str(llm_finding.get("rule_id", "meta.refined"))
                # Tách lấy phần cuối của rule_id để dùng làm suffix, hoặc dùng toàn bộ nếu không có dấu chấm
                rule_id_suffix = rule_id_from_llm.split('.')[-1] if '.' in rule_id_from_llm else rule_id_from_llm

                level_from_llm = str(llm_finding.get("level", DEFAULT_META_REVIEW_LEVEL)).lower()
                internal_level = SEVERITY_MAP.get(level_from_llm, DEFAULT_META_REVIEW_LEVEL)

                # Tạo finding đã chuẩn hóa
                # tool_name sẽ là "MetaReviewer" do self._format_finding
                refined_finding = self._format_finding(
                    file_path=str(file_path),
                    line_start=line_start,
                    message=str(message),
                    rule_id_suffix=rule_id_suffix, 
                    level=internal_level,
                    suggestion=llm_finding.get("suggestion"),
                    line_end=llm_finding.get("line_end"),
                    confidence=llm_finding.get("confidence")
                )
                
                # Thêm các trường tùy chọn khác nếu LLM cung cấp
                if "meta_comment" in llm_finding:
                    refined_finding["meta_comment"] = llm_finding["meta_comment"]
                if "original_rule_ids" in llm_finding and isinstance(llm_finding["original_rule_ids"], list):
                    refined_finding["original_rule_ids"] = llm_finding["original_rule_ids"]
                if "explanation_steps" in llm_finding and isinstance(llm_finding["explanation_steps"], list):
                    refined_finding["explanation_steps"] = llm_finding["explanation_steps"]
                
                # Nếu LLM cố gắng giữ lại tool_name gốc, chúng ta có thể lưu nó lại
                if "tool_name" in llm_finding and llm_finding["tool_name"] != self.agent_name:
                    refined_finding["original_tool_name_preserved_by_meta"] = llm_finding["tool_name"]
                
                final_refined_findings.append(refined_finding)
            
            logger.info(f"<{self.agent_name}> Meta-review processed {len(all_agent_findings)} original findings, resulted in {len(final_refined_findings)} refined findings.")
            return final_refined_findings

        except Exception as e:
            logger.error(f"<{self.agent_name}> Critical error during MetaReviewer LLM interaction or processing: {e}", exc_info=True)
            return all_agent_findings # Fallback an toàn là trả về list gốc

        # Fallback cuối cùng nếu có lỗi không mong muốn không được bắt ở trên
        logger.warning(f"<{self.agent_name}> Meta-review completed but fell through to final fallback. Original: {len(all_agent_findings)}, Output: {len(final_refined_findings)}.")
        return final_refined_findings if final_refined_findings else all_agent_findings