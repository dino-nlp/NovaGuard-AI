# NOVAGUARD-AI/tests/core/test_config_loader.py
import os
import sys
import unittest
import yaml
from pathlib import Path
import tempfile
import logging

# Thêm src vào sys.path để có thể import các module từ src
# Điều này quan trọng khi chạy test từ thư mục gốc của project
# bằng lệnh như: python -m unittest discover tests
# Hoặc nếu bạn dùng một test runner như pytest, nó thường tự xử lý.
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import Config, load_config, _deep_merge_dicts

# Tắt bớt logging của application trong khi chạy test, trừ khi bạn muốn debug
# logging.disable(logging.CRITICAL) # Bỏ comment nếu muốn tắt hoàn toàn
# Hoặc set level cao hơn cho logger của app
# logging.getLogger("src.core.config_loader").setLevel(logging.WARNING)


class TestDeepMergeDicts(unittest.TestCase):
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        expected = {"a": 1, "b": 3, "c": 4}
        self.assertEqual(_deep_merge_dicts(base, override), expected)

    def test_nested_merge(self):
        base = {"a": 1, "b": {"x": 10, "y": 20}}
        override = {"b": {"y": 30, "z": 40}, "c": 3}
        expected = {"a": 1, "b": {"x": 10, "y": 30, "z": 40}, "c": 3}
        self.assertEqual(_deep_merge_dicts(base, override), expected)

    def test_override_non_dict_with_dict(self):
        base = {"a": 1, "b": "not a dict"}
        override = {"b": {"x": 10}}
        expected = {"a": 1, "b": {"x": 10}}
        self.assertEqual(_deep_merge_dicts(base, override), expected)

    def test_override_dict_with_non_dict(self):
        base = {"a": 1, "b": {"x": 10}}
        override = {"b": "now a string"}
        expected = {"a": 1, "b": "now a string"}
        self.assertEqual(_deep_merge_dicts(base, override), expected)

    def test_list_override(self):
        base = {"a": [1, 2]}
        override = {"a": [3, 4]}
        expected = {"a": [3, 4]} # Lists are overridden, not merged element-wise
        self.assertEqual(_deep_merge_dicts(base, override), expected)


