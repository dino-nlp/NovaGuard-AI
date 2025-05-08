# NOVAGUARD-AI/src/orchestrator/nodes.py
import logging
from typing import Dict, List, Any, Optional, Literal # Thêm Literal nếu dùng cho conditional edges sau này
from pathlib import Path 

# Import các thành phần từ các module khác trong project
from .state import GraphState
from ..core.config_loader import Config
from ..core.tool_runner import ToolRunner, ToolExecutionError
from ..core.sarif_generator import SarifGenerator
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager
from ..core.shared_context import ChangedFile, SharedReviewContext # Import cả SharedReviewContext

# Import các lớp Agent (hiện tại là stub)
from ..agents.style_guardian_agent import StyleGuardianAgent
from ..agents.bug_hunter_agent import BugHunterAgent
from ..agents.securi_sense_agent import SecuriSenseAgent
from ..agents.opti_tune_agent import OptiTuneAgent
from ..agents.meta_reviewer_agent import MetaReviewerAgent

logger = logging.getLogger(__name__)

# --- Helper: Language Detection (Simple Example) ---
def guess_language(file_path: str) -> Optional[str]:
    """Simple language guessing based on file extension."""
    extension_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".java": "java", ".cs": "csharp", ".go": "go", ".rb": "ruby",
        ".php": "php", ".c": "c", ".cpp": "cpp", ".h": "c_header",
        ".kt": "kotlin", ".swift": "swift", ".rs": "rust",
        ".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".html": "html", ".css": "css", ".scss": "scss",
    }
    # Sử dụng Path đã import
    try:
        ext = Path(file_path).suffix.lower()
        return extension_map.get(ext)
    except Exception as e:
        logger.warning(f"Could not extract suffix from path '{file_path}': {e}")
        return None

# --- Node Functions ---

def prepare_review_files_node(state: GraphState) -> Dict[str, Any]:
    """
    Identifies and prepares files for review from the initial state.
    Attempts to guess the language for each file if not already set.
    Handles potential type inconsistencies in the input list.
    """
    logger.info("--- Running: Prepare Review Files Node ---")
    # Lấy dữ liệu từ state
    files_from_context: List[Any] = state.get("files_to_review", [])
    # Giữ lại các lỗi đã có từ các bước trước (nếu có)
    error_messages = list(state.get("error_messages", [])) 

    updated_files_to_review: List[ChangedFile] = []
    
    if files_from_context: # Chỉ xử lý nếu có file đầu vào
        logger.debug(f"Processing {len(files_from_context)} items from initial 'files_to_review'.")
        for idx, file_data in enumerate(files_from_context):
            file_obj = None
            # Đảm bảo xử lý đúng kiểu dữ liệu (có thể là dict hoặc ChangedFile)
            if isinstance(file_data, ChangedFile):
                file_obj = file_data # Already the correct type
            elif isinstance(file_data, dict):
                try:
                    # Cố gắng tạo đối tượng ChangedFile từ dict
                    file_obj = ChangedFile(**file_data)
                except Exception as e:
                    # Log lỗi nếu dict không đúng cấu trúc ChangedFile
                    logger.warning(f"Item {idx} in 'files_to_review' is a dict but failed validation for ChangedFile: {file_data}. Error: {e}")
                    error_messages.append(f"Invalid file data format encountered at index {idx}: {str(file_data)[:100]}")
                    continue # Bỏ qua file data không hợp lệ
            else:
                # Log lỗi nếu kiểu dữ liệu không mong đợi
                logger.warning(f"Unexpected data type at index {idx} in 'files_to_review': {type(file_data)}. Expected ChangedFile or dict. Skipping.")
                error_messages.append(f"Unexpected data type in 'files_to_review' at index {idx}: {type(file_data)}")
                continue

            # Nếu có file_obj hợp lệ, đoán ngôn ngữ nếu chưa có
            if file_obj.language is None:
                file_obj.language = guess_language(file_obj.path)
                log_lang = f"'{file_obj.language}'" if file_obj.language else "unknown"
                logger.debug(f"Language for '{file_obj.path}' guessed as: {log_lang}.")
            
            updated_files_to_review.append(file_obj)
    else: # Nếu input ban đầu đã rỗng
        logger.info("Initial 'files_to_review' list was empty. No files to prepare.")

    logger.info(f"Node finished. Prepared {len(updated_files_to_review)} files for review.")
    
    # Không thêm lỗi vào state nếu input ban đầu rỗng, chỉ log info.
    # Nếu có lỗi xảy ra trong quá trình xử lý (validation, etc.), chúng đã được thêm vào error_messages.

    # Trả về state update
    return {"files_to_review": updated_files_to_review, "error_messages": error_messages}


# --- Các Node Function khác (Giữ nguyên placeholder hoặc logic đã có) ---

