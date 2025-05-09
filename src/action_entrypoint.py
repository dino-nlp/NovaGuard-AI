# NOVAGUARD-AI/src/action_entrypoint.py

import os
import sys
import json
import logging
import subprocess
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests # Đảm bảo import requests

# --- Real Imports ---
# Giả sử các import này hoạt động đúng dựa trên cấu trúc project của bạn
# và PYTHONPATH đã được thiết lập chính xác trong Dockerfile.
from src.core.config_loader import load_config, Config
from src.core.sarif_generator import SarifGenerator
from src.core.shared_context import SharedReviewContext, ChangedFile
from src.orchestrator.graph_definition import get_compiled_graph
from src.orchestrator.state import GraphState

# Cấu hình logging cơ bản
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(), 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout # Log ra stdout để GitHub Actions có thể bắt được
)
logger = logging.getLogger("NovaGuardAI_Entrypoint")

# Định nghĩa các mức độ nghiêm trọng cho SARIF và so sánh
SEVERITY_LEVELS = {"error": 3, "warning": 2, "note": 1, "none": 0}

def get_env_input(name: str, required: bool = True, default: Optional[str] = None) -> Optional[str]:
    """Lấy input từ biến môi trường (INPUT_<NAME>)."""
    env_var_name = f"INPUT_{name.upper().replace('-', '_')}" # Xử lý cả gạch ngang
    value = os.environ.get(env_var_name)
    if value is None or value == "":
        if default is not None:
            logger.info(f"Input '{name}' not set, using default: '{default}'")
            return default
        if required:
            logger.error(f"Required input '{name}' (env var {env_var_name}) is missing.")
            # Không sys.exit(1) ở đây nữa, để main() xử lý lỗi chung
            raise ValueError(f"Required input '{name}' (env var {env_var_name}) is missing.")
        return None
    logger.debug(f"Input '{name}' has value: '{value}'")
    return value

def set_action_output_env_file(name: str, value: Any): # Chấp nhận Any, sẽ chuyển thành string
    """Sets an action output using environment files (GITHUB_OUTPUT)."""
    github_output_file = os.environ.get("GITHUB_OUTPUT")
    value_str = str(value) # Đảm bảo là string

    if github_output_file:
        # Xử lý giá trị nhiều dòng cho GITHUB_OUTPUT
        if '\n' in value_str or '\r' in value_str or '%' in value_str or '"' in value_str or "'" in value_str:
            # Sử dụng cú pháp heredoc an toàn
            delimiter = f"NOVA_EOF__{name.upper().replace('-', '_')}__" 
            # Đảm bảo delimiter không có trong value_str, nếu có thì cần phức tạp hơn
            # nhưng với UUID hoặc tên biến, thường là an toàn.
            # Ký tự '%' cần được escape đặc biệt trong GITHUB_OUTPUT heredoc
            value_to_write = value_str.replace('%', '%25')
            
            with open(github_output_file, "a", encoding="utf-8") as f:
                f.write(f"{name}<<{delimiter}\n")
                f.write(f"{value_to_write}\n") # value_to_write đã là string
                f.write(f"{delimiter}\n")
        else: # Giá trị một dòng, không có ký tự đặc biệt nguy hiểm
            with open(github_output_file, "a", encoding="utf-8") as f:
                f.write(f"{name}={value_str}\n")
        logger.info(f"Output '{name}' set via GITHUB_OUTPUT file.")
    else:
        logger.warning("GITHUB_OUTPUT environment variable not found. Cannot set output using environment files.")
        # Fallback to old ::set-output command for local testing or older runners (với cảnh báo)
        logger.warning(f"Falling back to deprecated ::set-output for '{name}'.")
        # Escape cho ::set-output (khác với GITHUB_OUTPUT)
        escaped_value_for_set_output = value_str.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print(f"::set-output name={name}::{escaped_value_for_set_output}")