class TestConfigLoader(unittest.TestCase):

    def setUp(self):
        """Tạo một thư mục tạm thời cho các file config của test."""
        self.temp_dir_manager = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temp_dir_manager.name)

        self.default_config_path = self.temp_dir / "default_config"
        self.default_config_path.mkdir()
        (self.default_config_path / "prompts").mkdir()

        self.project_config_path = self.temp_dir / "project_config"
        self.project_config_path.mkdir()
        (self.project_config_path / "prompts").mkdir()

        self.workspace_path = self.temp_dir / "workspace" # Giả lập GITHUB_WORKSPACE
        self.workspace_path.mkdir()
        
        # Lưu trữ giá trị gốc của biến môi trường nếu có
        self.original_novaguard_active_mode = os.environ.get("NOVAGUARD_ACTIVE_MODE")


    def tearDown(self):
        """Dọn dẹp thư mục tạm thời."""
        self.temp_dir_manager.cleanup()
        # Khôi phục biến môi trường
        if self.original_novaguard_active_mode is None:
            if "NOVAGUARD_ACTIVE_MODE" in os.environ:
                del os.environ["NOVAGUARD_ACTIVE_MODE"]
        else:
            os.environ["NOVAGUARD_ACTIVE_MODE"] = self.original_novaguard_active_mode


    def _write_yaml(self, path: Path, data: dict):
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f)

    def _write_text(self, path: Path, text: str):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)

    def test_load_defaults_only(self):
        """Kiểm tra load config chỉ với các file mặc định."""
        default_models_data = {
            "default_active_mode": "production",
            "modes": {
                "production": {"agents": {"StyleGuardian": "prod_style_model"}},
                "test": {"agents": {"StyleGuardian": "test_style_model"}}
            }
        }
        self._write_yaml(self.default_config_path / "models.yml", default_models_data)
        self._write_yaml(self.default_config_path / "tools.yml", {"linters": {"python": "pylint_cmd"}})
        self._write_text(self.default_config_path / "prompts" / "greet.md", "Hello {{ name }}")

        config = load_config(
            default_config_dir=self.default_config_path,
            project_config_dir_str=None,
            ollama_base_url="http://ollama-default:11434",
            workspace_path=self.workspace_path
        )

        self.assertIsInstance(config, Config)
        self.assertEqual(config.ollama_base_url, "http://ollama-default:11434")
        self.assertEqual(config.active_mode, "production")
        self.assertEqual(config.get_model_for_agent("StyleGuardian"), "prod_style_model")
        self.assertEqual(config.get_tool_command_template("linters", "python"), "pylint_cmd")
        self.assertEqual(config.get_prompt_template("greet"), "Hello {{ name }}")
        self.assertFalse(config.project_config_loaded)

    def test_load_with_project_overrides(self):
        """Kiểm tra load config với project-specific overrides."""
        default_models_data = {
            "default_active_mode": "production",
            "modes": {
                "production": {
                    "agents": {"StyleGuardian": "default_style", "BugHunter": "default_bug"}
                }
            }
        }
        project_models_data = {
            "modes": { # Ghi đè mode production
                "production": {"agents": {"StyleGuardian": "project_style_override"}}
            }
        }
        self._write_yaml(self.default_config_path / "models.yml", default_models_data)
        self._write_yaml(self.project_config_path / "models.yml", project_models_data)

        self._write_yaml(self.default_config_path / "tools.yml", {"linters": {"python": "default_pylint"}})
        self._write_yaml(self.project_config_path / "tools.yml", {"sast": {"semgrep": "project_semgrep"}}) # Thêm mới

        self._write_text(self.default_config_path / "prompts" / "common.md", "Default common prompt")
        self._write_text(self.project_config_path / "prompts" / "common.md", "Project common prompt override")
        self._write_text(self.project_config_path / "prompts" / "project_specific.md", "Project only prompt")

        config = load_config(
            default_config_dir=self.default_config_path,
            project_config_dir_str=str(self.project_config_path.relative_to(self.temp_dir)), # cần đường dẫn tương đối với workspace
            ollama_base_url="http://ollama:11434",
            workspace_path=self.temp_dir # workspace_path là cha của project_config_path
        )
        
        self.assertTrue(config.project_config_loaded)
        self.assertEqual(config.get_model_for_agent("StyleGuardian"), "project_style_override") # Overridden
        self.assertEqual(config.get_model_for_agent("BugHunter"), "default_bug") # From default, not overridden

        self.assertEqual(config.get_tool_command_template("linters", "python"), "default_pylint") # From default
        self.assertEqual(config.get_tool_command_template("sast", "semgrep"), "project_semgrep") # From project

        self.assertEqual(config.get_prompt_template("common"), "Project common prompt override") # Overridden
        self.assertEqual(config.get_prompt_template("project_specific"), "Project only prompt") # From project

    def test_active_mode_from_env_var(self):
        """Kiểm tra active_mode được set từ biến môi trường."""
        os.environ["NOVAGUARD_ACTIVE_MODE"] = "test_env"
        models_data = {
            "default_active_mode": "production",
            "modes": {
                "production": {"agents": {"GenericAgent": "prod_model"}},
                "test_env": {"agents": {"GenericAgent": "test_env_model"}}
            }
        }
        self._write_yaml(self.default_config_path / "models.yml", models_data)

        config = load_config(self.default_config_path, None, "url", self.workspace_path)
        self.assertEqual(config.active_mode, "test_env")
        self.assertEqual(config.get_model_for_agent("GenericAgent"), "test_env_model")

    def test_active_mode_fallback_when_mode_empty(self):
        """Kiểm tra fallback nếu active_mode được cấu hình nhưng không có model entries."""
        models_data = {
            "default_active_mode": "empty_test_mode", # Mode này sẽ không có 'agents'
            "modes": {
                "production": {"agents": {"StyleGuardian": "prod_model_for_fallback"}},
                "empty_test_mode": {
                    # không có key 'agents'
                }
            }
        }
        self._write_yaml(self.default_config_path / "models.yml", models_data)
        config = load_config(self.default_config_path, None, "url", self.workspace_path)
        
        self.assertEqual(config.active_mode, "empty_test_mode")
        # Config class hiện tại fallback về production nếu current_mode_models rỗng
        self.assertEqual(config.get_model_for_agent("StyleGuardian"), "prod_model_for_fallback")


    def test_missing_default_models_file(self):
        """Kiểm tra trường hợp file models.yml mặc định bị thiếu."""
        # Không tạo models.yml
        self._write_yaml(self.default_config_path / "tools.yml", {"linters": {"python": "pylint_cmd"}})
        config = load_config(self.default_config_path, None, "url", self.workspace_path)
        self.assertEqual(config.models_config_full.get("modes",{}), {}) # models_config_full sẽ không có modes
        self.assertIsNone(config.get_model_for_agent("AnyAgent")) # Không có model nào được load

    def test_malformed_yaml_file(self):
        """Kiểm tra trường hợp file YAML bị sai định dạng."""
        self._write_text(self.default_config_path / "models.yml", "key: value\n  bad_indent: problem")
        config = load_config(self.default_config_path, None, "url", self.workspace_path)
        # `_load_yaml_file` sẽ trả về None và log warning, nên models_cfg sẽ rỗng
        self.assertEqual(config.models_config_full, {}) # hoặc giá trị mặc định nếu có merge
        self.assertIsNone(config.get_model_for_agent("AnyAgent"))

    def test_empty_prompts_dir(self):
        """Kiểm tra trường hợp thư mục prompts rỗng."""
        # Thư mục prompts đã được tạo trong setUp, nhưng không có file nào trong đó.
        config = load_config(self.default_config_path, None, "url", self.workspace_path)
        self.assertEqual(config.prompt_templates, {})


if __name__ == '__main__':
    unittest.main()