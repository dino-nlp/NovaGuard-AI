# NOVAGUARD-AI/src/orchestrator/graph_definition.py

import logging
from typing import Literal

from langgraph.graph import StateGraph, END
# Assuming state.py and nodes.py are in the same 'orchestrator' directory
from .state import GraphState
from . import nodes # Import the nodes module

# Import Config for type hinting the parameter, though it's used by nodes via GraphState
from ..core.config_loader import Config


logger = logging.getLogger(__name__)

# --- Conditional Logic Functions ---

def should_run_meta_reviewer(state: GraphState) -> Literal["run_meta_reviewer", "skip_meta_reviewer"]:
    """
    Determines if the meta-reviewer agent should run.
    This could be based on configuration or the number of findings.
    """
    # Access the config through shared_context
    config_obj = state["shared_context"].config_obj
    
    # Example: Check a setting in models.yml (e.g., models.agents.meta_reviewer is defined)
    # Or a specific boolean flag in a general settings part of the config.
    # For now, let's assume if a model for "meta_reviewer" is defined, we run it.
    if config_obj.get_model_for_agent("meta_reviewer"): # or config_obj.get_model_for_task("meta_reviewer")
        logger.info("Condition met: Meta Reviewer will run.")
        return "run_meta_reviewer"
    else:
        logger.info("Condition not met: Skipping Meta Reviewer.")
        return "skip_meta_reviewer"

def initial_check_for_files(state: GraphState) -> Literal["proceed_to_tier1", "no_files_to_review_end"]:
    """
    Checks if there are any files to review after the preparation step.
    If not, the graph can end early.
    """
    if state.get("files_to_review") and len(state["files_to_review"]) > 0:
        logger.info(f"Initial check: {len(state['files_to_review'])} files to review. Proceeding.")
        return "proceed_to_tier1"
    else:
        logger.warning("Initial check: No files to review. Ending graph execution early.")
        # It might be good to still generate an empty SARIF report.
        # For now, this conditional edge allows bypassing main processing.
        # A more robust flow might go to generate_sarif directly to output an empty valid report.
        # Let's adjust this to go to generate_sarif.
        return "no_files_to_review_end" # This will go to a direct SARIF generation


def get_compiled_graph(
    # The config_obj is passed to allow graph construction decisions if needed,
    # but nodes will access it primarily via `state["shared_context"].config_obj` at runtime.
    app_config: Config):
    """
    Constructs and compiles the LangGraph StateGraph for the NovaGuard AI code review process.

    Args:
        app_config: The application's configuration object. Used here for potential
                    graph construction logic (e.g., conditionally adding nodes/edges based on config).
                    Nodes access this config at runtime via `state['shared_context'].config_obj`.
    """
    logger.info("Constructing NovaGuard AI review graph...")

    workflow = StateGraph(GraphState)

    # 1. Add Nodes
    logger.debug("Adding nodes to the graph...")
    workflow.add_node("prepare_files", nodes.prepare_review_files_node)
    workflow.add_node("run_tier1_tools", nodes.run_tier1_tools_node)
    
    # Agent Nodes
    workflow.add_node("style_guardian", nodes.activate_style_guardian_node)
    workflow.add_node("bug_hunter", nodes.activate_bug_hunter_node)
    workflow.add_node("securi_sense", nodes.activate_securi_sense_node)
    workflow.add_node("opti_tune", nodes.activate_opti_tune_node)
    
    # Optional Meta Reviewer Node
    if app_config.get_model_for_agent("meta_reviewer"): # Conditionally add node based on config
        logger.info("Meta Reviewer is configured. Adding meta_reviewer node.")
        workflow.add_node("meta_reviewer", nodes.run_meta_review_node)
    else:
        logger.info("Meta Reviewer is not configured. Node will not be added.")

    workflow.add_node("generate_sarif", nodes.generate_sarif_report_node)

    # 2. Set Entry Point
    workflow.set_entry_point("prepare_files")
    logger.debug("Entry point set to 'prepare_files'.")

    # 3. Define Edges and Conditional Logic
    logger.debug("Defining edges and conditional logic...")

    # Edge from prepare_files with a condition to end early if no files
    workflow.add_conditional_edges(
        "prepare_files",
        initial_check_for_files,
        {
            "proceed_to_tier1": "run_tier1_tools",
            "no_files_to_review_end": "generate_sarif" # Go to SARIF to generate empty report
        }
    )

    workflow.add_edge("run_tier1_tools", "style_guardian")
    
    # Sequential agent execution for simplicity.
    # In a more advanced setup, a router node could decide which agents to run
    # based on file types, configuration, or previous findings.
    # Or, if agents are independent, they could potentially be parallelized
    # (LangGraph has ways to manage parallel execution, though it's more complex).
    workflow.add_edge("style_guardian", "bug_hunter")
    workflow.add_edge("bug_hunter", "securi_sense")
    workflow.add_edge("securi_sense", "opti_tune")

    # Conditional edge for Meta Reviewer
    if app_config.get_model_for_agent("meta_reviewer"):
        # If meta_reviewer node was added, route to it
        workflow.add_edge("opti_tune", "meta_reviewer")
        workflow.add_edge("meta_reviewer", "generate_sarif")
        logger.debug("Edges configured to run through Meta Reviewer.")
    else:
        # If no meta_reviewer, opti_tune goes directly to SARIF generation
        workflow.add_edge("opti_tune", "generate_sarif")
        logger.debug("Edges configured to skip Meta Reviewer and go directly to SARIF generation.")

    # Final step: generate SARIF report and end
    workflow.add_edge("generate_sarif", END)
    logger.debug("Final edge set from 'generate_sarif' to END.")

    # 4. Compile the graph
    logger.info("Compiling the graph...")
    app = workflow.compile()
    logger.info("Graph compiled successfully.")
    
    return app