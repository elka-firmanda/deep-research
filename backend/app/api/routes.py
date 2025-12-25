from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Literal
import json
import httpx
from pathlib import Path

from ..agents import SearchAgent
from ..core.llm_providers import LLMProvider
from ..core.config import settings

router = APIRouter()

# Store agent sessions (in production, use Redis or similar)
sessions: dict[str, SearchAgent] = {}

# Settings file path from environment variable or default
SETTINGS_FILE = Path(settings.settings_file or "/app/settings.json")


def read_settings() -> dict:
    """Read settings from JSON file."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading settings file: {e}")
    return {}


def write_settings(data: dict) -> bool:
    """Write settings to JSON file."""
    try:
        # Ensure parent directory exists
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error writing settings file: {e}")
        return False


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    provider: Optional[Literal["openai", "anthropic", "openrouter"]] = None
    model: Optional[str] = None
    stream: bool = False
    system_prompt: Optional[str] = None
    deep_research: bool = False


class ChatResponse(BaseModel):
    response: str
    session_id: str


class SearchRequest(BaseModel):
    query: str
    search_type: Literal["basic", "deep"] = "basic"
    max_results: int = 5


class SearchResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class ProviderInfo(BaseModel):
    name: str
    available: bool
    models: list[str]


class StatusResponse(BaseModel):
    status: str
    providers: list[ProviderInfo]
    tavily_available: bool


def get_or_create_session(
    session_id: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> SearchAgent:
    """Get existing session or create a new one."""
    if session_id not in sessions:
        llm_provider = None
        if provider:
            llm_provider = LLMProvider(provider)

        sessions[session_id] = SearchAgent(
            provider=llm_provider,
            model=model,
        )

    return sessions[session_id]


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get API status and available providers."""
    providers = [
        ProviderInfo(
            name="openai",
            available=bool(settings.openai_api_key),
            models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        ),
        ProviderInfo(
            name="anthropic",
            available=bool(settings.anthropic_api_key),
            models=[
                "claude-sonnet-4-20250514",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
            ],
        ),
        ProviderInfo(
            name="openrouter",
            available=bool(settings.openrouter_api_key),
            models=[
                "anthropic/claude-sonnet-4-20250514",
                "openai/gpt-4o",
                "google/gemini-pro",
                "meta-llama/llama-3-70b-instruct",
            ],
        ),
    ]

    return StatusResponse(
        status="ok",
        providers=providers,
        tavily_available=bool(settings.tavily_api_key),
    )


