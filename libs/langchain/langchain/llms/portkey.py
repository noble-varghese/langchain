from __future__ import annotations

import logging
from typing import (TYPE_CHECKING, Any, Dict, List, Optional, Union, Iterator)

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.pydantic_v1 import Field, PrivateAttr
from langchain.schema import Generation, LLMResult
from langchain.schema.output import GenerationChunk

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import portkey
    from portkey import (
        LLMOptions,
        CacheLiteral,
        CacheType,
        Modes,
        ModesLiteral,
        PortkeyResponse,
    )


IMPORT_ERROR_MESSAGE = (
    "Portkey is not installed.Please install it with `pip install portkey-ai`."
)


class Portkey(LLM):
    """Portkey Service models

    To use, you should have the ``portkey-ai`` python package installed, and the
    environment variable ``PORTKEY_API_KEY``, set with your API key, or pass
    it as a named parameter to the `Portkey` constructor.

    NOTE: You can install portkey using ``pip install portkey-ai``

    Example:
        .. code-block:: python

            import portkey
            from langchain.llms import Portkey

            client = Portkey(api_key="PORTKEY_API_KEY", mode="single")

            # Simplest invocation for any openai provider. Can be extended to
            # others as well
            llm_option = portkey.LLMOptions(
                provider="openai",  
                virtual_key="openai-virtual-key", # Checkout the docs for the virtual-api-key
                model="text-davinci-003"
            )
            response = model("What are the biggest risks facing humanity?")

            # Or if you want to use the chat mode, build a few-shot-prompt, or
            # put words in the Assistant's mouth, use HUMAN_PROMPT and AI_PROMPT:
            raw_prompt = "What are the biggest risks facing humanity?"
            prompt = f"{anthropic.HUMAN_PROMPT} {prompt}{anthropic.AI_PROMPT}"
            response = model(prompt)
    
    """
    mode: Optional[Union["Modes", "ModesLiteral"]] = Field(
        description="The mode for using the Portkey integration", default=None
    )

    model: Optional[str] = Field(default="gpt-3.5-turbo")
    llm: "LLMOptions" = Field(description="LLM parameter", default_factory=dict)
    streaming: bool = False

    llms: List["LLMOptions"] = Field(description="LLM parameters", default_factory=list)

    _portkey: portkey = PrivateAttr()

    def __init__(
        self,
        *,
        mode: Union["Modes", "ModesLiteral"],
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        try:
            import portkey
        except ImportError as exc:
            raise ImportError(IMPORT_ERROR_MESSAGE) from exc

        super().__init__()
        if api_key is not None:
            portkey.api_key = api_key

        if base_url is not None:
            portkey.base_url = base_url

        portkey.mode = mode

        self._portkey = portkey
        self.model = None
        self.mode = mode
        

    def add_llms(self, llm_params: Union[LLMOptions, List[LLMOptions]]) -> "Portkey":
        """
        Adds the specified LLM parameters to the list of LLMs. This may be used for
        fallbacks or load-balancing as specified in the mode.

        Args:
            llm_params (Union[LLMOptions, List[LLMOptions]]): A single LLM parameter \
            set or a list of LLM parameter sets. Each set should be an instance of \
            LLMOptions with
            the specified attributes.
                > provider: Optional[ProviderTypes]
                > model: str
                > temperature: float
                > max_tokens: Optional[int]
                > max_retries: int
                > trace_id: Optional[str]
                > cache_status: Optional[CacheType]
                > cache: Optional[bool]
                > metadata: Dict[str, Any]
                > weight: Optional[float]
                > **kwargs : Other additional parameters that are supported by \
                    LLMOptions in portkey-ai

            NOTE: User may choose to pass additional params as well.
        Returns:
            self
        """
        try:
            from portkey import LLMOptions
        except ImportError as exc:
            raise ImportError(IMPORT_ERROR_MESSAGE) from exc
        if isinstance(llm_params, LLMOptions):
            llm_params = [llm_params]
        self.llms.extend(llm_params)
        if self.model is None:
            self.model = self.llms[0].model
        return self
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call Portkey's completions endpoint. 

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
        Returns:
            A generator representing the stream of tokens from Anthropic.
        Example:
            .. code-block:: python
                prompt = "Write a poem about a stream."
                prompt = f"\n\nHuman: {prompt}\n\nAssistant:"
                generator = anthropic.stream(prompt)
                for token in generator:
                    yield token
        """
        try:
            from portkey import Config
        except ImportError as exc:
            raise ImportError(IMPORT_ERROR_MESSAGE) from exc
        self._client.config = Config(llms=self.llms)
        response = self._client.Completions.create(prompt=prompt, stream=False, stop=stop, **kwargs)
        text = response.choices[0].text
        return text or ""

    @property
    def _client(self):
        try:
            from portkey import Config
        except ImportError as exc:
            raise ImportError(IMPORT_ERROR_MESSAGE) from exc
        self._portkey.config = Config(llms=self.llms)
        return self._portkey
    
    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """Call Portkey completion_stream and return the resulting generator.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
        Returns:
            A generator representing the stream of tokens from Anthropic.
        Example:
            .. code-block:: python

                prompt = "Write a poem about a stream."
                prompt = f"\n\nHuman: {prompt}\n\nAssistant:"
                generator = anthropic.stream(prompt)
                for token in generator:
                    yield token
        """
        response = self._client.Completions.create(stream=True, prompt=prompt, stop=stop, **kwargs)
        for token in response:
            chunk = GenerationChunk(text = token.choices[0].text or "")
            yield chunk
            if run_manager:
                run_manager.on_llm_new_token(chunk.text, chunk=chunk)


    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "portkey-ai-gateway"
