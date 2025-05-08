# NOVAGUARD-AI/src/orchestrator/nodes.py
import logging
from typing import Dict, List, Any, Optional, Literal, Union
from pathlib import Path
import traceback

# Import các thành phần từ các module khác trong project
from .state import GraphState
from ..core.config_loader import Config
from ..core.tool_runner import ToolRunner, ToolExecutionError
from ..core.sarif_generator import SarifGenerator
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager
from ..core.shared_context import ChangedFile, SharedReviewContext

# Import các lớp Agent
from ..agents.style_guardian_agent import StyleGuardianAgent
from ..agents.bug_hunter_agent import BugHunterAgent
from ..agents.securi_sense_agent import SecuriSenseAgent
from ..agents.opti_tune_agent import OptiTuneAgent
from ..agents.meta_reviewer_agent import MetaReviewerAgent

logger = logging.getLogger(__name__)

# --- Helper: Language Detection ---
def guess_language(file_path: str) -> Optional[str]:
    extension_map = { ".py": "python", ".js": "javascript", ".ts": "typescript", ".java": "java", ".cs": "csharp", ".go": "go", ".rb": "ruby", ".php": "php", ".c": "c", ".cpp": "cpp", ".h": "c_header", ".kt": "kotlin", ".swift": "swift", ".rs": "rust", ".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".html": "html", ".css": "css", ".scss": "scss", }
    try: ext = Path(file_path).suffix.lower(); return extension_map.get(ext)
    except Exception: return None

# --- Helper: Infer JSON expectation ---
def _infer_expect_json(tool_config_data: Optional[Union[str, Dict]], command_template: Optional[str]) -> bool:
    """Helper to infer if JSON output is expected based on config or command."""
    if isinstance(tool_config_data, dict):
        if tool_config_data.get("output_method") in ["stdout_json", "file_json"]: return True
        if tool_config_data.get("expect_json") is True: return True
    if command_template:
        cmd_lower = command_template.lower()
        # <<< Cải thiện logic nhận diện JSON flag >>>
        json_flags = ['--output-format=json', '--format=json', '--format json', '-f json'] 
        # Kiểm tra flag đầy đủ hoặc --json đứng riêng
        if any(flag in cmd_lower for flag in json_flags) or ('--json' in command_template.split()):
            return True
    return False

# --- Node Functions ---
def prepare_review_files_node(state: GraphState) -> Dict[str, Any]:
    # ... (Logic đã pass test, giữ nguyên) ...
    logger.info("--- Running: Prepare Review Files Node ---"); files_from_context: List[Any] = state.get("files_to_review", []); error_messages = list(state.get("error_messages", [])); updated_files_to_review: List[ChangedFile] = [];
    if files_from_context:
        logger.debug(f"Processing {len(files_from_context)} items from initial 'files_to_review'.")
        for idx, file_data in enumerate(files_from_context):
            file_obj = None;
            if isinstance(file_data, ChangedFile): file_obj = file_data
            elif isinstance(file_data, dict):
                try: file_obj = ChangedFile(**file_data)
                except Exception as e: logger.warning(f"Item {idx} failed ChangedFile validation: {file_data}. Error: {e}"); error_messages.append(f"Invalid file data format at index {idx}: {str(file_data)[:100]}"); continue
            else: logger.warning(f"Unexpected data type at index {idx}: {type(file_data)}. Skipping."); error_messages.append(f"Unexpected data type at index {idx}: {type(file_data)}"); continue
            if file_obj.language is None: file_obj.language = guess_language(file_obj.path); log_lang = f"'{file_obj.language}'" if file_obj.language else "unknown"; logger.debug(f"Language for '{file_obj.path}' guessed as: {log_lang}.")
            updated_files_to_review.append(file_obj)
    else: logger.info("Initial 'files_to_review' list was empty. No files to prepare.")
    logger.info(f"Node finished. Prepared {len(updated_files_to_review)} files for review."); return {"files_to_review": updated_files_to_review, "error_messages": error_messages}


def run_tier1_tools_node(state: GraphState) -> Dict[str, Any]:
    logger.info("--- Running: Tier 1 Tools Node ---")
    shared_ctx: Optional[SharedReviewContext] = state.get("shared_context")
    files_to_review: List[ChangedFile] = state.get("files_to_review", [])
    error_messages = list(state.get("error_messages", []))
    tier1_results: Dict[str, Dict[str, List[Dict[str, Any]]]] = {} 

    if not shared_ctx or not hasattr(shared_ctx, 'config_obj'):
        error_messages.append("Config object missing in run_tier1_tools_node."); logger.error("Config object missing."); return {"tier1_tool_results": tier1_results, "error_messages": error_messages}

    config_obj: Config = shared_ctx.config_obj
    tool_runner = ToolRunner(config_obj, shared_ctx.repo_local_path)
    configured_tools = config_obj.tools_config

    # --- Run tools per file ---
    for file_obj in files_to_review:
        if not file_obj.language: continue
        lang = file_obj.language.lower()
        logger.debug(f"Checking file-specific Tier 1 tools for: {file_obj.path} (Lang: {lang})")

        for category, tools_in_category in configured_tools.items():
            if not isinstance(tools_in_category, dict): continue
            for tool_key, tool_config_data in tools_in_category.items():
                is_project_tool = False; command_template = None;
                if isinstance(tool_config_data, str): command_template = tool_config_data
                elif isinstance(tool_config_data, dict):
                    command_template = tool_config_data.get("command")
                    if tool_config_data.get("target_type") == "project": is_project_tool = True
                    elif command_template and "{project_root}" in command_template and "{file_path}" not in command_template: is_project_tool = True
                
                if is_project_tool or not command_template: continue 

                run_this_tool = False
                if category == "linters" and tool_key == lang: run_this_tool = True
                # Add other file-specific conditions here

                if run_this_tool:
                    # <<< Đảm bảo khởi tạo key trước khi gọi run >>>
                    if category not in tier1_results: tier1_results[category] = {}
                    if tool_key not in tier1_results[category]: tier1_results[category][tool_key] = []
                            
                    expect_json = _infer_expect_json(tool_config_data, command_template) # <<< Đã sửa _infer_expect_json
                    logger.info(f"Running tool '{category}.{tool_key}' for file {file_obj.path} (expect_json={expect_json})")
                    try:
                        tool_output = tool_runner.run(
                            tool_category=category, tool_key=tool_key,
                            target_file_relative_path=file_obj.path,
                            expect_json_output=expect_json,
                        )
                        if tool_output is not None:
                            findings_list = []
                            if isinstance(tool_output, list): findings_list = tool_output
                            elif isinstance(tool_output, dict): findings_list = [tool_output] 
                            elif isinstance(tool_output, str) and tool_output.strip(): findings_list = [{"message_text": tool_output[:500], "rule_id": f"{category}.{tool_key}.raw", "level": "note", "line_start":1}]
                            
                            standardized_findings = []
                            for finding_dict in findings_list:
                                if isinstance(finding_dict, dict):
                                    adapted = finding_dict.copy() # Tạo bản sao để không sửa dict gốc
                                    adapted["file_path"] = adapted.get("file_path", file_obj.path)
                                    adapted["tool_name"] = f"{category}.{tool_key}"
                                    adapted["line_start"] = int(adapted.get("line_start", adapted.get("line", 1)))
                                    adapted["rule_id"] = str(adapted.get("rule_id", adapted.get("symbol", adapted.get("check_id", f"{tool_key}.unknown"))))
                                    adapted["level"] = str(adapted.get("level", adapted.get("severity", "note"))).lower()
                                    # <<< Sửa logic lấy message >>>
                                    adapted["message_text"] = str(adapted.get("message_text") or adapted.get("message") or adapted.get("msg") or "Message missing")
                                    standardized_findings.append(adapted)
                                else: error_messages.append(f"Invalid item type in findings list from {category}.{tool_key}: {type(finding_dict)}")
                            
                            tier1_results[category][tool_key].extend(standardized_findings)
                            logger.info(f"Tool '{category}.{tool_key}' completed for {file_obj.path}, added {len(standardized_findings)} findings.")
                        else: logger.info(f"Tool '{category}.{tool_key}' ran for {file_obj.path} but produced no output.")
                    except ToolExecutionError as e:
                        # <<< SỬA LỖI AttributeError: dùng str(e) >>>
                        msg = f"Tool '{category}.{tool_key}' execution failed for {file_obj.path}: {str(e)}" 
                        logger.error(f"{msg} (stderr: {e.stderr})")
                        error_messages.append(msg)
                    except Exception as e:
                        msg = f"Unexpected error running tool '{category}.{tool_key}' for {file_obj.path}: {e}"; logger.error(msg, exc_info=True); error_messages.append(msg)

    # --- Run project-wide tools ---
    project_tool_keys_run = set()
    for category, tools_in_category in configured_tools.items():
        if not isinstance(tools_in_category, dict): continue
        for tool_key, tool_config_data in tools_in_category.items():
            tool_id = f"{category}.{tool_key}"; command_template = None; is_project_tool = False;
            if tool_id in project_tool_keys_run: continue
            if isinstance(tool_config_data, str): command_template = tool_config_data
            elif isinstance(tool_config_data, dict):
                command_template = tool_config_data.get("command")
                if tool_config_data.get("target_type") == "project": is_project_tool = True
                elif command_template and "{project_root}" in command_template and "{file_path}" not in command_template: is_project_tool = True

            if is_project_tool and command_template:
                # <<< Đảm bảo khởi tạo key trước khi gọi run >>>
                if category not in tier1_results: tier1_results[category] = {}
                if tool_key not in tier1_results[category]: tier1_results[category][tool_key] = []
                            
                expect_json = _infer_expect_json(tool_config_data, command_template) # <<< Đã sửa _infer_expect_json
                logger.info(f"Running project-level tool: '{tool_id}' (expect_json={expect_json})")
                project_tool_keys_run.add(tool_id)
                try:
                    tool_output = tool_runner.run(
                        tool_category=category, tool_key=tool_key,
                        target_file_relative_path=None, expect_json_output=expect_json,
                    )
                    if tool_output is not None: 
                        findings_list = []
                        if isinstance(tool_output, list): findings_list = tool_output
                        elif isinstance(tool_output, dict):
                            if "results" in tool_output and isinstance(tool_output["results"], list): findings_list = tool_output["results"]
                            else: logger.warning(f"Dict output from '{tool_id}' lacks 'results' list."); findings_list = [tool_output]
                        elif isinstance(tool_output, str) and tool_output.strip(): findings_list = [{"message_text": tool_output[:500], "rule_id": f"{tool_id}.raw", "level": "note", "tool_name": tool_id, "line_start":1, "file_path": "project-wide"}]
                        
                        standardized_findings = []
                        for finding_dict in findings_list:
                            if isinstance(finding_dict, dict):
                                # <<< SỬA LỖI: Chuẩn hóa finding Semgrep >>>
                                adapted = finding_dict.copy()
                                adapted["tool_name"] = tool_id
                                adapted["line_start"] = int(adapted.get("line_start", adapted.get("start", {}).get("line", 1)))
                                adapted["rule_id"] = str(adapted.get("rule_id", adapted.get("check_id", f"{tool_key}.unknown")))
                                adapted["level"] = str(adapted.get("level", adapted.get("extra", {}).get("severity", "note"))).lower()
                                adapted["message_text"] = str(adapted.get("message_text") or adapted.get("message") or adapted.get("msg") or adapted.get("extra", {}).get("message") or "Message missing")
                                adapted["file_path"] = adapted.get("file_path") or adapted.get("path") # <<< Lấy từ 'path' nếu 'file_path' không có
                                adapted["line_end"] = adapted.get("line_end") or adapted.get("end", {}).get("line")
                                adapted["col_start"] = adapted.get("col_start") or adapted.get("start", {}).get("col")
                                adapted["col_end"] = adapted.get("col_end") or adapted.get("end", {}).get("col")
                                adapted["code_snippet"] = adapted.get("code_snippet") or adapted.get("extra", {}).get("lines")

                                if adapted.get("file_path"):
                                    standardized_findings.append(adapted)
                                else: logger.warning(f"Skipping finding from project tool '{tool_id}' due to missing file_path: {str(adapted)[:100]}")
                            else: error_messages.append(f"Invalid item type in findings list from project tool {tool_id}: {type(finding_dict)}")

                        tier1_results[category][tool_key].extend(standardized_findings)
                        logger.info(f"Project tool '{tool_id}' completed, added {len(standardized_findings)} findings.")
                    else:
                        logger.info(f"Project tool '{tool_id}' ran but produced no output.")

                except ToolExecutionError as e:
                    # <<< SỬA LỖI AttributeError: dùng str(e) >>>
                    msg = f"Project tool '{tool_id}' execution failed: {str(e)}" 
                    logger.error(f"{msg} (stderr: {e.stderr})")
                    error_messages.append(msg)
                except Exception as e:
                    msg = f"Unexpected error running project tool '{tool_id}': {e}"; logger.error(msg, exc_info=True); error_messages.append(msg)

    logger.info(f"Tier 1 tools phase completed. Results keys: {list(tier1_results.keys())}")
    return {"tier1_tool_results": tier1_results, "error_messages": error_messages}


# --- Các node activate agent và generate_sarif giữ nguyên như bản trước ---
def _activate_agent_node(agent_class: type, agent_name_log: str, state: GraphState, extra_agent_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    logger.info(f"--- Running: Activate {agent_name_log} Node ---"); shared_ctx: Optional[SharedReviewContext] = state.get("shared_context"); files_to_review = state.get("files_to_review", []); current_agent_findings = list(state.get("agent_findings", [])); error_messages = list(state.get("error_messages", []));
    if not shared_ctx or not hasattr(shared_ctx, 'config_obj'): msg = f"Config object not found for {agent_name_log}."; logger.error(msg); error_messages.append(msg); return {"agent_findings": current_agent_findings, "error_messages": error_messages}
    config_obj: Config = shared_ctx.config_obj; ollama_client = OllamaClientWrapper(base_url=config_obj.ollama_base_url); prompt_manager = PromptManager(config=config_obj)
    try:
        agent_instance = agent_class(config=config_obj, ollama_client=ollama_client, prompt_manager=prompt_manager); agent_specific_input = {"files_data": files_to_review};
        if extra_agent_input: agent_specific_input.update(extra_agent_input)
        if agent_name_log in ["StyleGuardian", "SecuriSense"]: agent_specific_input["tier1_tool_results"] = state.get("tier1_tool_results")
        new_findings = agent_instance.review(**agent_specific_input);
        if isinstance(new_findings, list): current_agent_findings.extend(new_findings); logger.info(f"{agent_name_log} contributed {len(new_findings)} findings.")
        else: msg = f"{agent_name_log} review method did not return a list."; logger.error(msg); error_messages.append(msg)
    except NotImplementedError: msg = f"{agent_name_log} 'review' method is not implemented."; logger.warning(msg)
    except Exception as e: msg = f"Error during {agent_name_log} execution: {e}"; logger.error(msg, exc_info=True); error_messages.append(msg)
    return {"agent_findings": current_agent_findings, "error_messages": error_messages}

def activate_style_guardian_node(state: GraphState) -> Dict[str, Any]: return _activate_agent_node(StyleGuardianAgent, "StyleGuardian", state)
def activate_bug_hunter_node(state: GraphState) -> Dict[str, Any]: return _activate_agent_node(BugHunterAgent, "BugHunter", state)
def activate_securi_sense_node(state: GraphState) -> Dict[str, Any]: return _activate_agent_node(SecuriSenseAgent, "SecuriSense", state)
def activate_opti_tune_node(state: GraphState) -> Dict[str, Any]: return _activate_agent_node(OptiTuneAgent, "OptiTune", state)
def run_meta_review_node(state: GraphState) -> Dict[str, Any]:
    logger.info(f"--- Running: Meta Reviewer Node ---"); shared_ctx: Optional[SharedReviewContext] = state.get("shared_context"); all_previous_findings = list(state.get("agent_findings", [])); files_to_review = state.get("files_to_review", []); error_messages = list(state.get("error_messages", []));
    if not all_previous_findings: logger.info("No previous agent findings to meta-review. Skipping."); return {"agent_findings": all_previous_findings, "error_messages": error_messages}
    if not shared_ctx or not hasattr(shared_ctx, 'config_obj'): msg = f"Config object not found for MetaReviewer."; logger.error(msg); error_messages.append(msg); return {"agent_findings": all_previous_findings, "error_messages": error_messages}
    config_obj: Config = shared_ctx.config_obj; ollama_client = OllamaClientWrapper(base_url=config_obj.ollama_base_url); prompt_manager = PromptManager(config=config_obj)
    try:
        meta_reviewer = MetaReviewerAgent(config=config_obj, ollama_client=ollama_client, prompt_manager=prompt_manager); refined_findings = meta_reviewer.review(all_agent_findings=all_previous_findings, files_data=files_to_review);
        if isinstance(refined_findings, list): logger.info(f"MetaReviewer processed {len(all_previous_findings)}, resulted in {len(refined_findings)}."); return {"agent_findings": refined_findings, "error_messages": error_messages}
        else: msg = "MetaReviewer review did not return a list."; logger.error(msg); error_messages.append(msg); return {"agent_findings": all_previous_findings, "error_messages": error_messages}
    except NotImplementedError: logger.warning("MetaReviewerAgent 'review' method is not implemented."); return {"agent_findings": all_previous_findings, "error_messages": error_messages}
    except Exception as e: msg = f"Error during MetaReviewer execution: {e}"; logger.error(msg, exc_info=True); error_messages.append(msg); return {"agent_findings": all_previous_findings, "error_messages": error_messages}

def generate_sarif_report_node(state: GraphState) -> Dict[str, Any]:
    logger.info("--- Running: Generate SARIF Report Node ---"); shared_ctx: Optional[SharedReviewContext] = state.get("shared_context"); tier1_results = state.get("tier1_tool_results", {}); agent_findings = state.get("agent_findings", []); error_messages = list(state.get("error_messages", []));
    if not shared_ctx or not hasattr(shared_ctx, 'config_obj'): error_messages.append("Config unavailable for SARIF generation."); logger.error("Config unavailable for SARIF."); sarif_generator = SarifGenerator(tool_name="NovaGuardAI", tool_version="unknown"); sarif_generator.set_invocation_status(successful=False, error_message="Configuration unavailable."); return {"final_sarif_report": sarif_generator.get_sarif_report(), "error_messages": error_messages}
    config_obj: Config = shared_ctx.config_obj; TOOL_NAME = getattr(config_obj, 'tool_name', "NovaGuardAI"); TOOL_VERSION = getattr(config_obj, 'tool_version', "0.1.0"); TOOL_INFO_URI = getattr(config_obj, 'tool_info_uri', None);
    sarif_generator = SarifGenerator(tool_name=TOOL_NAME, tool_version=TOOL_VERSION, tool_information_uri=TOOL_INFO_URI, repo_uri_for_artifacts=f"https://github.com/{shared_ctx.repository_name}", commit_sha_for_artifacts=shared_ctx.sha, workspace_root_for_relative_paths=shared_ctx.repo_local_path)
    findings_added_count = 0
    for category, tools_in_category in tier1_results.items():
        if isinstance(tools_in_category, dict):
            for tool_key, findings_list in tools_in_category.items():
                if isinstance(findings_list, list):
                    for finding in findings_list:
                        if isinstance(finding, dict): 
                             try: 
                                if all(k in finding for k in ["file_path", "message_text", "rule_id", "level", "line_start"]): sarif_generator.add_finding(file_path=finding["file_path"], message_text=finding["message_text"], rule_id=str(finding["rule_id"]), level=str(finding["level"]).lower(), line_start=int(finding["line_start"]), line_end=finding.get("line_end"), col_start=finding.get("col_start"), col_end=finding.get("col_end"), rule_name=f"{category}.{tool_key}"); findings_added_count += 1
                                else: logger.warning(f"Skipping Tier 1 finding from {category}.{tool_key} (missing keys): {str(finding)[:100]}"); error_messages.append(f"Invalid Tier 1 finding format skipped: {str(finding)[:100]}")
                             except (ValueError, TypeError) as e: msg = f"Failed adding Tier 1 finding ({category}.{tool_key}) to SARIF: {str(finding)[:200]}. Error: {e}"; logger.warning(msg); error_messages.append(msg)
                        else: logger.warning(f"Invalid finding type for {category}.{tool_key}: {type(finding)}"); error_messages.append(f"Invalid data type {type(finding)} for {category}.{tool_key}")
                else: logger.warning(f"Invalid structure for tool '{tool_key}' under '{category}'. Expected list."); error_messages.append(f"Invalid structure for tool '{tool_key}' under '{category}'.")
        else: logger.warning(f"Unexpected structure for category '{category}'. Expected dict."); error_messages.append(f"Unexpected structure for category '{category}'.")
    for finding in agent_findings:
        if isinstance(finding, dict):
             try:
                 if all(k in finding for k in ["file_path", "message_text", "rule_id", "level", "line_start"]): sarif_generator.add_finding(file_path=finding["file_path"], message_text=finding["message_text"], rule_id=str(finding["rule_id"]), level=str(finding["level"]).lower(), line_start=int(finding["line_start"]), line_end=finding.get("line_end"), col_start=finding.get("col_start"), col_end=finding.get("col_end"), code_snippet=finding.get("code_snippet")); findings_added_count += 1
                 else: logger.warning(f"Skipping Agent finding (missing keys): {str(finding)[:100]}"); error_messages.append(f"Invalid Agent finding format skipped: {str(finding)[:100]}")
             except (ValueError, TypeError) as e: msg = f"Failed adding Agent finding to SARIF: {str(finding)[:200]}. Error: {e}"; logger.warning(msg); error_messages.append(msg)
        else: logger.warning(f"Invalid finding type in agent_findings: {type(finding)}"); error_messages.append(f"Invalid data type {type(finding)} in agent_findings list.")
    execution_successful = not bool(state.get("error_messages")); final_error_message = "Errors occurred during analysis." if not execution_successful else None;
    if error_messages != state.get("error_messages", []): execution_successful = False; final_error_message = "Errors occurred during analysis or report generation."
    sarif_generator.set_invocation_status(successful=execution_successful, error_message=final_error_message); final_report = sarif_generator.get_sarif_report();
    logger.info(f"SARIF report generated with {findings_added_count} findings added."); return {"final_sarif_report": final_report, "error_messages": error_messages}