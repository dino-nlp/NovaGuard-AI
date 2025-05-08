# NOVAGUARD-AI/tests/orchestrator/test_nodes.py

import unittest
from pathlib import Path
import sys
import copy
from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock # <<< Import MagicMock

# Thêm src vào sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import các thành phần cần thiết
from src.orchestrator.state import GraphState
from src.orchestrator.nodes import prepare_review_files_node # Chỉ test node này trước
from src.core.shared_context import SharedReviewContext, ChangedFile
from src.core.config_loader import Config # <<< Import Config thật sự

# --- Test Class ---
class TestOrchestratorNodes_PrepareFiles(unittest.TestCase):

    def setUp(self):
        """Set up common data for prepare_review_files_node tests."""
        self.workspace_path = Path("/mock/workspace").resolve()

        # Dùng MagicMock(spec=Config)
        self.mock_config_instance = MagicMock(spec=Config)
        # Set các thuộc tính cần thiết nếu có, ví dụ:
        # self.mock_config_instance.some_needed_attribute = "value"

        # Tạo SharedReviewContext mẫu với mock config hợp lệ
        # Đảm bảo cung cấp đủ các trường bắt buộc của SharedReviewContext
        self.shared_context = SharedReviewContext(
            repository_name="test/repo",
            repo_local_path=self.workspace_path,
            sha="abcdef123",
            github_event_payload={},
            config_obj=self.mock_config_instance, # Truyền MagicMock
            # Thêm các trường khác nếu cần thiết và bắt buộc
            pr_url=None,
            pr_title=None,
            pr_body=None,
            pr_diff_url=None,
            pr_number=None,
            base_ref=None,
            head_ref=None,
            github_event_name=None,
        )

    def test_prepare_files_basic(self):
        """Test basic file preparation and language guessing."""
        initial_files = [
            ChangedFile(path="src/main.py", content="print('hello')"),
            ChangedFile(path="README.md", content="# Title"),
            ChangedFile(path="lib/script.js", content="console.log('hi');"),
            ChangedFile(path="data.unknown", content="some data"),
        ]
        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(initial_files),
            "error_messages": [],
            "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None,
        }
        result_update = prepare_review_files_node(initial_state)
        
        self.assertIn("files_to_review", result_update)
        self.assertIn("error_messages", result_update)
        updated_files = result_update.get("files_to_review", [])
        self.assertEqual(len(updated_files), len(initial_files))
        languages_found = {f.path: f.language for f in updated_files}
        self.assertEqual(languages_found.get("src/main.py"), "python")
        self.assertEqual(languages_found.get("README.md"), "markdown")
        self.assertEqual(languages_found.get("lib/script.js"), "javascript")
        self.assertIsNone(languages_found.get("data.unknown"))
        # Lỗi ban đầu là rỗng, và node không thêm lỗi mới trong trường hợp thành công
        self.assertEqual(len(result_update.get("error_messages", [])), 0)


    def test_prepare_files_empty_input(self):
        """Test node behavior when the initial files_to_review list is empty."""
        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": [],
            "error_messages": ["initial error"], # Giữ lại lỗi ban đầu
            "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None,
        }

        result_update = prepare_review_files_node(initial_state)

        self.assertIn("files_to_review", result_update)
        self.assertIn("error_messages", result_update)
        self.assertEqual(len(result_update.get("files_to_review", [])), 0)
        
        # >>> SỬA ASSERTION Ở ĐÂY <<<
        # Node không còn thêm lỗi nếu input ban đầu rỗng, nên error_messages chỉ chứa lỗi ban đầu
        self.assertEqual(result_update.get("error_messages"), ["initial error"])

    def test_prepare_files_language_already_set(self):
        """Test that existing language attribute is not overridden."""
        initial_files = [
            ChangedFile(path="src/main.py", content="print('hello')", language="override_python"),
        ]
        initial_state: GraphState = {
            "shared_context": self.shared_context,
            "files_to_review": copy.deepcopy(initial_files),
            "error_messages": [],
            "tier1_tool_results": {}, "agent_findings": [], "final_sarif_report": None,
        }
        result_update = prepare_review_files_node(initial_state)
        updated_files = result_update.get("files_to_review", [])
        self.assertEqual(len(updated_files), 1)
        self.assertEqual(updated_files[0].language, "override_python")


if __name__ == '__main__':
    unittest.main()