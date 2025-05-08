# NOVAGUARD-AI/tests/test_integration_graph.py

import unittest
import sys
import os
from pathlib import Path
import tempfile
import yaml
import copy
import json # Cần json
import traceback # Cần traceback
from typing import Dict, Any, Optional, List
from unittest.mock import patch, MagicMock, call, ANY # Import ANY nếu cần

# Thêm src vào sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import các thành phần cần thiết từ src
from src.orchestrator.state import GraphState
from src.orchestrator.graph_definition import get_compiled_graph
from src.core.shared_context import SharedReviewContext, ChangedFile
from src.core.config_loader import Config, load_config
# Import các class cần mock (để patch đúng chỗ)
from src.core.tool_runner import ToolRunner, ToolExecutionError
from src.core.ollama_client import OllamaClientWrapper
from src.core.sarif_generator import SarifGenerator
# Import các agent class (chỉ cần để patch)
from src.agents.style_guardian_agent import StyleGuardianAgent
from src.agents.bug_hunter_agent import BugHunterAgent
from src.agents.securi_sense_agent import SecuriSenseAgent
from src.agents.opti_tune_agent import OptiTuneAgent
from src.agents.meta_reviewer_agent import MetaReviewerAgent


# --- Test Class ---
class TestIntegrationGraphRun(unittest.TestCase):

    def setUp(self):
        """Setup môi trường test với config thật và dữ liệu mẫu."""
        self.temp_dir_manager = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temp_dir_manager.name)
        self.default_config_path = self.temp_dir / "default_config"
        self.default_config_path.mkdir(); (self.default_config_path / "prompts").mkdir()
        models_data = {"default_active_mode": "test", "modes": {"production": {"agents": {"StyleGuardian": "prod_model", "BugHunter":"prod_model"}}, "test": {"agents": {"StyleGuardian": "test_style_model", "BugHunter": "test_bug_model", "SecuriSense": "test_sec_model", "OptiTune": "test_opti_model"}}}}
        with open(self.default_config_path / "models.yml", 'w') as f: yaml.dump(models_data, f)
        tools_data = {"linters": { "python": "pylint_mock --json {file_path}" }, "sast": { "generic_semgrep_project": { "command": "semgrep_mock --json -o {output_file} {project_root}", "target_type": "project" } }}
        with open(self.default_config_path / "tools.yml", 'w') as f: yaml.dump(tools_data, f)
        os.environ["NOVAGUARD_ACTIVE_MODE"] = "test" 
        self.config = load_config(default_config_dir=self.default_config_path, project_config_dir_str=None, ollama_base_url="http://mock-ollama:11434", workspace_path=self.temp_dir)
        self.workspace_path = self.temp_dir / "repo"; self.workspace_path.mkdir()
        self.py_file_path = "src/code_to_review.py" # Lưu lại để dùng trong mock findings
        py_file_abs = self.workspace_path / self.py_file_path; py_file_abs.parent.mkdir(parents=True, exist_ok=True); py_file_abs.write_text("def hello():\n  print('world') # Style issue?\n  # Bug here?\n  # Security risk?\n  # Optimize?")
        self.sample_files = [ChangedFile(path=self.py_file_path, content=py_file_abs.read_text(), language="python")]
        self.shared_context = SharedReviewContext(repository_name="test/integration-repo", repo_local_path=self.workspace_path, sha="integ123", github_event_payload={"pull_request":{"number":1}}, config_obj=self.config, pr_url=None, pr_title=None, pr_body=None, pr_diff_url=None, pr_number=1, base_ref="main", head_ref="feature", github_event_name="pull_request")
        
        # --- ĐỊNH NGHĨA MOCK FINDINGS ĐÚNG CHUẨN ---
        # Phải bao gồm đủ các key: file_path, line_start, message_text, rule_id, level, tool_name
        self.mock_pylint_findings = [{"file_path": self.py_file_path, "line_start": 2, "message_text": "Mock Pylint: Bad whitespace", "rule_id": "W0311", "level": "warning", "tool_name": "linters.python"}]
        self.mock_semgrep_findings = {"results": [{"check_id": "mock-sast-rule", "path": self.py_file_path, "start": {"line": 4}, "extra": {"message": "Mock Semgrep: Hardcoded secret?", "severity": "ERROR"}}]} # Node sẽ chuẩn hóa thành finding dict
        
        self.mock_style_finding_list = [{"file_path": self.py_file_path, "line_start": 2, "message_text": "LLM Style: Use 4 spaces.", "rule_id": "StyleGuardian.LLM_STYLE01", "level": "note", "tool_name": "StyleGuardian", "suggestion": "indent = '    '"}]
        self.mock_bug_finding_list = [{"file_path": self.py_file_path, "line_start": 3, "message_text": "LLM Bug: Potential off-by-one.", "rule_id": "BugHunter.LLM_BUG01", "level": "warning", "tool_name": "BugHunter"}]
        self.mock_sec_finding_list = [{"file_path": self.py_file_path, "line_start": 4, "message_text": "LLM Security: Confirmed hardcoded secret.", "rule_id": "SecuriSense.LLM_SEC01", "level": "error", "tool_name": "SecuriSense"}]
        self.mock_opti_finding_list = [{"file_path": self.py_file_path, "line_start": 5, "message_text": "LLM Optimize: Can use list comprehension.", "rule_id": "OptiTune.LLM_OPT01", "level": "note", "tool_name": "OptiTune"}]
        self.mock_meta_finding_list = [{"file_path": self.py_file_path, "line_start": 4, "message_text": "MetaReviewer: Prioritized hardcoded secret.", "rule_id": "MetaReviewer.Priority", "level": "error", "tool_name":"MetaReviewer"}]
        self.mock_final_sarif = {"version": "2.1.0", "runs": [{"results": [{"message":{"text":"Mock SARIF Generated"}}]}]} # Sửa lại message để phân biệt

    def tearDown(self):
        self.temp_dir_manager.cleanup()
        if "NOVAGUARD_ACTIVE_MODE" in os.environ: del os.environ["NOVAGUARD_ACTIVE_MODE"]
            
    # Patch các class tại nơi chúng được import và sử dụng trong nodes.py
    @patch('src.orchestrator.nodes.SarifGenerator') 
    @patch('src.orchestrator.nodes.OllamaClientWrapper') # OllamaClient dùng bởi _activate_agent_node
    @patch('src.orchestrator.nodes.ToolRunner') # ToolRunner dùng bởi run_tier1_tools_node
    # Patch các agent class để kiểm soát return value của chúng
    @patch('src.orchestrator.nodes.MetaReviewerAgent') 
    @patch('src.orchestrator.nodes.OptiTuneAgent') 
    @patch('src.orchestrator.nodes.SecuriSenseAgent') 
    @patch('src.orchestrator.nodes.BugHunterAgent') 
    @patch('src.orchestrator.nodes.StyleGuardianAgent') 
    def test_graph_invocation_success_flow(
        self, MockStyleAgent, MockBugAgent, MockSecAgent, MockOptiAgent, MockMetaAgent, 
        MockToolRunner, MockOllamaClient, MockSarifGenerator): # << Sửa lại: Mock Agent Class trước
        """Integration test for the main graph execution flow."""

        # --- Configure Mocks ---
        mock_tool_runner_instance = MockToolRunner.return_value
        # mock_ollama_client_instance = MockOllamaClient.return_value # Không cần mock invoke vì agent bị mock
        mock_sarif_generator_instance = MockSarifGenerator.return_value

        # Config mock ToolRunner.run
        def tool_run_side_effect(*args, **kwargs):
            cat = kwargs.get("tool_category"); key = kwargs.get("tool_key")
            if cat == "linters" and key == "python": return self.mock_pylint_findings
            if cat == "sast" and key == "generic_semgrep_project": return self.mock_semgrep_findings
            return None
        mock_tool_runner_instance.run.side_effect = tool_run_side_effect

        # <<< SỬA LỖI: Config mock agent review methods để trả về list finding ĐÚNG CHUẨN >>>
        MockStyleAgent.return_value.review.return_value = self.mock_style_finding_list
        MockBugAgent.return_value.review.return_value = self.mock_bug_finding_list
        MockSecAgent.return_value.review.return_value = self.mock_sec_finding_list
        MockOptiAgent.return_value.review.return_value = self.mock_opti_finding_list
        MockMetaAgent.return_value.review.return_value = self.mock_meta_finding_list 

        # Config mock SarifGenerator
        mock_sarif_generator_instance.get_sarif_report.return_value = self.mock_final_sarif
        # add_finding và set_invocation_status không cần return value, chỉ cần kiểm tra call

        # --- Prepare Initial State ---
        initial_state = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(self.sample_files),
            "tier1_tool_results": {}, "agent_findings": [], "error_messages": [],
            "final_sarif_report": None,
        }

        # --- Get Compiled Graph ---
        run_meta = "MetaReviewer" in self.config.current_mode_models.get("agents", {})
        app = get_compiled_graph(app_config=self.config) 

        # --- Invoke Graph ---
        final_state = app.invoke(initial_state)

        # --- Assertions ---
        
        # 1. Check Final State Structure and Errors
        self.assertIsInstance(final_state, dict)
        # <<< SỬA ASSERTION: Kiểm tra error_messages phải rỗng >>>
        self.assertEqual(final_state.get("error_messages", []), [], f"Graph run produced errors: {final_state.get('error_messages')}")

        # 2. Check ToolRunner Calls and Tier1 Results
        mock_tool_runner_instance.run.assert_any_call(tool_category='linters', tool_key='python', target_file_relative_path=self.py_file_path, expect_json_output=True)
        mock_tool_runner_instance.run.assert_any_call(tool_category='sast', tool_key='generic_semgrep_project', target_file_relative_path=None, expect_json_output=True)
        self.assertIn("tier1_tool_results", final_state); tier1 = final_state["tier1_tool_results"]
        self.assertIn("linters", tier1); self.assertIn("python", tier1["linters"]); self.assertEqual(len(tier1["linters"]["python"]), 1) # Chỉ có 1 finding từ pylint mock
        self.assertIn("sast", tier1); self.assertIn("generic_semgrep_project", tier1["sast"]); self.assertEqual(len(tier1["sast"]["generic_semgrep_project"]), 1) # Chỉ có 1 finding từ semgrep mock (sau chuẩn hóa)

        # 3. Check Agent Calls and Agent Findings
        MockStyleAgent.return_value.review.assert_called_once()
        MockBugAgent.return_value.review.assert_called_once()
        MockSecAgent.return_value.review.assert_called_once()
        MockOptiAgent.return_value.review.assert_called_once()
        
        self.assertIn("agent_findings", final_state); agent_results = final_state["agent_findings"]

        if run_meta:
             MockMetaAgent.assert_called_once()
             self.assertEqual(len(agent_results), len(self.mock_meta_finding_list))
             self.assertEqual(agent_results[0]['rule_id'], self.mock_meta_finding_list[0]['rule_id'])
        else:
             MockMetaAgent.assert_not_called()
             expected_agent_findings_count = len(self.mock_style_finding_list) + len(self.mock_bug_finding_list) + len(self.mock_sec_finding_list) + len(self.mock_opti_finding_list)
             self.assertEqual(len(agent_results), expected_agent_findings_count)
             rule_ids = {f.get("rule_id") for f in agent_results}
             expected_rule_ids = { f["rule_id"] for f in self.mock_style_finding_list + self.mock_bug_finding_list + self.mock_sec_finding_list + self.mock_opti_finding_list }
             self.assertSetEqual(rule_ids, expected_rule_ids)
             
        # 4. Check SarifGenerator Calls and Final Report
        MockSarifGenerator.assert_called_once() 
        # <<< Sửa logic tính expected_add_finding_calls >>>
        expected_tier1_count = len(tier1["linters"]["python"]) + len(tier1["sast"]["generic_semgrep_project"])
        expected_agent_count = len(agent_results) # agent_results là list cuối cùng
        expected_add_finding_calls = expected_tier1_count + expected_agent_count
        
        # Kiểm tra từng finding được truyền vào add_finding nếu cần debug sâu hơn
        # for call_args in mock_sarif_generator_instance.add_finding.call_args_list:
        #    print("add_finding called with kwargs:", call_args.kwargs) 

        self.assertEqual(mock_sarif_generator_instance.add_finding.call_count, expected_add_finding_calls)
        mock_sarif_generator_instance.set_invocation_status.assert_called_once_with(successful=True, error_message=None)
        mock_sarif_generator_instance.get_sarif_report.assert_called_once()
        self.assertIn("final_sarif_report", final_state)
        self.assertEqual(final_state["final_sarif_report"], self.mock_final_sarif)

# --- Main execution ---
if __name__ == '__main__':
    unittest.main()