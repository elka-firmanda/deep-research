from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Literal, List, Dict
import json
import httpx
import uuid
from pathlib import Path
from datetime import datetime

from ..agents import SearchAgent
from ..core.llm_providers import LLMProvider
from ..core.config import settings
from ..database import ChatStorage, SQLiteChatStorage, PostgresChatStorage, MessageRole

router = APIRouter()

# Database storage instance (initialized on startup)
_chat_storage: Optional[ChatStorage] = None


async def get_chat_storage() -> ChatStorage:
    """Get or initialize the chat storage."""
    global _chat_storage
    if _chat_storage is None:
        if settings.db_type == "postgres" and settings.postgres_password:
            _chat_storage = PostgresChatStorage(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
            )
        else:
            # Default to SQLite
            _chat_storage = SQLiteChatStorage(database_path=settings.db_path)

        await _chat_storage.initialize()
    return _chat_storage


async def generate_conversation_title(
    user_message: str,
    assistant_response: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Generate a short, descriptive title for a conversation using the LLM."""
    try:
        # Use a simple LLM call to generate a title
        llm_provider = None
        if provider:
            llm_provider = LLMProvider(provider)

        # Create a minimal agent just for title generation
        agent = SearchAgent(
            provider=llm_provider,
            model=model,
            system_prompt="You are a helpful assistant that generates very short, concise titles.",
        )

        prompt = f"""Generate a short title (3-6 words) for this conversation. 
Return ONLY the title, no quotes, no punctuation at the end.

User's first message: {user_message[:200]}
Assistant's response summary: {assistant_response[:200]}

Title:"""

        title = await agent.chat(prompt, stream=False)
        # Clean up the title
        title = title.strip().strip("\"'").strip()
        # Limit length
        if len(title) > 50:
            title = title[:47] + "..."
        return title if title else user_message[:30] + "..."
    except Exception as e:
        print(f"Error generating title: {e}")
        # Fallback to simple truncation
        return user_message[:30] + "..." if len(user_message) > 30 else user_message


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
    conversation_id: Optional[str] = None  # UUID for conversation persistence
    provider: Optional[Literal["openai", "anthropic", "openrouter"]] = None
    model: Optional[str] = None
    stream: bool = False
    system_prompt: Optional[str] = None
    deep_research: bool = False
    timezone: Optional[str] = "UTC"  # User's timezone for date/time queries
    max_tokens: Optional[int] = None  # Max tokens for response generation
    multi_agent_mode: bool = False  # Enable multi-agent orchestration (experimental)
    # Per-agent model configuration (for multi-agent mode)
    master_agent_model: Optional[str] = None  # Model for MasterAgent synthesis
    master_agent_provider: Optional[Literal["openai", "anthropic", "openrouter"]] = None  # Provider for MasterAgent
    planner_agent_model: Optional[str] = None  # Model for PlannerAgent
    planner_agent_provider: Optional[Literal["openai", "anthropic", "openrouter"]] = None  # Provider for PlannerAgent
    search_scraper_agent_model: Optional[str] = None  # Model for SearchScraperAgent
    search_scraper_agent_provider: Optional[Literal["openai", "anthropic", "openrouter"]] = None  # Provider for SearchScraperAgent
    tool_executor_agent_model: Optional[str] = None  # Model for ToolExecutorAgent
    tool_executor_agent_provider: Optional[Literal["openai", "anthropic", "openrouter"]] = None  # Provider for ToolExecutorAgent
    # Per-agent system prompts (for multi-agent mode)
    master_agent_system_prompt: Optional[str] = None  # System prompt for MasterAgent
    planner_agent_system_prompt: Optional[str] = None  # System prompt for PlannerAgent
    search_scraper_agent_system_prompt: Optional[str] = None  # System prompt for SearchScraperAgent
    # API Keys (configurable via settings)
    tavily_api_key: Optional[str] = None  # Tavily API key for web search
    serpapi_api_key: Optional[str] = None  # SerpAPI key for Google search
    apify_api_key: Optional[str] = None  # Apify API key for web scraping
    # Database connections
    database_connections: Optional[List[Dict]] = None  # Database connection configurations
    # Database agent configuration
    database_agent_provider: Optional[Literal["openai", "anthropic", "openrouter"]] = None  # Provider for DatabaseAgent
    database_agent_model: Optional[str] = None  # Model for DatabaseAgent
    database_agent_system_prompt: Optional[str] = None  # System prompt for DatabaseAgent


class ChatResponse(BaseModel):
    response: str
    session_id: str
    conversation_id: str  # Return the conversation ID for the frontend to track


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
    serpapi_available: bool


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
        serpapi_available=bool(settings.serpapi_api_key),
    )


@router.post("/chat")
async def chat(request: ChatRequest):
    """Send a message to the agent with optional streaming progress."""
    try:
        # Get or create conversation ID
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Initialize chat storage and ensure conversation exists
        storage = await get_chat_storage()

        # Check if conversation exists, create if not
        existing_conv = await storage.get_conversation(conversation_id)
        if not existing_conv:
            await storage.create_conversation(
                conversation_id=conversation_id,
                metadata={
                    "provider": request.provider,
                    "model": request.model,
                    "deep_research": request.deep_research,
                },
            )

        # Save user message to database
        await storage.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=request.message,
        )

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
            # When deep research is disabled, remove search tool mentions from system prompt
            system_prompt = """You are a knowledgeable assistant that provides informative and helpful responses based on your training data.

## Response Guidelines

### Writing Style
- Write in a clear, conversational tone
- Use complete paragraphs with flowing prose
- Provide comprehensive coverage when possible
- Include relevant context and background
- Maintain objectivity and present balanced perspectives

### Important Rules
- Answer based on your knowledge and training data
- If you're unsure about something, acknowledge your uncertainty
- Provide thoughtful, well-reasoned responses
- Include specific details when you know them
- Be clear when information might be outdated or when you're making inferences

Remember: You don't have access to real-time information or web search. Your knowledge is based on your training data."""

        # Select agent based on mode
        if request.multi_agent_mode:
            # Use MasterAgent for multi-agent orchestration
            from ..agents import MasterAgent

            # Convert per-agent providers to LLMProvider enum if specified
            planner_provider = None
            if request.planner_agent_provider:
                planner_provider = LLMProvider(request.planner_agent_provider)

            search_scraper_provider = None
            if request.search_scraper_agent_provider:
                search_scraper_provider = LLMProvider(request.search_scraper_agent_provider)

            tool_executor_provider = None
            if request.tool_executor_agent_provider:
                tool_executor_provider = LLMProvider(request.tool_executor_agent_provider)

            # Master agent provider
            master_provider = llm_provider
            if request.master_agent_provider:
                master_provider = LLMProvider(request.master_agent_provider)

            # Use per-agent models and providers if specified, otherwise fall back to main
            agent = MasterAgent(
                provider=master_provider,
                model=request.master_agent_model or request.model,
                tavily_api_key=settings.tavily_api_key,
                system_prompt=request.master_agent_system_prompt or system_prompt,
                timezone=request.timezone,
                max_tokens=request.max_tokens,
                # Per-agent model and provider configuration
                planner_model=request.planner_agent_model or request.model,
                planner_provider=planner_provider or llm_provider,
                planner_system_prompt=request.planner_agent_system_prompt,
                search_scraper_model=request.search_scraper_agent_model or request.model,
                search_scraper_provider=search_scraper_provider or llm_provider,
                search_scraper_system_prompt=request.search_scraper_agent_system_prompt,
                tool_executor_model=request.tool_executor_agent_model or request.model,
                tool_executor_provider=tool_executor_provider or llm_provider,
            )
        else:
            # Use traditional SearchAgent
            agent = SearchAgent(
                provider=llm_provider,
                model=request.model,
                tavily_api_key=settings.tavily_api_key,
                serpapi_api_key=settings.serpapi_api_key,
                system_prompt=system_prompt,
                timezone=request.timezone,
                enable_search=request.deep_research,  # Only enable search tools when deep research is on
            )

        # Store/update session
        if request.session_id:
            sessions[request.session_id] = agent

        if request.stream:

            async def generate():
                final_response = ""
                async for event in agent.chat_stream(request.message):
                    # Capture the final response for saving
                    if event.get("type") == "response":
                        final_response = event.get("content", "")
                    yield f"data: {json.dumps(event)}\n\n"

                # Save assistant response to database after streaming completes
                if final_response:
                    try:
                        await storage.add_message(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=final_response,
                        )
                        # Generate title if this is the first exchange (2 messages: user + assistant)
                        messages = await storage.get_messages(conversation_id, limit=3)
                        if len(messages) == 2:
                            title = await generate_conversation_title(
                                request.message,
                                final_response,
                                request.provider,
                                request.model,
                            )
                            await storage.update_conversation(
                                conversation_id, title=title
                            )
                    except Exception as e:
                        print(f"Error saving assistant message: {e}")

                # Send conversation_id in the done event
                yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conversation_id})}\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
            )

        response = await agent.chat(request.message, stream=False)

        # Save assistant response to database
        await storage.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=response,
        )

        # Generate title if this is the first exchange
        messages = await storage.get_messages(conversation_id, limit=3)
        if len(messages) == 2:
            title = await generate_conversation_title(
                request.message,
                response,
                request.provider,
                request.model,
            )
            await storage.update_conversation(conversation_id, title=title)

        return ChatResponse(
            response=response,
            session_id=request.session_id,
            conversation_id=conversation_id,
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
    timezone: Optional[str] = None
    max_tokens: Optional[int] = None
    multi_agent_mode: Optional[bool] = None
    # Per-agent model configuration
    master_agent_model: Optional[str] = None
    master_agent_provider: Optional[str] = None
    planner_agent_model: Optional[str] = None
    planner_agent_provider: Optional[str] = None
    search_scraper_agent_model: Optional[str] = None
    search_scraper_agent_provider: Optional[str] = None
    tool_executor_agent_model: Optional[str] = None
    tool_executor_agent_provider: Optional[str] = None
    # Per-agent system prompts
    master_agent_system_prompt: Optional[str] = None
    planner_agent_system_prompt: Optional[str] = None
    search_scraper_agent_system_prompt: Optional[str] = None


class SettingsResponse(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    deep_research: Optional[bool] = None
    timezone: Optional[str] = None
    max_tokens: Optional[int] = None
    multi_agent_mode: Optional[bool] = None
    # Per-agent model configuration
    master_agent_model: Optional[str] = None
    master_agent_provider: Optional[str] = None
    planner_agent_model: Optional[str] = None
    planner_agent_provider: Optional[str] = None
    search_scraper_agent_model: Optional[str] = None
    search_scraper_agent_provider: Optional[str] = None
    tool_executor_agent_model: Optional[str] = None
    tool_executor_agent_provider: Optional[str] = None
    # Per-agent system prompts
    master_agent_system_prompt: Optional[str] = None
    planner_agent_system_prompt: Optional[str] = None
    search_scraper_agent_system_prompt: Optional[str] = None


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
        timezone=saved.get("timezone", "UTC"),
        max_tokens=saved.get("max_tokens"),
        multi_agent_mode=saved.get("multi_agent_mode", False),
        # Per-agent model configuration
        master_agent_model=saved.get("master_agent_model"),
        master_agent_provider=saved.get("master_agent_provider"),
        planner_agent_model=saved.get("planner_agent_model"),
        planner_agent_provider=saved.get("planner_agent_provider"),
        search_scraper_agent_model=saved.get("search_scraper_agent_model"),
        search_scraper_agent_provider=saved.get("search_scraper_agent_provider"),
        tool_executor_agent_model=saved.get("tool_executor_agent_model"),
        tool_executor_agent_provider=saved.get("tool_executor_agent_provider"),
        # Per-agent system prompts
        master_agent_system_prompt=saved.get("master_agent_system_prompt"),
        planner_agent_system_prompt=saved.get("planner_agent_system_prompt"),
        search_scraper_agent_system_prompt=saved.get("search_scraper_agent_system_prompt"),
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
        "timezone": request.timezone,
        "max_tokens": request.max_tokens,
        "multi_agent_mode": request.multi_agent_mode,
        # Per-agent model configuration
        "master_agent_model": request.master_agent_model,
        "master_agent_provider": request.master_agent_provider,
        "planner_agent_model": request.planner_agent_model,
        "planner_agent_provider": request.planner_agent_provider,
        "search_scraper_agent_model": request.search_scraper_agent_model,
        "search_scraper_agent_provider": request.search_scraper_agent_provider,
        "tool_executor_agent_model": request.tool_executor_agent_model,
        "tool_executor_agent_provider": request.tool_executor_agent_provider,
        # Per-agent system prompts
        "master_agent_system_prompt": request.master_agent_system_prompt,
        "planner_agent_system_prompt": request.planner_agent_system_prompt,
        "search_scraper_agent_system_prompt": request.search_scraper_agent_system_prompt,
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


# ============== Chat History Endpoints ==============


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    metadata: Optional[dict] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    metadata: Optional[dict] = None


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int


class MessagesListResponse(BaseModel):
    messages: List[MessageResponse]
    conversation_id: str


class AddMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    metadata: Optional[dict] = None


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(limit: int = 50, offset: int = 0):
    """List all conversations, ordered by most recent."""
    try:
        storage = await get_chat_storage()
        conversations = await storage.list_conversations(limit=limit, offset=offset)

        return ConversationListResponse(
            conversations=[
                ConversationResponse(
                    id=c.id,
                    title=c.title,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    metadata=c.metadata,
                )
                for c in conversations
            ],
            total=len(conversations),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str):
    """Get a specific conversation."""
    try:
        storage = await get_chat_storage()
        conversation = await storage.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationResponse(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=conversation.metadata,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages."""
    try:
        storage = await get_chat_storage()
        deleted = await storage.delete_conversation(conversation_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Also clean up in-memory session
        if conversation_id in sessions:
            del sessions[conversation_id]

        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/conversations/{conversation_id}/messages", response_model=MessagesListResponse
)
async def get_conversation_messages(conversation_id: str, limit: Optional[int] = None):
    """Get all messages in a conversation."""
    try:
        storage = await get_chat_storage()
        messages = await storage.get_messages(conversation_id, limit=limit)

        return MessagesListResponse(
            messages=[
                MessageResponse(
                    id=m.id or "",
                    conversation_id=m.conversation_id,
                    role=m.role.value,
                    content=m.content,
                    created_at=m.created_at,
                    metadata=m.metadata,
                )
                for m in messages
            ],
            conversation_id=conversation_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageResponse
)
async def add_message(conversation_id: str, request: AddMessageRequest):
    """Add a message to a conversation."""
    try:
        storage = await get_chat_storage()
        role = MessageRole.USER if request.role == "user" else MessageRole.ASSISTANT

        message = await storage.add_message(
            conversation_id=conversation_id,
            role=role,
            content=request.content,
            metadata=request.metadata,
        )

        return MessageResponse(
            id=message.id or "",
            conversation_id=message.conversation_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
            metadata=message.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}/messages")
async def clear_conversation_messages(conversation_id: str):
    """Delete all messages in a conversation."""
    try:
        storage = await get_chat_storage()
        count = await storage.delete_messages(conversation_id)

        # Also reset in-memory session
        if conversation_id in sessions:
            sessions[conversation_id].reset()

        return {
            "status": "cleared",
            "conversation_id": conversation_id,
            "deleted_count": count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
