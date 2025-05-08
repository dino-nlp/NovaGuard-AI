# NOVAGUARD-AI/src/core/tool_runner.py

import json
import shlex
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple, List # Thêm List

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
        # Ensure workspace_path is absolute and resolved
        self.workspace_path = workspace_path.resolve() 
        self.tool_output_dir = self.workspace_path / TOOL_OUTPUT_SUBDIR
        
        try:
            self.tool_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create tool output directory {self.tool_output_dir}: {e}")
            # Depending on configuration, this could be critical

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
            # Ensure relative path is handled correctly even if None is passed initially
            "relative_file_path": target_file_relative_path or "", 
        }
        
        if target_file_relative_path:
            # Ensure the relative path doesn't start with '/'
            if target_file_relative_path.startswith('/'):
                 logger.warning(f"Received an absolute-looking path '{target_file_relative_path}' where relative was expected. Attempting to use it directly relative to workspace.")
                 target_file_relative_path = target_file_relative_path.lstrip('/')

            abs_file_path = (self.workspace_path / target_file_relative_path).resolve()
            context_vars["file_path"] = str(abs_file_path)
            # Double check relative_file_path logic if abs_file_path calculation changes context
            try:
                 context_vars["relative_file_path"] = str(abs_file_path.relative_to(self.workspace_path))
            except ValueError:
                 logger.warning(f"Could not make path {abs_file_path} relative to workspace {self.workspace_path}. Using original relative path '{target_file_relative_path}'.")
                 context_vars["relative_file_path"] = target_file_relative_path # Use original if relative_to fails

        else:
             context_vars["file_path"] = "" # Provide empty string if no target file

        
        if additional_context_vars:
            context_vars.update(additional_context_vars)

        temp_output_file: Optional[Path] = None
        if "{output_file}" in command_template:
            # Generate a unique name for the temporary output file
            safe_target_name = Path(target_file_relative_path).name if target_file_relative_path else "project"
            safe_target_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in safe_target_name)
            safe_tool_key = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in tool_key)

            temp_output_filename = f"{tool_category}_{safe_tool_key}_{safe_target_name}.output"
            temp_output_file = (self.tool_output_dir / temp_output_filename).resolve()
            context_vars["output_file"] = str(temp_output_file)
            logger.debug(f"Tool '{tool_category}.{tool_key}' configured to write to temporary output file: {temp_output_file}")
        
        try:
            formatted_command = command_template.format(**context_vars)
            logger.info(f"Prepared command for '{tool_category}.{tool_key}': {formatted_command}")
            return formatted_command, temp_output_file
        except KeyError as e:
            logger.error(
                f"Missing placeholder '{e}' in command template for '{tool_category}.{tool_key}'. "
                f"Available context keys: {list(context_vars.keys())}"
            )
            return None, None
        except Exception as e:
            logger.error(f"Error formatting command for '{tool_category}.{tool_key}': {e}")
            return None, None


    def run(
        self,
        tool_category: str,
        tool_key: str,
        target_file_relative_path: Optional[str] = None,
        additional_context_vars: Optional[Dict[str, str]] = None,
        expect_json_output: bool = False,
        timeout_seconds: int = 120
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """
        Runs a configured CLI tool.

        Args:
            tool_category: The category of the tool (e.g., 'linters', 'sast').
            tool_key: The specific key for the tool under the category.
            target_file_relative_path: Optional relative path to the specific file to be analyzed.
            additional_context_vars: Optional dictionary of additional variables to format the command string.
            expect_json_output: If True, attempts to parse the tool's output (from stdout or file) as JSON.
            timeout_seconds: Maximum time to wait for the tool to complete.

        Returns:
            The parsed output (JSON as dict/list, or raw text as str), or None if the tool failed critically
            or ran successfully but produced no output.
        
        Raises:
            ToolExecutionError: If the tool runs but returns a non-zero exit code AND produces no output.
        """
        formatted_command, temp_output_file = self._prepare_command_and_context(
            tool_category, tool_key, target_file_relative_path, additional_context_vars
        )

        if not formatted_command:
            return None # Error already logged

        try:
            command_parts = shlex.split(formatted_command)
        except Exception as e:
            logger.error(f"Failed to parse command string '{formatted_command}' with shlex: {e}. ")
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
                check=False # Check returncode manually
            )

            logger.debug(f"Tool '{tool_category}.{tool_key}' finished. Return code: {process_completed.returncode}")
            if process_completed.stderr:
                logger.debug(f"Tool '{tool_category}.{tool_key}' Stderr:\n{process_completed.stderr.strip()}")

        except subprocess.TimeoutExpired:
            logger.error(f"Tool '{tool_category}.{tool_key}' timed out after {timeout_seconds} seconds.")
            return None # Timeout is treated as None result
        except FileNotFoundError:
            logger.error(f"Command not found for tool '{tool_category}.{tool_key}'. "
                         f"Command started with: '{command_parts[0]}'. Ensure it's installed and in PATH.")
            return None # Command not found is treated as None result
        except Exception as e:
            logger.error(f"Unexpected error executing tool '{tool_category}.{tool_key}': {e}", exc_info=True)
            # Depending on policy, might raise or return None. Let's return None.
            return None
        finally:
             # --- Xác định nội dung output thô ---
            # Ưu tiên đọc file nếu được sử dụng VÀ tồn tại sau khi process chạy xong
            if temp_output_file:
                try:
                    if temp_output_file.exists():
                        raw_output_text = temp_output_file.read_text(encoding='utf-8').strip()
                        logger.debug(f"Read output from temporary file: {temp_output_file}. Length: {len(raw_output_text or '')}")
                        # Xóa file tạm sau khi đọc thành công
                        try:
                            temp_output_file.unlink()
                            logger.debug(f"Cleaned up temporary output file: {temp_output_file}")
                        except OSError as unlink_e:
                            logger.warning(f"Failed to clean up temporary output file {temp_output_file}: {unlink_e}")
                    else:
                        logger.warning(f"Temporary output file {temp_output_file} was expected but not found after execution.")
                        # Nếu file không tồn tại, và process thành công, thì output là rỗng từ file perspective
                        # Nếu file không tồn tại, VÀ process lỗi, thì có thể dựa vào stdout/stderr
                        # => Để logic bên dưới xử lý stdout nếu raw_output_text vẫn là None
                except Exception as read_e:
                     logger.error(f"Failed to read or handle temporary output file {temp_output_file}: {read_e}")
                     # Nếu đọc file lỗi, và tiến trình cũng lỗi, thì raise lỗi ngay (hành vi cũ, có thể giữ)
                     if process_completed and process_completed.returncode != 0:
                         raise ToolExecutionError(
                            f"Tool '{tool_category}.{tool_key}' failed with exit code {process_completed.returncode} and its output file '{temp_output_file.name}' could not be read.",
                            stderr=process_completed.stderr,
                            return_code=process_completed.returncode
                         ) from read_e
                     # Nếu đọc file lỗi nhưng tiến trình thành công, thì coi như không có output từ file
                     raw_output_text = None # Reset để thử stdout

            # Nếu không dùng file output hoặc đọc file lỗi (và tiến trình không lỗi), thử đọc stdout
            if raw_output_text is None and process_completed:
                raw_output_text = process_completed.stdout.strip()
                if raw_output_text: # Chỉ log nếu stdout có nội dung
                    logger.debug(f"Read output from stdout. Length: {len(raw_output_text)}")
                else:
                    logger.debug("Read output from stdout: No content.")
            # --- Kết thúc xác định output thô ---


        # --- Kiểm tra các điều kiện lỗi và output ---
        # Trường hợp 1: Tool chạy lỗi VÀ không có output nào cả (raw_output_text là None hoặc rỗng)
        if process_completed and process_completed.returncode != 0 and not raw_output_text:
            logger.error(f"Tool '{tool_category}.{tool_key}' failed with exit code {process_completed.returncode} and produced no output (checked file and stdout).")
            raise ToolExecutionError(
                f"Tool '{tool_category}.{tool_key}' failed with exit code {process_completed.returncode} and produced no output.",
                stderr=process_completed.stderr,
                return_code=process_completed.returncode
            )

        # Trường hợp 2: Tool chạy thành công NHƯNG không có output
        if process_completed and process_completed.returncode == 0 and not raw_output_text:
            logger.info(f"Tool '{tool_category}.{tool_key}' ran successfully but produced no output.")
            return None # Trả về None nếu chạy xong mà không có gì

        # Trường hợp 3: Có output (raw_output_text có nội dung)
        # (Bao gồm cả trường hợp tool chạy lỗi nhưng vẫn có output)

        if process_completed and process_completed.returncode != 0:
            # Chỉ log warning, vì chúng ta sẽ cố gắng xử lý output bên dưới
            logger.warning(f"Tool '{tool_category}.{tool_key}' exited with code {process_completed.returncode}, but attempting to process its output.")

        # Xử lý output (parse JSON nếu cần)
        if expect_json_output:
            if not raw_output_text: # Nếu vì lý do nào đó raw_output_text là rỗng ở đây thì không parse
                 logger.warning(f"Expected JSON output for '{tool_category}.{tool_key}', but received empty output string after processing.")
                 return raw_output_text # Trả về chuỗi rỗng

            try:
                # Phải có output ở đây mới parse
                parsed_json: Union[Dict[str, Any], List[Any]] = json.loads(raw_output_text)
                logger.info(f"Successfully parsed JSON output for '{tool_category}.{tool_key}'.")
                return parsed_json
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse output from '{tool_category}.{tool_key}' as JSON despite expect_json_output=True. "
                    f"Error: {e}. Output starting with: '{raw_output_text[:100]}...'. Returning raw text instead."
                )
                # Rơi xuống trả về raw text
            except Exception as e:
                 logger.error(f"Unexpected error parsing JSON output for '{tool_category}.{tool_key}': {e}", exc_info=True)
                 # Trả về text gốc trong trường hợp lỗi parse không rõ ràng
        
        # Trả về text nếu không yêu cầu JSON, parse JSON lỗi, hoặc các trường hợp khác
        # Đảm bảo trả về string, không phải None ở đây nếu đã có output
        return raw_output_text if raw_output_text is not None else ""