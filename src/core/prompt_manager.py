# NOVAGUARD-AI/src/core/prompt_manager.py

import logging
from typing import Dict, Any, Optional, List, Set

# Ensure this import path is correct based on your project structure.
# It assumes config_loader.py is in the same 'core' directory.
from .config_loader import Config

try:
    import jinja2
except ImportError:
    # This is a critical dependency. If not found, the module cannot function.
    # The action_entrypoint should handle this by exiting if setup is incorrect.
    logging.critical("Jinja2 library not found. Please install it: pip install Jinja2")
    # A more robust solution might involve raising a custom exception.
    # For now, we'll let it fail at runtime if Jinja2 is missing.
    pass


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
        try:
            # Initialize Jinja2 Environment
            # We don't need a FileSystemLoader here because templates are already loaded
            # as strings into config.prompt_templates by ConfigLoader.
            self.jinja_env = jinja2.Environment(
                loader=jinja2.DictLoader(self.config.prompt_templates), # Use DictLoader for pre-loaded templates
                autoescape=jinja2.select_autoescape(['html', 'xml', 'md']), # Basic auto-escaping
                undefined=jinja2.StrictUndefined, # Raise an error for undefined variables
                trim_blocks=True, # Good for cleaning up template whitespace
                lstrip_blocks=True # Good for cleaning up template whitespace
            )
            logger.info(f"PromptManager initialized with {len(self.config.prompt_templates)} templates from Config.")
            logger.debug(f"Available prompt keys: {list(self.config.prompt_templates.keys())}")

        except NameError as e: # Catches if jinja2 itself was not imported
            logger.critical(f"Jinja2 is not available, PromptManager cannot operate. Error: {e}")
            # Propagate or handle critical failure
            raise ImportError("Jinja2 library is required but not found or failed to initialize.") from e
        except Exception as e:
            logger.error(f"Failed to initialize Jinja2 environment: {e}", exc_info=True)
            # Depending on desired robustness, you might want to re-raise or handle
            raise RuntimeError("Jinja2 environment initialization failed.") from e


    def get_prompt(self, prompt_name: str, variables: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Retrieves and renders a specific prompt template.

        Args:
            prompt_name: The name of the prompt template (filename stem).
            variables: A dictionary of variables to render the template with.

        Returns:
            The rendered prompt string, or None if the template is not found
            or a rendering error occurs.
        """
        if variables is None:
            variables = {}

        if prompt_name not in self.config.prompt_templates:
            logger.warning(f"Prompt template '{prompt_name}' not found in loaded templates.")
            return None

        try:
            # The template is already loaded into DictLoader via self.config.prompt_templates
            template = self.jinja_env.get_template(prompt_name) # Jinja loads from the dict
            rendered_prompt = template.render(variables)
            logger.debug(f"Successfully rendered prompt template: '{prompt_name}'")
            return rendered_prompt
        except jinja2.exceptions.TemplateNotFound:
            # This case should ideally be caught by the check above,
            # but DictLoader might behave differently or there could be a race condition
            # if templates were modified post-initialization (not the case here).
            logger.warning(f"Jinja2 TemplateNotFound for '{prompt_name}', though it was expected to be in DictLoader.")
            return None
        except jinja2.exceptions.UndefinedError as e:
            logger.error(f"Error rendering prompt '{prompt_name}': Missing variable - {e.message}", exc_info=True)
            return None
        except jinja2.exceptions.TemplateSyntaxError as e:
            logger.error(f"Syntax error in prompt template '{prompt_name}' at line {e.lineno}: {e.message}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while rendering prompt '{prompt_name}': {e}", exc_info=True)
            return None

    def get_available_prompt_names(self) -> List[str]:
        """
        Returns a list of names of all available prompt templates.
        """
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
        template_source = self.config.get_prompt_template(prompt_name)
        if not template_source:
            logger.warning(f"Cannot get variables for an unknown prompt template: '{prompt_name}'")
            return None

        try:
            # We need to parse the source string to find undeclared variables
            ast = self.jinja_env.parse(template_source)
            undeclared_variables = jinja2.meta.find_undeclared_variables(ast)
            return undeclared_variables
        except jinja2.exceptions.TemplateSyntaxError as e:
            logger.error(f"Syntax error while parsing template '{prompt_name}' to find variables: {e.message}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error while analyzing template '{prompt_name}' for variables: {e}", exc_info=True)
            return None