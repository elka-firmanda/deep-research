from typing import Optional, Literal
from tavily import TavilyClient, AsyncTavilyClient
from .base import BaseTool, ToolResult
from ..core.config import settings


class TavilySearchTool(BaseTool):
    """Tavily search tool for web search capabilities."""

    name = "tavily_search"
    description = "Search the web for current information using Tavily. Use this for finding up-to-date information, news, facts, and general web content."

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.tavily_api_key
        if not self.api_key:
            raise ValueError("Tavily API key not configured")
        self.client = AsyncTavilyClient(api_key=self.api_key)

    async def execute(
        self,
        query: str,
        search_depth: Literal["basic", "advanced"] = "basic",
        max_results: int = 5,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        include_answer: bool = True,
        include_raw_content: bool = False,
        include_images: bool = False,
    ) -> ToolResult:
        """
        Execute a Tavily search.

        Args:
            query: The search query
            search_depth: "basic" for quick search, "advanced" for deeper search
            max_results: Maximum number of results to return
            include_domains: List of domains to include
            exclude_domains: List of domains to exclude
            include_answer: Whether to include an AI-generated answer
            include_raw_content: Whether to include raw page content
            include_images: Whether to include images
        """
        try:
            response = await self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_domains=include_domains or [],
                exclude_domains=exclude_domains or [],
                include_answer=include_answer,
                include_raw_content=include_raw_content,
                include_images=include_images,
            )

            # Format results
            results = {
                "query": query,
                "answer": response.get("answer"),
                "results": [
                    {
                        "title": r.get("title"),
                        "url": r.get("url"),
                        "content": r.get("content"),
                        "score": r.get("score"),
                    }
                    for r in response.get("results", [])
                ],
                "images": response.get("images", []) if include_images else [],
            }

            return ToolResult(success=True, data=results)

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up",
                    },
                    "search_depth": {
                        "type": "string",
                        "enum": ["basic", "advanced"],
                        "description": "Search depth - 'basic' for quick results, 'advanced' for more thorough search",
                        "default": "basic",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "include_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of domains to specifically include in search",
                    },
                    "exclude_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of domains to exclude from search",
                    },
                },
                "required": ["query"],
            },
        }
