"""
MasterAgent - Main orchestrator for multi-agent system.

Coordinates specialized subagents to handle complex queries through
intelligent routing and result synthesis.
"""

import asyncio
from typing import Optional, AsyncGenerator, Callable
from ..core.llm_providers import get_llm_client, LLMProvider
from .base_agent import BaseAgent, format_conversation_history
from .types import QueryAnalysis, SubagentResult, SubagentType
from .query_analyzer import QueryAnalyzer
from .planner_agent import PlannerAgent
from .search_scraper_agent import SearchScraperAgent
from .tool_executor_agent import ToolExecutorAgent


class MasterAgent(BaseAgent):
    """
    Master orchestrator agent that coordinates specialized subagents.

    The MasterAgent:
    1. Analyzes incoming queries to determine type and complexity
    2. Routes queries to appropriate subagents based on analysis
    3. Coordinates subagent execution (sequential, parallel, conditional)
    4. Aggregates and synthesizes results from multiple subagents
    5. Handles errors gracefully with fallback strategies
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        tavily_api_key: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        system_prompt: Optional[str] = None,
        timezone: Optional[str] = None,
        max_tokens: Optional[int] = None,
        # Per-agent model configuration
        planner_model: Optional[str] = None,
        planner_provider: Optional[LLMProvider] = None,
        planner_system_prompt: Optional[str] = None,
        search_scraper_model: Optional[str] = None,
        search_scraper_provider: Optional[LLMProvider] = None,
        search_scraper_system_prompt: Optional[str] = None,
        tool_executor_model: Optional[str] = None,
        tool_executor_provider: Optional[LLMProvider] = None,
    ):
        """
        Initialize MasterAgent.

        Args:
            provider: LLM provider (openai, anthropic, openrouter) for MasterAgent
            model: Specific model to use for MasterAgent (synthesis)
            tavily_api_key: API key for search tools
            progress_callback: Optional callback for progress events
            system_prompt: Optional system prompt for synthesis
            timezone: User's timezone
            max_tokens: Max tokens for response generation
            planner_model: Optional model for PlannerAgent (defaults to model)
            planner_provider: Optional provider for PlannerAgent (defaults to provider)
            planner_system_prompt: Optional system prompt for PlannerAgent
            search_scraper_model: Optional model for SearchScraperAgent (defaults to model)
            search_scraper_provider: Optional provider for SearchScraperAgent (defaults to provider)
            search_scraper_system_prompt: Optional system prompt for SearchScraperAgent
            tool_executor_model: Optional model for ToolExecutorAgent (defaults to model)
            tool_executor_provider: Optional provider for ToolExecutorAgent (defaults to provider)
        """
        super().__init__(progress_callback)

        self.provider = provider
        self.model = model
        self.tavily_api_key = tavily_api_key
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.timezone = timezone or "UTC"
        self.max_tokens = max_tokens

        # Initialize LLM client for synthesis (uses master agent's model)
        self.llm = get_llm_client(provider=provider, model=model)

        # Initialize query analyzer (uses master agent's model)
        self.analyzer = QueryAnalyzer(self.llm)

        # Initialize subagents with their specific models, providers, and system prompts
        self.planner = PlannerAgent(
            provider=planner_provider or provider,  # Use planner-specific provider or fallback
            model=planner_model or model,  # Use planner-specific model or fallback
            system_prompt=planner_system_prompt,  # Use custom prompt if provided
            progress_callback=None,  # Will be set dynamically
        )

        self.search_scraper = SearchScraperAgent(
            tavily_api_key=tavily_api_key,
            provider=search_scraper_provider or provider,  # Use search-scraper-specific provider or fallback
            model=search_scraper_model or model,  # Use search-scraper-specific model or fallback
            system_prompt=search_scraper_system_prompt,  # Use custom prompt if provided
            progress_callback=None,  # Will be set dynamically
        )

        self.tool_executor = ToolExecutorAgent(
            timezone=timezone,
            progress_callback=None,  # Will be set dynamically (ToolExecutor doesn't use LLM typically)
        )

        # Conversation history (mimics SearchAgent)
        self.messages: list[dict] = []

    async def chat_stream(self, message: str) -> AsyncGenerator[dict, None]:
        """
        Main entry point for processing user messages.

        Mimics SearchAgent.chat_stream() interface for backward compatibility.

        Args:
            message: User's message

        Yields:
            Progress events and final response
        """
        # Add user message to history
        self.messages.append({"role": "user", "content": message})

        try:
            # Step 1: Analyze query
            yield {
                "type": "progress",
                "step": "analyzing",
                "status": "in_progress",
                "detail": "Analyzing your request...",
                "progress": 5,
                "source": "master_agent",
            }

            analysis = await self.analyzer.analyze(message, self.messages)

            # Step 2: Route to subagents
            yield {
                "type": "progress",
                "step": "routing",
                "status": "in_progress",
                "detail": f"Planning {analysis.query_type} response...",
                "progress": 10,
                "source": "master_agent",
            }

            # Execute appropriate routing strategy
            if analysis.execution_strategy == "sequential":
                results = await self._route_sequential(analysis, message)
            elif analysis.execution_strategy == "parallel":
                results = await self._route_parallel(analysis, message)
            elif analysis.execution_strategy == "conditional":
                results = await self._route_conditional(analysis, message)
            else:  # direct
                results = await self._route_direct(analysis, message)

            # Step 3: Synthesize results
            yield {
                "type": "progress",
                "step": "synthesizing",
                "status": "in_progress",
                "detail": "Analyzing and synthesizing results...",
                "progress": 90,
                "source": "master_agent",
            }

            final_response = await self._synthesize_results(message, results, analysis)

            # Add assistant message to history
            self.messages.append({"role": "assistant", "content": final_response})

            # Step 4: Yield final response
            yield {"type": "response", "content": final_response}
            yield {"type": "done"}

        except Exception as e:
            # Handle unexpected errors
            error_response = f"I encountered an unexpected error: {str(e)}. Please try again."
            self.messages.append({"role": "assistant", "content": error_response})
            yield {"type": "response", "content": error_response}
            yield {"type": "done"}

    async def _route_sequential(
        self,
        analysis: QueryAnalysis,
        query: str
    ) -> list[SubagentResult]:
        """
        Execute subagents sequentially, passing results forward.

        Args:
            analysis: Query analysis with routing information
            query: User's query

        Returns:
            List of SubagentResults
        """
        results = []
        plan = None
        datetime_context = None

        # Execute in order: ToolExecutor → Planner → SearchScraper

        # 1. Tool Executor (if needed)
        if SubagentType.TOOL_EXECUTOR.value in analysis.required_subagents:
            tool_result = await self._execute_subagent_safe(
                self.tool_executor,
                "tool_executor_agent",
                execute_method="execute",
                tool_name="get_current_datetime",
                arguments={"timezone": self.timezone},
            )
            results.append(tool_result)

            if tool_result.success:
                datetime_context = tool_result.data

        # 2. Planner (if needed)
        if SubagentType.PLANNER.value in analysis.required_subagents:
            plan_result = await self._execute_subagent_safe(
                self.planner,
                "planner_agent",
                execute_method="execute",
                query=query,
                context=self.messages,
            )
            results.append(plan_result)

            if plan_result.success:
                plan = plan_result.data.get("plan")

        # 3. SearchScraper (always executed if in subagents list)
        if SubagentType.SEARCH_SCRAPER.value in analysis.required_subagents:
            search_result = await self._execute_subagent_safe(
                self.search_scraper,
                "search_scraper_agent",
                execute_method="execute",
                query=query,
                plan=plan,  # May be None if Planner failed or wasn't used
                context=self.messages,
            )
            results.append(search_result)

        return results

    async def _route_parallel(
        self,
        analysis: QueryAnalysis,
        query: str
    ) -> list[SubagentResult]:
        """
        Execute subagents in parallel.

        Args:
            analysis: Query analysis
            query: User's query

        Returns:
            List of SubagentResults
        """
        tasks = []

        # Build parallel tasks
        if SubagentType.TOOL_EXECUTOR.value in analysis.required_subagents:
            tasks.append(
                self._execute_subagent_safe(
                    self.tool_executor,
                    "tool_executor_agent",
                    execute_method="execute",
                    tool_name="get_current_datetime",
                    arguments={"timezone": self.timezone},
                )
            )

        if SubagentType.SEARCH_SCRAPER.value in analysis.required_subagents:
            tasks.append(
                self._execute_subagent_safe(
                    self.search_scraper,
                    "search_scraper_agent",
                    execute_method="execute",
                    query=query,
                    plan=None,  # No plan in parallel mode
                    context=self.messages,
                )
            )

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _route_conditional(
        self,
        analysis: QueryAnalysis,
        query: str
    ) -> list[SubagentResult]:
        """
        Execute subagents based on runtime conditions.

        Args:
            analysis: Query analysis
            query: User's query

        Returns:
            List of SubagentResults
        """
        # For now, use sequential routing for conditional
        # Future: Add logic to decide based on intermediate results
        return await self._route_sequential(analysis, query)

    async def _route_direct(
        self,
        analysis: QueryAnalysis,
        query: str
    ) -> list[SubagentResult]:
        """
        Direct execution without orchestration (simple queries).

        Args:
            analysis: Query analysis
            query: User's query

        Returns:
            List of SubagentResults (typically just one)
        """
        # Simple queries go straight to SearchScraper
        result = await self._execute_subagent_safe(
            self.search_scraper,
            "search_scraper_agent",
            execute_method="execute",
            query=query,
            plan=None,
            context=self.messages,
        )
        return [result]

    async def _synthesize_results(
        self,
        query: str,
        results: list[SubagentResult],
        analysis: QueryAnalysis
    ) -> str:
        """
        Synthesize results from multiple subagents into final response.

        Args:
            query: User's query
            results: List of SubagentResults
            analysis: Query analysis

        Returns:
            Final synthesized response
        """
        # Separate successful and failed results
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # If all subagents failed, return error message
        if not successful:
            return "I apologize, but I encountered errors while researching your question. Please try again or rephrase your query."

        # If only one successful result, use its data directly (simple case)
        if len(successful) == 1 and not failed:
            return self._format_single_result(query, successful[0])

        # Multiple results: use LLM to synthesize
        return await self._llm_synthesize(query, successful, failed)

    def _format_single_result(self, query: str, result: SubagentResult) -> str:
        """
        Format a single subagent result into a response.

        Args:
            query: User's query
            result: SubagentResult

        Returns:
            Formatted response string
        """
        if result.subagent == "search_scraper_agent":
            # SearchScraper result - extract synthesis or format sources
            data = result.data
            if isinstance(data, dict):
                # Check if it has a synthesis from DeepSearchTool
                if "synthesis" in data:
                    return data["synthesis"]
                # Otherwise format results
                if "results" in data or "all_sources" in data:
                    # Let DeepSearchTool handle formatting
                    # For now, return a simple message
                    sources_count = len(data.get("all_sources", []))
                    return f"Found {sources_count} sources. Let me synthesize the information..."

        # Default: return data as string
        return str(result.data)

    async def _llm_synthesize(
        self,
        query: str,
        successful: list[SubagentResult],
        failed: list[SubagentResult]
    ) -> str:
        """
        Use LLM to synthesize results from multiple subagents.

        Args:
            query: User's query
            successful: Successful subagent results
            failed: Failed subagent results

        Returns:
            Synthesized response
        """
        # Build synthesis prompt
        context_parts = []

        for result in successful:
            if result.subagent == "tool_executor_agent":
                context_parts.append(f"Date/Time Information:\n{result.data}")
            elif result.subagent == "planner_agent":
                plan = result.data.get("plan", {})
                context_parts.append(f"Research Plan:\n{plan.get('goal', 'N/A')}")
            elif result.subagent == "search_scraper_agent":
                data = result.data
                if isinstance(data, dict):
                    sources = data.get("all_sources", [])
                    context_parts.append(f"Search Results: {len(sources)} sources found")
                    # Add source summaries
                    for i, source in enumerate(sources[:10], 1):
                        title = source.get("title", "")
                        url = source.get("url", "")
                        context_parts.append(f"{i}. {title}\n   {url}")

        context_str = "\n\n".join(context_parts)

        synthesis_prompt = f"""{self.system_prompt}

