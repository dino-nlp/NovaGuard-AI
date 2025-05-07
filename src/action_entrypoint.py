# NOVAGUARD-AI/src/action_entrypoint.py

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Real Imports ---
from .core.config_loader import load_config, Config
from .core.sarif_generator import SarifGenerator # Only for "no files" case if graph doesn't run
from .core.shared_context import SharedReviewContext, ChangedFile
from .orchestrator.graph_definition import get_compiled_graph
from .orchestrator.state import GraphState # For type hinting final_state


# Cấu hình logging cơ bản
logging.basicConfig(
    level=logging.INFO, # Change to DEBUG for more verbose logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
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
    logger.info(f"Setting output '{name}' to '{value}'")
    print(f"::set-output name={name}::{value}")

def get_changed_files(workspace_path: Path, base_ref: str, head_ref: str) -> List[ChangedFile]:
    """
    Lấy danh sách các file đã thay đổi giữa base_ref và head_ref,
    và đọc nội dung của chúng, returning List[ChangedFile].
    """
    changed_files_data: List[ChangedFile] = []
    try:
        if not (workspace_path / ".git").is_dir():
            logger.warning(f"Directory {workspace_path} does not appear to be a git repository. Cannot get diff.")
            return []

        # Using origin/ prefix assumes remotes are set up as 'origin' and refs are fetched.
        # fetch-depth: 0 in checkout action is important.
        diff_command = ["git", "diff", "--name-only", f"origin/{base_ref}", f"origin/{head_ref}"]
        logger.info(f"Running git diff command: {' '.join(diff_command)}")
        result = subprocess.run(diff_command, capture_output=True, text=True, cwd=workspace_path, check=False)

        if result.returncode != 0:
            logger.warning(f"Git diff with 'origin/' prefix failed (code {result.returncode}). Stderr: {result.stderr.strip()}. Retrying without 'origin/'.")
            diff_command_local = ["git", "diff", "--name-only", base_ref, head_ref]
            logger.info(f"Retrying git diff command locally: {' '.join(diff_command_local)}")
            result = subprocess.run(diff_command_local, capture_output=True, text=True, cwd=workspace_path, check=False)
            if result.returncode != 0:
                logger.error(f"Local git diff command also failed (code {result.returncode}). Stderr: {result.stderr.strip()}")
                return []

        changed_file_paths_str = result.stdout.strip()
        if not changed_file_paths_str:
            logger.info("Git diff returned no changed file paths.")
            return []
            
        changed_file_paths = changed_file_paths_str.split('\n')
        logger.info(f"Changed files (raw list from git): {changed_file_paths}")

        for file_path_str in changed_file_paths:
            if not file_path_str: continue
            full_file_path = workspace_path / file_path_str
            if full_file_path.is_file():
                try:
                    content = full_file_path.read_text(encoding='utf-8')
                    # Create ChangedFile instance. Language and diff_hunks are optional.
                    # Language will be guessed in prepare_review_files_node.
                    changed_files_data.append(ChangedFile(path=file_path_str, content=content))
                    logger.debug(f"Read content for changed file: {file_path_str}")
                except Exception as e:
                    logger.warning(f"Could not read file {full_file_path}: {e}")
            else:
                logger.info(f"Changed path '{file_path_str}' is not a file or does not exist, skipping.")
    except FileNotFoundError:
        logger.error("Git command not found. Ensure git is installed in the Docker image.")
        # This is a critical failure for diffing.
        raise
    except Exception as e:
        logger.error(f"Error getting changed files: {e}", exc_info=True)
        # Depending on severity, might want to raise or return empty
        raise

    if not changed_files_data:
        logger.info("No changed files found or could be read between the specified refs.")
    return changed_files_data

def main():
    logger.info("NovaGuard AI Action started (Real Version).")

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
    github_sha = os.environ.get("GITHUB_SHA")
    github_base_ref = os.environ.get("GITHUB_BASE_REF")
    github_head_ref = os.environ.get("GITHUB_HEAD_REF")
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
        logger.warning(f"Could not load GitHub event payload: {e}")

    pr_url = github_event_payload.get("pull_request", {}).get("html_url")
    pr_title = github_event_payload.get("pull_request", {}).get("title")
    pr_body = github_event_payload.get("pull_request", {}).get("body")
    pr_diff_url = github_event_payload.get("pull_request", {}).get("diff_url")
    pr_number = github_event_payload.get("pull_request", {}).get("number")


    if not github_base_ref or not github_head_ref:
        if github_event_name == "pull_request":
            github_base_ref = github_event_payload.get("pull_request", {}).get("base", {}).get("ref")
            github_head_ref = github_event_payload.get("pull_request", {}).get("head", {}).get("ref")
            if not github_base_ref or not github_head_ref:
                logger.error("Could not determine base and head refs from PR payload for a pull_request event.")
                sys.exit(1)
            logger.info(f"Retrieved base_ref: {github_base_ref}, head_ref: {github_head_ref} from PR payload.")
        else:
            logger.warning("GITHUB_BASE_REF or GITHUB_HEAD_REF not set and not a pull_request event. Diff analysis will be skipped.")
            # For non-PR events, changed_files will be empty. Graph will handle this.
    
    # 3. Tải Cấu hình (Real ConfigLoader)
    config_obj = load_config(
        default_config_dir=default_config_dir,
        project_config_dir_str=project_config_path_str,
        ollama_base_url=ollama_base_url,
        workspace_path=workspace_path # Needed for resolving project_config_path
    )

    # 4. Lấy Code Changes
    changed_files: List[ChangedFile] = []
    if github_base_ref and github_head_ref:
        logger.info(f"Attempting to get changed files between base: {github_base_ref} and head: {github_head_ref}")
        try:
            changed_files = get_changed_files(workspace_path, github_base_ref, github_head_ref)
        except Exception as e: # Catch errors from get_changed_files if it raises them
            logger.error(f"Failed to get changed files, cannot proceed with review: {e}", exc_info=True)
            # Create a SARIF report indicating this failure
            sarif_gen = SarifGenerator(
                tool_name="NovaGuardAI-Entrypoint", tool_version="0.1.0", # TODO: Get version properly
                repo_uri_for_artifacts=f"https://github.com/{github_repository}",
                commit_sha_for_artifacts=github_sha,
                workspace_root_for_relative_paths=workspace_path
            )
            sarif_gen.set_invocation_status(successful=False, error_message=f"Critical error getting changed files: {e}")
            error_report = sarif_gen.get_sarif_report()
            sarif_report_path = workspace_path / sarif_output_filename
            try:
                sarif_report_path.parent.mkdir(parents=True, exist_ok=True)
                with open(sarif_report_path, "w", encoding="utf-8") as f: json.dump(error_report, f, indent=2)
                set_action_output("sarif_file_path", str(sarif_report_path.relative_to(workspace_path)))
            except Exception as write_e: logger.error(f"Failed to write error SARIF report: {write_e}")
            set_action_output("report_summary_text", f"Action failed: Error getting changed files.")
            sys.exit(1) # Exit due to critical error
    else:
        logger.info("Skipping get_changed_files as base_ref or head_ref is not available.")
        # changed_files will remain empty. The graph's conditional logic will handle this.

    # 5. Khởi tạo Orchestrator (Real get_compiled_graph)
    logger.info("Initializing review orchestrator graph...")
    orchestrator_app = get_compiled_graph(app_config=config_obj)

    # 6. Chuẩn bị Input cho Graph
    logger.info("Preparing initial input for the graph...")
    shared_context_instance = SharedReviewContext(
        repository_name=str(github_repository), # Ensure it's a string
        repo_local_path=workspace_path,
        sha=str(github_sha),
        pr_url=pr_url,
        pr_title=pr_title,
        pr_body=pr_body,
        pr_diff_url=pr_diff_url,
        pr_number=pr_number,
        base_ref=github_base_ref,
        head_ref=github_head_ref,
        github_event_name=github_event_name,
        github_event_payload=github_event_payload,
        config_obj=config_obj # Pass the loaded config object
    )

    initial_graph_input: Dict[str, Any] = {
        "shared_context": shared_context_instance,
        "files_to_review": changed_files, # Directly pass the List[ChangedFile]
        # Initial empty states for accumulators, nodes will manage them
        "tier1_tool_results": {},
        "agent_findings": [],
        "error_messages": [],
        "final_sarif_report": None # Ensure all keys from GraphState are present if graph expects them
    }
    logger.info(f"Initial graph input prepared with {len(changed_files)} files for review.")

    # 7. Chạy Orchestrator Graph
    logger.info("Invoking the review orchestrator graph...")
    final_state: Optional[GraphState] = None
    try:
        # Pass config_obj via RunnableConfig if nodes are adapted to use it
        # For now, nodes access config_obj via state['shared_context'].config_obj
        final_state = orchestrator_app.invoke(initial_graph_input)
        
        if final_state and final_state.get("error_messages"):
            logger.warning("Graph execution completed with the following errors/warnings:")
            for err_msg in final_state["error_messages"]:
                logger.warning(f"- {err_msg}")
    except Exception as e:
        logger.error(f"An unhandled exception occurred during graph invocation: {e}", exc_info=True)
        # Create a SARIF report indicating this failure if possible
        # This is a critical failure of the graph itself.
        sarif_gen = SarifGenerator(
            tool_name="NovaGuardAI-Orchestrator", tool_version="0.1.0",
            repo_uri_for_artifacts=f"https://github.com/{github_repository}",
            commit_sha_for_artifacts=github_sha,
            workspace_root_for_relative_paths=workspace_path
        )
        # Try to get any partial state if available, otherwise, just log the main error
        partial_errors = final_state.get("error_messages", []) if final_state else []
        all_errors_str = "\n".join(partial_errors + [f"Graph Invocation Error: {str(e)}"])
        sarif_gen.set_invocation_status(successful=False, error_message=f"Critical error during graph execution: {all_errors_str}")
        error_report = sarif_gen.get_sarif_report()
        sarif_report_path = workspace_path / sarif_output_filename
        try:
            sarif_report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(sarif_report_path, "w", encoding="utf-8") as f: json.dump(error_report, f, indent=2)
            set_action_output("sarif_file_path", str(sarif_report_path.relative_to(workspace_path)))
        except Exception as write_e: logger.error(f"Failed to write graph error SARIF report: {write_e}")
        set_action_output("report_summary_text", f"Action failed: Graph execution error.")
        sys.exit(1)


    if not final_state or not final_state.get("final_sarif_report"):
        logger.error("Graph execution did not produce a final SARIF report in the state.")
        # Handle missing SARIF report, possibly generate a basic error one
        # For now, exit with error, assuming generate_sarif_report_node should always produce something.
        sys.exit(1)

    # 8. Xử lý Kết quả (SARIF report is already generated by a graph node)
    sarif_report_object: Dict[str, Any] = final_state["final_sarif_report"]
    
    sarif_report_path = workspace_path / sarif_output_filename
    try:
        sarif_report_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        with open(sarif_report_path, "w", encoding="utf-8") as f:
            json.dump(sarif_report_object, f, indent=2)
        logger.info(f"Final SARIF report saved to {sarif_report_path}")
    except Exception as e:
        logger.error(f"Failed to write final SARIF report: {e}", exc_info=True)
        sys.exit(1)

    # 9. Set Action Outputs
    relative_sarif_path = str(sarif_report_path.relative_to(workspace_path))
    set_action_output("sarif_file_path", relative_sarif_path)

    # Create tóm tắt text
    num_errors = sum(1 for r in sarif_report_object.get("runs", [{}])[0].get("results", []) if r.get("level") == "error")
    num_warnings = sum(1 for r in sarif_report_object.get("runs", [{}])[0].get("results", []) if r.get("level") == "warning")
    num_notes = sum(1 for r in sarif_report_object.get("runs", [{}])[0].get("results", []) if r.get("level") == "note")
    summary_text = f"NovaGuard AI Review: {num_errors} error(s), {num_warnings} warning(s), {num_notes} note(s) found."
    if final_state.get("error_messages"):
        summary_text += f" ({len(final_state['error_messages'])} operational warnings/errors occurred)."
    set_action_output("report_summary_text", summary_text)
    logger.info(summary_text)

    # 10. Kiểm tra `fail_on_severity`
    fail_level_threshold = SEVERITY_LEVELS.get(fail_on_severity_str, 0)
    action_should_fail = False
    if fail_level_threshold > 0:
        max_finding_level = 0
        for result in sarif_report_object.get("runs", [{}])[0].get("results", []):
            level = result.get("level", "note") # Default to 'note' if level is missing
            max_finding_level = max(max_finding_level, SEVERITY_LEVELS.get(level, 0))
        
        if max_finding_level >= fail_level_threshold:
            logger.warning(
                f"Action configured to fail on severity '{fail_on_severity_str}' (threshold {fail_level_threshold}). "
                f"Highest finding severity value was {max_finding_level}. Action will fail."
            )
            action_should_fail = True

    # Also consider failing if there were critical errors logged in error_messages
    # For instance, if any error_message indicates a tool or agent outright failed.
    # This logic can be refined. For now, only severity of findings.

    logger.info("NovaGuard AI Action finished.")
    if action_should_fail:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit: # Allow sys.exit() to pass through without logging as an "unexpected error"
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred at the top level: {e}", exc_info=True)
        set_action_output("report_summary_text", f"Action failed due to unexpected error: {e}")
        set_action_output("sarif_file_path", "")
        sys.exit(1)