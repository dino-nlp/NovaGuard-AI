# NOVAGUARD-AI/src/orchestrator/nodes.py
import logging
from typing import Dict, List, Any, Optional

from .state import GraphState # Assuming state.py is in the same directory
from ..core.config_loader import Config # For type hinting if passed around
from ..core.tool_runner import ToolRunner, ToolExecutionError
from ..core.sarif_generator import SarifGenerator
from ..core.ollama_client import OllamaClientWrapper
from ..core.prompt_manager import PromptManager
from ..core.shared_context import ChangedFile # For type hinting

# Import stubbed agent classes
from ..agents.style_guardian_agent import StyleGuardianAgent
# Create these stub files similar to StyleGuardianAgent:
from ..agents.bug_hunter_agent import BugHunterAgent # Placeholder
from ..agents.securi_sense_agent import SecuriSenseAgent # Placeholder
from ..agents.opti_tune_agent import OptiTuneAgent # Placeholder
from ..agents.meta_reviewer_agent import MetaReviewerAgent # Placeholder


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
    ext = Path(file_path).suffix.lower()
    return extension_map.get(ext)


# --- Node Functions ---

def prepare_review_files_node(state: GraphState) -> Dict[str, Any]:
    """
    Identifies and prepares files for review from the shared context.
    Currently, it directly uses the changed files provided in shared_context.
    It also attempts to guess the language for each file.
    """
    logger.info("--- Running: Prepare Review Files Node ---")
    shared_ctx = state["shared_context"]
    error_messages = list(state.get("error_messages", [])) # Preserve existing errors

    # changed_files_with_content is already List[ChangedFile] populated by action_entrypoint
    # This list is set in the initial graph input in action_entrypoint.py
    # files_for_review_raw = shared_ctx.changed_files_with_content (this structure is from an older thought)
    
    # In the current setup, 'changed_files_data' from action_entrypoint is directly put
    # into initial_graph_input as "files_to_review" when the mock app is invoked.
    # For the real graph, action_entrypoint will prepare `SharedReviewContext`.
    # This node will extract the files from `shared_context.changed_files_with_content`
    # which is expected to be List[ChangedFile] based on how SharedReviewContext is defined.
    
    # Let's assume shared_context is populated correctly by action_entrypoint and available.
    # The files are already ChangedFile objects. Now, let's enrich them with language.
    
    files_from_context: List[ChangedFile] = state.get("files_to_review", []) # Get from initial state
    if not files_from_context and hasattr(shared_ctx, 'changed_files_with_content'):
        # Fallback or primary way if files_to_review isn't directly in initial state
        # but rather shared_context is fully populated. This depends on how graph is invoked.
        # For now, action_entrypoint mock puts 'files_to_review' directly.
        # Real scenario: shared_ctx.changed_files_with_content would be the source.
        # Let's assume files_to_review is directly populated for now from initial input.
        pass


    updated_files_to_review: List[ChangedFile] = []
    for cf_dict in files_from_context: # If files_from_context is List[Dict] not List[ChangedFile]
        if isinstance(cf_dict, ChangedFile):
            file_obj = cf_dict
        else: # Adapt if it's still a plain dict from earlier mock/entrypoint
            file_obj = ChangedFile(**cf_dict)

        if not file_obj.language: # Guess language if not already set
            file_obj.language = guess_language(file_obj.path)
            if file_obj.language:
                logger.debug(f"Guessed language '{file_obj.language}' for file '{file_obj.path}'")
            else:
                logger.debug(f"Could not guess language for file '{file_obj.path}'")
        updated_files_to_review.append(file_obj)


    logger.info(f"Prepared {len(updated_files_to_review)} files for review.")
    if not updated_files_to_review:
        error_messages.append("No files identified for review in prepare_review_files_node.")
    
    return {"files_to_review": updated_files_to_review, "error_messages": error_messages}