def run_tier1_tools_node(state: GraphState) -> Dict[str, Any]:
    """
    Runs traditional static analysis tools (linters, basic SAST) on the files.
    (Implementation needs access to Config and ToolRunner, typically via state or RunnableConfig)
    """
    logger.info("--- Running: Tier 1 Tools Node ---")
    shared_ctx: Optional[SharedReviewContext] = state.get("shared_context")
    files_to_review: List[ChangedFile] = state.get("files_to_review", [])
    error_messages = list(state.get("error_messages", []))
    tier1_results: Dict[str, List[Dict[str, Any]]] = {} # Thay đổi cấu trúc này nếu cần

    if not shared_ctx or not hasattr(shared_ctx, 'config_obj'):
        error_messages.append("Config object not found in shared_context for run_tier1_tools_node.")
        logger.error("Config object not available in shared_context. Cannot run Tier 1 tools.")
        return {"tier1_tool_results": tier1_results, "error_messages": error_messages}

    config_obj: Config = shared_ctx.config_obj
    tool_runner = ToolRunner(config_obj, shared_ctx.repo_local_path)

    processed_tools: Dict[str, List] = {} # Để nhóm kết quả theo tool_category.tool_key

    # Logic chạy tool (ví dụ Pylint, Semgrep) như đã thảo luận trước đó
    # ... (Iterate through files_to_review) ...
    # ... (Determine applicable tools based on file_obj.language and config_obj.tools_config) ...
    # ... (Call tool_runner.run(...)) ...
    # ... (Parse output and populate `processed_tools` dict) ...
    #     Ví dụ:
    #     tool_id = f"{tool_cat}.{tool_key}"
    #     if tool_id not in processed_tools: processed_tools[tool_id] = []
    #     processed_tools[tool_id].extend(parsed_findings_from_tool)

    # Cấu trúc lại kết quả cuối cùng nếu cần (ví dụ: nhóm theo category)
    # tier1_results = processed_tools # Hoặc cấu trúc lại nếu GraphState yêu cầu khác
    logger.warning("Tier 1 tool execution logic is currently a placeholder in nodes.py")


    logger.info(f"Tier 1 tools phase completed.")
    return {"tier1_tool_results": tier1_results, "error_messages": error_messages}


