# NOVAGUARD-AI/src/action_entrypoint.py

import os
import sys
import json
import logging
import subprocess
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Real Imports ---
from .core.config_loader import load_config, Config
from .core.sarif_generator import SarifGenerator # Cần thiết cho việc tạo report lỗi nếu graph không chạy được
from .core.shared_context import SharedReviewContext, ChangedFile
from .orchestrator.graph_definition import get_compiled_graph
from .orchestrator.state import GraphState # For type hinting final_state

# Cấu hình logging cơ bản
logging.basicConfig(
    level=logging.INFO, # Change to DEBUG for more verbose logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout # Log ra stdout để GitHub Actions có thể bắt được
)
logger = logging.getLogger("NovaGuardAI_Entrypoint")

# Định nghĩa các mức độ nghiêm trọng cho SARIF và so sánh
SEVERITY_LEVELS = {"error": 3, "warning": 2, "note": 1, "none": 0}

def get_env_input(name: str, required: bool = True, default: Optional[str] = None) -> Optional[str]:
    """Lấy input từ biến môi trường."""
    env_var_name = f"INPUT_{name.upper()}"
    value = os.environ.get(env_var_name)
    if value is None or value == "":
        if default is not None:
            logger.info(f"Input '{name}' not set, using default: '{default}'")
            return default
        if required:
            logger.error(f"Required input '{name}' (env var {env_var_name}) is missing.")
            sys.exit(1) # Critical failure
        return None
    return value

def set_action_output(name: str, value: str):
    """Set output cho GitHub Action."""
    # Escape special characters for GitHub Actions output
    # see: https://github.com/actions/runner/issues/1178 and related issues
    value = value.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    logger.info(f"Setting output '{name}' to '{value}'")
    print(f"::set-output name={name}::{value}")


def get_changed_files(
    workspace_path: Path, 
    head_sha: str, # Sử dụng head_sha (GITHUB_SHA)
    base_sha: Optional[str] # Lấy từ event payload
) -> List[ChangedFile]:
    """
    Lấy danh sách file thay đổi giữa base_sha và head_sha,
    và đọc nội dung của chúng, returning List[ChangedFile].
    """
    changed_files_data: List[ChangedFile] = []
    
    if not base_sha:
        logger.error("Base commit SHA is missing. Cannot perform git diff.")
        # Consider this a critical failure for actions triggered by events that should have a base SHA (like PRs)
        raise ValueError("Base commit SHA is required for diffing but was not found.")
        # return [] # Or return empty if non-critical

    try:
        if not (workspace_path / ".git").is_dir():
            # This might happen if checkout action failed or depth was too shallow
            logger.error(f"Directory {workspace_path} does not appear to contain a valid .git directory.")
            raise FileNotFoundError("Git repository not found in workspace.")
            # return []
        
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", str(workspace_path)], check=True, cwd=workspace_path)
        logger.info(f"Set safe.directory for {workspace_path} inside container.")
        # <<< SỬA LỆNH DIFF: Dùng SHAs >>>
        # Đảm bảo các commit này tồn tại trong lịch sử local (fetch-depth=0 quan trọng)
        diff_command = ["git", "diff", "--name-only", base_sha, head_sha]
        logger.info(f"Running git diff command using SHAs: {' '.join(diff_command)}")
        result = subprocess.run(diff_command, capture_output=True, text=True, cwd=workspace_path, check=False)

        if result.returncode != 0:
            logger.error(f"Git diff command failed (code {result.returncode}) when diffing {base_sha}..{head_sha}.")
            logger.error(f"Stderr: {result.stderr.strip()}")
            logger.error("Ensure both commit SHAs exist in the local repository history (fetch-depth: 0 might be needed in checkout).")
            # Raise lỗi để dừng xử lý nếu không diff được
            raise RuntimeError(f"git diff failed between {base_sha} and {head_sha}")
            
        changed_file_paths_str = result.stdout.strip()
        if not changed_file_paths_str:
            logger.info(f"Git diff between {base_sha} and {head_sha} returned no changed file paths.")
            return [] # No changes found is a valid outcome
            
        changed_file_paths = changed_file_paths_str.split('\n')
        logger.info(f"Changed files found between SHAs: {changed_file_paths}")

        for file_path_str in changed_file_paths:
            if not file_path_str: continue # Skip empty lines if any
            
            # Construct absolute path for reading, store relative path in ChangedFile
            full_file_path = (workspace_path / file_path_str).resolve()

            # Check if path exists and is a file before reading
            # This handles cases where the diff lists a deleted file
            if full_file_path.is_file(): 
                try:
                    content = full_file_path.read_text(encoding='utf-8')
                    # Store the path relative to workspace_path
                    relative_path_str = str(Path(file_path_str)) # Ensure it's string
                    changed_files_data.append(ChangedFile(path=relative_path_str, content=content))
                    logger.debug(f"Read content for changed file: {relative_path_str}")
                except Exception as e:
                    logger.warning(f"Could not read file {full_file_path} (relative: {file_path_str}): {e}")
            elif full_file_path.exists():
                 logger.info(f"Changed path '{file_path_str}' exists but is not a file (e.g., a directory), skipping.")
            else:
                logger.info(f"Changed path '{file_path_str}' not found (likely deleted), skipping content read.")
                # Optional: You could create a ChangedFile entry indicating deletion if needed later
                # changed_files_data.append(ChangedFile(path=file_path_str, content="", is_deleted=True)) # Needs is_deleted field in model

    except FileNotFoundError:
        logger.error("Git command not found. Ensure git is installed in the Docker image.")
        raise # Critical failure
    except Exception as e:
        logger.error(f"Error getting changed files using SHAs: {e}", exc_info=True)
        raise # Raise other critical errors during diff process

    logger.info(f"Found {len(changed_files_data)} readable changed files between specified SHAs.")
    return changed_files_data