def run_tier1_tools_node(state: GraphState) -> Dict[str, Any]:
    """
    Runs traditional static analysis tools (linters, basic SAST) on the files.
    """
    logger.info("--- Running: Tier 1 Tools Node ---")
    shared_ctx = state["shared_context"]
    files_to_review = state["files_to_review"]
    error_messages = list(state.get("error_messages", []))
    tier1_results: Dict[str, List[Dict[str, Any]]] = {}

    # SIMPLIFICATION: Instantiate Config and ToolRunner here.
    # Ideally, these are initialized once and passed via RunnableConfig or graph context.
    # This requires `default_config_dir` and `workspace_path` to be accessible,
    # e.g., from shared_ctx or if this node is a method of a class holding them.
    # For now, assume we can get necessary info from shared_ctx to init Config.
    # Then init ToolRunner with that config and shared_ctx.repo_local_path.
    
    # This is a placeholder for accessing a central Config object.
    # In a real LangGraph app, `config_obj` would be passed via `RunnableConfig(configurable={...})`
    # or be part of a class that these nodes are methods of.
    # For this standalone node definition, we'll have to assume it's retrieved magically or
    # we make it part of GraphState (which is not ideal for read-only config).
    # Let's mock its retrieval for now or assume it's in shared_ctx.
    # Assume Config is now directly part of SharedReviewContext or passed via state['config']
    
    # This part requires careful thought on how `config_obj` is made available.
    # For now, let's assume `shared_ctx` somehow provides access to the `Config` instance.
    # A pragmatic way is to add 'config_obj: Config' to GraphState, initialized by action_entrypoint.
    # Or, as a temporary hack, re-load it here (NOT RECOMMENDED FOR PRODUCTION).
    # Let's assume a `config_obj` is available in the state for this example.
    # In reality, you'd pass it in when you call the graph: `app.invoke(..., config={"configurable": {"config_obj": my_config}})`
    # and the node would access it via the `config` argument: `def run_tier1_tools_node(state: GraphState, config: RunnableConfig)`
    
    # For now, let's assume `config_obj` is magically available or loaded from shared_ctx.
    # A more realistic approach for standalone nodes without modifying GraphState just for this:
    # tool_runner = ToolRunner(config_obj_from_somewhere, shared_ctx.repo_local_path)

    # Simplified: access config parameters directly from shared_ctx where they might be stored.
    # This is not using the full Config object yet, but illustrates the idea.
    # This is a temporary workaround. We need a proper way to get the Config object.
    
    # Let's assume for this step that the 'action_entrypoint' will initialize
    # the Config, ToolRunner, OllamaClient, PromptManager and pass them in the GraphState
    # or make them accessible through a shared mechanism.
    # For this example, we'll proceed as if `config_obj` exists in `state` or `shared_ctx`.
    #
    # If `state['config']` is not available, this node can't function.
    # This structure assumes `config` is passed through the state or accessible globally.
    # A better way for LangGraph is to use `RunnableConfig`.
    # To proceed, let's assume `config_obj` and `tool_runner_instance` are available via state.
    # This is a simplification for the node definition phase.
    
    config_obj: Optional[Config] = getattr(shared_ctx, 'config_obj', None) # Hypothetical
    if not config_obj:
        error_messages.append("Config object not available in run_tier1_tools_node.")
        logger.error("Config object not available. Cannot run Tier 1 tools.")
        return {"tier1_tool_results": tier1_results, "error_messages": error_messages}

    tool_runner = ToolRunner(config_obj, shared_ctx.repo_local_path)


    for file_obj in files_to_review:
        logger.debug(f"Running Tier 1 tools for file: {file_obj.path} (lang: {file_obj.language})")
        if not file_obj.language:
            logger.debug(f"Skipping Tier 1 tools for {file_obj.path} as language is unknown.")
            continue

        # Example: Run Pylint for Python files
        if file_obj.language == "python":
            tool_cat, tool_k = "linters", "python" # As per tools.yml design
            # Check if this tool is configured
            if config_obj.get_tool_command_template(tool_cat, tool_k):
                try:
                    # `target_file_relative_path` is used by ToolRunner to construct full path with workspace
                    output = tool_runner.run(
                        tool_category=tool_cat,
                        tool_key=tool_k,
                        target_file_relative_path=file_obj.path,
                        expect_json_output=True # Pylint configured for JSON
                    )
                    if output:
                        if tool_cat not in tier1_results: tier1_results[tool_cat] = {} # pylint might be under 'linters'
                        if tool_k not in tier1_results[tool_cat]: tier1_results[tool_cat][tool_k] = []
                        
                        # Assuming output is List[Dict] for Pylint JSON
                        if isinstance(output, list):
                            for finding in output:
                                finding['file_path'] = file_obj.path # Ensure file_path is consistent
                                finding['tool_name'] = f"{tool_cat}.{tool_k}"
                                tier1_results[tool_cat][tool_k].append(finding)
                        else:
                             error_messages.append(f"Pylint for {file_obj.path} did not return a list: {type(output)}")
                        logger.info(f"Pylint found {len(output) if isinstance(output,list) else 0} issues in {file_obj.path}")

                except ToolExecutionError as e:
                    msg = f"Pylint execution failed for {file_obj.path}: {e.message} (stderr: {e.stderr})"
                    logger.error(msg)
                    error_messages.append(msg)
                except Exception as e:
                    msg = f"Unexpected error running Pylint for {file_obj.path}: {e}"
                    logger.error(msg, exc_info=True)
                    error_messages.append(msg)
        
        # Example: Run Semgrep (generic SAST) - assuming it's configured under "sast.generic"
        # Semgrep might run on the whole project or specific paths.
        # This example assumes it runs once per project, not per file, so maybe put in a separate node
        # or run it here only once. For now, let's assume it could be file-specific for some configs.
        tool_cat_sast, tool_k_sast = "sast", "generic"
        if config_obj.get_tool_command_template(tool_cat_sast, tool_k_sast) and file_obj.path.endswith(('.py', '.js')): # Example filter
            # This logic might need adjustment based on how semgrep is configured (per file vs project)
            # For simplicity, let's assume a per-file run if template uses {file_path}
            # If it uses {project_root}, then it should run only once.
            # The current tool_runner.run takes target_file_relative_path, implying per-file.
            pass # Add Semgrep logic here similar to Pylint if needed per file.

    # Centralized Semgrep run (if configured for project-level scan)
    semgrep_tool_cat, semgrep_tool_key = "sast", "generic_semgrep_project" # Example key for project scan
    if config_obj.get_tool_command_template(semgrep_tool_cat, semgrep_tool_key):
        logger.info("Running Semgrep (project-level scan)...")
        try:
            # Semgrep command template should use {project_root} or similar, not {file_path}
            output = tool_runner.run(
                tool_category=semgrep_tool_cat,
                tool_key=semgrep_tool_key,
                # target_file_relative_path=None, # Not for a project-wide scan using {project_root}
                expect_json_output=True # Assuming Semgrep is configured for JSON output
            )
            if output and isinstance(output, dict) and "results" in output:
                if semgrep_tool_cat not in tier1_results: tier1_results[semgrep_tool_cat] = {}
                if semgrep_tool_key not in tier1_results[semgrep_tool_cat]: tier1_results[semgrep_tool_cat][semgrep_tool_key] = []
                
                parsed_semgrep_findings = []
                for finding_data in output["results"]:
                    # Adapt semgrep JSON to our internal finding structure
                    # Semgrep's `path` is often relative already.
                    # Location: finding_data["start"]["line"], finding_data["end"]["line"]
                    # Message: finding_data["extra"]["message"]
                    # Rule ID: finding_data["check_id"]
                    adapted_finding = {
                        "file_path": finding_data.get("path"),
                        "line_start": finding_data.get("start", {}).get("line"),
                        "line_end": finding_data.get("end", {}).get("line"),
                        "message_text": finding_data.get("extra", {}).get("message"),
                        "rule_id": finding_data.get("check_id"),
                        "level": finding_data.get("extra", {}).get("severity", "warning").lower(), # ERROR, WARNING, INFO
                        "tool_name": f"{semgrep_tool_cat}.{semgrep_tool_key}",
                        "raw_tool_output": finding_data # Store original for reference
                    }
                    if adapted_finding["file_path"] and adapted_finding["line_start"] and adapted_finding["message_text"]:
                       parsed_semgrep_findings.append(adapted_finding)

                tier1_results[semgrep_tool_cat][semgrep_tool_key].extend(parsed_semgrep_findings)
                logger.info(f"Semgrep (project) found {len(parsed_semgrep_findings)} issues.")
            elif output:
                error_messages.append(f"Semgrep (project) output was not in expected JSON format: {str(output)[:200]}")


        except ToolExecutionError as e:
            msg = f"Semgrep (project) execution failed: {e.message} (stderr: {e.stderr})"
            logger.error(msg)
            error_messages.append(msg)
        except Exception as e:
            msg = f"Unexpected error running Semgrep (project): {e}"
            logger.error(msg, exc_info=True)
            error_messages.append(msg)


    logger.info(f"Tier 1 tools phase completed. Results: { {k: len(v) for k,v in tier1_results.items()} }")
    return {"tier1_tool_results": tier1_results, "error_messages": error_messages}