def _activate_agent_node(
    agent_class: type,
    agent_name_log: str,
    state: GraphState,
    extra_agent_input: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Helper function to instantiate and run an agent."""
    logger.info(f"--- Running: Activate {agent_name_log} Node ---")
    shared_ctx: Optional[SharedReviewContext] = state.get("shared_context")
    files_to_review = state.get("files_to_review", [])
    current_agent_findings = list(state.get("agent_findings", []))
    error_messages = list(state.get("error_messages", []))

    if not shared_ctx or not hasattr(shared_ctx, 'config_obj'):
        msg = f"Config object not found in shared_context for {agent_name_log}."
        logger.error(msg)
        error_messages.append(msg)
        # Trả về state hiện tại để không làm mất dữ liệu trước đó
        return {"agent_findings": current_agent_findings, "error_messages": error_messages}

    config_obj: Config = shared_ctx.config_obj
    
    # Khởi tạo các client cần thiết (nên được tối ưu hóa sau này)
    ollama_client = OllamaClientWrapper(base_url=config_obj.ollama_base_url)
    prompt_manager = PromptManager(config=config_obj)
    
    try:
        agent_instance = agent_class(config=config_obj, ollama_client=ollama_client, prompt_manager=prompt_manager)
        
        agent_specific_input = {"files_data": files_to_review}
        if extra_agent_input:
            agent_specific_input.update(extra_agent_input)

        # Pass relevant tier1 results if the agent needs them
        if agent_name_log == "StyleGuardian" or agent_name_log == "SecuriSense":
            agent_specific_input["tier1_tool_results"] = state.get("tier1_tool_results")

        # Gọi phương thức review của agent
        new_findings = agent_instance.review(**agent_specific_input)
        
        if isinstance(new_findings, list):
            current_agent_findings.extend(new_findings)
            logger.info(f"{agent_name_log} contributed {len(new_findings)} findings.")
        else:
            msg = f"{agent_name_log} review method did not return a list."
            logger.error(msg)
            error_messages.append(msg)

    except NotImplementedError:
        msg = f"{agent_name_log} 'review' method is not implemented."
        logger.warning(msg)
    except Exception as e:
        msg = f"Error during {agent_name_log} execution: {e}"
        logger.error(msg, exc_info=True)
        error_messages.append(msg)
        
    return {"agent_findings": current_agent_findings, "error_messages": error_messages}

# Các node gọi agent sử dụng helper _activate_agent_node
def activate_style_guardian_node(state: GraphState) -> Dict[str, Any]:
    return _activate_agent_node(StyleGuardianAgent, "StyleGuardian", state)

def activate_bug_hunter_node(state: GraphState) -> Dict[str, Any]:
    return _activate_agent_node(BugHunterAgent, "BugHunter", state)

def activate_securi_sense_node(state: GraphState) -> Dict[str, Any]:
    return _activate_agent_node(SecuriSenseAgent, "SecuriSense", state)

def activate_opti_tune_node(state: GraphState) -> Dict[str, Any]:
    return _activate_agent_node(OptiTuneAgent, "OptiTune", state)

# Node MetaReviewer có thể cần logic gọi hơi khác
def run_meta_review_node(state: GraphState) -> Dict[str, Any]:
    logger.info(f"--- Running: Meta Reviewer Node ---")
    shared_ctx: Optional[SharedReviewContext] = state.get("shared_context")
    all_previous_findings = list(state.get("agent_findings", []))
    files_to_review = state.get("files_to_review", [])
    error_messages = list(state.get("error_messages", []))

    if not all_previous_findings:
        logger.info("No previous agent findings to meta-review. Skipping.")
        # Trả về state không đổi (ngoài error_messages nếu có lỗi config)
        return {"agent_findings": all_previous_findings, "error_messages": error_messages}

    if not shared_ctx or not hasattr(shared_ctx, 'config_obj'):
        msg = f"Config object not found in shared_context for MetaReviewer."
        logger.error(msg)
        error_messages.append(msg)
        return {"agent_findings": all_previous_findings, "error_messages": error_messages}

    config_obj: Config = shared_ctx.config_obj
    
    ollama_client = OllamaClientWrapper(base_url=config_obj.ollama_base_url)
    prompt_manager = PromptManager(config=config_obj)
    
    try:
        meta_reviewer = MetaReviewerAgent(config=config_obj, ollama_client=ollama_client, prompt_manager=prompt_manager)
        # Giả sử signature của MetaReviewer là review(self, all_agent_findings, files_data)
        refined_findings = meta_reviewer.review(all_agent_findings=all_previous_findings, files_data=files_to_review)
        
        if isinstance(refined_findings, list):
            logger.info(f"MetaReviewer processed {len(all_previous_findings)} findings, resulted in {len(refined_findings)} findings.")
            # Ghi đè danh sách findings cũ bằng danh sách đã tinh chỉnh
            return {"agent_findings": refined_findings, "error_messages": error_messages}
        else:
            msg = "MetaReviewer review method did not return a list."
            logger.error(msg)
            error_messages.append(msg)
            # Trả về findings gốc nếu MetaReviewer trả về sai định dạng
            return {"agent_findings": all_previous_findings, "error_messages": error_messages}

    except NotImplementedError:
        logger.warning("MetaReviewerAgent 'review' method is not implemented.")
        return {"agent_findings": all_previous_findings, "error_messages": error_messages}
    except Exception as e:
        msg = f"Error during MetaReviewer execution: {e}"
        logger.error(msg, exc_info=True)
        error_messages.append(msg)
        # Trả về findings gốc nếu MetaReviewer lỗi
        return {"agent_findings": all_previous_findings, "error_messages": error_messages}

# Node tạo báo cáo SARIF
def generate_sarif_report_node(state: GraphState) -> Dict[str, Any]:
    """
    Generates the final SARIF report from all collected findings.
    """
    logger.info("--- Running: Generate SARIF Report Node ---")
    shared_ctx: Optional[SharedReviewContext] = state.get("shared_context")
    tier1_results = state.get("tier1_tool_results", {})
    agent_findings = state.get("agent_findings", [])
    error_messages = list(state.get("error_messages", [])) # Lấy lỗi TỪ TRƯỚC node này

    if not shared_ctx or not hasattr(shared_ctx, 'config_obj'):
        error_messages.append("Config object not found in shared_context for generate_sarif_report_node.")
        logger.error("Config object not available in shared_context. Cannot generate SARIF report accurately.")
        # Vẫn cố gắng tạo report rỗng hoặc báo lỗi
        # Tạo SarifGenerator với thông tin tối thiểu
        sarif_generator = SarifGenerator(tool_name="NovaGuardAI", tool_version="unknown")
        sarif_generator.set_invocation_status(successful=False, error_message="Configuration unavailable.")
        return {"final_sarif_report": sarif_generator.get_sarif_report(), "error_messages": error_messages}

    config_obj: Config = shared_ctx.config_obj
    
    # Lấy thông tin tool từ config hoặc dùng giá trị mặc định
    TOOL_NAME = getattr(config_obj, 'tool_name', "NovaGuardAI") # Ví dụ lấy từ config nếu có
    TOOL_VERSION = getattr(config_obj, 'tool_version', "0.1.0") # Ví dụ
    TOOL_INFO_URI = getattr(config_obj, 'tool_info_uri', None) # Ví dụ

    sarif_generator = SarifGenerator(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        tool_information_uri=TOOL_INFO_URI,
        repo_uri_for_artifacts=f"https://github.com/{shared_ctx.repository_name}",
        commit_sha_for_artifacts=shared_ctx.sha,
        workspace_root_for_relative_paths=shared_ctx.repo_local_path
    )

    # Add findings from Tier 1 tools
    # Cần chuẩn hóa cấu trúc tier1_results nếu nó phức tạp
    # Giả sử nó là Dict[str, List[Dict]] với key là tool_id (e.g., "linters.python")
    findings_added_count = 0
    for tool_id, findings_list in tier1_results.items():
        if isinstance(findings_list, list): # Đảm bảo là list
            for finding in findings_list:
                if isinstance(finding, dict): # Đảm bảo là dict
                    try:
                        # Cần đảm bảo finding dict có đủ các key cần thiết
                        # (file_path, message_text, rule_id, level, line_start)
                        if all(k in finding for k in ["file_path", "message_text", "rule_id", "level", "line_start"]):
                            sarif_generator.add_finding(
                                file_path=finding["file_path"],
                                message_text=finding["message_text"],
                                rule_id=str(finding["rule_id"]),
                                level=str(finding["level"]).lower(),
                                line_start=int(finding["line_start"]),
                                line_end=finding.get("line_end"),
                                col_start=finding.get("col_start"),
                                col_end=finding.get("col_end"),
                            )
                            findings_added_count += 1
                        else:
                            logger.warning(f"Skipping Tier 1 finding due to missing keys: {finding}")
                            error_messages.append(f"Invalid Tier 1 finding format skipped: {str(finding)[:100]}")
                    except (ValueError, TypeError) as e:
                        msg = f"Failed to add Tier 1 finding to SARIF due to type error: {str(finding)[:200]}. Error: {e}"
                        logger.warning(msg)
                        error_messages.append(msg)
                else:
                    logger.warning(f"Invalid finding type in Tier 1 results for {tool_id}: {type(finding)}")
                    error_messages.append(f"Invalid data type {type(finding)} in Tier 1 results for {tool_id}")
        else:
            logger.warning(f"Unexpected data structure for tool '{tool_id}' in tier1_results: Expected list, got {type(findings_list)}")
            error_messages.append(f"Unexpected data structure for tool '{tool_id}' in tier1_results.")


    # Add findings from LLM Agents
    for finding in agent_findings:
        if isinstance(finding, dict):
            try:
                if all(k in finding for k in ["file_path", "message_text", "rule_id", "level", "line_start"]):
                    sarif_generator.add_finding(
                        file_path=finding["file_path"],
                        message_text=finding["message_text"],
                        rule_id=str(finding["rule_id"]),
                        level=str(finding["level"]).lower(),
                        line_start=int(finding["line_start"]),
                        line_end=finding.get("line_end"),
                        col_start=finding.get("col_start"),
                        col_end=finding.get("col_end"),
                        code_snippet=finding.get("code_snippet"),
                        # Cần chuẩn bị cấu trúc fixes nếu agent cung cấp suggestion
                        # fixes=[{"description": {"text": "Suggested fix"}, "artifactChanges": [...]}] if finding.get("suggestion") else None
                    )
                    findings_added_count += 1
                else:
                    logger.warning(f"Skipping Agent finding due to missing keys: {finding}")
                    error_messages.append(f"Invalid Agent finding format skipped: {str(finding)[:100]}")
            except (ValueError, TypeError) as e:
                msg = f"Failed to add Agent finding to SARIF due to type error: {str(finding)[:200]}. Error: {e}"
                logger.warning(msg)
                error_messages.append(msg)
        else:
            logger.warning(f"Invalid finding type in agent_findings: {type(finding)}")
            error_messages.append(f"Invalid data type {type(finding)} in agent_findings list.")


    # Set overall invocation status based on errors collected BEFORE this node started
    execution_successful = not bool(state.get("error_messages"))
    final_error_message = "One or more errors occurred during analysis. Check logs and SARIF notifications." if not execution_successful else None
    # Nếu có lỗi mới phát sinh trong node này (vd: parse finding lỗi), cũng nên coi là không thành công?
    if error_messages != state.get("error_messages", []): # Nếu có lỗi mới được thêm vào
        execution_successful = False
        final_error_message = "One or more errors occurred during analysis or SARIF generation. Check logs and SARIF notifications."


    sarif_generator.set_invocation_status(
        successful=execution_successful,
        error_message=final_error_message
    )

    final_report = sarif_generator.get_sarif_report()
    logger.info(f"SARIF report generated with {findings_added_count} findings added to results.")
    
    # Trả về state update cuối cùng
    return {"final_sarif_report": final_report, "error_messages": error_messages}