def main():
    logger.info("NovaGuard AI Action started (Real Version).")
    final_report_generated = False # Flag to check if SARIF was generated

    try:
        # 1. Đọc các input từ biến môi trường
        github_token = get_env_input("github_token", required=True)
        ollama_base_url = get_env_input("ollama_base_url", required=True, default="http://localhost:11434")
        project_config_path_str = get_env_input("project_config_path", required=False)
        sarif_output_filename = get_env_input("sarif_output_file", required=False, default="novaguard-report.sarif")
        fail_on_severity_str = get_env_input("fail_on_severity", required=False, default="none").lower()

        # 2. Lấy thông tin ngữ cảnh GitHub
        github_event_path_str = os.environ.get("GITHUB_EVENT_PATH")
        github_repository = os.environ.get("GITHUB_REPOSITORY")
        github_workspace_str = os.environ.get("GITHUB_WORKSPACE")
        github_sha = os.environ.get("GITHUB_SHA") # This is the HEAD SHA for PRs/pushes
        github_base_ref = os.environ.get("GITHUB_BASE_REF") # Branch/tag name
        github_head_ref = os.environ.get("GITHUB_HEAD_REF") # Branch name (for PRs)
        github_event_name = os.environ.get("GITHUB_EVENT_NAME")

        if not all([github_event_path_str, github_repository, github_workspace_str, github_sha]):
            logger.error("Missing critical GitHub environment variables.")
            sys.exit(1)
        
        workspace_path = Path(github_workspace_str).resolve()
        default_config_dir = Path("/app/config").resolve()

        github_event_payload: Dict[str, Any] = {}
        try:
            github_event_payload = json.loads(Path(github_event_path_str).read_text(encoding='utf-8'))
            logger.info(f"GitHub event payload loaded for event: {github_event_name}")
        except Exception as e:
            logger.warning(f"Could not load GitHub event payload from {github_event_path_str}: {e}")

        # <<< Lấy Base và Head SHAs >>>
        github_head_sha = github_sha # GITHUB_SHA is the commit SHA being checked out
        github_base_sha = None
        if github_event_name == "pull_request":
             github_base_sha = github_event_payload.get("pull_request", {}).get("base", {}).get("sha")
             # Fallback to base_ref if base SHA isn't in payload (less reliable)
             if not github_base_sha and github_base_ref:
                  logger.warning("Base SHA not found in PR payload, attempting to use base ref name.")
                  # Note: Using ref name directly in diff can be problematic if history is complex
                  # For local tests, ensure SHAs are set correctly in event.json
                  # github_base_sha = github_base_ref # Less reliable than SHA
        elif github_event_name == "push":
             # For pushes, diff against the 'before' commit
             github_base_sha = github_event_payload.get("before")
        else:
             logger.warning(f"Unsupported event type '{github_event_name}' for determining base SHA for diffing.")
             # Cannot reliably determine base SHA, diff will likely fail or be skipped.

        # Lấy các thông tin PR khác từ payload
        pr_url = github_event_payload.get("pull_request", {}).get("html_url")
        pr_title = github_event_payload.get("pull_request", {}).get("title")
        pr_body = github_event_payload.get("pull_request", {}).get("body")
        pr_diff_url = github_event_payload.get("pull_request", {}).get("diff_url")
        pr_number = github_event_payload.get("pull_request", {}).get("number")


        # 3. Tải Cấu hình
        config_obj = load_config(
            default_config_dir=default_config_dir,
            project_config_dir_str=project_config_path_str,
            ollama_base_url=ollama_base_url,
            workspace_path=workspace_path
        )

        # 4. Lấy Code Changes sử dụng SHAs
        changed_files: List[ChangedFile] = []
        if github_base_sha and github_head_sha:
            logger.info(f"Attempting to get changed files between base SHA: {github_base_sha[:8]} and head SHA: {github_head_sha[:8]}")
            try:
                changed_files = get_changed_files(workspace_path, github_head_sha, github_base_sha) 
            except Exception as e: 
                logger.error(f"Failed to get changed files using SHAs: {e}", exc_info=True)
                # Critical error, generate SARIF indicating failure and exit
                raise # Re-raise to be caught by the top-level handler
        else:
            logger.warning("Base SHA or Head SHA is missing/unavailable for diff. Proceeding without file analysis.")
            # changed_files remains empty, graph's conditional logic will handle it.

        # 5. Khởi tạo Orchestrator Graph
        logger.info("Initializing review orchestrator graph...")
        orchestrator_app = get_compiled_graph(app_config=config_obj)

        # 6. Chuẩn bị Input cho Graph
        logger.info("Preparing initial input for the graph...")
        shared_context_instance = SharedReviewContext(
            repository_name=str(github_repository),
            repo_local_path=workspace_path,
            sha=str(github_head_sha), # Use the determined head SHA
            pr_url=pr_url, pr_title=pr_title, pr_body=pr_body,
            pr_diff_url=pr_diff_url, pr_number=pr_number,
            base_ref=github_base_ref, # Store ref names if available
            head_ref=github_head_ref,
            github_event_name=github_event_name,
            github_event_payload=github_event_payload,
            config_obj=config_obj # Pass the loaded config object
        )

        initial_graph_input: Dict[str, Any] = {
            "shared_context": shared_context_instance,
            "files_to_review": changed_files, # List[ChangedFile]
            "tier1_tool_results": {}, "agent_findings": [],
            "error_messages": [], "final_sarif_report": None,
        }
        logger.info(f"Initial graph input prepared with {len(changed_files)} files for review.")

        # 7. Chạy Orchestrator Graph
        logger.info("Invoking the review orchestrator graph...")
        final_state: Optional[GraphState] = None
        
        # Invoke the graph (handle potential exceptions)
        final_state = orchestrator_app.invoke(initial_graph_input)
        
        if final_state and final_state.get("error_messages"):
            logger.warning("Graph execution completed with the following errors/warnings:")
            for err_msg in final_state["error_messages"]: logger.warning(f"- {err_msg}")
        
        if not final_state or not final_state.get("final_sarif_report"):
            # This case should ideally not happen if generate_sarif node always runs
            logger.error("Graph execution failed to produce a final SARIF report in the state.")
            raise RuntimeError("SARIF report generation failed within the graph.")

        # 8. Xử lý Kết quả (Lấy SARIF report từ state và lưu file)
        logger.info("Processing final state and saving SARIF report...")
        sarif_report_object: Dict[str, Any] = final_state["final_sarif_report"]
        
        # Xác định đường dẫn lưu file SARIF tuyệt đối
        sarif_report_path = (workspace_path / sarif_output_filename).resolve()
        
        # Ghi file SARIF
        sarif_report_path.parent.mkdir(parents=True, exist_ok=True) # Đảm bảo thư mục tồn tại
        with open(sarif_report_path, "w", encoding="utf-8") as f:
            json.dump(sarif_report_object, f, indent=2)
        logger.info(f"Final SARIF report saved to {sarif_report_path}")
        final_report_generated = True # Đánh dấu đã tạo thành công


        # 9. Set Action Outputs
        relative_sarif_path = str(sarif_report_path.relative_to(workspace_path))
        set_action_output("sarif_file_path", relative_sarif_path)

        num_errors = sum(1 for r in sarif_report_object.get("runs", [{}])[0].get("results", []) if r.get("level") == "error")
        num_warnings = sum(1 for r in sarif_report_object.get("runs", [{}])[0].get("results", []) if r.get("level") == "warning")
        num_notes = sum(1 for r in sarif_report_object.get("runs", [{}])[0].get("results", []) if r.get("level") == "note")
        summary_text = f"NovaGuard AI Review: {num_errors} error(s), {num_warnings} warning(s), {num_notes} note(s) found."
        if final_state.get("error_messages"): summary_text += f" ({len(final_state['error_messages'])} operational warnings/errors occurred)."
        set_action_output("report_summary_text", summary_text)
        logger.info(summary_text)

        # 10. Kiểm tra `fail_on_severity`
        fail_level_threshold = SEVERITY_LEVELS.get(fail_on_severity_str, 0)
        action_should_fail = False
        if fail_level_threshold > 0:
            max_finding_level = 0
            for result in sarif_report_object.get("runs", [{}])[0].get("results", []):
                level = result.get("level", "note")
                max_finding_level = max(max_finding_level, SEVERITY_LEVELS.get(level, 0))
            
            if max_finding_level >= fail_level_threshold:
                logger.warning(f"Action configured to fail on severity '{fail_on_severity_str}'. Highest severity found ({max_finding_level}) meets threshold. Failing action.")
                action_should_fail = True
        
        # Optional: Also fail if critical errors occurred during execution?
        # if final_state.get("error_messages"):
        #     action_should_fail = True
        #     logger.warning("Action failed due to operational errors during execution.")


        logger.info("NovaGuard AI Action finished successfully.")
        if action_should_fail:
            sys.exit(1)
        sys.exit(0)

    except Exception as e:
        # --- Top-level Exception Handling ---
        logger.error(f"A critical error occurred in the action entrypoint: {e}", exc_info=True)
        
        # Attempt to generate a minimal SARIF report indicating the failure
        if not final_report_generated:
            try:
                # Try to get workspace path again, default if error happened early
                ws_path = Path(os.environ.get("GITHUB_WORKSPACE", "/github/workspace")).resolve()
                sarif_filename = os.environ.get("INPUT_SARIF_OUTPUT_FILE", "novaguard-error-report.sarif")
                repo_name = os.environ.get("GITHUB_REPOSITORY", "unknown/repo")
                sha = os.environ.get("GITHUB_SHA", "unknown")

                sarif_gen = SarifGenerator(
                    tool_name="NovaGuardAI-Entrypoint", tool_version="error",
                    repo_uri_for_artifacts=f"https://github.com/{repo_name}", commit_sha_for_artifacts=sha,
                    workspace_root_for_relative_paths=ws_path
                )
                error_summary = f"Action failed critically: {type(e).__name__} - {str(e)}"
                sarif_gen.set_invocation_status(successful=False, error_message=error_summary)
                # Add a generic error result
                sarif_gen.add_finding(
                    file_path=__file__, # Report error in this file
                    message_text=error_summary + f"\n\nTraceback:\n{traceback.format_exc()}",
                    rule_id="ENTRYPOINT.CRITICAL_ERROR",
                    level="error",
                    line_start=1 # Placeholder line
                )
                error_report = sarif_gen.get_sarif_report()
                sarif_report_path = (ws_path / sarif_filename).resolve()
                sarif_report_path.parent.mkdir(parents=True, exist_ok=True)
                with open(sarif_report_path, "w", encoding="utf-8") as f: json.dump(error_report, f, indent=2)
                logger.info(f"Generated error SARIF report at {sarif_report_path}")
                set_action_output("sarif_file_path", str(sarif_report_path.relative_to(ws_path)))
            except Exception as sarif_err:
                logger.error(f"Failed even to generate error SARIF report: {sarif_err}")
                set_action_output("sarif_file_path", "") # Set empty if cannot create error report

        set_action_output("report_summary_text", f"Action failed critically: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()