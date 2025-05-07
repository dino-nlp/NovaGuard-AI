# NOVAGUARD-AI/src/core/tool_runner.py

import json
import shlex
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple

# Assuming Config is in the same 'core' directory
from .config_loader import Config

logger = logging.getLogger(__name__)

# A temporary directory within the workspace for tool outputs, if they write to files
TOOL_OUTPUT_SUBDIR = ".novaguard_tool_outputs"

class ToolExecutionError(Exception):
    """Custom exception for errors during tool execution."""
    def __init__(self, message: str, stderr: Optional[str] = None, return_code: Optional[int] = None):
        super().__init__(message)
        self.stderr = stderr
        self.return_code = return_code

class ToolRunner:
    """
    Executes external CLI tools based on pre-defined command templates
    and captures their output.
    """

    def __init__(self, config: Config, workspace_path: Path):
        """
        Initializes the ToolRunner.

        Args:
            config: The Config object containing tool command templates.
            workspace_path: The absolute path to the GitHub workspace, used as
                            the primary CWD for tool execution and for resolving paths.
        """
        self.config = config
        self.workspace_path = workspace_path
        self.tool_output_dir = self.workspace_path / TOOL_OUTPUT_SUBDIR
        
        # Ensure the temporary output directory exists
        try:
            self.tool_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create tool output directory {self.tool_output_dir}: {e}")
            # This might be a critical issue depending on tool configurations
            # For now, we'll log and continue; tools writing to files might fail.

        logger.info(f"ToolRunner initialized. Workspace: {self.workspace_path}")

    def _prepare_command_and_context(
        self,
        tool_category: str,
        tool_key: str,
        target_file_relative_path: Optional[str] = None, # Path to a specific file being analyzed
        additional_context_vars: Optional[Dict[str, str]] = None
    ) -> Tuple[Optional[str], Optional[Path]]:
        """
        Prepares the command string and identifies if an output file is used.

        Returns:
            A tuple: (formatted_command_string, path_to_temporary_output_file_if_any)
        """
        command_template = self.config.get_tool_command_template(tool_category, tool_key)
        if not command_template:
            logger.error(f"No command template found for tool '{tool_category}.{tool_key}'.")
            return None, None

        context_vars: Dict[str, str] = {
            "project_root": str(self.workspace_path),
        }
        
        if target_file_relative_path:
            # Absolute path to the specific file being analyzed
            abs_file_path = (self.workspace_path / target_file_relative_path).resolve()
            context_vars["file_path"] = str(abs_file_path)
            # Relative path from project_root (workspace_path)
            context_vars["relative_file_path"] = target_file_relative_path
        
        if additional_context_vars:
            context_vars.update(additional_context_vars)

        temp_output_file: Optional[Path] = None
        if "{output_file}" in command_template:
            # Generate a unique name for the temporary output file
            # Sanitize parts of the name to be filesystem-friendly
            safe_target_name = Path(target_file_relative_path).name if target_file_relative_path else "global"
            safe_target_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in safe_target_name)

            temp_output_filename = f"{tool_category}_{tool_key}_{safe_target_name}.output"
            temp_output_file = (self.tool_output_dir / temp_output_filename).resolve()
            context_vars["output_file"] = str(temp_output_file)
            logger.debug(f"Tool '{tool_category}.{tool_key}' will write to temporary output file: {temp_output_file}")
        
        try:
            formatted_command = command_template.format(**context_vars)
            logger.info(f"Prepared command for '{tool_category}.{tool_key}': {formatted_command}")
            return formatted_command, temp_output_file
        except KeyError as e:
            logger.error(
                f"Missing placeholder '{e}' in command template for '{tool_category}.{tool_key}'. "
                f"Available context: {list(context_vars.keys())}"
            )
            return None, None
        except Exception as e:
            logger.error(f"Error formatting command for '{tool_category}.{tool_key}': {e}")
            return None, None


    def run(
        self,
        tool_category: str,  # e.g., "linters", "sast"
        tool_key: str,       # e.g., "python" (for pylint), "generic" (for semgrep)
        target_file_relative_path: Optional[str] = None, # Path of the specific file to analyze, relative to workspace
        additional_context_vars: Optional[Dict[str, str]] = None, # For other placeholders in command
        expect_json_output: bool = False, # Hint to try parsing output as JSON
        timeout_seconds: int = 120 # Default timeout for the tool execution
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """
        Runs a configured CLI tool.

        Args:
            tool_category: The category of the tool (e.g., 'linters', 'sast').
            tool_key: The specific key for the tool under the category (e.g., 'python', 'generic_semgrep').
            target_file_relative_path: Optional relative path to the specific file to be analyzed.
                                    Some tools operate on the project root or don't need a specific file.
            additional_context_vars: Optional dictionary of additional variables to format the command string.
            expect_json_output: If True, attempts to parse the tool's output (from stdout or file) as JSON.
                                If False or parsing fails, returns raw text.
            timeout_seconds: Maximum time to wait for the tool to complete.

        Returns:
            The parsed output of the tool (JSON as dict/list, or raw text as str),
            or None if the tool failed to run or its command was not found.
        
        Raises:
            ToolExecutionError: If the tool runs but returns a non-zero exit code.
        """
        formatted_command, temp_output_file = self._prepare_command_and_context(
            tool_category, tool_key, target_file_relative_path, additional_context_vars
        )

        if not formatted_command:
            return None # Error already logged by _prepare_command_and_context

        # Security: Using shlex.split for commands not requiring shell=True.
        # If shell=True is absolutely needed for complex commands with pipes/redirects
        # not handled by subprocess, ensure command_template is from a trusted source.
        # For now, assume commands are simple enough for shlex.split.
        try:
            command_parts = shlex.split(formatted_command)
        except Exception as e:
            logger.error(f"Failed to parse command string '{formatted_command}' with shlex: {e}. "
                        "Consider using shell=True if the command is complex and trusted, "
                        "or simplify the command.")
            return None
        
        raw_output_text: Optional[str] = None
        process_completed: Optional[subprocess.CompletedProcess] = None

        try:
            logger.info(f"Executing: {' '.join(command_parts)} in CWD: {self.workspace_path}")
            process_completed = subprocess.run(
                command_parts,
                capture_output=True,
                text=True,
                cwd=self.workspace_path,
                timeout=timeout_seconds,
                check=False # We will check returncode manually
            )

            logger.debug(f"Tool '{tool_category}.{tool_key}' finished. Return code: {process_completed.returncode}")
            if process_completed.stderr:
                # Log stderr even if return code is 0, as it might contain warnings
                logger.debug(f"Tool '{tool_category}.{tool_key}' Stderr:\n{process_completed.stderr.strip()}")


            if process_completed.returncode != 0:
                # Some tools use non-zero exit codes to indicate findings (e.g., linters).
                # This behavior should ideally be configured per-tool.
                # For now, we treat non-zero as an execution error that might prevent parsing.
                # However, if an output file was generated, it might still contain valid results.
                logger.warning(
                    f"Tool '{tool_category}.{tool_key}' exited with code {process_completed.returncode}."
                )
                # Decide if this is a hard error or if we should still try to process output
                # Raising an exception makes it explicit.
                # raise ToolExecutionError(
                #     f"Tool '{tool_category}.{tool_key}' failed.",
                #     stderr=process_completed.stderr,
                #     return_code=process_completed.returncode
                # )
                # For now, let's try to process output even on non-zero exit if output exists.

            if temp_output_file and temp_output_file.exists():
                logger.debug(f"Reading output from temporary file: {temp_output_file}")
                raw_output_text = temp_output_file.read_text(encoding='utf-8')
            elif process_completed: # process_completed should exist if we got this far
                raw_output_text = process_completed.stdout.strip()
                logger.debug(f"Tool '{tool_category}.{tool_key}' Stdout:\n{raw_output_text[:1000]}...") # Log snippet

        except subprocess.TimeoutExpired:
            logger.error(f"Tool '{tool_category}.{tool_key}' timed out after {timeout_seconds} seconds.")
            return None # Or raise ToolExecutionError
        except FileNotFoundError:
            logger.error(f"Command not found for tool '{tool_category}.{tool_key}'. "
                        f"First part of command: '{command_parts[0]}'. Ensure it's in PATH or use absolute path.")
            return None
        except Exception as e:
            logger.error(f"Error executing tool '{tool_category}.{tool_key}': {e}", exc_info=True)
            return None
        finally:
            if temp_output_file and temp_output_file.exists():
                try:
                    temp_output_file.unlink()
                    logger.debug(f"Cleaned up temporary output file: {temp_output_file}")
                except OSError as e:
                    logger.warning(f"Failed to clean up temporary output file {temp_output_file}: {e}")

        if raw_output_text is None:
            logger.warning(f"No output (stdout or file) captured for tool '{tool_category}.{tool_key}'.")
            if process_completed and process_completed.returncode != 0 :
                # If there was an error and no output, it's likely a failure
                raise ToolExecutionError(
                    f"Tool '{tool_category}.{tool_key}' failed with no output.",
                    stderr=process_completed.stderr if process_completed else "Unknown error",
                    return_code=process_completed.returncode if process_completed else -1
                )
            return None


        if expect_json_output:
            try:
                parsed_json: Union[Dict[str, Any], List[Any]] = json.loads(raw_output_text)
                logger.info(f"Successfully parsed JSON output for '{tool_category}.{tool_key}'.")
                return parsed_json
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse output from '{tool_category}.{tool_key}' as JSON. "
                    f"Error: {e}. Returning raw text instead."
                )
                # Fall through to return raw_output_text
        
        return raw_output_text