# NOVAGUARD-AI/tests/core/test_tool_runner.py

import unittest
import subprocess
import json
import shlex
import tempfile
from pathlib import Path
import os
import sys
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any, Optional, Union, List # Thêm List

# Thêm src vào sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.tool_runner import ToolRunner, ToolExecutionError, TOOL_OUTPUT_SUBDIR
from src.core.config_loader import Config # Chỉ để type hint

# Mock Config class
class MockConfig:
    """A simplified mock of the Config class for ToolRunner tests."""
    def __init__(self, tools_cfg: Dict[str, Any]):
        self.tools_config = tools_cfg

    def get_tool_command_template(self, tool_category: str, tool_key: str) -> Optional[str]:
        command_config = self.tools_config.get(tool_category, {}).get(tool_key)
        if isinstance(command_config, dict):
            return command_config.get("command")
        elif isinstance(command_config, str):
            return command_config
        return None

# --- Test Class ---
class TestToolRunner(unittest.TestCase):

    def setUp(self):
        """Set up a ToolRunner instance with mock config and temp workspace."""
        self.temp_dir_manager = tempfile.TemporaryDirectory()
        self.workspace_path = Path(self.temp_dir_manager.name).resolve()

        self.mock_tools_config = {
            "echo": {
                "simple": "echo Hello World",
                "file_arg": "echo Processing {relative_file_path}",
                "needs_var": "echo Var is {custom_var}"
            },
            "linter": {
                "output_stdout_json": "fake_linter --format=json {file_path}",
                "output_stdout_text": "fake_linter_text {file_path}",
                "fails_nonzero": "fail_tool --code=1 {file_path}", # Tool trả exit code 1
                "empty_output_ok": "empty_tool_ok {file_path}", # Tool chạy ok, không output
                "empty_output_fail": "empty_tool_fail --code=1 {file_path}", # Tool chạy lỗi, không output
            },
            "sast": {
                "output_file_json": "fake_sast --json --output {output_file} {project_root}",
                "output_file_text": "fake_sast_text --output {output_file} {project_root}"
            }
        }
        self.mock_config = MockConfig(self.mock_tools_config)
        self.runner = ToolRunner(self.mock_config, self.workspace_path)
        
        # Tạo file mẫu
        self.test_file_rel_path = "src/my_code.py"
        self.test_file_abs_path = self.workspace_path / self.test_file_rel_path
        self.test_file_abs_path.parent.mkdir(parents=True, exist_ok=True)
        self.test_file_abs_path.write_text("print('hello')")
        
        self.expected_tool_output_dir = self.workspace_path / TOOL_OUTPUT_SUBDIR


    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir_manager.cleanup()

    def create_mock_process(self, stdout="", stderr="", returncode=0):
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.stdout = stdout
        proc.stderr = stderr
        proc.returncode = returncode
        return proc

    @patch('subprocess.run')
    def test_run_success_stdout_text(self, mock_subprocess_run):
        """Test successful run returning text via stdout."""
        mock_process = self.create_mock_process(stdout="Simple tool output text\n ") # Include whitespace to test strip()
        mock_subprocess_run.return_value = mock_process
        result = self.runner.run(
            tool_category="echo", tool_key="file_arg",
            target_file_relative_path=self.test_file_rel_path,
            expect_json_output=False
        )
        self.assertEqual(result, "Simple tool output text") # strip() should remove trailing whitespace
        expected_command = f"echo Processing {self.test_file_rel_path}"
        mock_subprocess_run.assert_called_once()
        args, kwargs = mock_subprocess_run.call_args
        self.assertEqual(args[0], shlex.split(expected_command))
        self.assertEqual(kwargs.get('cwd'), self.workspace_path)


    @patch('subprocess.run')
    def test_run_success_stdout_json(self, mock_subprocess_run):
        """Test successful run returning JSON via stdout."""
        json_output = '{"status": "ok", "count": 5}'
        mock_process = self.create_mock_process(stdout=json_output)
        mock_subprocess_run.return_value = mock_process
        result = self.runner.run(
            tool_category="linter", tool_key="output_stdout_json",
            target_file_relative_path=self.test_file_rel_path,
            expect_json_output=True
        )
        self.assertEqual(result, {"status": "ok", "count": 5})
        expected_command = f"fake_linter --format=json {self.test_file_abs_path}"
        mock_subprocess_run.assert_called_once_with(
            shlex.split(expected_command),
            capture_output=True, text=True, cwd=self.workspace_path, timeout=120, check=False
        )

    @patch('subprocess.run')
    def test_run_success_stdout_json_parse_error(self, mock_subprocess_run):
        """Test run succeeding but outputting invalid JSON when JSON is expected."""
        invalid_json_output = '{"status": "ok", count: 5}'
        mock_process = self.create_mock_process(stdout=invalid_json_output)
        mock_subprocess_run.return_value = mock_process
        result = self.runner.run(
            tool_category="linter", tool_key="output_stdout_json",
            target_file_relative_path=self.test_file_rel_path,
            expect_json_output=True
        )
        self.assertEqual(result, invalid_json_output) # Returns raw text due to parse error

    @patch('subprocess.run')
    @patch('pathlib.Path.exists') # Mock exists check
    @patch('pathlib.Path.read_text') # Mock reading
    @patch('pathlib.Path.unlink') # Mock deleting
    def test_run_success_output_file_json(self, mock_unlink, mock_read_text, mock_exists, mock_subprocess_run):
        """Test successful run where output is written to a JSON file."""
        json_output_in_file = '{"findings": [{"id": "A1"}]}'
        mock_process = self.create_mock_process(returncode=0)
        mock_subprocess_run.return_value = mock_process

        # Configure mocks for file operations
        mock_exists.return_value = True
        mock_read_text.return_value = json_output_in_file

        result = self.runner.run(
            tool_category="sast",
            tool_key="output_file_json",
            target_file_relative_path=None,
            expect_json_output=True
        )

        self.assertEqual(result, {"findings": [{"id": "A1"}]})

        # Check subprocess call includes a path to the temp file
        args, kwargs = mock_subprocess_run.call_args
        command_list = args[0]
        temp_file_path_in_cmd_str = None
        for part in command_list:
            if TOOL_OUTPUT_SUBDIR in part and part.endswith(".output"):
                temp_file_path_in_cmd_str = part
                break
        self.assertIsNotNone(temp_file_path_in_cmd_str, "Temporary output file path not found in subprocess command args")
        
        # Check file operations were called
        self.assertTrue(mock_exists.called, "Path.exists() was not called.")
        mock_read_text.assert_called_once_with(encoding='utf-8')
        mock_unlink.assert_called_once() 
        
        self.assertTrue(mock_unlink.called, "Path.unlink() was not called on the mock.")
        if mock_unlink.called:
            call_info = mock_unlink.call_args_list[0]
            # call_info.args sẽ là ()
            # call_info.kwargs sẽ là {}
            # Chúng ta không thể dễ dàng lấy đối tượng instance từ đây
            # Chỉ cần xác nhận nó được gọi là đủ trong ngữ cảnh này.
            pass # Assertion passed if called


    @patch('subprocess.run', side_effect=FileNotFoundError("Command not found"))
    def test_run_command_not_found(self, mock_subprocess_run):
        """Test failure when the command executable is not found."""
        result = self.runner.run("echo", "simple", expect_json_output=False)
        self.assertIsNone(result)
        mock_subprocess_run.assert_called_once()

    @patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd="cmd", timeout=10))
    def test_run_timeout_expired(self, mock_subprocess_run):
        """Test failure due to command timeout."""
        result = self.runner.run("echo", "simple", timeout_seconds=10)
        self.assertIsNone(result)
        mock_subprocess_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_non_zero_exit_code_no_output(self, mock_subprocess_run):
        """Test failure with non-zero exit code and no output."""
        mock_process = self.create_mock_process(returncode=1, stdout="", stderr="Tool failed")
        mock_subprocess_run.return_value = mock_process

        with self.assertRaises(ToolExecutionError) as cm:
            self.runner.run(
                tool_category="linter",
                tool_key="empty_output_fail", # Use specific key for clarity
                target_file_relative_path=self.test_file_rel_path
            )
        self.assertEqual(cm.exception.return_code, 1)
        self.assertEqual(cm.exception.stderr, "Tool failed")
        # >>> SỬA ASSERTION MESSAGE <<<
        expected_msg_part = "failed with exit code 1 and produced no output"
        self.assertIn(expected_msg_part, str(cm.exception))

    @patch('subprocess.run')
    def test_run_non_zero_exit_code_with_output(self, mock_subprocess_run):
        """Test non-zero exit but with valid output (e.g., linters finding issues)."""
        json_output = '{"findings": 1, "message": "Issues found"}'
        mock_process = self.create_mock_process(returncode=1, stdout=json_output, stderr="Found 1 issue")
        mock_subprocess_run.return_value = mock_process

        result = self.runner.run(
            tool_category="linter",
            tool_key="fails_nonzero", # Command template doesn't strictly matter due to mock
            target_file_relative_path=self.test_file_rel_path,
            expect_json_output=True
        )
        # Logic mới sẽ cố gắng parse output ngay cả khi exit code != 0
        self.assertEqual(result, {"findings": 1, "message": "Issues found"})


    def test_run_command_formatting_error(self):
        """Test error when command template has missing variables."""
        result = self.runner.run(
            tool_category="echo",
            tool_key="needs_var",
            target_file_relative_path=self.test_file_rel_path
            # Missing additional_context_vars={"custom_var": ...}
        )
        self.assertIsNone(result) # _prepare_command_and_context should return None, None

    def test_run_missing_tool_key_in_config(self):
        """Test trying to run a tool not defined in the config."""
        result = self.runner.run("linters", "non_existent_linter", self.test_file_rel_path)
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_run_success_empty_output(self, mock_subprocess_run):
        """Test successful run that produces empty stdout."""
        mock_process = self.create_mock_process(stdout=" \n ") # Empty after strip()
        mock_subprocess_run.return_value = mock_process
        result = self.runner.run(
            tool_category="linter",
            tool_key="empty_output_ok",
            target_file_relative_path=self.test_file_rel_path,
            expect_json_output=False
        )
        # Logic mới trả về None nếu thành công nhưng không có output
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()