def get_changed_files(
    workspace_path: Path, 
    head_sha: str, 
    base_sha: Optional[str]
) -> List[ChangedFile]:
    """
    Lấy danh sách file thay đổi giữa base_sha và head_sha,
    và đọc nội dung của chúng.
    """
    changed_files_data: List[ChangedFile] = []
    
    if not base_sha:
        logger.error("Base commit SHA is missing. Cannot perform git diff.")
        raise ValueError("Base commit SHA is required for diffing but was not found.")
        
    try:
        if not (workspace_path / ".git").is_dir():
            logger.error(f"Directory {workspace_path} does not appear to contain a valid .git directory. Ensure fetch-depth:0 or full checkout.")
            raise FileNotFoundError("Git repository not found in workspace. Check checkout depth.")

        # Đảm bảo an toàn thư mục cho git (quan trọng khi chạy trong container)
        # Lệnh này đã được thêm vào workflow `run_local.sh` rồi, nhưng thêm ở đây để chắc chắn.
        safe_dir_cmd = ["git", "config", "--global", "--add", "safe.directory", str(workspace_path)]
        subprocess.run(safe_dir_cmd, check=True, cwd=workspace_path, capture_output=True, text=True)
        logger.info(f"Set safe.directory for {workspace_path} inside container.")

        diff_command = ["git", "diff", "--name-only", base_sha, head_sha]
        logger.info(f"Running git diff command using SHAs: {' '.join(diff_command)}")
        
        result = subprocess.run(diff_command, capture_output=True, text=True, cwd=workspace_path, check=False)

        if result.returncode != 0:
            logger.error(f"Git diff command failed (code {result.returncode}) when diffing {base_sha}..{head_sha}.")
            logger.error(f"Stdout: {result.stdout.strip()}")
            logger.error(f"Stderr: {result.stderr.strip()}")
            logger.error("Ensure both commit SHAs exist in the local repository history (fetch-depth: 0 might be needed in checkout action).")
            raise RuntimeError(f"git diff failed between {base_sha} and {head_sha}. Stderr: {result.stderr.strip()}")
            
        changed_file_paths_str = result.stdout.strip()
        if not changed_file_paths_str:
            logger.info(f"Git diff between {base_sha} and {head_sha} returned no changed file paths.")
            return [] # Không có file thay đổi là một kịch bản hợp lệ
            
        changed_file_paths = [p for p in changed_file_paths_str.split('\n') if p] # Lọc dòng rỗng
        logger.info(f"Changed files found between SHAs: {changed_file_paths}")

        for file_path_str in changed_file_paths:
            full_file_path = (workspace_path / file_path_str).resolve()
            if full_file_path.is_file(): 
                try:
                    content = full_file_path.read_text(encoding='utf-8')
                    # Lưu đường dẫn tương đối với workspace_path
                    relative_path_str = str(Path(file_path_str)) 
                    changed_files_data.append(ChangedFile(path=relative_path_str, content=content))
                    logger.debug(f"Read content for changed file: {relative_path_str}")
                except Exception as e:
                    logger.warning(f"Could not read file {full_file_path} (relative: {file_path_str}): {e}")
            elif full_file_path.exists():
                logger.info(f"Changed path '{file_path_str}' exists but is not a file (e.g., a directory or submodule), skipping content read.")
            else:
                logger.info(f"Changed path '{file_path_str}' not found (likely deleted or renamed without follow), skipping content read.")
    except FileNotFoundError as fnf_err: # Lỗi nếu git không được cài
        logger.error(f"Git command not found. Ensure git is installed in the Docker image: {fnf_err}")
        raise
    except subprocess.CalledProcessError as sp_err: # Lỗi từ lệnh git config
        logger.error(f"Error running git config safe.directory: {sp_err.stderr}")
        raise
    except Exception as e: # Các lỗi khác
        logger.error(f"Error getting changed files using SHAs: {e}", exc_info=True)
        raise 

    logger.info(f"Found {len(changed_files_data)} readable changed files between specified SHAs.")
    return changed_files_data


