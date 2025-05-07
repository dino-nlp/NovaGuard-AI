# NOVAGUARD-AI/src/core/config_loader.py
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Pydantic is not strictly needed for the Config class here if we just use it as a container,
# but if we wanted to add validation for the structure of models_config or tools_config,
# we could make them Pydantic models themselves. For now, simple dicts.

logger = logging.getLogger(__name__)

DEFAULT_MODELS_FILE = "models.yml"
DEFAULT_TOOLS_FILE = "tools.yml"
DEFAULT_PROMPTS_DIR_NAME = "prompts"
PROMPT_FILE_EXTENSIONS = [".md", ".txt"]


def _load_yaml_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Loads a YAML file and returns its content as a dictionary."""
    if not file_path.is_file():
        logger.warning(f"Configuration file not found: {file_path}")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
            if not isinstance(content, dict):
                logger.warning(f"Configuration file {file_path} does not contain a dictionary at the root.")
                return None
            return content
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None

def _load_prompt_templates_from_dir(prompts_dir: Path) -> Dict[str, str]:
    """Loads all prompt templates from a directory."""
    templates: Dict[str, str] = {}
    if not prompts_dir.is_dir():
        logger.debug(f"Prompts directory not found or not a directory: {prompts_dir}")
        return templates

    for file_path in prompts_dir.iterdir():
        if file_path.is_file() and file_path.suffix in PROMPT_FILE_EXTENSIONS:
            try:
                templates[file_path.stem] = file_path.read_text(encoding='utf-8')
                logger.debug(f"Loaded prompt template: {file_path.name}")
            except Exception as e:
                logger.warning(f"Could not load prompt template {file_path}: {e}")
    return templates

def _deep_merge_dicts(base: Dict[Any, Any], override: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Recursively merges 'override' dict into 'base' dict.
    If a key exists in both and both values are dicts, it recursively merges them.
    Otherwise, the value from 'override' takes precedence.
    Lists are overridden, not merged item by item.
    """
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


class Config:
    """
    Configuration class for NovaGuard AI.
    Holds settings for Ollama, models, tools, and prompt templates.
    """
    def __init__(self,
                ollama_base_url: str,
                models_config: Dict[str, Any],
                tools_config: Dict[str, Any],
                prompt_templates: Dict[str, str],
                active_mode: str, 
                project_config_loaded: bool = False):
        self.ollama_base_url = ollama_base_url
        self.models_config_full = models_config 
        self.tools_config = tools_config
        self.prompt_templates = prompt_templates
        self.active_mode = active_mode
        self.project_config_loaded = project_config_loaded
        
        self.current_mode_models = self.models_config_full.get("modes", {}).get(self.active_mode, {})
        if not self.current_mode_models:
            logger.warning(f"Model configuration for active_mode '{self.active_mode}' not found. Falling back to potential shared_models or empty.")
            # Bạn có thể thêm logic fallback ở đây, ví dụ dùng production nếu test mode thiếu, hoặc một section 'shared_models'
            self.current_mode_models = self.models_config_full.get("modes", {}).get("production", {}) # Fallback to production as an example


        logger.info(f"Config initialized. Ollama URL: {self.ollama_base_url}")
        logger.debug(f"Models config: {self.models_config_full}")
        logger.debug(f"Tools config: {self.tools_config}")
        logger.debug(f"Loaded {len(self.prompt_templates)} prompt templates. Project config loaded: {self.project_config_loaded}")

    def get_model_for_agent(self, agent_name: str) -> Optional[str]:
        model_name = self.current_mode_models.get("agents", {}).get(agent_name)
        if not model_name:
            logger.warning(f"Model name not found for agent: {agent_name} in active mode: {self.active_mode}")
            # Fallback strategy: check shared_models or production if desired
            # shared_model = self.models_config_full.get("shared_models", {}).get(agent_name)
            # if shared_model: return shared_model
        return model_name

    def get_model_for_task(self, task_name: str) -> Optional[str]: # Tương tự cho tasks
        model_name = self.current_mode_models.get("tasks", {}).get(task_name)
        if not model_name:
            logger.warning(f"Model name not found for task: {task_name} in active mode: {self.active_mode}")
        return model_name

    def get_tool_command_template(self, tool_category: str, tool_key: str) -> Optional[str]:
        """
        Retrieves the command template for a specific tool.
        Example path in tools.yml: <tool_category> -> <tool_key> (e.g., linters -> python)
        The tool_key could be a language or a specific tool name.
        """
        command_template = self.tools_config.get(tool_category, {}).get(tool_key)
        if not command_template:
            logger.warning(f"Command template not found for tool category '{tool_category}' and key '{tool_key}'")
        return command_template
    
    def get_tool_config(self, tool_category: str, tool_key: str) -> Optional[Union[str, Dict[str, Any]]]:
        """
        Retrieves the full configuration for a specific tool, which might be a string (command)
        or a dictionary (for more complex settings).
        Example path in tools.yml: <tool_category> -> <tool_key>
        """
        tool_cfg = self.tools_config.get(tool_category, {}).get(tool_key)
        if not tool_cfg:
            logger.warning(f"Configuration not found for tool category '{tool_category}' and key '{tool_key}'")
        return tool_cfg


    def get_prompt_template(self, prompt_name: str) -> Optional[str]:
        """Retrieves a specific prompt template by its name (filename stem)."""
        template = self.prompt_templates.get(prompt_name)
        if not template:
            logger.warning(f"Prompt template not found: {prompt_name}")
        return template


