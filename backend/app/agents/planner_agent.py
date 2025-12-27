"""
PlannerAgent - Subagent for creating step-by-step research plans.

Analyzes complex queries and breaks them down into structured
research plans with specific search queries and actions.
"""

import json
from typing import Optional
from ..core.llm_providers import get_llm_client, LLMProvider
from ..tools import ToolResult
from .base_agent import BaseAgent, format_conversation_history


class PlannerAgent(BaseAgent):
    """
    Subagent responsible for creating structured research plans.

    For complex queries, the PlannerAgent:
    1. Analyzes the query to understand information needs
    2. Breaks down the query into research steps
    3. Generates specific search queries for each step
    4. Outputs a structured plan for SearchScraperAgent to execute
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ):
        """
        Initialize PlannerAgent.

        Args:
            provider: LLM provider (openai, anthropic, openrouter)
            model: Specific model to use
            system_prompt: Optional custom system prompt for planning
            progress_callback: Optional callback for progress events
        """
        super().__init__(progress_callback)
        self.llm_provider = provider
        self.llm_model = model
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.llm = get_llm_client(provider=provider, model=model)

    async def execute(
        self,
        query: str,
        context: Optional[list[dict]] = None,
        num_steps: int = 3,
        **kwargs
    ) -> ToolResult:
        """
        Generate a research plan for the given query.

        Args:
            query: User's query to plan research for
            context: Optional conversation history for context
            num_steps: Target number of research steps to generate
            **kwargs: Additional context (ignored for now)

        Returns:
            ToolResult containing the research plan
        """
        query_preview = query[:50] + "..." if len(query) > 50 else query
        self._emit_progress(
            step="planner_analyzing",
            status="in_progress",
            detail=f"Analyzing query to create research strategy...",
            progress=10,
            source="planner_agent",
            agent_name="PlannerAgent",
            agent_icon="📋",
        )

        # Build context from conversation history
        context_str = ""
        if context:
            context_str = f"\n\nConversation Context:\n{format_conversation_history(context, max_messages=5)}"

        # Build planning prompt with system prompt
        prompt = f"""{self.system_prompt}

Query: "{query}"{context_str}

Create a research plan that breaks down this query into {num_steps} specific, actionable research steps. Each step should:
1. Have a clear action (search, scrape, or analyze)
2. Include specific search queries if the action is "search"
3. Be focused on gathering specific information

Respond ONLY with a JSON object in this exact format:
{{
    "goal": "A clear statement of what we're trying to learn",
    "steps": [
        {{
            "step_number": 1,
            "action": "search",
            "description": "Brief description of what this step accomplishes",
            "search_queries": ["specific search query 1", "specific search query 2"]
        }},
        ...
    ],
    "expected_sources": 10
}}

Rules:
- Use "search" action for web searches
- Each search step should have 1-3 specific, searchable queries
- Focus on different aspects of the topic across steps
- Be specific and actionable
- Expected_sources should be your estimate of how many sources we'll need

Generate the plan now:"""

        try:
            self._emit_progress(
                step="planner_generating",
                status="in_progress",
                detail=f"Creating {num_steps}-step research plan for '{query_preview}'",
                progress=40,
                source="planner_agent",
                agent_name="PlannerAgent",
                agent_icon="📋",
            )

            # Call LLM to generate plan
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Low temperature for structured output
                max_tokens=1000,
            )

            # Parse JSON response
            plan = json.loads(response)

            # Validate plan structure
            if not self._validate_plan(plan):
                raise ValueError("Generated plan has invalid structure")

            steps_count = len(plan.get('steps', []))
            goal = plan.get('goal', '')[:50]
            self._emit_progress(
                step="planner_complete",
                status="completed",
                detail=f"Research plan ready with {steps_count} steps",
                progress=100,
                source="planner_agent",
                agent_name="PlannerAgent",
                agent_icon="📋",
            )

            return ToolResult(
                success=True,
                data={"plan": plan},
            )

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse plan JSON: {str(e)}"
            self._emit_progress(
                step="planner_error",
                status="failed",
                detail="Failed to generate research plan",
                progress=100,
                source="planner_agent",
                agent_name="PlannerAgent",
                agent_icon="📋",
            )
            return ToolResult(
                success=False,
                data=None,
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Error generating plan: {str(e)}"
            self._emit_progress(
                step="planner_error",
                status="failed",
                detail="Error during planning phase",
                progress=100,
                source="planner_agent",
                agent_name="PlannerAgent",
                agent_icon="📋",
            )
            return ToolResult(
                success=False,
                data=None,
                error=error_msg,
            )

    def _validate_plan(self, plan: dict) -> bool:
        """
        Validate that a plan has the expected structure.

        Args:
            plan: Plan dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(plan, dict):
            return False

        # Check required fields
        if "goal" not in plan or "steps" not in plan:
            return False

        if not isinstance(plan["steps"], list):
            return False

        # Validate each step
        for step in plan["steps"]:
            if not isinstance(step, dict):
                return False

            # Check required step fields
            required_fields = ["step_number", "action", "description"]
            if not all(field in step for field in required_fields):
                return False

            # If action is search, must have search_queries
            if step["action"] == "search":
                if "search_queries" not in step or not isinstance(step["search_queries"], list):
                    return False

        return True

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for planning."""
        return "You are a research planning assistant. Your task is to create a detailed, structured research plan for the following query."