def post_pr_comment(
    repo_full_name: str, 
    pr_number: int, 
    comment_body: str, 
    github_token: str,
    github_api_url: str # Lấy từ GITHUB_API_URL
):
    """Posts a comment to the specified Pull Request."""
    if not all([repo_full_name, pr_number > 0, comment_body, github_token, github_api_url]):
        logger.warning("Missing required information to post PR comment (repo, PR number, body, token, or API URL). Skipping.")
        return

    # Đảm bảo GITHUB_API_URL không có dấu / ở cuối nếu nó được cung cấp
    api_url_base = github_api_url.rstrip('/')
    comments_api_url = f"{api_url_base}/repos/{repo_full_name}/issues/{pr_number}/comments"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28" 
    }
    payload = {"body": comment_body}

    logger.info(f"Attempting to post comment to PR #{pr_number} in repo {repo_full_name} via {comments_api_url}.")
    try:
        response = requests.post(comments_api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status() 
        logger.info(f"Successfully posted comment to PR #{pr_number}. Comment ID: {response.json().get('id')}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to post PR comment to {comments_api_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}, Response body: {e.response.text[:500]}...") # Truncate body
    except Exception as e:
        logger.error(f"An unexpected error occurred while posting PR comment: {e}", exc_info=True)


def main():
    logger.info("NovaGuard AI Action started.")
    final_report_generated = False
    final_sarif_report_object: Optional[Dict[str, Any]] = None
    final_error_messages: List[str] = []
    final_summary_text: str = "NovaGuard AI review did not complete fully."


    try:
        # 1. Đọc inputs
        github_token = get_env_input("github_token", required=True)
        ollama_base_url = get_env_input("ollama_base_url", required=True, default="http://localhost:11434")
        project_config_path_str = get_env_input("project_config_path", required=False)
        sarif_output_filename = get_env_input("sarif_output_file", required=False, default="novaguard-report.sarif")
        fail_on_severity_str = get_env_input("fail_on_severity", required=False, default="none").lower()

        # 2. Lấy ngữ cảnh GitHub
        github_event_path_str = os.environ.get("GITHUB_EVENT_PATH")
        github_repository = os.environ.get("GITHUB_REPOSITORY") # VD: "owner/repo"
        github_workspace_str = os.environ.get("GITHUB_WORKSPACE")
        github_sha = os.environ.get("GITHUB_SHA") # SHA của commit hiện tại (HEAD)
        github_base_ref_name = os.environ.get("GITHUB_BASE_REF") # Tên nhánh base (VD: "main")
        github_head_ref_name = os.environ.get("GITHUB_HEAD_REF") # Tên nhánh head (VD: "feature-branch")
        github_event_name = os.environ.get("GITHUB_EVENT_NAME")
        github_api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
        github_server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")


        if not all([github_event_path_str, github_repository, github_workspace_str, github_sha]):
            raise ValueError("Missing critical GitHub environment variables (EVENT_PATH, REPOSITORY, WORKSPACE, SHA).")
        
        workspace_path = Path(github_workspace_str).resolve() # type: ignore
        # Mặc định config của action nằm trong image tại /app/config
        default_config_dir = Path("/app/config").resolve() 

        github_event_payload: Dict[str, Any] = {}
        try:
            github_event_payload = json.loads(Path(github_event_path_str).read_text(encoding='utf-8')) # type: ignore
            logger.info(f"GitHub event payload loaded for event: {github_event_name}")
        except Exception as e:
            logger.warning(f"Could not load GitHub event payload from {github_event_path_str}: {e}")
            # Có thể không phải là lỗi nghiêm trọng nếu không cần payload cho event hiện tại

        # Xác định base SHA và PR number
        github_head_sha_to_diff = github_sha # SHA để diff *tới*
        github_base_sha_to_diff: Optional[str] = None
        pr_number_for_comment: Optional[int] = None

        if github_event_name == "pull_request":
            pr_data = github_event_payload.get("pull_request", {})
            github_base_sha_to_diff = pr_data.get("base", {}).get("sha")
            pr_number_for_comment = pr_data.get("number")
            if not github_base_sha_to_diff:
                logger.warning(f"Base SHA for PR not found in event payload. GITHUB_BASE_REF ('{github_base_ref_name}') might be used by git diff if it resolves to a commit, but this is less reliable.")
                #  Trong trường hợp này, get_changed_files có thể sẽ fail nếu base_ref_name không rõ ràng.
        elif github_event_name == "push":
            github_base_sha_to_diff = github_event_payload.get("before")
            logger.info(f"Push event. Using 'before' SHA as base for diff: {github_base_sha_to_diff}")
        else:
            logger.warning(f"Event type '{github_event_name}' might not provide a clear base for diffing. Changed files list may be empty or inaccurate.")
        
        pr_url = github_event_payload.get("pull_request", {}).get("html_url")
        pr_title = github_event_payload.get("pull_request", {}).get("title")
        pr_body = github_event_payload.get("pull_request", {}).get("body")
        pr_diff_url = github_event_payload.get("pull_request", {}).get("diff_url")

        # 3. Tải Cấu hình
        config_obj = load_config(
            default_config_dir=default_config_dir,
            project_config_dir_str=project_config_path_str, # Có thể là None
            ollama_base_url=str(ollama_base_url),
            workspace_path=workspace_path
        )

        # 4. Lấy Code Changes
        changed_files: List[ChangedFile] = []
        if github_base_sha_to_diff and github_head_sha_to_diff:
            changed_files = get_changed_files(workspace_path, github_head_sha_to_diff, github_base_sha_to_diff)
        else:
            logger.warning("Base SHA or Head SHA for diffing is unavailable. No files will be analyzed for changes.")
            final_error_messages.append("Could not determine base and head commits for diffing. Analysis skipped.")


        # 5. Khởi tạo Orchestrator
        logger.info("Initializing review orchestrator graph...")
        orchestrator_app = get_compiled_graph(app_config=config_obj)

        # 6. Chuẩn bị Input cho Graph
        logger.info("Preparing initial input for the graph...")
        shared_context_instance = SharedReviewContext(
            repository_name=str(github_repository),
            repo_local_path=workspace_path,
            sha=str(github_head_sha_to_diff),
            pr_url=pr_url, pr_title=pr_title, pr_body=pr_body,
            pr_diff_url=pr_diff_url, pr_number=pr_number_for_comment,
            base_ref=github_base_ref_name, head_ref=github_head_ref_name,
            github_event_name=github_event_name,
            github_event_payload=github_event_payload,
            config_obj=config_obj
        )
        initial_graph_input: Dict[str, Any] = {
            "shared_context": shared_context_instance,
            "files_to_review": changed_files,
            "tier1_tool_results": {}, "agent_findings": [],
            "error_messages": final_error_messages, # Truyền lỗi đã có từ trước (nếu có)
            "final_sarif_report": None,
        }
        logger.info(f"Initial graph input prepared with {len(changed_files)} files for review.")

        # 7. Chạy Orchestrator Graph
        logger.info("Invoking the review orchestrator graph...")
        final_state_from_graph: Optional[GraphState] = orchestrator_app.invoke(initial_graph_input) # type: ignore
        
        if final_state_from_graph:
            final_error_messages.extend(err for err in final_state_from_graph.get("error_messages", []) if err not in final_error_messages)
            final_sarif_report_object = final_state_from_graph.get("final_sarif_report")
        
        if final_error_messages: # Kiểm tra lại final_error_messages sau khi graph chạy
            logger.warning("Graph execution completed with the following errors/warnings:")
            for err_msg in final_error_messages: logger.warning(f"- {err_msg}")
        
        if not final_sarif_report_object:
            logger.error("Graph execution failed to produce a final SARIF report in the state.")
            raise RuntimeError("SARIF report generation failed within the graph.")

        # 8. Xử lý Kết quả
        logger.info("Processing final state and saving SARIF report...")
        # sarif_output_filename đã được get_env_input xử lý default
        sarif_report_path = (workspace_path / sarif_output_filename).resolve() # type: ignore
        sarif_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sarif_report_path, "w", encoding="utf-8") as f:
            json.dump(final_sarif_report_object, f, indent=2)
        logger.info(f"Final SARIF report saved to {sarif_report_path}")
        final_report_generated = True

        # 9. Set Action Outputs
        relative_sarif_path_str = str(sarif_report_path.relative_to(workspace_path))
        set_action_output_env_file("sarif_file_path", relative_sarif_path_str)

        num_results = 0
        num_errors = 0
        num_warnings = 0
        num_notes = 0
        if final_sarif_report_object and "runs" in final_sarif_report_object and final_sarif_report_object["runs"]:
            run_results = final_sarif_report_object["runs"][0].get("results", [])
            num_results = len(run_results)
            num_errors = sum(1 for r in run_results if r.get("level") == "error")
            num_warnings = sum(1 for r in run_results if r.get("level") == "warning")
            num_notes = sum(1 for r in run_results if r.get("level") == "note")
            
        final_summary_text = f"NovaGuard AI Review: {num_errors} error(s), {num_warnings} warning(s), {num_notes} note(s) found ({num_results} total findings)."
        if final_error_messages: 
            final_summary_text += f" Operational warnings/errors: {len(final_error_messages)}."
        
        set_action_output_env_file("report_summary_text", final_summary_text)
        logger.info(final_summary_text)

        # 10. Post PR Comment
        if github_event_name == "pull_request" and pr_number_for_comment and github_repository and github_token:
            comment_header = f"### NovaGuard AI Review Summary 🛡️ ({shared_context_instance.sha[:7]})"
            comment_body_content = f"{final_summary_text}\n\n"
            
            code_scanning_link = f"{github_server_url}/{github_repository}/security/code-scanning?query=pr%3A{pr_number_for_comment}+ref%3A{github_head_ref_name}+commit%3A{shared_context_instance.sha}"
            comment_body_content += f"[View full details in Code Scanning Tab]({code_scanning_link})\n"

            if final_error_messages:
                comment_body_content += "\n**Operational Issues Encountered:**\n"
                for err_item in final_error_messages[:3]: 
                    comment_body_content += f"- `{err_item[:200]}`\n" 
                if len(final_error_messages) > 3:
                    comment_body_content += "- ... and more (check Action logs for details).\n"
            
            full_comment = f"{comment_header}\n{comment_body_content}"
            max_comment_length = 65000 
            if len(full_comment) > max_comment_length:
                full_comment = full_comment[:max_comment_length-100] + "\n... (comment truncated due to length)"

            post_pr_comment(
                repo_full_name=str(github_repository),
                pr_number=pr_number_for_comment,
                comment_body=full_comment,
                github_token=str(github_token),
                github_api_url=str(github_api_url)
            )
        else:
            logger.info("Not a Pull Request event or PR number/repository info missing, skipping PR comment.")
        
        # 11. Kiểm tra `fail_on_severity`
        fail_level_threshold = SEVERITY_LEVELS.get(str(fail_on_severity_str).lower(), 0)
        action_should_fail = False
        if fail_level_threshold > 0 and final_sarif_report_object:
            max_finding_level = 0
            for result in final_sarif_report_object.get("runs", [{}])[0].get("results", []):
                level = result.get("level", "note")
                max_finding_level = max(max_finding_level, SEVERITY_LEVELS.get(level, 0))
            
            if max_finding_level >= fail_level_threshold:
                logger.warning(f"Action configured to fail on severity '{fail_on_severity_str}'. Highest severity found ({max_finding_level}) meets/exceeds threshold. Failing action.")
                action_should_fail = True
        
        # Cân nhắc fail action nếu có lỗi vận hành nghiêm trọng
        # if final_error_messages and not action_should_fail:
        #     logger.warning("Action completed with operational errors. Consider failing based on these.")
        #     # action_should_fail = True # Bỏ comment dòng này nếu muốn fail khi có lỗi vận hành

        logger.info("NovaGuard AI Action finished.")
        if action_should_fail:
            sys.exit(1)
        sys.exit(0)

    except Exception as e:
        logger.error(f"A critical error occurred in the action entrypoint: {e}", exc_info=True)
        
        # Sử dụng final_summary_text đã được khởi tạo hoặc lỗi mặc định
        summary_text_on_error = f"NovaGuard AI Action failed critically: {type(e).__name__} - {str(e)[:200]}"
        if final_summary_text == "NovaGuard AI review did not complete fully.": # Nếu chưa được set bởi logic chính
            set_action_output_env_file("report_summary_text", summary_text_on_error)
        # Nếu final_summary_text đã có giá trị từ trước (ví dụ từ lần thử chạy graph), không ghi đè trừ khi nó rỗng.

        if not final_report_generated:
            try:
                ws_path_str_err = os.environ.get("GITHUB_WORKSPACE", "/github/workspace")
                ws_path_err = Path(ws_path_str_err).resolve() if ws_path_str_err else Path(".").resolve()
                
                sarif_fname_err = os.environ.get("INPUT_SARIF_OUTPUT_FILE")
                if not sarif_fname_err or not isinstance(sarif_fname_err, str):
                    sarif_fname_err = "novaguard-critical-error-report.sarif"
                
                repo_name_err = os.environ.get("GITHUB_REPOSITORY", "unknown/repo")
                sha_val_err = os.environ.get("GITHUB_SHA", "unknown_sha")

                sarif_gen = SarifGenerator(
                    tool_name="NovaGuardAI-Entrypoint", tool_version="critical_error",
                    repo_uri_for_artifacts=f"https://{os.environ.get('GITHUB_SERVER_URL', 'github.com')}/{repo_name_err}", 
                    commit_sha_for_artifacts=sha_val_err,
                    workspace_root_for_relative_paths=ws_path_str_err
                )
                error_summary_for_sarif = f"Action failed critically: {type(e).__name__} - {str(e)}"
                sarif_gen.set_invocation_status(successful=False, error_message=error_summary_for_sarif)
                # Báo lỗi trong file entrypoint này
                # Lấy đường dẫn tương đối của file này bên trong container (nếu có thể)
                try:
                    entrypoint_file_rel_path = str(Path(__file__).relative_to(Path("/app")))
                except ValueError:
                    entrypoint_file_rel_path = str(Path(__file__).name) # Nếu không trong /app (ví dụ test local)

                sarif_gen.add_finding(
                    file_path=entrypoint_file_rel_path, 
                    message_text=error_summary_for_sarif + f"\n\nTraceback:\n{traceback.format_exc()}",
                    rule_id="ENTRYPOINT.CRITICAL_ERROR", level="error", line_start=1 
                )
                error_report_obj = sarif_gen.get_sarif_report()
                
                sarif_report_path_error = (ws_path_err / sarif_fname_err).resolve()
                sarif_report_path_error.parent.mkdir(parents=True, exist_ok=True)
                with open(sarif_report_path_error, "w", encoding="utf-8") as f: json.dump(error_report_obj, f, indent=2)
                logger.info(f"Generated critical error SARIF report at {sarif_report_path_error}")
                
                relative_error_sarif_path_str = str(sarif_report_path_error.relative_to(ws_path_err)) if ws_path_str_err else str(sarif_report_path_error)
                set_action_output_env_file("sarif_file_path", relative_error_sarif_path_str)

            except Exception as sarif_err_final:
                logger.error(f"Failed catastrophically to generate critical error SARIF report: {sarif_err_final}")
                set_action_output_env_file("sarif_file_path", "") # Đảm bảo output rỗng nếu không thể tạo
        sys.exit(1)


