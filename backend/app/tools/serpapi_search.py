from typing import Optional
import httpx
from .base import BaseTool, ToolResult
from ..core.config import settings


class SerpApiSearchTool(BaseTool):
    """SerpAPI search tool for Google search results."""

    name = "serpapi_search"
    description = "Search Google using SerpAPI for current information, news, and facts. Provides organic search results from Google."

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.serpapi_api_key
        if not self.api_key:
            raise ValueError("SerpAPI API key not configured")
        self.base_url = "https://serpapi.com/search"

    async def execute(
        self,
        query: str,
        num_results: int = 10,
        location: Optional[str] = None,
        gl: str = "us",
        hl: str = "en",
    ) -> ToolResult:
        """
        Execute a Google search via SerpAPI.

        Args:
            query: The search query
            num_results: Number of organic results to return (max 100)
            location: Location for localized results (e.g., "Austin, Texas")
            gl: Country code for search (e.g., "us", "uk")
            hl: Language code (e.g., "en", "es")
        """
        try:
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google",
                "num": min(num_results, 100),
                "gl": gl,
                "hl": hl,
            }

            if location:
                params["location"] = location

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

            # Extract organic results
            organic_results = data.get("organic_results", [])

            # Format answer box if available
            answer_box = data.get("answer_box", {})
            answer = None
            if answer_box:
                answer = answer_box.get("answer") or answer_box.get("snippet")

            # Format knowledge graph if available
            knowledge_graph = data.get("knowledge_graph", {})

            # Format results
            results = {
                "query": query,
                "answer": answer,
                "knowledge_graph": {
                    "title": knowledge_graph.get("title"),
                    "description": knowledge_graph.get("description"),
                } if knowledge_graph else None,
                "results": [
                    {
                        "title": r.get("title"),
                        "url": r.get("link"),
                        "content": r.get("snippet"),
                        "position": r.get("position"),
                        "date": r.get("date"),
                    }
                    for r in organic_results
                ],
                "related_searches": [
                    rs.get("query") for rs in data.get("related_searches", [])
                ][:5],
            }

            return ToolResult(success=True, data=results)

        except httpx.HTTPStatusError as e:
            error_msg = f"SerpAPI HTTP error: {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg = "Invalid SerpAPI API key"
            elif e.response.status_code == 429:
                error_msg = "SerpAPI rate limit exceeded"
            return ToolResult(success=False, data=None, error=error_msg)
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
                        "description": "The search query to look up on Google",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of organic results to return (1-100)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "location": {
                        "type": "string",
                        "description": "Location for localized results (e.g., 'Austin, Texas', 'London, England')",
                    },
                    "gl": {
                        "type": "string",
                        "description": "Country code for search (e.g., 'us', 'uk', 'ca')",
                        "default": "us",
                    },
                    "hl": {
                        "type": "string",
                        "description": "Language code (e.g., 'en', 'es', 'fr')",
                        "default": "en",
                    },
                },
                "required": ["query"],
            },
        }