def load_config(default_config_dir: Path,
                project_config_dir_str: Optional[str],
                ollama_base_url: str,
                workspace_path: Path) -> Config:
    """
    Loads configuration from default and project-specific paths.
    Project-specific configurations override defaults.

    Args:
        default_config_dir: Path to the directory containing default config files (models.yml, tools.yml, prompts/).
        project_config_dir_str: Optional string path to the project-specific config directory,
                                relative to the workspace_path.
        ollama_base_url: The base URL for the Ollama server.
        workspace_path: The path to the GitHub workspace.

    Returns:
        An instance of the Config class.
    """
    models_cfg: Dict[str, Any] = {}
    tools_cfg: Dict[str, Any] = {}
    prompt_tpls: Dict[str, str] = {}
    project_config_actually_loaded = False

    # 1. Load default configurations
    logger.info(f"Loading default configurations from: {default_config_dir}")
    default_models_file = default_config_dir / DEFAULT_MODELS_FILE
    default_tools_file = default_config_dir / DEFAULT_TOOLS_FILE
    default_prompts_dir = default_config_dir / DEFAULT_PROMPTS_DIR_NAME

    loaded_default_models = _load_yaml_file(default_models_file)
    if loaded_default_models:
        models_cfg = loaded_default_models
    else:
        logger.warning(f"Default models file ({default_models_file}) missing or invalid. Proceeding with empty models config.")


    loaded_default_tools = _load_yaml_file(default_tools_file)
    if loaded_default_tools:
        tools_cfg = loaded_default_tools
    else:
        logger.warning(f"Default tools file ({default_tools_file}) missing or invalid. Proceeding with empty tools config.")

    prompt_tpls = _load_prompt_templates_from_dir(default_prompts_dir)
    if not prompt_tpls:
        logger.warning(f"No prompt templates found in default prompts directory: {default_prompts_dir}")
        
    # Xác định active_mode
    # Ưu tiên biến môi trường, sau đó đến default_active_mode trong models.yml, cuối cùng là "production"
    default_mode_from_file = models_cfg.get("default_active_mode", "production") # models_cfg là dict đã load từ models.yml
    active_mode = os.environ.get("NOVAGUARD_ACTIVE_MODE", default_mode_from_file).lower()
    logger.info(f"Determined active_mode: {active_mode}")


    # 2. Load and merge project-specific configurations if path is provided
    if project_config_dir_str:
        project_config_dir = (workspace_path / project_config_dir_str).resolve()
        logger.info(f"Attempting to load project-specific configurations from: {project_config_dir}")

        if project_config_dir.is_dir():
            project_models_file = project_config_dir / DEFAULT_MODELS_FILE
            project_tools_file = project_config_dir / DEFAULT_TOOLS_FILE
            project_prompts_dir = project_config_dir / DEFAULT_PROMPTS_DIR_NAME

            loaded_project_models = _load_yaml_file(project_models_file)
            if loaded_project_models:
                models_cfg = _deep_merge_dicts(models_cfg, loaded_project_models)
                project_config_actually_loaded = True
                logger.info(f"Merged project-specific models config from: {project_models_file}")

            loaded_project_tools = _load_yaml_file(project_tools_file)
            if loaded_project_tools:
                tools_cfg = _deep_merge_dicts(tools_cfg, loaded_project_tools)
                project_config_actually_loaded = True
                logger.info(f"Merged project-specific tools config from: {project_tools_file}")

            project_specific_prompts = _load_prompt_templates_from_dir(project_prompts_dir)
            if project_specific_prompts:
                # For prompts, override is simpler: if a prompt with the same name exists, it's replaced.
                prompt_tpls.update(project_specific_prompts)
                project_config_actually_loaded = True
                logger.info(f"Loaded/Overridden {len(project_specific_prompts)} project-specific prompt templates from: {project_prompts_dir}")
        else:
            logger.info(f"Project-specific configuration directory not found: {project_config_dir}")
    else:
        logger.info("No project-specific configuration path provided.")

    return Config(
        ollama_base_url=ollama_base_url,
        models_config=models_cfg, # Truyền toàn bộ models_cfg
        tools_config=tools_cfg,
        prompt_templates=prompt_tpls,
        active_mode=active_mode, # Truyền active_mode
        project_config_loaded=project_config_actually_loaded
    )