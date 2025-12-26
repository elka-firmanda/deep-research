import asyncio
import json
from typing import Optional, Literal, AsyncGenerator, Callable
from .base import BaseTool, ToolResult
from .tavily_search import TavilySearchTool
from .web_scraper import WebScraperTool
from ..core.config import settings
from ..core.llm_providers import get_llm_client, LLMProvider


class DeepSearchTool(BaseTool):
    """
    Deep search tool that performs multi-step research with progress updates.

    This tool:
    1. Breaks down complex queries into sub-queries
    2. Performs multiple searches in parallel
    3. Scrapes top results for full content
    4. Synthesizes results into a comprehensive answer
    """

    name = "deep_search"
    description = "Perform a deep, comprehensive search on a complex topic. Use this for research questions that require multiple searches and synthesis of information from various sources."

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        llm_provider: Optional[LLMProvider] = None,
        llm_model: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        system_prompt: Optional[str] = None,
    ):
        self.tavily_tool = TavilySearchTool(api_key=tavily_api_key)
        self.web_scraper = WebScraperTool()
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.progress_callback = progress_callback
        self.system_prompt = system_prompt or "You are an expert research analyst."

    def _emit_progress(
        self, step: str, status: str, detail: str = "", progress: int = 0
    ):
        """Emit a progress update."""
        if self.progress_callback:
            self.progress_callback(
                {
                    "type": "progress",
                    "step": step,
                    "status": status,
                    "detail": detail,
                    "progress": progress,
                }
            )

    async def _generate_sub_queries(
        self, query: str, num_queries: int = 3
    ) -> list[str]:
        """Generate sub-queries to explore different aspects of the main query."""
        self._emit_progress(
            step="generate_queries",
            status="in_progress",
            detail="Analyzing query and generating research questions...",
            progress=5,
        )

        llm = get_llm_client(provider=self.llm_provider, model=self.llm_model)

        prompt = f"""You are a research assistant. Given a complex query, generate {num_queries} specific sub-queries that will help comprehensively answer the main question.

Main Query: {query}

Generate {num_queries} different search queries that explore different aspects of this topic. Each query should be specific and searchable.

Respond with a JSON array of strings, nothing else. Example:
["query 1", "query 2", "query 3"]"""

        response = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        try:
            # Parse JSON response
            queries = json.loads(response)
            if isinstance(queries, list):
                self._emit_progress(
                    step="generate_queries",
                    status="completed",
                    detail=f"Generated {len(queries)} research questions",
                    progress=10,
                )
                return queries[:num_queries]
        except json.JSONDecodeError:
            pass

        # Fallback: return original query
        return [query]

    async def _scrape_url(self, url: str, title: str) -> Optional[dict]:
        """Scrape a single URL and return content."""
        try:
            result = await self.web_scraper.execute(url=url, max_length=6000)
            if result.success:
                return {
                    "url": url,
                    "title": title,
                    "content": result.data.get("content", ""),
                }
        except Exception:
            pass
        return None

    async def _scrape_top_results(
        self, search_results: list[dict], max_pages: int = 5
    ) -> list[dict]:
        """Scrape the top search results for full content."""
        self._emit_progress(
            step="scrape_pages",
            status="in_progress",
            detail=f"Reading full content from top {max_pages} pages...",
            progress=50,
        )

        # Collect unique URLs from all results
        urls_to_scrape = []
        seen_urls = set()

        for result in search_results:
            for r in result.get("results", []):
                url = r.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    urls_to_scrape.append(
                        {
                            "url": url,
                            "title": r.get("title", ""),
                        }
                    )
                    if len(urls_to_scrape) >= max_pages:
                        break
            if len(urls_to_scrape) >= max_pages:
                break

        # Scrape in parallel
        scrape_tasks = [
            self._scrape_url(item["url"], item["title"]) for item in urls_to_scrape
        ]

        scraped_results = await asyncio.gather(*scrape_tasks)

        # Filter successful scrapes
        successful_scrapes = [r for r in scraped_results if r is not None]

        self._emit_progress(
            step="scrape_pages",
            status="completed",
            detail=f"Successfully read {len(successful_scrapes)} pages",
            progress=65,
        )

        return successful_scrapes

    async def _synthesize_results(
        self,
        original_query: str,
        search_results: list[dict],
        scraped_pages: list[dict],
    ) -> str:
        """Synthesize multiple search results into a comprehensive answer."""
        self._emit_progress(
            step="synthesize",
            status="in_progress",
            detail="Analyzing and synthesizing all information...",
            progress=75,
        )

        llm = get_llm_client(provider=self.llm_provider, model=self.llm_model)

        # Format search results
        formatted_results = ""
        for i, result in enumerate(search_results, 1):
            formatted_results += f"\n\n### Search {i}: {result.get('query', 'N/A')}\n"
            if result.get("answer"):
                formatted_results += f"**Quick Answer:** {result['answer']}\n"
            for r in result.get("results", [])[:3]:
                formatted_results += f"\n- **{r.get('title', 'N/A')}**\n  {r.get('content', 'N/A')[:300]}...\n"

        # Format scraped pages
        formatted_pages = ""
        for page in scraped_pages[:5]:  # Limit to top 5 pages
            formatted_pages += f"\n\n### Page: {page.get('title', 'Unknown')}\n"
            formatted_pages += f"URL: {page.get('url', 'N/A')}\n"
            content = page.get("content", "")[:3000]  # Limit content length
            formatted_pages += f"Content:\n{content}\n"

        prompt = f"""{self.system_prompt}

Based on the search results and full page content below, provide a comprehensive, well-structured answer to the query.

## Original Query
{original_query}

## Search Results Summary
{formatted_results}

## Full Page Content
{formatted_pages}

## Instructions
Provide a comprehensive answer that:
1. Directly addresses the original query with specific details
2. Synthesizes information from multiple sources
3. Includes relevant facts, statistics, and examples found in the content
4. Uses proper markdown formatting (headers, lists, tables where appropriate)
5. Cites sources with URLs where possible
6. Highlights any conflicting information or uncertainties
7. Provides actionable insights or conclusions

Write your response:"""

        response = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=4000,
        )

        self._emit_progress(
            step="synthesize",
            status="completed",
            detail="Research complete!",
            progress=100,
        )

        return response

    async def execute(
        self,
        query: str,
        num_sub_queries: int = 3,
        search_depth: Literal["basic", "advanced"] = "advanced",
        max_results_per_query: int = 5,
        scrape_pages: bool = True,
        max_pages_to_scrape: int = 5,
    ) -> ToolResult:
        """
        Execute a deep search.

        Args:
            query: The main research query
            num_sub_queries: Number of sub-queries to generate
            search_depth: Tavily search depth
            max_results_per_query: Results per sub-query
            scrape_pages: Whether to scrape full page content
            max_pages_to_scrape: Maximum pages to scrape
        """
        try:
            self._emit_progress(
                step="start",
                status="in_progress",
                detail=f"Starting deep research on: {query[:50]}...",
                progress=0,
            )

            # Step 1: Generate sub-queries
            sub_queries = await self._generate_sub_queries(query, num_sub_queries)

            # Always include the original query
            all_queries = [query] + [q for q in sub_queries if q != query]

            # Step 2: Execute all searches in parallel
            self._emit_progress(
                step="search",
                status="in_progress",
                detail=f"Searching {len(all_queries)} queries...",
                progress=15,
            )

            search_tasks = [
                self.tavily_tool.execute(
                    query=q,
                    search_depth=search_depth,
                    max_results=max_results_per_query,
                    include_answer=True,
                )
                for q in all_queries
            ]

            search_results = await asyncio.gather(*search_tasks)

            # Collect successful results
            successful_results = []
            for i, result in enumerate(search_results):
                if result.success:
                    result_data = (
                        result.data.copy() if isinstance(result.data, dict) else {}
                    )
                    result_data["query"] = all_queries[i]
                    successful_results.append(result_data)

            self._emit_progress(
                step="search",
                status="completed",
                detail=f"Found results from {len(successful_results)} searches",
                progress=40,
            )

            if not successful_results:
                return ToolResult(
                    success=False,
                    data=None,
                    error="All searches failed",
                )

            # Step 3: Scrape top results for full content
            scraped_pages = []
            if scrape_pages:
                scraped_pages = await self._scrape_top_results(
                    successful_results, max_pages_to_scrape
                )

            # Step 4: Synthesize results
            synthesis = await self._synthesize_results(
                query, successful_results, scraped_pages
            )

            # Collect all sources
            all_sources = []
            for result in successful_results:
                for r in result.get("results", []):
                    source = {
                        "title": r.get("title"),
                        "url": r.get("url"),
                        "query": result.get("query"),
                    }
                    if source not in all_sources:
                        all_sources.append(source)

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "sub_queries": sub_queries,
                    "synthesis": synthesis,
                    "sources": all_sources,
                    "pages_scraped": len(scraped_pages),
                    "raw_results": successful_results,
                },
            )

        except Exception as e:
            self._emit_progress(
                step="error",
                status="failed",
                detail=str(e),
                progress=0,
            )
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
                        "description": "The main research query or question to investigate",
                    },
                    "num_sub_queries": {
                        "type": "integer",
                        "description": "Number of sub-queries to generate for comprehensive research",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "search_depth": {
                        "type": "string",
                        "enum": ["basic", "advanced"],
                        "description": "Search depth for each query",
                        "default": "advanced",
                    },
                    "scrape_pages": {
                        "type": "boolean",
                        "description": "Whether to read full page content",
                        "default": True,
                    },
                },
                "required": ["query"],
            },
        }