# --- Agent Activation Nodes ---
# These nodes will instantiate and run their respective agents.
# They need access to Config, OllamaClientWrapper, PromptManager.
# Again, assuming these are available (e.g., via `shared_ctx.config_obj` and then initialized).

def _activate_agent_node(
    agent_class: type, # The class of the agent to activate
    agent_name_log: str, # For logging
    state: GraphState,
    # Pass additional context specific to this agent if needed
    extra_agent_input: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    logger.info(f"--- Running: Activate {agent_name_log} Node ---")
    shared_ctx = state["shared_context"]
    files_to_review = state["files_to_review"]
    current_agent_findings = list(state.get("agent_findings", [])) # Accumulate
    error_messages = list(state.get("error_messages", []))

    config_obj: Optional[Config] = getattr(shared_ctx, 'config_obj', None) # Hypothetical access
    if not config_obj:
        msg = f"Config object not available for {agent_name_log}."
        logger.error(msg)
        error_messages.append(msg)
        return {"agent_findings": current_agent_findings, "error_messages": error_messages}

    # Instantiate clients here (simplification)
    ollama_client = OllamaClientWrapper(base_url=config_obj.ollama_base_url)
    prompt_manager = PromptManager(config=config_obj)
    
    agent_instance = agent_class(config=config_obj, ollama_client=ollama_client, prompt_manager=prompt_manager)
    
    agent_specific_input = {"files_data": files_to_review}
    if extra_agent_input:
        agent_specific_input.update(extra_agent_input)

    try:
        # Pass relevant tier1 results if the agent needs them
        if agent_name_log == "StyleGuardian" or agent_name_log == "SecuriSense":
             agent_specific_input["tier1_tool_results"] = state.get("tier1_tool_results")

        new_findings = agent_instance.review(**agent_specific_input)
        current_agent_findings.extend(new_findings)
        logger.info(f"{agent_name_log} contributed {len(new_findings)} findings.")
    except NotImplementedError:
        msg = f"{agent_name_log} 'review' method is not implemented in the stub."
        logger.warning(msg)
        # error_messages.append(msg) # Not necessarily an error for a stub
    except Exception as e:
        msg = f"Error during {agent_name_log} execution: {e}"
        logger.error(msg, exc_info=True)
        error_messages.append(msg)
        
    return {"agent_findings": current_agent_findings, "error_messages": error_messages}


def activate_style_guardian_node(state: GraphState) -> Dict[str, Any]:
    # StyleGuardian might use linter results from tier1_tool_results
    return _activate_agent_node(StyleGuardianAgent, "StyleGuardian", state)

def activate_bug_hunter_node(state: GraphState) -> Dict[str, Any]:
    return _activate_agent_node(BugHunterAgent, "BugHunter", state)

def activate_securi_sense_node(state: GraphState) -> Dict[str, Any]:
    # SecuriSense might use SAST results from tier1_tool_results
    return _activate_agent_node(SecuriSenseAgent, "SecuriSense", state)

def activate_opti_tune_node(state: GraphState) -> Dict[str, Any]:
    return _activate_agent_node(OptiTuneAgent, "OptiTune", state)

def run_meta_review_node(state: GraphState) -> Dict[str, Any]:
    # MetaReviewer takes all previous agent_findings
    # The _activate_agent_node needs adjustment if MetaReviewer has a different signature for review()
    # For now, assume its review() method also takes 'files_data', and we pass existing findings
    # via extra_agent_input.
    
    # A more direct way for MetaReviewer:
    logger.info(f"--- Running: Meta Reviewer Node ---")
    shared_ctx = state["shared_context"]
    all_previous_findings = list(state.get("agent_findings", []))
    error_messages = list(state.get("error_messages", []))

    config_obj: Optional[Config] = getattr(shared_ctx, 'config_obj', None)
    if not config_obj:
        # ... error handling ...
        return {"agent_findings": all_previous_findings, "error_messages": error_messages}

    ollama_client = OllamaClientWrapper(base_url=config_obj.ollama_base_url)
    prompt_manager = PromptManager(config=config_obj)
    meta_reviewer = MetaReviewerAgent(config=config_obj, ollama_client=ollama_client, prompt_manager=prompt_manager)

    try:
        # MetaReviewer's review method might take `all_findings` directly
        # Assume MetaReviewerAgent.review signature is: review(self, all_findings: List[Dict], files_data: List[ChangedFile])
        refined_findings = meta_reviewer.review(all_findings=all_previous_findings, files_data=state["files_to_review"])
        logger.info(f"MetaReviewer processed {len(all_previous_findings)} findings, resulted in {len(refined_findings)} findings.")
        return {"agent_findings": refined_findings, "error_messages": error_messages} # Overwrites with refined list
    except NotImplementedError:
        logger.warning("MetaReviewerAgent 'review' method is not implemented.")
        return {"agent_findings": all_previous_findings, "error_messages": error_messages} # Return original if stubbed
    except Exception as e:
        msg = f"Error during MetaReviewer execution: {e}"
        logger.error(msg, exc_info=True)
        error_messages.append(msg)
        return {"agent_findings": all_previous_findings, "error_messages": error_messages}


def generate_sarif_report_node(state: GraphState) -> Dict[str, Any]:
    """
    Generates the final SARIF report from all collected findings.
    """
    logger.info("--- Running: Generate SARIF Report Node ---")
    shared_ctx = state["shared_context"]
    tier1_results = state.get("tier1_tool_results", {})
    agent_findings = state.get("agent_findings", [])
    error_messages = list(state.get("error_messages", []))

    # SIMPLIFICATION: Instantiate SarifGenerator here.
    # This requires tool_name, version, etc. Potentially from Config or constants.
    # Let's assume these are available e.g. via shared_ctx or a new config field in state
    
    # Placeholder values for tool info - should come from config or constants
    TOOL_NAME = "NovaGuardAI"
    TOOL_VERSION = "0.1.0" # Get from a central place, e.g. project version

    sarif_generator = SarifGenerator(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        tool_information_uri=getattr(shared_ctx, 'config_obj', {}).get('project_url', 'https://example.com/novaguardai'), # Hypothetical
        repo_uri_for_artifacts=f"https://github.com/{shared_ctx.repository_name}",
        commit_sha_for_artifacts=shared_ctx.sha,
        workspace_root_for_relative_paths=shared_ctx.repo_local_path
    )

    # Add findings from Tier 1 tools
    for tool_category, category_results in tier1_results.items():
        for tool_key, findings_list in category_results.items():
            for finding in findings_list:
                try:
                    sarif_generator.add_finding(
                        file_path=finding.get("file_path", "unknown_file"),
                        message_text=finding.get("message_text", "No message provided."),
                        rule_id=str(finding.get("rule_id", f"{tool_category}.{tool_key}.unknown")),
                        level=str(finding.get("level", "note")).lower(),
                        line_start=int(finding.get("line_start", 1)),
                        line_end=finding.get("line_end"), # Optional
                        col_start=finding.get("col_start"), # Optional
                        col_end=finding.get("col_end"),     # Optional
                        # rule_name, rule_short_description can be added if available from tool
                    )
                except Exception as e:
                    msg = f"Failed to add Tier 1 finding to SARIF: {str(finding)[:200]}. Error: {e}"
                    logger.warning(msg)
                    error_messages.append(msg)

    # Add findings from LLM Agents
    for finding in agent_findings:
        try:
            sarif_generator.add_finding(
                file_path=finding.get("file_path", "unknown_file"),
                message_text=finding.get("message_text", "No message provided."),
                rule_id=str(finding.get("rule_id", "agent.unknown")),
                level=str(finding.get("level", "note")).lower(),
                line_start=int(finding.get("line_start", 1)),
                line_end=finding.get("line_end"),
                col_start=finding.get("col_start"),
                col_end=finding.get("col_end"),
                code_snippet=finding.get("code_snippet"),
                # Fixes structure needs to be built carefully if agents provide suggestions
                # fixes=[{"description": {"text": "Suggested fix"}, ...}] if "suggestion" in finding else None
            )
        except Exception as e:
            msg = f"Failed to add Agent finding to SARIF: {str(finding)[:200]}. Error: {e}"
            logger.warning(msg)
            error_messages.append(msg)

    # Set overall invocation status
    # If any errors were logged during the process, mark execution as not entirely successful
    # even if a report is generated.
    execution_successful = not bool(state.get("error_messages")) # Check original errors before this node potentially adds more
    sarif_generator.set_invocation_status(
        successful=execution_successful,
        error_message="One or more errors occurred during analysis. Check logs and SARIF notifications." if not execution_successful else None
    )

    final_report = sarif_generator.get_sarif_report()
    logger.info(f"SARIF report generated with {len(final_report['runs'][0]['results'])} results.")
    
    return {"final_sarif_report": final_report, "error_messages": error_messages}