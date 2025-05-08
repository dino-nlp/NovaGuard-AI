import unittest
from pathlib import Path
import sys
import copy
from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock, patch, call # Import call

# Thêm src vào sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import các thành phần cần thiết
from src.orchestrator.state import GraphState
# Import các node functions cần test
from src.core.shared_context import SharedReviewContext, ChangedFile
from src.core.config_loader import Config
from src.core.tool_runner import ToolRunner, ToolExecutionError 
from src.orchestrator.state import GraphState
# Import thêm node mới và agent tương ứng
from src.orchestrator.nodes import (
    prepare_review_files_node, 
    run_tier1_tools_node,
    activate_style_guardian_node,
    activate_bug_hunter_node,
    activate_securi_sense_node,
    activate_opti_tune_node,
    run_meta_review_node,
    generate_sarif_report_node
)
from src.core.shared_context import SharedReviewContext, ChangedFile
from src.core.config_loader import Config
from src.core.tool_runner import ToolRunner, ToolExecutionError 
# Import các agent class để mock
from src.agents.style_guardian_agent import StyleGuardianAgent 
from src.agents.bug_hunter_agent import BugHunterAgent
from src.agents.securi_sense_agent import SecuriSenseAgent
from src.agents.opti_tune_agent import OptiTuneAgent
from src.agents.meta_reviewer_agent import MetaReviewerAgent
from src.core.sarif_generator import SarifGenerator

# --- Test Class cho prepare_review_files_node ---
class TestOrchestratorNodes_PrepareFiles(unittest.TestCase):

    def setUp(self):
        self.workspace_path = Path("/mock/workspace").resolve()
        self.mock_config_instance = MagicMock(spec=Config)
        self.shared_context = SharedReviewContext(
            repository_name="test/repo", repo_local_path=self.workspace_path,
            sha="abcdef123", github_event_payload={}, config_obj=self.mock_config_instance,
            pr_url=None, pr_title=None, pr_body=None, pr_diff_url=None,
            pr_number=None, base_ref=None, head_ref=None, github_event_name=None,
        )
        self.maxDiff = None

    def test_prepare_files_basic(self):
        initial_files = [
            ChangedFile(path="src/main.py", content=""), ChangedFile(path="README.md", content=""), 
            ChangedFile(path="lib/script.js", content=""), ChangedFile(path="data.unknown", content="")
        ]
        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": copy.deepcopy(initial_files),
            "error_messages": [], "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None,
        }
        result_update = prepare_review_files_node(initial_state)
        self.assertIn("files_to_review", result_update); self.assertIn("error_messages", result_update)
        updated_files = result_update.get("files_to_review", [])
        self.assertEqual(len(updated_files), len(initial_files))
        languages_found = {f.path: f.language for f in updated_files}
        self.assertEqual(languages_found.get("src/main.py"), "python")
        self.assertEqual(languages_found.get("README.md"), "markdown")
        self.assertEqual(languages_found.get("lib/script.js"), "javascript")
        self.assertIsNone(languages_found.get("data.unknown"))
        self.assertEqual(len(result_update.get("error_messages", [])), 0)

    def test_prepare_files_empty_input(self):
        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": [],
            "error_messages": ["initial error"], "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None,
        }
        result_update = prepare_review_files_node(initial_state)
        self.assertIn("files_to_review", result_update); self.assertIn("error_messages", result_update)
        self.assertEqual(len(result_update.get("files_to_review", [])), 0)
        self.assertEqual(result_update.get("error_messages"), ["initial error"])

    def test_prepare_files_language_already_set(self):
        initial_files = [ChangedFile(path="src/main.py", content="", language="override_python")]
        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": copy.deepcopy(initial_files),
            "error_messages": [], "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None,
        }
        result_update = prepare_review_files_node(initial_state)
        updated_files = result_update.get("files_to_review", [])
        self.assertEqual(len(updated_files), 1); self.assertEqual(updated_files[0].language, "override_python")

