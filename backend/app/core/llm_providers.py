from enum import Enum
from typing import Optional, AsyncGenerator, Union
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from .config import settings


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"


# Default models for each provider
DEFAULT_MODELS = {
    LLMProvider.OPENAI: "gpt-4o",
    LLMProvider.ANTHROPIC: "claude-sonnet-4-20250514",
    LLMProvider.OPENROUTER: "anthropic/claude-sonnet-4-20250514",
}


def _is_new_openai_model(model: str) -> bool:
    """Check if model uses the newer API parameters (max_completion_tokens)."""
    if not model:
        return False
    model_lower = model.lower()
    # o1, o3, o4 series and gpt-4.1+, gpt-5+ use new parameters
    new_model_patterns = (
        "o1",
        "o3",
        "o4",  # o-series models
        "gpt-4.1",
        "gpt-4-1",
        "gpt-4.5",
        "gpt-4-5",  # GPT 4.1/4.5
        "gpt-5",
        "gpt5",  # GPT-5 series
        "nano",
        "mini-preview",  # Specific variants
    )
    return any(pattern in model_lower for pattern in new_model_patterns)


class LLMClient:
    def __init__(
        self,
        provider: LLMProvider,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model or DEFAULT_MODELS.get(provider)
        self._client = None
        self._api_key = api_key
        self._initialize_client()

    def _initialize_client(self):
        if self.provider == LLMProvider.OPENAI:
            api_key = self._api_key or settings.openai_api_key
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            self._client = AsyncOpenAI(api_key=api_key)

        elif self.provider == LLMProvider.ANTHROPIC:
            api_key = self._api_key or settings.anthropic_api_key
            if not api_key:
                raise ValueError("Anthropic API key not configured")
            self._client = AsyncAnthropic(api_key=api_key)

        elif self.provider == LLMProvider.OPENROUTER:
            api_key = self._api_key or settings.openrouter_api_key
            if not api_key:
                raise ValueError("OpenRouter API key not configured")
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.openrouter_base_url,
            )

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[list[dict]] = None,
    ) -> Union[str, AsyncGenerator[str, None], dict]:
        """Send a chat completion request."""

        if self.provider == LLMProvider.ANTHROPIC:
            return await self._anthropic_chat(
                messages, temperature, max_tokens, stream, tools
            )
        else:
            return await self._openai_chat(
                messages, temperature, max_tokens, stream, tools
            )

    async def _openai_chat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        stream: bool,
        tools: Optional[list[dict]] = None,
    ) -> Union[str, AsyncGenerator[str, None], dict]:
        """Handle OpenAI/OpenRouter chat completion."""
        # Check if this is a newer model that uses max_completion_tokens
        use_new_params = (
            _is_new_openai_model(self.model) and self.provider == LLMProvider.OPENAI
        )

        kwargs = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }

        # Use appropriate token parameter based on model
        if use_new_params:
            kwargs["max_completion_tokens"] = max_tokens
            # Many new models don't support custom temperature
            # o1, o3, gpt-5 series only support default temperature (1)
            model_lower = self.model.lower() if self.model else ""
            no_temp_models = ("o1", "o3", "gpt-5", "gpt5", "nano")
            if not any(p in model_lower for p in no_temp_models):
                kwargs["temperature"] = temperature
            # If temperature is explicitly 1, we can still include it (it's the default)
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = temperature

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if stream and not tools:
            return self._openai_stream(**kwargs)

        response = await self._client.chat.completions.create(**kwargs)

        if tools and response.choices[0].message.tool_calls:
            return {
                "content": response.choices[0].message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in response.choices[0].message.tool_calls
                ],
            }

        return response.choices[0].message.content

    async def _openai_stream(self, **kwargs) -> AsyncGenerator[str, None]:
        """Stream OpenAI/OpenRouter responses."""
        async for chunk in await self._client.chat.completions.create(**kwargs):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _anthropic_chat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        stream: bool,
        tools: Optional[list[dict]] = None,
    ) -> Union[str, AsyncGenerator[str, None], dict]:
        """Handle Anthropic chat completion."""
        # Extract system message if present
        system = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)

        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system:
            kwargs["system"] = system

        if tools:
            # Convert OpenAI tool format to Anthropic format
            anthropic_tools = []
            for tool in tools:
                anthropic_tools.append(
                    {
                        "name": tool["function"]["name"],
                        "description": tool["function"]["description"],
                        "input_schema": tool["function"]["parameters"],
                    }
                )
            kwargs["tools"] = anthropic_tools

        if stream and not tools:
            return self._anthropic_stream(**kwargs)

        response = await self._client.messages.create(**kwargs)

        # Check for tool use
        tool_calls = []
        content = ""

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    }
                )

        if tool_calls:
            return {
                "content": content,
                "tool_calls": tool_calls,
            }

        return content

    async def _anthropic_stream(self, **kwargs) -> AsyncGenerator[str, None]:
        """Stream Anthropic responses."""
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text


def get_llm_client(
    provider: Optional[Union[str, LLMProvider]] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMClient:
    """Factory function to get an LLM client."""
    if provider is None:
        provider = settings.default_provider

    if isinstance(provider, str):
        provider = LLMProvider(provider)

    if model is None:
        model = settings.default_model

    return LLMClient(provider=provider, model=model, api_key=api_key)
