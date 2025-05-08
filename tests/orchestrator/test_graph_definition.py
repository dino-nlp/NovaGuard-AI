# NOVAGUARD-AI/tests/orchestrator/test_graph_definition.py

import unittest
from pathlib import Path
import sys
from unittest.mock import MagicMock 
import traceback

# Thêm src vào sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import các thành phần cần test và các phụ thuộc
from src.orchestrator.graph_definition import (
    should_run_meta_reviewer, 
    initial_check_for_files,
    get_compiled_graph # Import để test việc biên dịch
) 
from src.orchestrator.state import GraphState
from src.core.shared_context import SharedReviewContext, ChangedFile
from src.core.config_loader import Config

# --- Test Class ---
class TestGraphDefinitionConditionals(unittest.TestCase):

    def setUp(self):
        """Setup mock config và context cơ bản."""
        self.mock_config_instance = MagicMock(spec=Config)
        # Giả lập các phương thức get_model... mà hàm điều kiện sử dụng
        # self.mock_config_instance.get_model_for_agent.return_value = None # Mặc định không có model

        self.shared_context = SharedReviewContext(
            repository_name="test/graph-cond", repo_local_path=Path("/mock"), sha="cond123",
            github_event_payload={}, config_obj=self.mock_config_instance,
            # Các trường khác có thể là None hoặc giá trị mặc định
             pr_url=None, pr_title=None, pr_body=None, pr_diff_url=None,
             pr_number=None, base_ref=None, head_ref=None, github_event_name=None,
        )

    # --- Test cho initial_check_for_files ---

    def test_initial_check_proceeds_with_files(self):
        """Kiểm tra trả về 'proceed_to_tier1' khi có files_to_review."""
        state = GraphState(
            files_to_review=[ChangedFile(path="a.py", content="")], # Có file
            shared_context=self.shared_context, 
            # Các trường state khác không quan trọng cho hàm điều kiện này
            tier1_tool_results={}, agent_findings=[], error_messages=[], final_sarif_report=None
        )
        result = initial_check_for_files(state)
        self.assertEqual(result, "proceed_to_tier1")

    def test_initial_check_ends_with_no_files(self):
        """Kiểm tra trả về 'no_files_to_review_end' khi files_to_review rỗng."""
        state = GraphState(
            files_to_review=[], # Không có file
            shared_context=self.shared_context, 
            tier1_tool_results={}, agent_findings=[], error_messages=[], final_sarif_report=None
        )
        result = initial_check_for_files(state)
        self.assertEqual(result, "no_files_to_review_end")

    def test_initial_check_ends_with_files_key_missing(self):
        """Kiểm tra trả về 'no_files_to_review_end' khi key 'files_to_review' thiếu trong state."""
        # Tạo state thiếu key 'files_to_review' một cách tường minh
        state = {
            "shared_context": self.shared_context, 
            "tier1_tool_results": {}, "agent_findings": [], "error_messages": [], "final_sarif_report": None
        }
        # Ép kiểu về GraphState để type checker không báo lỗi, dù runtime nó là dict thường
        result = initial_check_for_files(state) # type: ignore 
        self.assertEqual(result, "no_files_to_review_end")

    # --- Test cho should_run_meta_reviewer ---

    def test_meta_reviewer_runs_if_model_configured(self):
        """Kiểm tra trả về 'run_meta_reviewer' khi model được cấu hình."""
        # Giả lập config có model cho meta_reviewer
        self.mock_config_instance.get_model_for_agent.return_value = "some_meta_model"
        
        state = GraphState( # State không quan trọng nội dung, chỉ cần có shared_context
            shared_context=self.shared_context, files_to_review=[],
            tier1_tool_results={}, agent_findings=[], error_messages=[], final_sarif_report=None
        )
        result = should_run_meta_reviewer(state)
        
        # Kiểm tra get_model_for_agent được gọi đúng
        self.mock_config_instance.get_model_for_agent.assert_called_once_with("meta_reviewer")
        self.assertEqual(result, "run_meta_reviewer")

    def test_meta_reviewer_skips_if_model_not_configured(self):
        """Kiểm tra trả về 'skip_meta_reviewer' khi model không được cấu hình."""
        # Giả lập config KHÔNG có model cho meta_reviewer
        self.mock_config_instance.get_model_for_agent.return_value = None 
        
        state = GraphState( # State không quan trọng nội dung
             shared_context=self.shared_context, files_to_review=[],
             tier1_tool_results={}, agent_findings=[], error_messages=[], final_sarif_report=None
        )
        result = should_run_meta_reviewer(state)
        
        self.mock_config_instance.get_model_for_agent.assert_called_once_with("meta_reviewer")
        self.assertEqual(result, "skip_meta_reviewer")

# --- Test Class cho việc biên dịch graph (Đã sửa) ---
class TestGraphCompilation(unittest.TestCase):
     def test_graph_compiles_without_error(self):
         """Kiểm tra xem hàm get_compiled_graph có chạy và trả về app không."""
         mock_config = MagicMock(spec=Config)
         # Cấu hình các phương thức config được gọi trong get_compiled_graph
         mock_config.get_model_for_agent.return_value = None # Giả sử không chạy meta reviewer

         try:
             app = get_compiled_graph(app_config=mock_config)
             # <<< SỬA ASSERTION: Chỉ kiểm tra app không phải None và có các phương thức cơ bản >>>
             self.assertIsNotNone(app, "Compiled graph app should not be None")
             self.assertTrue(hasattr(app, "invoke") and callable(app.invoke), "Compiled graph should have an invoke method")
             self.assertTrue(hasattr(app, "stream") and callable(app.stream), "Compiled graph should have a stream method")
         except Exception as e:
             # Sử dụng traceback đã import để in lỗi chi tiết hơn
             self.fail(f"get_compiled_graph failed during compilation: {e}\n{traceback.format_exc()}")


if __name__ == '__main__':
    unittest.main()