@router.post("/chat")
async def chat(request: ChatRequest):
    """Send a message to the agent with optional streaming progress."""
    try:
        # Always create a new agent with the specified provider/model for consistency
        llm_provider = None
        if request.provider:
            llm_provider = LLMProvider(request.provider)

        # Modify system prompt based on deep_research setting
        system_prompt = request.system_prompt or SearchAgent.DEFAULT_SYSTEM_PROMPT
        if request.deep_research:
            # Update prompt to emphasize deep_search
            system_prompt = system_prompt.replace(
                "## Available Tools\n1. **tavily_search**:",
                "## Available Tools\n1. **tavily_search**: (Limited use - use sparingly)",
            )
            system_prompt = system_prompt.replace(
                "## Important Rules\n- ALWAYS search for information before answering",
                "## Important Rules\n- ALWAYS use **deep_search** for comprehensive research. Only use tavily_search for simple fact-checking.",
            )
        else:
            # Quick search mode - modify prompt to use tavily_search only
            system_prompt = system_prompt.replace(
                "## Available Tools\n1. **tavily_search**: Quick web search for current information, news, and facts.\n2. **deep_search**",
                "## Available Tools\n1. **tavily_search**: Quick web search for current information, news, and facts.",
            )
            system_prompt = system_prompt.replace("3. **web_scraper**", "")
            system_prompt = system_prompt.replace(
                "2. **deep_search**: Comprehensive research that searches multiple queries, reads full page content, and synthesizes information. Use this for complex topics.\n3. **web_scraper**: Read the full content of a specific webpage URL.",
                "2. **web_scraper**: Read the full content of a specific webpage URL.",
            )

        agent = SearchAgent(
            provider=llm_provider,
            model=request.model,
            system_prompt=system_prompt,
        )

        # Store/update session
        if request.session_id:
            sessions[request.session_id] = agent

        if request.stream:

            async def generate():
                async for event in agent.chat_stream(request.message):
                    yield f"data: {json.dumps(event)}\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
            )

        response = await agent.chat(request.message, stream=False)

        return ChatResponse(
            response=response,
            session_id=request.session_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/default-prompt")
async def get_default_prompt():
    """Get the default system prompt."""
    return {"prompt": SearchAgent.DEFAULT_SYSTEM_PROMPT}


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Perform a direct search without agent conversation."""
    try:
        from ..tools import TavilySearchTool, DeepSearchTool

        if request.search_type == "basic":
            tool = TavilySearchTool()
            result = await tool.execute(
                query=request.query,
                max_results=request.max_results,
            )
        else:
            tool = DeepSearchTool()
            result = await tool.execute(
                query=request.query,
                num_sub_queries=3,
            )

        return SearchResponse(
            success=result.success,
            data=result.data,
            error=result.error,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    if session_id in sessions:
        del sessions[session_id]
        return {"status": "deleted", "session_id": session_id}

    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/session/{session_id}/reset")
async def reset_session(session_id: str):
    """Reset a chat session's history."""
    if session_id in sessions:
        sessions[session_id].reset()
        return {"status": "reset", "session_id": session_id}

    raise HTTPException(status_code=404, detail="Session not found")


class SettingsRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    deep_research: Optional[bool] = None


class SettingsResponse(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    deep_research: Optional[bool] = None


@router.get("/settings/{session_id}", response_model=SettingsResponse)
async def get_settings(session_id: str):
    """Get user settings for a session."""
    # Read from file
    saved = read_settings()
    print(f"DEBUG: read_settings returned: {saved}")

    response = SettingsResponse(
        provider=saved.get("provider", "openai"),
        model=saved.get("model", ""),
        system_prompt=saved.get("system_prompt", None),
        deep_research=saved.get("deep_research", False),
    )
    print(f"DEBUG: returning settings: {response}")
    return response


@router.post("/settings/{session_id}")
async def save_settings(session_id: str, request: SettingsRequest):
    """Save user settings for a session."""
    # Write to file
    data = {
        "provider": request.provider,
        "model": request.model,
        "system_prompt": request.system_prompt,
        "deep_research": request.deep_research,
    }
    if write_settings(data):
        return {"status": "saved", "session_id": session_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings")


class ModelInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    context_length: Optional[int] = None
    pricing: Optional[dict] = None


class ModelsResponse(BaseModel):
    provider: str
    models: list[ModelInfo]
    error: Optional[str] = None


@router.get("/models/{provider}", response_model=ModelsResponse)
async def get_models(provider: str):
    """Fetch available models from a provider's API."""
    try:
        if provider == "openai":
            return await fetch_openai_models()
        elif provider == "anthropic":
            return await fetch_anthropic_models()
        elif provider == "openrouter":
            return await fetch_openrouter_models()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    except Exception as e:
        return ModelsResponse(provider=provider, models=[], error=str(e))


async def fetch_openai_models() -> ModelsResponse:
    """Fetch models from OpenAI API."""
    if not settings.openai_api_key:
        return ModelsResponse(
            provider="openai", models=[], error="API key not configured"
        )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            timeout=30.0,
        )

        if response.status_code != 200:
            return ModelsResponse(
                provider="openai",
                models=[],
                error=f"API error: {response.status_code}",
            )

        data = response.json()
        models = []

        # Filter for chat/completion models - include all gpt and o-series models
        # Exclude embedding, tts, whisper, dall-e, moderation models
        exclude_prefixes = (
            "text-embedding",
            "embedding",
            "tts",
            "whisper",
            "dall-e",
            "davinci",
            "babbage",
            "curie",
            "ada",
            "moderation",
            "text-davinci",
            "text-babbage",
            "text-curie",
            "text-ada",
            "code-",
            "text-search",
            "text-similarity",
            "curie-",
            "babbage-",
            "ada-",
            "ft:",
            "ft-",  # fine-tuned models
        )

        # Include these model patterns
        include_patterns = (
            "gpt-",
            "o1",
            "o3",
            "o4",
            "chatgpt",
            # Future-proof for newer naming conventions
        )

        for model in data.get("data", []):
            model_id = model.get("id", "")
            model_lower = model_id.lower()

            # Skip excluded models
            if any(model_lower.startswith(prefix) for prefix in exclude_prefixes):
                continue

            # Include matching models
            if any(pattern in model_lower for pattern in include_patterns):
                models.append(
                    ModelInfo(
                        id=model_id,
                        name=model_id,
                        description=None,
                        context_length=None,
                    )
                )

        # Sort: newer/better models first (simple heuristic)
        def model_sort_key(m: ModelInfo) -> tuple:
            model_id = m.id.lower()
            # Priority order: o-series first, then gpt-4.1, gpt-4o, gpt-4, gpt-3.5
            if model_id.startswith("o3"):
                return (0, model_id)
            elif model_id.startswith("o1"):
                return (1, model_id)
            elif "4.1" in model_id or "4-1" in model_id:
                return (2, model_id)
            elif "4o" in model_id or "4-o" in model_id:
                return (3, model_id)
            elif "4.5" in model_id:
                return (4, model_id)
            elif model_id.startswith("gpt-4"):
                return (5, model_id)
            elif model_id.startswith("gpt-3"):
                return (6, model_id)
            else:
                return (7, model_id)

        models.sort(key=model_sort_key)

        return ModelsResponse(provider="openai", models=models)


async def fetch_anthropic_models() -> ModelsResponse:
    """Fetch models from Anthropic API."""
    if not settings.anthropic_api_key:
        return ModelsResponse(
            provider="anthropic", models=[], error="API key not configured"
        )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            # Fallback to known models if API fails
            return ModelsResponse(
                provider="anthropic",
                models=[
                    ModelInfo(
                        id="claude-sonnet-4-20250514",
                        name="Claude Sonnet 4",
                        context_length=200000,
                    ),
                    ModelInfo(
                        id="claude-3-5-sonnet-20241022",
                        name="Claude 3.5 Sonnet",
                        context_length=200000,
                    ),
                    ModelInfo(
                        id="claude-3-5-haiku-20241022",
                        name="Claude 3.5 Haiku",
                        context_length=200000,
                    ),
                    ModelInfo(
                        id="claude-3-opus-20240229",
                        name="Claude 3 Opus",
                        context_length=200000,
                    ),
                    ModelInfo(
                        id="claude-3-sonnet-20240229",
                        name="Claude 3 Sonnet",
                        context_length=200000,
                    ),
                    ModelInfo(
                        id="claude-3-haiku-20240307",
                        name="Claude 3 Haiku",
                        context_length=200000,
                    ),
                ],
            )

        data = response.json()
        models = []

        for model in data.get("data", []):
            models.append(
                ModelInfo(
                    id=model.get("id", ""),
                    name=model.get("display_name", model.get("id", "")),
                    description=None,
                    context_length=model.get("context_window"),
                )
            )

        return ModelsResponse(provider="anthropic", models=models)


async def fetch_openrouter_models() -> ModelsResponse:
    """Fetch models from OpenRouter API."""
    if not settings.openrouter_api_key:
        return ModelsResponse(
            provider="openrouter", models=[], error="API key not configured"
        )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            timeout=30.0,
        )

        if response.status_code != 200:
            return ModelsResponse(
                provider="openrouter",
                models=[],
                error=f"API error: {response.status_code}",
            )

        data = response.json()
        models = []

        for model in data.get("data", []):
            model_id = model.get("id", "")
            pricing = None
            if "pricing" in model:
                pricing = {
                    "prompt": model["pricing"].get("prompt"),
                    "completion": model["pricing"].get("completion"),
                }

            models.append(
                ModelInfo(
                    id=model_id,
                    name=model.get("name", model_id),
                    description=model.get("description"),
                    context_length=model.get("context_length"),
                    pricing=pricing,
                )
            )

        # Sort by name
        models.sort(key=lambda x: x.name.lower())

        return ModelsResponse(provider="openrouter", models=models)