class TestOrchestratorNodes_RunTier1(unittest.TestCase):

    def setUp(self):
        self.workspace_path = Path("/mock/workspace").resolve()
        self.mock_tools_config = {
            "linters": { "python": "pylint_cmd --json {file_path}", "javascript": "eslint_cmd {file_path}" },
            "sast": { "generic_semgrep_project": { "command": "semgrep --json -o {output_file} {project_root}", "target_type": "project" } }
        }
        self.mock_config_instance = MagicMock(spec=Config)
        def mock_get_template(category, key):
            cmd_config = self.mock_tools_config.get(category, {}).get(key)
            if isinstance(cmd_config, dict): return cmd_config.get("command")
            return cmd_config
        self.mock_config_instance.get_tool_command_template.side_effect = mock_get_template
        self.mock_config_instance.tools_config = self.mock_tools_config 

        self.shared_context = SharedReviewContext(
            repository_name="test/repo", repo_local_path=self.workspace_path, sha="abcdef123",
            github_event_payload={}, config_obj=self.mock_config_instance, pr_url=None, pr_title=None,
            pr_body=None, pr_diff_url=None, pr_number=None, base_ref=None, head_ref=None, github_event_name=None,
        )
        self.maxDiff = None

    @patch('src.orchestrator.nodes.ToolRunner') 
    def test_run_tier1_pylint_success(self, MockToolRunner):
        mock_runner_instance = MockToolRunner.return_value
        pylint_output = [
            {"line": 10, "message": "Missing docstring", "symbol": "C0114", "level":"note"},
            {"line": 25, "msg": "Invalid name", "symbol": "C0103", "level":"warning"} 
        ]
        # <<< Sửa Side Effect: Xử lý cả eslint và semgrep >>>
        def run_side_effect(*args, **kwargs):
            tool_cat = kwargs.get("tool_category")
            tool_k = kwargs.get("tool_key")
            if tool_cat == "linters" and tool_k == "python": return pylint_output
            if tool_cat == "linters" and tool_k == "javascript": return [] # Giả lập eslint chạy ok, không finding
            if tool_cat == "sast": return None # Semgrep trả None
            return None 
        mock_runner_instance.run.side_effect = run_side_effect

        py_file = ChangedFile(path="src/main.py", content="...", language="python")
        js_file = ChangedFile(path="lib/script.js", content="...", language="javascript")
        initial_state: GraphState = {"shared_context": self.shared_context, "files_to_review": [py_file, js_file], "error_messages": [], "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None}
        result_update = run_tier1_tools_node(initial_state)

        self.assertIn("tier1_tool_results", result_update); results = result_update["tier1_tool_results"]
        self.assertIn("linters", results); self.assertIn("python", results["linters"]); self.assertIn("javascript", results["linters"])
        self.assertEqual(len(results["linters"]["python"]), 2)
        self.assertEqual(len(results["linters"]["javascript"]), 0) # Eslint không có finding
        # Kiểm tra chuẩn hóa message pylint (đã sửa trong nodes.py)
        self.assertEqual(results["linters"]["python"][0]["message_text"], "Missing docstring")
        self.assertEqual(results["linters"]["python"][1]["message_text"], "Invalid name")

        # Kiểm tra các lệnh gọi mock
        mock_runner_instance.run.assert_any_call(tool_category='linters', tool_key='python', target_file_relative_path='src/main.py', expect_json_output=True)
        mock_runner_instance.run.assert_any_call(tool_category='linters', tool_key='javascript', target_file_relative_path='lib/script.js', expect_json_output=False) # Eslint cmd không có flag json
        mock_runner_instance.run.assert_any_call(tool_category='sast', tool_key='generic_semgrep_project', target_file_relative_path=None, expect_json_output=True)
        # >>> SỬA ASSERTION CALL COUNT <<<
        self.assertEqual(mock_runner_instance.run.call_count, 3) # Pylint + Eslint + Semgrep
        self.assertEqual(len(result_update.get("error_messages", [])), 0)
        self.assertIn("sast", results); self.assertIn("generic_semgrep_project", results["sast"]); self.assertEqual(len(results["sast"]["generic_semgrep_project"]), 0)

    @patch('src.orchestrator.nodes.ToolRunner')
    def test_run_tier1_semgrep_success(self, MockToolRunner):
        mock_runner_instance = MockToolRunner.return_value
        semgrep_output = {"results": [
                {"check_id": "CWE-XYZ", "path": "src/utils.py", "start": {"line": 55}, "end": {"line": 55}, "extra": {"message": "Vuln details", "severity": "ERROR"}},
                {"check_id": "API-KEY", "path": "config/deploy.yml", "start": {"line": 12}, "end": {"line": 12}, "extra": {"message": "API key found", "severity": "WARNING"}}]}
        def run_side_effect(*args, **kwargs):
            if kwargs.get("tool_category") == "sast": return semgrep_output
            if kwargs.get("tool_category") == "linters": return None # Pylint trả None
            return None
        mock_runner_instance.run.side_effect = run_side_effect

        py_file = ChangedFile(path="src/utils.py", content="...", language="python") # File đầu vào
        initial_state: GraphState = {"shared_context": self.shared_context, "files_to_review": [py_file], "error_messages": [], "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None}
        result_update = run_tier1_tools_node(initial_state)

        self.assertIn("tier1_tool_results", result_update); results = result_update["tier1_tool_results"]
        self.assertIn("sast", results); self.assertIn("generic_semgrep_project", results["sast"])
        self.assertEqual(len(results["sast"]["generic_semgrep_project"]), 2) 
        finding1 = results["sast"]["generic_semgrep_project"][0]; finding2 = results["sast"]["generic_semgrep_project"][1]
        self.assertEqual(finding1["file_path"], "src/utils.py"); self.assertEqual(finding1["line_start"], 55); self.assertEqual(finding1["message_text"], "Vuln details"); self.assertEqual(finding1["rule_id"], "CWE-XYZ"); self.assertEqual(finding1["level"], "error"); self.assertEqual(finding1["tool_name"], "sast.generic_semgrep_project")
        self.assertEqual(finding2["file_path"], "config/deploy.yml"); self.assertEqual(finding2["level"], "warning")
        
        # <<< SỬA ASSERTION CALL: Dùng assert_any_call >>>
        mock_runner_instance.run.assert_any_call(tool_category="sast", tool_key="generic_semgrep_project", target_file_relative_path=None, expect_json_output=True)
        mock_runner_instance.run.assert_any_call(tool_category="linters", tool_key="python", target_file_relative_path="src/utils.py", expect_json_output=True) # Pylint cũng được gọi
        self.assertEqual(mock_runner_instance.run.call_count, 2) # Pylint + Semgrep
        self.assertEqual(len(result_update.get("error_messages", [])), 0)

    @patch('src.orchestrator.nodes.ToolRunner')
    def test_run_tier1_no_applicable_tools(self, MockToolRunner):
        mock_runner_instance = MockToolRunner.return_value
        def run_side_effect_for_no_tools(*args, **kwargs):
            if kwargs.get("tool_category") == "sast": return None 
            return None
        mock_runner_instance.run.side_effect = run_side_effect_for_no_tools

        other_file = ChangedFile(path="docs/guide.rst", content="...", language="rst")
        initial_state: GraphState = {"shared_context": self.shared_context, "files_to_review": [other_file], "error_messages": [], "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None}
        result_update = run_tier1_tools_node(initial_state)

        self.assertIn("tier1_tool_results", result_update)
        # >>> SỬA ASSERTION: Mong đợi cấu trúc với list rỗng <<<
        expected_results = {'sast': {'generic_semgrep_project': []}} 
        self.assertDictEqual(result_update["tier1_tool_results"], expected_results)
        mock_runner_instance.run.assert_called_once_with(tool_category="sast", tool_key="generic_semgrep_project", target_file_relative_path=None, expect_json_output=True)
        self.assertEqual(len(result_update.get("error_messages", [])), 0)

    @patch('src.orchestrator.nodes.ToolRunner')
    def test_run_tier1_tool_execution_error(self, MockToolRunner):
        mock_runner_instance = MockToolRunner.return_value
        error_msg = "Pylint crashed spectacularly"
        def run_side_effect(*args, **kwargs):
            if kwargs.get("tool_category") == "linters": raise ToolExecutionError(error_msg, stderr="Traceback...", return_code=127)
            if kwargs.get("tool_category") == "sast": return None # Semgrep chạy ok (trả None)
            return None
        mock_runner_instance.run.side_effect = run_side_effect

        py_file = ChangedFile(path="src/main.py", content="...", language="python")
        initial_state: GraphState = {"shared_context": self.shared_context, "files_to_review": [py_file], "error_messages": ["previous error"], "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None}
        result_update = run_tier1_tools_node(initial_state)

        self.assertIn("tier1_tool_results", result_update)
        # >>> SỬA ASSERTION: Mong đợi kết quả chứa cả key tool lỗi và tool thành công <<<
        expected_results = {
            'linters': {'python': []}, # Key được tạo trước khi lỗi
            'sast': {'generic_semgrep_project': []} # Key được tạo vì Semgrep được gọi (trả None)
            } 
        self.assertDictEqual(result_update["tier1_tool_results"], expected_results)

        expected_error_msg = f"Tool 'linters.python' execution failed for src/main.py: {error_msg}"
        final_errors = result_update.get("error_messages", [])
        self.assertIn("previous error", final_errors)
        self.assertIn(expected_error_msg, final_errors)

    @patch('src.orchestrator.nodes.ToolRunner')
    def test_run_tier1_tool_returns_none(self, MockToolRunner):
        mock_runner_instance = MockToolRunner.return_value
        mock_runner_instance.run.return_value = None 

        py_file = ChangedFile(path="src/main.py", content="...", language="python")
        initial_state: GraphState = {"shared_context": self.shared_context, "files_to_review": [py_file], "error_messages": [], "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None}
        result_update = run_tier1_tools_node(initial_state)

        self.assertIn("tier1_tool_results", result_update)
        # >>> SỬA ASSERTION: Mong đợi cấu trúc key được tạo <<<
        expected_results = {'linters': {'python': []}, 'sast': {'generic_semgrep_project': []}}
        self.assertDictEqual(result_update["tier1_tool_results"], expected_results)
        self.assertEqual(len(result_update.get("error_messages", [])), 0)

# --- Test Class cho Agent Activation Nodes ---
# --- Test Class cho Agent Activation Nodes ---
class TestOrchestratorNodes_AgentActivation(unittest.TestCase):

    def setUp(self):
        """Setup for agent activation node tests."""
        self.workspace_path = Path("/mock/workspace").resolve()
        self.mock_config_instance = MagicMock(spec=Config)
        # Thiết lập các thuộc tính config cần thiết nếu agent's __init__ đọc chúng
        self.mock_config_instance.ollama_base_url = "mock_ollama_url" 
        
        self.shared_context = SharedReviewContext(
            repository_name="test/agent-repo", repo_local_path=self.workspace_path,
            sha="agent123", github_event_payload={}, config_obj=self.mock_config_instance,
            pr_url=None, pr_title=None, pr_body=None, pr_diff_url=None,
            pr_number=None, base_ref=None, head_ref=None, github_event_name=None,
        )
        
        # File mẫu cho state
        self.sample_files = [
            ChangedFile(path="style.py", content="bad style", language="python"),
            ChangedFile(path="good.py", content="good style", language="python"),
            ChangedFile(path="other.txt", content="text", language="text"),
        ]
        # Kết quả tier1 mẫu (cho StyleGuardian và SecuriSense)
        self.sample_tier1_results = {
            "linters": {
                "python": [
                    {"file_path": "style.py", "line_start": 1, "message_text": "Pylint issue", "rule_id": "C001", "level": "warning", "tool_name":"linters.python"}
                ]
            },
             "sast": {
                "generic_semgrep_project": [
                     {"file_path": "style.py", "line_start": 5, "message_text": "Semgrep issue", "rule_id": "SEC01", "level": "error", "tool_name":"sast.generic_semgrep_project"}
                ]
            }
        }
        self.maxDiff = None
        

    # --- Tests for StyleGuardian ---

    @patch('src.orchestrator.nodes.StyleGuardianAgent') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_activate_style_guardian_success(self, MockPromptManager, MockOllamaClient, MockStyleGuardianAgent):
        """Test successful activation of StyleGuardianAgent."""
        mock_agent_instance = MockStyleGuardianAgent.return_value
        mock_style_findings = [
            {"file_path": "style.py", "line_start": 2, "message_text": "LLM style suggestion 1", "rule_id": "StyleGuardian.llm_style_1", "level": "note", "tool_name": "StyleGuardian"},
            {"file_path": "style.py", "line_start": 8, "message_text": "LLM style suggestion 2", "rule_id": "StyleGuardian.llm_style_2", "level": "note", "tool_name": "StyleGuardian"},
        ]
        mock_agent_instance.review.return_value = mock_style_findings
        initial_agent_findings = [{"file_path": "initial.py", "line_start": 1, "message_text": "Finding from previous agent", "rule_id": "PrevAgent.some_rule", "level": "warning", "tool_name": "PrevAgent"}]
        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": copy.deepcopy(self.sample_tier1_results),
            "agent_findings": copy.deepcopy(initial_agent_findings), 
            "error_messages": [], "final_sarif_report": None,
        }

        result_update = activate_style_guardian_node(initial_state)

        self.assertIn("agent_findings", result_update)
        final_findings = result_update["agent_findings"]
        self.assertEqual(len(final_findings), len(initial_agent_findings) + len(mock_style_findings))
        self.assertEqual(final_findings[0]["rule_id"], "PrevAgent.some_rule") 
        self.assertEqual(final_findings[1]["rule_id"], "StyleGuardian.llm_style_1")
        self.assertEqual(final_findings[2]["message_text"], "LLM style suggestion 2")
        MockStyleGuardianAgent.assert_called_once()
        MockOllamaClient.assert_called_once()
        MockPromptManager.assert_called_once()
        mock_agent_instance.review.assert_called_once()
        call_args, call_kwargs = mock_agent_instance.review.call_args
        self.assertEqual(call_kwargs.get("files_data"), initial_state["files_to_review"])
        self.assertEqual(call_kwargs.get("tier1_tool_results"), initial_state["tier1_tool_results"])
        self.assertEqual(result_update.get("error_messages", []), [])

    @patch('src.orchestrator.nodes.StyleGuardianAgent') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_activate_style_guardian_agent_raises_error(self, MockPromptManager, MockOllamaClient, MockStyleGuardianAgent):
        """Test node handles exception from agent's review method."""
        mock_agent_instance = MockStyleGuardianAgent.return_value
        error_message = "Agent failed during review!"
        mock_agent_instance.review.side_effect = Exception(error_message)
        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": {}, "agent_findings": [], "error_messages": ["initial"],
            "final_sarif_report": None,
        }

        result_update = activate_style_guardian_node(initial_state)

        self.assertListEqual(result_update.get("agent_findings"), [])
        final_errors = result_update.get("error_messages")
        self.assertIn("initial", final_errors)
        expected_error_substring = f"Error during StyleGuardian execution: {error_message}"
        self.assertTrue(any(expected_error_substring in msg for msg in final_errors), 
                        f"Expected error substring '{expected_error_substring}' not found in {final_errors}")

    # --- Tests for BugHunter ---

    @patch('src.orchestrator.nodes.BugHunterAgent') # Patch đúng agent class
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_activate_bug_hunter_success(self, MockPromptManager, MockOllamaClient, MockBugHunterAgent):
        """Test successful activation of BugHunterAgent."""
        mock_agent_instance = MockBugHunterAgent.return_value
        mock_bug_findings = [
            {"file_path": "style.py", "line_start": 5, "message_text": "Potential null pointer", "rule_id": "BugHunter.llm_bug_null", "level": "warning", "tool_name": "BugHunter"}
        ]
        mock_agent_instance.review.return_value = mock_bug_findings

        initial_agent_findings = [{"rule_id": "StyleGuardian.some_finding", "message_text":"Style issue"}] 
        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": copy.deepcopy(self.sample_tier1_results), 
            "agent_findings": copy.deepcopy(initial_agent_findings), 
            "error_messages": [], "final_sarif_report": None,
        }

        result_update = activate_bug_hunter_node(initial_state) # Gọi node BugHunter

        self.assertIn("agent_findings", result_update)
        final_findings = result_update["agent_findings"]
        self.assertEqual(len(final_findings), len(initial_agent_findings) + len(mock_bug_findings))
        self.assertEqual(final_findings[0]["rule_id"], "StyleGuardian.some_finding") 
        self.assertEqual(final_findings[1]["rule_id"], "BugHunter.llm_bug_null")     

        MockBugHunterAgent.assert_called_once()
        mock_agent_instance.review.assert_called_once()
        call_args, call_kwargs = mock_agent_instance.review.call_args
        self.assertEqual(call_kwargs.get("files_data"), initial_state["files_to_review"])
        # Kiểm tra xem tier1_results có được truyền vào không (BugHunter không cần)
        self.assertNotIn("tier1_tool_results", call_kwargs, "BugHunter review should not receive tier1_results based on _activate_agent_node logic") 
        
        self.assertEqual(result_update.get("error_messages", []), [])

    @patch('src.orchestrator.nodes.BugHunterAgent') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_activate_bug_hunter_agent_raises_error(self, MockPromptManager, MockOllamaClient, MockBugHunterAgent):
        """Test node handles exception from BugHunterAgent's review method."""
        mock_agent_instance = MockBugHunterAgent.return_value
        error_message = "BugHunter exploded!"
        mock_agent_instance.review.side_effect = Exception(error_message)

        initial_agent_findings = [{"rule_id":"prev"}]
        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": {}, "agent_findings": copy.deepcopy(initial_agent_findings), 
            "error_messages": ["old"], "final_sarif_report": None,
        }

        result_update = activate_bug_hunter_node(initial_state)

        # agent_findings không thay đổi so với ban đầu
        self.assertEqual(result_update.get("agent_findings"), initial_agent_findings) 
        
        final_errors = result_update.get("error_messages")
        self.assertIn("old", final_errors)
        expected_error_substring = f"Error during BugHunter execution: {error_message}"
        self.assertTrue(any(expected_error_substring in msg for msg in final_errors),
                        f"Expected error substring '{expected_error_substring}' not found in {final_errors}")
        
    # >>> THÊM TEST CASES CHO SECURI SENSE <<<

    @patch('src.orchestrator.nodes.SecuriSenseAgent') # Patch đúng agent class
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_activate_securi_sense_success(self, MockPromptManager, MockOllamaClient, MockSecuriSenseAgent):
        """Test successful activation of SecuriSenseAgent."""
        mock_agent_instance = MockSecuriSenseAgent.return_value
        mock_sec_findings = [
            {"file_path": "sec_vuln.py", "line_start": 10, "message_text": "LLM confirms potential SQL Injection", "rule_id": "SecuriSense.llm_sec_sqli", "level": "error", "tool_name": "SecuriSense"}
        ]
        mock_agent_instance.review.return_value = mock_sec_findings

        # State ban đầu có thể có finding từ BugHunter
        initial_agent_findings = [{"rule_id": "BugHunter.some_bug"}] 
        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": copy.deepcopy(self.sample_tier1_results), # <<< SecuriSense cần tier1
            "agent_findings": copy.deepcopy(initial_agent_findings), 
            "error_messages": [], "final_sarif_report": None,
        }

        result_update = activate_securi_sense_node(initial_state) # Gọi node SecuriSense

        # Assertions
        self.assertIn("agent_findings", result_update)
        final_findings = result_update["agent_findings"]
        self.assertEqual(len(final_findings), len(initial_agent_findings) + len(mock_sec_findings))
        self.assertEqual(final_findings[0]["rule_id"], "BugHunter.some_bug") # Finding cũ
        self.assertEqual(final_findings[1]["rule_id"], "SecuriSense.llm_sec_sqli")     # Finding mới

        # Kiểm tra agent được khởi tạo và gọi đúng
        MockSecuriSenseAgent.assert_called_once()
        mock_agent_instance.review.assert_called_once()
        call_args, call_kwargs = mock_agent_instance.review.call_args
        self.assertEqual(call_kwargs.get("files_data"), initial_state["files_to_review"])
        # <<< Kiểm tra tier1_tool_results được truyền vào >>>
        self.assertEqual(call_kwargs.get("tier1_tool_results"), initial_state["tier1_tool_results"], "SecuriSense review should receive tier1_tool_results") 
        
        self.assertEqual(result_update.get("error_messages", []), [])

    @patch('src.orchestrator.nodes.SecuriSenseAgent') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_activate_securi_sense_agent_raises_error(self, MockPromptManager, MockOllamaClient, MockSecuriSenseAgent):
        """Test node handles exception from SecuriSenseAgent's review method."""
        mock_agent_instance = MockSecuriSenseAgent.return_value
        error_message = "SecuriSense scan failed!"
        mock_agent_instance.review.side_effect = Exception(error_message)

        initial_agent_findings = [{"rule_id":"prev_bug"}]
        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": copy.deepcopy(self.sample_tier1_results), # Vẫn truyền tier1 vào state
            "agent_findings": copy.deepcopy(initial_agent_findings), 
            "error_messages": ["old_sec_error"], "final_sarif_report": None,
        }

        result_update = activate_securi_sense_node(initial_state)

        # agent_findings không thay đổi
        self.assertEqual(result_update.get("agent_findings"), initial_agent_findings) 
        
        # error_messages chứa lỗi cũ và lỗi mới
        final_errors = result_update.get("error_messages")
        self.assertIn("old_sec_error", final_errors)
        expected_error_substring = f"Error during SecuriSense execution: {error_message}"
        self.assertTrue(any(expected_error_substring in msg for msg in final_errors),
                        f"Expected error substring '{expected_error_substring}' not found in {final_errors}")
        
    # >>> THÊM TEST CASES CHO OPTI TUNE <<<

    @patch('src.orchestrator.nodes.OptiTuneAgent') # Patch đúng agent class
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_activate_opti_tune_success(self, MockPromptManager, MockOllamaClient, MockOptiTuneAgent):
        """Test successful activation of OptiTuneAgent."""
        mock_agent_instance = MockOptiTuneAgent.return_value
        mock_opti_findings = [
            {"file_path": "perf_critical.go", "line_start": 25, "message_text": "Inefficient string concatenation in loop", "rule_id": "OptiTune.llm_opt_loop", "level": "note", "tool_name": "OptiTune", "suggestion": "Use strings.Builder"},
            {"file_path": "perf_critical.go", "line_start": 50, "message_text": "Consider using goroutine for parallel processing", "rule_id": "OptiTune.llm_opt_concurrency", "level": "note", "tool_name": "OptiTune"}
        ]
        mock_agent_instance.review.return_value = mock_opti_findings

        # State ban đầu có thể có finding từ SecuriSense
        initial_agent_findings = [{"rule_id": "SecuriSense.some_vuln"}] 
        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": copy.deepcopy(self.sample_tier1_results), # OptiTune không dùng nhưng vẫn có thể tồn tại trong state
            "agent_findings": copy.deepcopy(initial_agent_findings), 
            "error_messages": [], "final_sarif_report": None,
        }

        result_update = activate_opti_tune_node(initial_state) # Gọi node OptiTune

        # Assertions
        self.assertIn("agent_findings", result_update)
        final_findings = result_update["agent_findings"]
        self.assertEqual(len(final_findings), len(initial_agent_findings) + len(mock_opti_findings))
        self.assertEqual(final_findings[0]["rule_id"], "SecuriSense.some_vuln") # Finding cũ
        self.assertEqual(final_findings[1]["rule_id"], "OptiTune.llm_opt_loop")    # Finding mới 1
        self.assertEqual(final_findings[2]["rule_id"], "OptiTune.llm_opt_concurrency") # Finding mới 2

        # Kiểm tra agent được khởi tạo và gọi đúng
        MockOptiTuneAgent.assert_called_once()
        mock_agent_instance.review.assert_called_once()
        call_args, call_kwargs = mock_agent_instance.review.call_args
        self.assertEqual(call_kwargs.get("files_data"), initial_state["files_to_review"])
        # OptiTune không dùng tier1_results trong logic gọi của _activate_agent_node
        self.assertNotIn("tier1_tool_results", call_kwargs, "OptiTune review should not receive tier1_tool_results") 
        
        self.assertEqual(result_update.get("error_messages", []), [])

    @patch('src.orchestrator.nodes.OptiTuneAgent') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_activate_opti_tune_agent_raises_error(self, MockPromptManager, MockOllamaClient, MockOptiTuneAgent):
        """Test node handles exception from OptiTuneAgent's review method."""
        mock_agent_instance = MockOptiTuneAgent.return_value
        error_message = "Optimization check failed!"
        mock_agent_instance.review.side_effect = Exception(error_message)

        initial_agent_findings = [{"rule_id":"prev_sec"}]
        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": {}, "agent_findings": copy.deepcopy(initial_agent_findings), 
            "error_messages": ["old_opt_error"], "final_sarif_report": None,
        }

        result_update = activate_opti_tune_node(initial_state)

        # agent_findings không thay đổi
        self.assertEqual(result_update.get("agent_findings"), initial_agent_findings) 
        
        # error_messages chứa lỗi cũ và lỗi mới
        final_errors = result_update.get("error_messages")
        self.assertIn("old_opt_error", final_errors)
        expected_error_substring = f"Error during OptiTune execution: {error_message}"
        self.assertTrue(any(expected_error_substring in msg for msg in final_errors),
                        f"Expected error substring '{expected_error_substring}' not found in {final_errors}")


