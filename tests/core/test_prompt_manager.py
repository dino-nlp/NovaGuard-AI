# NOVAGUARD-AI/tests/core/test_prompt_manager.py
import os
import sys
import unittest
from pathlib import Path
from typing import Dict, Optional, Set # Thêm Set

# Thêm src vào sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.prompt_manager import PromptManager
# Import Config chỉ để type hint, chúng ta sẽ dùng MockConfig
from src.core.config_loader import Config

# Mock Config class chỉ chứa phần cần thiết cho PromptManager
class MockConfig:
    """A simplified mock of the Config class for PromptManager tests."""
    def __init__(self, templates: Dict[str, str]):
        self.prompt_templates: Dict[str, str] = templates
        # Các thuộc tính khác của Config không cần thiết cho test PromptManager

    def get_prompt_template(self, prompt_name: str) -> Optional[str]:
        """Mimics the get_prompt_template method."""
        return self.prompt_templates.get(prompt_name)

# --- Test Class ---
class TestPromptManager(unittest.TestCase):

    def setUp(self):
        """Set up a PromptManager instance with mock config and templates."""
        self.test_templates = {
            "greeting": "Hello {{ name }}!",
            "static": "This is a static prompt.",
            "complex": "Data: {{ data.value }}. User: {{ user }}. Count: {{ count }}.",
            "syntax_error": "Hello {{ name", # Lỗi cú pháp Jinja
            "needs_var": "Value is {{ required_var }}.", # Cần biến required_var
        }
        self.mock_config = MockConfig(templates=self.test_templates)
        # Khởi tạo PromptManager với mock config
        # Nếu Jinja2 không được cài, dòng này sẽ raise ImportError
        try:
            self.prompt_manager = PromptManager(config=self.mock_config)
        except ImportError as e:
            self.skipTest(f"Skipping PromptManager tests: {e}") # Bỏ qua test nếu thiếu Jinja2


    def test_initialization(self):
        """Test if PromptManager initializes correctly."""
        self.assertIsInstance(self.prompt_manager, PromptManager)
        # Kiểm tra xem Jinja environment có được tạo không (nếu không lỗi ở setUp)
        self.assertTrue(hasattr(self.prompt_manager, 'jinja_env'))

    def test_get_available_prompt_names(self):
        """Test retrieving the names of available prompts."""
        expected_names = list(self.test_templates.keys())
        # So sánh set để không phụ thuộc thứ tự
        self.assertSetEqual(set(self.prompt_manager.get_available_prompt_names()), set(expected_names))

    def test_get_prompt_simple_render(self):
        """Test rendering a simple template with one variable."""
        rendered = self.prompt_manager.get_prompt("greeting", {"name": "World"})
        self.assertEqual(rendered, "Hello World!")

    def test_get_prompt_complex_render(self):
        """Test rendering a template with multiple and nested variables."""
        variables = {
            "data": {"value": 123},
            "user": "Alice",
            "count": 5
        }
        rendered = self.prompt_manager.get_prompt("complex", variables)
        self.assertEqual(rendered, "Data: 123. User: Alice. Count: 5.")

    def test_get_prompt_no_variables_needed(self):
        """Test rendering a template that doesn't have variables."""
        rendered = self.prompt_manager.get_prompt("static")
        self.assertEqual(rendered, "This is a static prompt.")
        # Cũng test khi truyền biến thừa vào template tĩnh
        rendered_extra_vars = self.prompt_manager.get_prompt("static", {"extra": "ignored"})
        self.assertEqual(rendered_extra_vars, "This is a static prompt.")

    def test_get_prompt_missing_template(self):
        """Test requesting a template name that doesn't exist."""
        # Nên ghi log warning, nhưng hàm trả về None
        rendered = self.prompt_manager.get_prompt("non_existent_template")
        self.assertIsNone(rendered)

    def test_get_prompt_missing_variable(self):
        """Test rendering failure when a required variable is missing (StrictUndefined)."""
        # Hàm nên trả về None và ghi log error
        rendered = self.prompt_manager.get_prompt("needs_var", {"other_var": "value"})
        self.assertIsNone(rendered, "Expected None when required variable is missing due to StrictUndefined")

    def test_get_prompt_syntax_error(self):
        """Test rendering failure when the template has a syntax error."""
        # Hàm nên trả về None và ghi log error
        rendered = self.prompt_manager.get_prompt("syntax_error", {"name": "Test"})
        self.assertIsNone(rendered, "Expected None for template with syntax error")

    def test_get_template_variables_found(self):
        """Test finding undeclared variables in a template."""
        expected_vars = {"data", "user", "count"}
        found_vars = self.prompt_manager.get_template_variables("complex")
        self.assertIsInstance(found_vars, set)
        self.assertSetEqual(found_vars, expected_vars)

    def test_get_template_variables_none_found(self):
        """Test finding variables in a template with no variables."""
        expected_vars = set()
        found_vars = self.prompt_manager.get_template_variables("static")
        self.assertIsInstance(found_vars, set)
        self.assertSetEqual(found_vars, expected_vars)

    def test_get_template_variables_missing_template(self):
        """Test finding variables for a non-existent template."""
        found_vars = self.prompt_manager.get_template_variables("non_existent")
        self.assertIsNone(found_vars)
        
    def test_get_template_variables_syntax_error(self):
        """Test finding variables in a template with syntax error."""
        # Parsing sẽ thất bại, hàm nên trả về None
        found_vars = self.prompt_manager.get_template_variables("syntax_error")
        self.assertIsNone(found_vars)


if __name__ == '__main__':
    # Thêm một chút setup để đảm bảo import hoạt động khi chạy file trực tiếp (ít phổ biến hơn)
    # if str(project_root) not in sys.path:
    #      sys.path.insert(0, str(project_root))
    unittest.main()