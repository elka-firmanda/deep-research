"""
SearchScraperAgent - Subagent for executing searches and web scraping.

Can execute plan-guided research or fall back to DeepSearchTool for
autonomous research.
"""

import asyncio
from typing import Optional
from ..core.llm_providers import LLMProvider
from ..tools import TavilySearchTool, DeepSearchTool, WebScraperTool, ToolResult
from .base_agent import BaseAgent


class SearchScraperAgent(BaseAgent):
    """
    Subagent responsible for executing web searches and scraping.

    Can operate in two modes:
    1. Plan-guided: Follows a structured plan from PlannerAgent
    2. Autonomous: Uses DeepSearchTool for self-directed research
    """

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ):
        """
        Initialize SearchScraperAgent.

        Args:
            tavily_api_key: API key for Tavily search
            provider: LLM provider for DeepSearchTool
            model: Specific model for DeepSearchTool
            system_prompt: Optional custom system prompt for search synthesis
            progress_callback: Optional callback for progress events
        """
        super().__init__(progress_callback)

        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # Initialize search tools
        self.tavily_tool = TavilySearchTool(api_key=tavily_api_key)
        self.deep_search_tool = DeepSearchTool(
            tavily_api_key=tavily_api_key,
            llm_provider=provider,
            llm_model=model,
            progress_callback=self._create_subagent_callback("deep_search"),
            system_prompt=self.system_prompt,
        )
        self.web_scraper = WebScraperTool()

    async def execute(
        self,
        query: str,
        plan: Optional[dict] = None,
        context: Optional[list[dict]] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute search and scraping operations.

        Args:
            query: User's query
            plan: Optional research plan from PlannerAgent
            context: Optional conversation history
            **kwargs: Additional parameters

        Returns:
            ToolResult containing search results and scraped content
        """
        if plan:
            # Plan-guided execution
            return await self._execute_plan(query, plan)
        else:
            # Autonomous execution using DeepSearchTool
            return await self._execute_autonomous(query)

    async def _execute_plan(self, query: str, plan: dict) -> ToolResult:
        """
        Execute research following a structured plan.

        Args:
            query: User's query
            plan: Research plan with steps

        Returns:
            ToolResult containing aggregated results
        """
        query_preview = query[:50] + "..." if len(query) > 50 else query
        plan_goal = plan.get("goal", "research")[:50] if plan.get("goal") else "research"

        self._emit_progress(
            step="search_scraper_start",
            status="in_progress",
            detail=f"Starting research: {plan_goal}",
            progress=5,
            source="search_scraper_agent",
            agent_name="SearchScraperAgent",
            agent_icon="🔍",
        )

        steps = plan.get("steps", [])
        all_results = []
        all_sources = []

        total_steps = len(steps)

        for i, step in enumerate(steps):
            step_num = step.get("step_number", i + 1)
            action = step.get("action", "search")
            description = step.get("description", "")
            search_queries = step.get("search_queries", [])

            # Show the search queries being executed
            query_sample = search_queries[0][:40] + "..." if search_queries and len(search_queries[0]) > 40 else (search_queries[0] if search_queries else description)
            self._emit_progress(
                step="search_scraper_step",
                status="in_progress",
                detail=f"Searching '{query_sample}' ({step_num}/{total_steps})",
                progress=int(10 + (i / total_steps) * 70),
                source="search_scraper_agent",
                agent_name="SearchScraperAgent",
                agent_icon="🔍",
            )

            if action == "search" and search_queries:
                # Execute search queries for this step
                step_results = await self._execute_searches(search_queries)
                all_results.extend(step_results)

                # Collect sources
                for result in step_results:
                    if result.success and result.data:
                        sources = result.data.get("results", [])
                        all_sources.extend(sources)

        # Optionally scrape top results
        if all_sources:
            self._emit_progress(
                step="search_scraper_scraping",
                status="in_progress",
                detail=f"Reading {min(5, len(all_sources))} pages in detail...",
                progress=85,
                source="search_scraper_agent",
                agent_name="SearchScraperAgent",
                agent_icon="🔍",
            )

            scraped_content = await self._scrape_top_results(all_sources, max_pages=5)
        else:
            scraped_content = []

        self._emit_progress(
            step="search_scraper_complete",
            status="completed",
            detail=f"Found {len(all_sources)} sources, read {len(scraped_content)} pages",
            progress=100,
            source="search_scraper_agent",
            agent_name="SearchScraperAgent",
            agent_icon="🔍",
        )

        return ToolResult(
            success=True,
            data={
                "query": query,
                "plan": plan,
                "searches_performed": len(all_results),
                "pages_scraped": len(scraped_content),
                "results": all_results,
                "all_sources": all_sources,
                "scraped_content": scraped_content,
            },
        )

    async def _execute_autonomous(self, query: str) -> ToolResult:
        """
        Execute research autonomously using DeepSearchTool.

        Args:
            query: User's query

        Returns:
            ToolResult from DeepSearchTool
        """
        query_preview = query[:50] + "..." if len(query) > 50 else query

        self._emit_progress(
            step="search_scraper_start",
            status="in_progress",
            detail=f"Researching '{query_preview}'",
            progress=5,
            source="search_scraper_agent",
            agent_name="SearchScraperAgent",
            agent_icon="🔍",
        )

        # Delegate to DeepSearchTool
        result = await self.deep_search_tool.execute(query=query)

        self._emit_progress(
            step="search_scraper_complete",
            status="completed" if result.success else "failed",
            detail="Research complete" if result.success else "Research encountered errors",
            progress=100,
            source="search_scraper_agent",
            agent_name="SearchScraperAgent",
            agent_icon="🔍",
        )

        return result

    async def _execute_searches(self, queries: list[str]) -> list[ToolResult]:
        """
        Execute multiple search queries in parallel.

        Args:
            queries: List of search queries

        Returns:
            List of ToolResults from searches
        """
        self._emit_progress(
            step="search_scraper_searching",
            status="in_progress",
            detail=f"Running {len(queries)} search queries in parallel...",
            source="search_scraper_agent",
            agent_name="SearchScraperAgent",
            agent_icon="🔍",
        )

        # Execute all searches in parallel
        search_tasks = [
            self.tavily_tool.execute(query=q, search_depth="advanced")
            for q in queries
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Filter out exceptions and convert to ToolResults
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                valid_results.append(ToolResult(
                    success=False,
                    data=None,
                    error=f"Search failed for '{queries[i]}': {str(result)}"
                ))
            else:
                valid_results.append(result)

        return valid_results

    async def _scrape_top_results(
        self,
        sources: list[dict],
        max_pages: int = 5
    ) -> list[dict]:
        """
        Scrape content from top search result URLs.

        Args:
            sources: List of source dictionaries with 'url' field
            max_pages: Maximum number of pages to scrape

        Returns:
            List of scraped content dictionaries
        """
        # Get unique URLs from top results
        urls = []
        seen_urls = set()

        for source in sources[:max_pages * 2]:  # Get more than needed in case some fail
            url = source.get("url")
            if url and url not in seen_urls:
                urls.append(url)
                seen_urls.add(url)

            if len(urls) >= max_pages:
                break

        if not urls:
            return []

        # Scrape all URLs in parallel
        scrape_tasks = [
            self.web_scraper.execute(url=url, max_length=6000)
            for url in urls
        ]

        results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

        # Extract successful scrapes
        scraped_content = []
        for result in results:
            if isinstance(result, ToolResult) and result.success and result.data:
                scraped_content.append(result.data)

        return scraped_content

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for search and scraping."""
        return """You are a research assistant specialized in web search and content analysis. Synthesize information from multiple sources into comprehensive, well-structured answers.

CRITICAL: Do NOT include tool names, XML tags like <deep_search>, or tool invocation syntax in your responses. Call tools silently using the function calling mechanism only."""