# >>> THÊM TEST CLASS MỚI CHO META REVIEWER NODE <<<
class TestOrchestratorNodes_MetaReviewer(unittest.TestCase):

    def setUp(self):
        """Setup for meta_reviewer_node tests."""
        self.workspace_path = Path("/mock/workspace").resolve()
        self.mock_config_instance = MagicMock(spec=Config)
        self.mock_config_instance.ollama_base_url = "mock_ollama_url" 
        
        self.shared_context = SharedReviewContext(
            repository_name="test/meta-repo", repo_local_path=self.workspace_path,
            sha="meta123", github_event_payload={}, config_obj=self.mock_config_instance,
            pr_url=None, pr_title=None, pr_body=None, pr_diff_url=None,
            pr_number=None, base_ref=None, head_ref=None, github_event_name=None,
        )
        self.sample_files = [ ChangedFile(path="code.py", content="...", language="python") ]
        # Sample findings from previous agents
        self.initial_agent_findings = [
            {"file_path": "code.py", "line_start": 10, "message_text": "Duplicate style issue?", "rule_id": "StyleGuardian.X", "level": "note", "tool_name": "StyleGuardian"},
            {"file_path": "code.py", "line_start": 10, "message_text": "Possible bug related to style issue", "rule_id": "BugHunter.Y", "level": "warning", "tool_name": "BugHunter"},
            {"file_path": "code.py", "line_start": 50, "message_text": "Unrelated finding", "rule_id": "SecuriSense.Z", "level": "error", "tool_name": "SecuriSense"}
        ]
        self.maxDiff = None

    @patch('src.orchestrator.nodes.MetaReviewerAgent') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_run_meta_review_success_refines_findings(self, MockPromptManager, MockOllamaClient, MockMetaReviewerAgent):
        """Test successful meta-review that refines/replaces findings."""
        mock_agent_instance = MockMetaReviewerAgent.return_value
        # Giả lập MetaReviewer trả về danh sách đã được tinh chỉnh (ví dụ: gộp 2 finding đầu)
        refined_findings = [
            {"file_path": "code.py", "line_start": 10, "message_text": "Consolidated finding: Style issue might cause bug", "rule_id": "MetaReviewer.Consolidated1", "level": "warning", "tool_name": "MetaReviewer"},
            # Finding thứ 3 được giữ lại (có thể được chỉnh sửa bởi MetaReviewer)
            {"file_path": "code.py", "line_start": 50, "message_text": "Unrelated finding (MetaReviewed)", "rule_id": "SecuriSense.Z", "level": "error", "tool_name": "SecuriSense"} 
        ]
        mock_agent_instance.review.return_value = refined_findings

        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": {}, 
            "agent_findings": copy.deepcopy(self.initial_agent_findings), # Input findings
            "error_messages": [], "final_sarif_report": None,
        }

        result_update = run_meta_review_node(initial_state) # Gọi node MetaReviewer

        # Assertions
        self.assertIn("agent_findings", result_update)
        final_findings = result_update["agent_findings"]
        # Kiểm tra list findings đã bị THAY THẾ bằng list đã tinh chỉnh
        self.assertEqual(len(final_findings), len(refined_findings)) 
        self.assertEqual(final_findings, refined_findings) # So sánh nội dung

        # Kiểm tra agent được khởi tạo và gọi đúng
        MockMetaReviewerAgent.assert_called_once()
        mock_agent_instance.review.assert_called_once()
        # Kiểm tra các tham số của review() - cần all_agent_findings và files_data
        call_args, call_kwargs = mock_agent_instance.review.call_args
        self.assertEqual(call_kwargs.get("all_agent_findings"), self.initial_agent_findings)
        self.assertEqual(call_kwargs.get("files_data"), initial_state["files_to_review"])
        
        self.assertEqual(result_update.get("error_messages", []), [])

    @patch('src.orchestrator.nodes.MetaReviewerAgent') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_run_meta_review_no_initial_findings(self, MockPromptManager, MockOllamaClient, MockMetaReviewerAgent):
        """Test meta-review node skips if no initial agent findings exist."""
        mock_agent_instance = MockMetaReviewerAgent.return_value

        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": {}, 
            "agent_findings": [], # <<< Input findings rỗng
            "error_messages": [], "final_sarif_report": None,
        }

        result_update = run_meta_review_node(initial_state)

        # agent_findings vẫn rỗng
        self.assertListEqual(result_update.get("agent_findings"), [])
        # Agent không được khởi tạo hoặc gọi review
        MockMetaReviewerAgent.assert_not_called()
        mock_agent_instance.review.assert_not_called()
        # error_messages không đổi
        self.assertEqual(result_update.get("error_messages", []), [])

    @patch('src.orchestrator.nodes.MetaReviewerAgent') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') 
    @patch('src.orchestrator.nodes.PromptManager') 
    def test_run_meta_review_agent_raises_error(self, MockPromptManager, MockOllamaClient, MockMetaReviewerAgent):
        """Test node handles exception from MetaReviewerAgent's review method."""
        mock_agent_instance = MockMetaReviewerAgent.return_value
        error_message = "MetaReviewer failed!"
        mock_agent_instance.review.side_effect = Exception(error_message)

        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": {}, "agent_findings": copy.deepcopy(self.initial_agent_findings), 
            "error_messages": ["old_meta_error"], "final_sarif_report": None,
        }

        result_update = run_meta_review_node(initial_state)

        # agent_findings không thay đổi, trả về list gốc
        self.assertEqual(result_update.get("agent_findings"), self.initial_agent_findings) 
        
        # error_messages chứa lỗi cũ và lỗi mới
        final_errors = result_update.get("error_messages")
        self.assertIn("old_meta_error", final_errors)
        expected_error_substring = f"Error during MetaReviewer execution: {error_message}"
        self.assertTrue(any(expected_error_substring in msg for msg in final_errors),
                        f"Expected error substring '{expected_error_substring}' not found in {final_errors}")