User Query: {query}

Research Results:
{context_str}

Based on the research results above, provide a comprehensive answer to the user's query. Include citations to sources where appropriate."""

        # Use LLM to synthesize
        response = await self.llm.chat(
            messages=[{"role": "user", "content": synthesis_prompt}],
            temperature=0.7,
            max_tokens=2000,
        )

        # Clean up any tool invocation artifacts from the response
        import re
        response = re.sub(r'<(deep_search|tavily_search|web_scraper|get_current_datetime|planner|search)[^>]*>.*?</\1>', '', response, flags=re.DOTALL)
        response = re.sub(r'<(deep_search|tavily_search|web_scraper|get_current_datetime|planner|search)[^>]*/?>', '', response)
        response = re.sub(r'\n\s*\n\s*\n', '\n\n', response).strip()

        # Add note about failures if any
        if failed:
            response += f"\n\n*Note: Some research components encountered issues but I've provided the best answer possible with available information.*"

        return response

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for synthesis."""
        return """You are an expert research assistant. Synthesize the provided research results into a comprehensive, well-structured response. Use proper citations and maintain an encyclopedic tone.

CRITICAL: Do NOT include XML tags, tool names like <deep_search>, or any tool invocation syntax in your response. Your response should be pure content only, formatted with proper markdown and citations."""

    async def execute(self, **kwargs):
        """Not used - MasterAgent uses chat_stream() interface."""
        raise NotImplementedError("Use chat_stream() instead")