if __name__ == "__main__":
    # Thiết lập PYTHONPATH nếu chạy local mà không qua Docker build có sẵn ENV
    # Điều này giúp các import "from src..." hoạt động khi chạy python src/action_entrypoint.py từ thư mục gốc
    if "PYTHONPATH" not in os.environ:
        current_dir = Path(__file__).resolve().parent.parent # Trỏ về thư mục gốc NovaGuard-AI
        os.environ["PYTHONPATH"] = str(current_dir)
        logger.info(f"Running locally, setting PYTHONPATH to: {os.environ['PYTHONPATH']}")
        # Cập nhật sys.path ngay lập tức cho tiến trình hiện tại
        if str(current_dir) not in sys.path:
            sys.path.insert(0, str(current_dir))


    # Mock GITHUB_OUTPUT nếu chạy local và nó không tồn tại
    # Điều này giúp hàm set_action_output_env_file không bị lỗi hoàn toàn
    # và bạn có thể xem output được ghi vào file tạm này.
    if not os.environ.get("GITHUB_OUTPUT") and not os.environ.get("CI"): # CI là biến thường được set bởi GitHub Actions
        temp_output_file = Path("local_github_output.env")
        temp_output_file.touch()
        os.environ["GITHUB_OUTPUT"] = str(temp_output_file.resolve())
        logger.info(f"Running locally, GITHUB_OUTPUT mocked to: {os.environ['GITHUB_OUTPUT']}")
        # Xóa nội dung file output cũ nếu có
        open(os.environ["GITHUB_OUTPUT"], 'w').close()


    # Mock các biến môi trường GitHub khác nếu cần thiết cho test local
    # (đã được thực hiện bởi run_local.sh, nhưng đây là fallback nếu chạy file này trực tiếp)
    if not os.environ.get("GITHUB_WORKSPACE"):
        os.environ["GITHUB_WORKSPACE"] = str(Path(".").resolve() / "temp_workspace_local_run")
        Path(os.environ["GITHUB_WORKSPACE"]).mkdir(parents=True, exist_ok=True)
        logger.info(f"Mocking GITHUB_WORKSPACE to {os.environ['GITHUB_WORKSPACE']}")
    if not os.environ.get("GITHUB_REPOSITORY"):
        os.environ["GITHUB_REPOSITORY"] = "localuser/localrepo"
    if not os.environ.get("GITHUB_SHA"):
        os.environ["GITHUB_SHA"] = "fakelocalsha"
    if not os.environ.get("GITHUB_EVENT_NAME"):
        os.environ["GITHUB_EVENT_NAME"] = "local_manual_run" # Để không post comment
    if not os.environ.get("INPUT_GITHUB_TOKEN"): # Đảm bảo có token dummy
        os.environ["INPUT_GITHUB_TOKEN"] = "dummy_local_token_for_entrypoint"


    main()