# >>> THÊM TEST CLASS MỚI CHO SARIF GENERATION NODE <<<
class TestOrchestratorNodes_GenerateSarif(unittest.TestCase):

    def setUp(self):
        """Setup for generate_sarif_report_node tests."""
        self.workspace_path = Path("/mock/workspace/sarif").resolve()
        self.mock_config_instance = MagicMock(spec=Config)
        # Giả lập các thuộc tính config có thể được dùng để lấy tên/version tool
        setattr(self.mock_config_instance, 'tool_name', "MockToolFromConfig") 
        setattr(self.mock_config_instance, 'tool_version', "1.1.0")

        self.shared_context = SharedReviewContext(
            repository_name="test/sarif-repo", repo_local_path=self.workspace_path,
            sha="sarif123", github_event_payload={}, config_obj=self.mock_config_instance,
            pr_url=None, pr_title=None, pr_body=None, pr_diff_url=None,
            pr_number=None, base_ref=None, head_ref=None, github_event_name=None,
        )
        
        # Finding mẫu từ các nguồn khác nhau
        self.sample_tier1 = {
            "linters": { "python": [ {"file_path": "a.py", "line_start": 10, "message_text": "Lint error", "rule_id": "L001", "level": "warning", "tool_name":"linters.python"}]},
            "sast": { "generic": [ {"file_path": "b.java", "line_start": 20, "message_text": "SAST issue", "rule_id": "S001", "level": "error", "tool_name":"sast.generic"}]}
        }
        self.sample_agents = [
            {"file_path": "a.py", "line_start": 15, "message_text": "Agent suggestion", "rule_id": "Agent1.RuleX", "level": "note", "tool_name": "Agent1"},
        ]
        # Mock SARIF report trả về từ generator
        self.mock_sarif_dict = {"version": "2.1.0", "runs": [{"results": [...]}]} # Cấu trúc giả đơn giản
        self.maxDiff = None

    # Patch SarifGenerator tại nơi nó được import và sử dụng trong nodes.py
    @patch('src.orchestrator.nodes.SarifGenerator') 
    def test_generate_sarif_success_with_findings(self, MockSarifGenerator):
        """Test successful SARIF generation with findings."""
        # Cấu hình mock instance và các phương thức của nó
        mock_generator_instance = MockSarifGenerator.return_value
        mock_generator_instance.get_sarif_report.return_value = self.mock_sarif_dict

        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": [], # Không cần thiết cho node này
            "tier1_tool_results": copy.deepcopy(self.sample_tier1),
            "agent_findings": copy.deepcopy(self.sample_agents),
            "error_messages": [], # Không có lỗi ban đầu
            "final_sarif_report": None,
        }

        result_update = generate_sarif_report_node(initial_state)

        # 1. Kiểm tra SarifGenerator được khởi tạo đúng
        MockSarifGenerator.assert_called_once()
        init_args, init_kwargs = MockSarifGenerator.call_args
        self.assertEqual(init_kwargs.get('tool_name'), "MockToolFromConfig") # Lấy từ mock config
        self.assertEqual(init_kwargs.get('tool_version'), "1.1.0")
        self.assertEqual(init_kwargs.get('repo_uri_for_artifacts'), f"https://github.com/{self.shared_context.repository_name}")
        self.assertEqual(init_kwargs.get('commit_sha_for_artifacts'), self.shared_context.sha)
        self.assertEqual(init_kwargs.get('workspace_root_for_relative_paths'), self.shared_context.repo_local_path)

        # 2. Kiểm tra add_finding được gọi đúng số lần
        total_findings = len(self.sample_tier1["linters"]["python"]) + \
                         len(self.sample_tier1["sast"]["generic"]) + \
                         len(self.sample_agents)
        self.assertEqual(mock_generator_instance.add_finding.call_count, total_findings)

        # 3. Kiểm tra một vài lệnh gọi add_finding (tùy chọn, nếu cần chi tiết)
        mock_generator_instance.add_finding.assert_any_call(
            file_path='a.py', message_text='Lint error', rule_id='L001', 
            level='warning', line_start=10, line_end=None, col_start=None, 
            col_end=None, rule_name='linters.python' # Node tự thêm rule_name
        )
        mock_generator_instance.add_finding.assert_any_call(
            file_path='a.py', message_text='Agent suggestion', rule_id='Agent1.RuleX', 
            level='note', line_start=15, line_end=None, col_start=None, 
            col_end=None, code_snippet=None # Truyền các giá trị mặc định hoặc None
        )

        # 4. Kiểm tra set_invocation_status được gọi đúng
        mock_generator_instance.set_invocation_status.assert_called_once_with(
            successful=True, error_message=None
        )

        # 5. Kiểm tra get_sarif_report được gọi
        mock_generator_instance.get_sarif_report.assert_called_once()

        # 6. Kiểm tra state update
        self.assertIn("final_sarif_report", result_update)
        self.assertEqual(result_update["final_sarif_report"], self.mock_sarif_dict)
        self.assertEqual(result_update.get("error_messages", []), []) # Không có lỗi mới


    @patch('src.orchestrator.nodes.SarifGenerator') 
    def test_generate_sarif_success_no_findings(self, MockSarifGenerator):
        """Test SARIF generation when there are no findings."""
        mock_generator_instance = MockSarifGenerator.return_value
        mock_generator_instance.get_sarif_report.return_value = self.mock_sarif_dict

        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": [],
            "tier1_tool_results": {}, "agent_findings": [], # <<< Không có finding
            "error_messages": [], "final_sarif_report": None,
        }
        result_update = generate_sarif_report_node(initial_state)

        MockSarifGenerator.assert_called_once() # Vẫn khởi tạo
        mock_generator_instance.add_finding.assert_not_called() # Không gọi add_finding
        mock_generator_instance.set_invocation_status.assert_called_once_with(successful=True, error_message=None)
        mock_generator_instance.get_sarif_report.assert_called_once()
        self.assertEqual(result_update["final_sarif_report"], self.mock_sarif_dict)
        self.assertEqual(result_update.get("error_messages", []), [])

    @patch('src.orchestrator.nodes.SarifGenerator') 
    def test_generate_sarif_with_initial_errors(self, MockSarifGenerator):
        """Test SARIF generation when initial state has errors."""
        mock_generator_instance = MockSarifGenerator.return_value
        mock_generator_instance.get_sarif_report.return_value = self.mock_sarif_dict

        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": [],
            "tier1_tool_results": copy.deepcopy(self.sample_tier1),
            "agent_findings": [], 
            "error_messages": ["Tool X failed earlier"], # <<< Có lỗi ban đầu
            "final_sarif_report": None,
        }
        result_update = generate_sarif_report_node(initial_state)

        MockSarifGenerator.assert_called_once() 
        # add_finding vẫn được gọi cho các finding hợp lệ
        self.assertEqual(mock_generator_instance.add_finding.call_count, 
                         len(self.sample_tier1["linters"]["python"]) + len(self.sample_tier1["sast"]["generic"]))
        # set_invocation_status phải là False
        mock_generator_instance.set_invocation_status.assert_called_once()
        status_args, status_kwargs = mock_generator_instance.set_invocation_status.call_args
        self.assertFalse(status_kwargs.get("successful"))
        self.assertIsNotNone(status_kwargs.get("error_message"))
        
        mock_generator_instance.get_sarif_report.assert_called_once()
        self.assertEqual(result_update["final_sarif_report"], self.mock_sarif_dict)
        # error_messages gốc được giữ lại
        self.assertEqual(result_update.get("error_messages", []), ["Tool X failed earlier"])


    @patch('src.orchestrator.nodes.SarifGenerator') 
    def test_generate_sarif_handles_bad_finding_format(self, MockSarifGenerator):
        """Test that the node skips findings with missing required keys."""
        mock_generator_instance = MockSarifGenerator.return_value
        mock_generator_instance.get_sarif_report.return_value = self.mock_sarif_dict

        bad_tier1 = { "linters": { "python": [ {"file_path": "a.py", "message_text": "Missing line_start", "rule_id": "L002", "level": "note"} ] } } # Thiếu line_start
        bad_agent = [ {"file_path": "b.py", "line_start": 1, "rule_id": "A001", "level": "warn"} ] # Thiếu message_text

        initial_state: GraphState = {
            "shared_context": self.shared_context, "files_to_review": [],
            "tier1_tool_results": bad_tier1,
            "agent_findings": bad_agent,
            "error_messages": [], "final_sarif_report": None,
        }
        result_update = generate_sarif_report_node(initial_state)

        MockSarifGenerator.assert_called_once() 
        # add_finding không được gọi vì cả 2 finding đều thiếu key bắt buộc
        mock_generator_instance.add_finding.assert_not_called() 
        
        # error_messages phải chứa thông báo về việc skip finding
        errors = result_update.get("error_messages", [])
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("Invalid Tier 1 finding format skipped" in msg for msg in errors))
        self.assertTrue(any("Invalid Agent finding format skipped" in msg for msg in errors))
        
        # Invocation status phải là False vì có lỗi mới được thêm vào
        mock_generator_instance.set_invocation_status.assert_called_once()
        status_args, status_kwargs = mock_generator_instance.set_invocation_status.call_args
        self.assertFalse(status_kwargs.get("successful"))
        self.assertIn("report generation", status_kwargs.get("error_message", "")) # Check nội dung message lỗi

        mock_generator_instance.get_sarif_report.assert_called_once()
        self.assertEqual(result_update["final_sarif_report"], self.mock_sarif_dict)


if __name__ == '__main__':
    unittest.main()