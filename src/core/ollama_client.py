# NOVAGUARD-AI/src/core/ollama_client.py

import logging
from typing import Optional, Dict, Any, Iterator, AsyncIterator, List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk
# Ensure langchain_ollama is installed and an appropriate version
try:
    from langchain_ollama import ChatOllama
except ImportError:
    logging.critical("langchain-ollama library not found. Please install it: pip install langchain-ollama")
    # This is a critical dependency for this module to function.
    # We'll let it raise an error at runtime if ChatOllama cannot be imported.
    ChatOllama = None # To satisfy linters if the import fails, real error will happen at instantiation.

# Import Config for type hinting if OllamaClientWrapper takes it directly
# from .config_loader import Config # Not strictly needed if base_url is passed explicitly

logger = logging.getLogger(__name__)

class OllamaClientWrapper:
    """
    A wrapper class for interacting with an Ollama server using langchain-ollama.
    Provides methods for synchronous and potentially asynchronous invocations.
    """

    def __init__(self, base_url: str):
        """
        Initializes the OllamaClientWrapper.

        Args:
            base_url: The base URL of the Ollama server (e.g., "http://localhost:11434").
        """
        if ChatOllama is None:
            msg = "ChatOllama could not be imported. Is langchain-ollama installed correctly?"
            logger.critical(msg)
            raise ImportError(msg)

        self.base_url = base_url
        logger.info(f"OllamaClientWrapper initialized for Ollama server at: {self.base_url}")

    def _get_chat_ollama_instance(
        self,
        model_name: str,
        temperature: float = 0.7,
        is_json_mode: bool = False,
        request_timeout: float = 120.0, # Default timeout for requests to Ollama
        keep_alive: str = "5m", # How long to keep the model loaded in memory
        **kwargs: Any
    ) -> ChatOllama:
        """
        Creates and configures a ChatOllama instance.

        Args:
            model_name: The name of the Ollama model to use.
            temperature: The temperature for sampling.
            is_json_mode: If True, instruct Ollama to output JSON.
            request_timeout: Timeout for the Ollama API request in seconds.
            keep_alive: Controls how long the model stays loaded.
                        Examples: "5m", "1h", "-1" (load indefinitely), "0" (unload immediately).
            **kwargs: Additional parameters to pass to ChatOllama.

        Returns:
            A configured ChatOllama instance.
        """
        ollama_params: Dict[str, Any] = {
            "model": model_name,
            "temperature": temperature,
            "base_url": self.base_url,
            "keep_alive": keep_alive,
            "request_timeout": request_timeout,
            **kwargs # Allows passing other ChatOllama params like top_k, top_p, num_ctx, etc.
        }

        if is_json_mode:
            ollama_params["format"] = "json"
            logger.debug(f"Configuring ChatOllama for model '{model_name}' in JSON mode.")
        else:
            logger.debug(f"Configuring ChatOllama for model '{model_name}'.")
        
        try:
            return ChatOllama(**ollama_params)
        except Exception as e:
            logger.error(f"Failed to initialize ChatOllama with params {ollama_params}: {e}", exc_info=True)
            raise  # Re-raise the exception as this is a critical failure


    def invoke(
        self,
        model_name: str,
        prompt: str,
        system_message_content: Optional[str] = None,
        temperature: float = 0.5, # Default temperature from original design
        is_json_mode: bool = False,
        request_timeout: float = 120.0,
        keep_alive: str = "5m",
        **kwargs: Any
    ) -> str:
        """
        Synchronously invokes the Ollama model with a given prompt.

        Args:
            model_name: The name of the Ollama model.
            prompt: The user's prompt/query.
            system_message_content: Optional system message to guide the model's behavior.
            temperature: The generation temperature.
            is_json_mode: Whether to request JSON output from the model.
            request_timeout: Timeout for this specific request.
            keep_alive: Keep-alive setting for this request.
            **kwargs: Additional parameters for ChatOllama.

        Returns:
            The string content of the AI's response.

        Raises:
            Exception: If the Ollama API call fails or returns an error.
        """
        logger.info(f"Invoking model '{model_name}' at {self.base_url}. JSON mode: {is_json_mode}.")
        logger.debug(f"System Message: '{system_message_content}'. Prompt: '{prompt[:100]}...'")

        llm = self._get_chat_ollama_instance(
            model_name=model_name,
            temperature=temperature,
            is_json_mode=is_json_mode,
            request_timeout=request_timeout,
            keep_alive=keep_alive,
            **kwargs
        )

        messages: List[BaseMessage] = []
        if system_message_content:
            messages.append(SystemMessage(content=system_message_content))
        messages.append(HumanMessage(content=prompt))

        try:
            response_message = llm.invoke(messages)
            if isinstance(response_message.content, str):
                logger.info(f"Successfully received response from model '{model_name}'.")
                logger.debug(f"Response content: {response_message.content[:200]}...")
                return response_message.content
            else:
                # Should not happen with standard ChatOllama usage returning AIMessage
                logger.error(f"Unexpected response content type from model '{model_name}': {type(response_message.content)}")
                raise ValueError("Ollama response content is not a string.")
        except Exception as e:
            # This could be a connection error, model not found, timeout, etc.
            logger.error(f"Error invoking Ollama model '{model_name}': {e}", exc_info=True)
            # Consider specific error handling or custom exceptions if needed
            raise  # Re-raise the caught exception


    def stream(
        self,
        model_name: str,
        prompt: str,
        system_message_content: Optional[str] = None,
        temperature: float = 0.5,
        is_json_mode: bool = False,
        request_timeout: float = 120.0,
        keep_alive: str = "5m",
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Streams responses from the Ollama model.

        Args:
            model_name: The name of the Ollama model.
            prompt: The user's prompt/query.
            system_message_content: Optional system message.
            temperature: The generation temperature.
            is_json_mode: Whether to request JSON output (note: streaming JSON might require careful handling by the LLM).
            request_timeout: Timeout for the request.
            keep_alive: Keep-alive setting.
            **kwargs: Additional parameters for ChatOllama.

        Yields:
            String chunks of the AI's response.
        """
        logger.info(f"Streaming from model '{model_name}' at {self.base_url}. JSON mode: {is_json_mode}.")
        llm = self._get_chat_ollama_instance(
            model_name=model_name,
            temperature=temperature,
            is_json_mode=is_json_mode,
            request_timeout=request_timeout,
            keep_alive=keep_alive,
            **kwargs
        )

        messages: List[BaseMessage] = []
        if system_message_content:
            messages.append(SystemMessage(content=system_message_content))
        messages.append(HumanMessage(content=prompt))

        try:
            for chunk in llm.stream(messages):
                if isinstance(chunk, (ChatGenerationChunk, GenerationChunk)) and isinstance(chunk.content, str):
                    yield chunk.content
                # else: (handle other chunk types if necessary, though ChatOllama usually yields AIMessageChunk with string content)
        except Exception as e:
            logger.error(f"Error streaming from Ollama model '{model_name}': {e}", exc_info=True)
            raise # Re-raise

    # --- Placeholder for async methods ---
    async def ainvoke(
        self,
        model_name: str,
        prompt: str,
        system_message_content: Optional[str] = None,
        temperature: float = 0.5,
        is_json_mode: bool = False,
        request_timeout: float = 120.0,
        keep_alive: str = "5m",
        **kwargs: Any
    ) -> str:
        """
        Asynchronously invokes the Ollama model. (Not fully implemented, relies on ChatOllama.ainvoke)
        """
        logger.info(f"Asynchronously invoking model '{model_name}' (ainvoke).")
        llm = self._get_chat_ollama_instance(
            model_name=model_name,
            temperature=temperature,
            is_json_mode=is_json_mode,
            request_timeout=request_timeout,
            keep_alive=keep_alive,
            **kwargs
        )
        messages: List[BaseMessage] = []
        if system_message_content:
            messages.append(SystemMessage(content=system_message_content))
        messages.append(HumanMessage(content=prompt))

        try:
            response_message = await llm.ainvoke(messages)
            if isinstance(response_message.content, str):
                return response_message.content
            else:
                raise ValueError("Ollama async response content is not a string.")
        except Exception as e:
            logger.error(f"Error asynchronously invoking Ollama model '{model_name}': {e}", exc_info=True)
            raise

    async def astream(
        self,
        model_name: str,
        prompt: str,
        system_message_content: Optional[str] = None,
        temperature: float = 0.5,
        is_json_mode: bool = False,
        request_timeout: float = 120.0,
        keep_alive: str = "5m",
        **kwargs: Any
    ) -> AsyncIterator[str]:
        """
        Asynchronously streams responses from the Ollama model. (Not fully implemented, relies on ChatOllama.astream)
        """
        logger.info(f"Asynchronously streaming from model '{model_name}' (astream).")
        llm = self._get_chat_ollama_instance(
            model_name=model_name,
            temperature=temperature,
            is_json_mode=is_json_mode,
            request_timeout=request_timeout,
            keep_alive=keep_alive,
            **kwargs
        )
        messages: List[BaseMessage] = []
        if system_message_content:
            messages.append(SystemMessage(content=system_message_content))
        messages.append(HumanMessage(content=prompt))

        try:
            async for chunk in llm.astream(messages):
                if isinstance(chunk, (ChatGenerationChunk, GenerationChunk)) and isinstance(chunk.content, str):
                    yield chunk.content
        except Exception as e:
            logger.error(f"Error asynchronously streaming from Ollama model '{model_name}': {e}", exc_info=True)
            raise