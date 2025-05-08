# NOVAGUARD-AI/src/core/prompt_manager.py

import logging
from typing import Dict, Any, Optional, List, Set

from .config_loader import Config

try:
    import jinja2
    from jinja2 import meta as jinja2_meta # Import meta một cách tường minh
except ImportError:
    logging.critical("Jinja2 library not found. Please install it: pip install Jinja2")
    jinja2 = None # Để tránh lỗi nếu import thất bại hoàn toàn
    jinja2_meta = None


logger = logging.getLogger(__name__)

class PromptManager:
    """
    Manages and renders prompt templates using Jinja2.
    It retrieves raw prompt templates from the Config object.
    """

    def __init__(self, config: Config):
        """
        Initializes the PromptManager with a Config object.

        Args:
            config: The Config object containing loaded prompt templates.
        """
        self.config = config
        if not jinja2: # Kiểm tra nếu import ban đầu thất bại
            msg = "Jinja2 is not available, PromptManager cannot operate."
            logger.critical(msg)
            raise ImportError(msg)
        
        try:
            self.jinja_env = jinja2.Environment(
                loader=jinja2.DictLoader(self.config.prompt_templates),
                autoescape=jinja2.select_autoescape(['html', 'xml', 'md']),
                undefined=jinja2.StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True
            )
            logger.info(f"PromptManager initialized with {len(self.config.prompt_templates)} templates from Config.")
            logger.debug(f"Available prompt keys: {list(self.config.prompt_templates.keys())}")

        except Exception as e: # Bắt lỗi rộng hơn ở đây nếu cần thiết cho init
            logger.error(f"Failed to initialize Jinja2 environment: {e}", exc_info=True)
            raise RuntimeError("Jinja2 environment initialization failed.") from e


    def get_prompt(self, prompt_name: str, variables: Optional[Dict[str, Any]] = None) -> Optional[str]:
        # ... (Nội dung phương thức này giữ nguyên như trước)
        if variables is None:
            variables = {}

        if prompt_name not in self.config.prompt_templates: # Kiểm tra trực tiếp từ config
            logger.warning(f"Prompt template '{prompt_name}' not found in loaded templates (via config.prompt_templates).")
            return None
        
        # Hoặc bạn có thể dùng get_prompt_template từ config nếu muốn thống nhất cách truy cập
        # template_source = self.config.get_prompt_template(prompt_name)
        # if not template_source:
        #     logger.warning(f"Prompt template '{prompt_name}' not found (via config.get_prompt_template).")
        #     return None

        try:
            template = self.jinja_env.get_template(prompt_name)
            rendered_prompt = template.render(variables)
            logger.debug(f"Successfully rendered prompt template: '{prompt_name}'")
            return rendered_prompt
        except jinja2.exceptions.TemplateNotFound:
            logger.warning(f"Jinja2 TemplateNotFound for '{prompt_name}', this might indicate an issue with DictLoader or template name.")
            return None
        except jinja2.exceptions.UndefinedError as e:
            logger.error(f"Error rendering prompt '{prompt_name}': Missing variable - {e.message}", exc_info=False) # exc_info=False để bớt noise
            return None
        except jinja2.exceptions.TemplateSyntaxError as e:
            logger.error(f"Syntax error in prompt template '{prompt_name}' at line {e.lineno}: {e.message}", exc_info=False)
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while rendering prompt '{prompt_name}': {e}", exc_info=True)
            return None


    def get_available_prompt_names(self) -> List[str]:
        # ... (Nội dung phương thức này giữ nguyên như trước)
        return list(self.config.prompt_templates.keys())


    def get_template_variables(self, prompt_name: str) -> Optional[Set[str]]:
        """
        Inspects a prompt template and returns a set of undeclared variables it uses.
        This is useful for debugging or validating that all necessary variables are provided.

        Args:
            prompt_name: The name of the prompt template.

        Returns:
            A set of variable names used in the template, or None if the template
            is not found or cannot be parsed.
        """
        if not jinja2_meta: # Kiểm tra nếu import jinja2.meta thất bại
             logger.error("jinja2.meta module not available. Cannot get template variables.")
             return None

        template_source = self.config.get_prompt_template(prompt_name)
        if not template_source:
            logger.warning(f"Cannot get variables for an unknown prompt template: '{prompt_name}'")
            return None

        try:
            ast = self.jinja_env.parse(template_source)
            # SỬA LỖI Ở ĐÂY: Sử dụng jinja2_meta đã import
            undeclared_variables = jinja2_meta.find_undeclared_variables(ast)
            return undeclared_variables
        except jinja2.exceptions.TemplateSyntaxError as e:
            logger.error(f"Syntax error while parsing template '{prompt_name}' to find variables: {e.message}", exc_info=False)
            return None
        except AttributeError as ae: # Bắt cụ thể lỗi AttributeError nếu jinja2_meta vẫn có vấn đề
            logger.error(f"AttributeError while trying to use jinja2.meta for '{prompt_name}': {ae}. Is Jinja2 installed correctly and 'meta' accessible?", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error while analyzing template '{prompt_name}' for variables: {e}", exc_info=True)
            return None