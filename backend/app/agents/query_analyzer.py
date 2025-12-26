"""
Query analysis and classification for intelligent routing to subagents.
"""

import json
import re
from typing import Optional
from .types import QueryAnalysis, QueryType, ExecutionStrategy
from ..core.llm_providers import LLMClient


class QueryAnalyzer:
    """
    Analyzes user queries to determine appropriate subagent routing.

    Uses a combination of keyword matching and LLM-based classification
    to categorize queries and determine execution strategy.
    """

    # Keywords for different query types
    TIME_KEYWORDS = [
        "yesterday", "today", "tomorrow", "last week", "this week", "next week",
        "last month", "this month", "recently", "latest", "current", "now",
        "when", "what time", "date",
    ]

    COMPARISON_KEYWORDS = [
        "vs", "versus", "compare", "comparison", "difference", "better",
        "which is", "or", "between",
    ]

    RESEARCH_KEYWORDS = [
        "research", "analyze", "study", "investigate", "explore", "explain",
        "comprehensive", "detailed", "in-depth", "overview",
    ]

    SIMPLE_QUESTION_KEYWORDS = [
        "what is", "who is", "where is", "define", "meaning of",
    ]

    def __init__(self, llm_client: LLMClient):
        """
        Initialize query analyzer.

        Args:
            llm_client: LLM client for advanced classification
        """
        self.llm = llm_client

    async def analyze(
        self,
        query: str,
        conversation_history: Optional[list[dict]] = None
    ) -> QueryAnalysis:
        """
        Analyze query and determine routing strategy.

        Args:
            query: User's query string
            conversation_history: Optional conversation context

        Returns:
            QueryAnalysis with routing information
        """
        query_lower = query.lower()

        # Fast path: keyword-based classification
        keyword_analysis = self._keyword_classify(query_lower)
        if keyword_analysis:
            return keyword_analysis

        # Fallback: LLM-based classification for ambiguous queries
        return await self._llm_classify(query, conversation_history)

    def _keyword_classify(self, query_lower: str) -> Optional[QueryAnalysis]:
        """
        Fast keyword-based classification.

        Args:
            query_lower: Lowercased query string

        Returns:
            QueryAnalysis if confident classification, None otherwise
        """
        # Check for time-based queries
        if any(keyword in query_lower for keyword in self.TIME_KEYWORDS):
            # Time-based with research keywords = complex time-based research
            if any(keyword in query_lower for keyword in self.RESEARCH_KEYWORDS):
                return QueryAnalysis(
                    query_type="time_based",
                    requires_planning=True,
                    required_subagents=["tool_executor", "planner", "search_scraper"],
                    execution_strategy="sequential",
                    estimated_complexity="high",
                    confidence=0.85,
                )
            else:
                # Simple time-based query
                return QueryAnalysis(
                    query_type="time_based",
                    requires_planning=False,
                    required_subagents=["tool_executor", "search_scraper"],
                    execution_strategy="sequential",
                    estimated_complexity="medium",
                    confidence=0.9,
                )

        # Check for comparison queries
        if any(keyword in query_lower for keyword in self.COMPARISON_KEYWORDS):
            return QueryAnalysis(
                query_type="comparison",
                requires_planning=True,
                required_subagents=["planner", "search_scraper"],
                execution_strategy="sequential",
                estimated_complexity="high",
                confidence=0.9,
            )

        # Check for simple questions
        if any(query_lower.startswith(keyword) for keyword in self.SIMPLE_QUESTION_KEYWORDS):
            # Check if it's actually complex despite the phrasing
            word_count = len(query_lower.split())
            if word_count <= 6:  # Short questions are usually simple
                return QueryAnalysis(
                    query_type="simple_fact",
                    requires_planning=False,
                    required_subagents=["search_scraper"],
                    execution_strategy="direct",
                    estimated_complexity="low",
                    confidence=0.8,
                )

        # Check for research/analysis queries
        if any(keyword in query_lower for keyword in self.RESEARCH_KEYWORDS):
            return QueryAnalysis(
                query_type="complex_research",
                requires_planning=True,
                required_subagents=["planner", "search_scraper"],
                execution_strategy="sequential",
                estimated_complexity="high",
                confidence=0.85,
            )

        # Check for simple search (news, updates)
        if any(keyword in query_lower for keyword in ["news", "update", "information"]):
            return QueryAnalysis(
                query_type="simple_search",
                requires_planning=False,
                required_subagents=["search_scraper"],
                execution_strategy="direct",
                estimated_complexity="low",
                confidence=0.8,
            )

        # Not confident enough for keyword classification
        return None

    async def _llm_classify(
        self,
        query: str,
        conversation_history: Optional[list[dict]] = None
    ) -> QueryAnalysis:
        """
        LLM-based classification for ambiguous queries.

        Args:
            query: User's query string
            conversation_history: Optional conversation context

        Returns:
            QueryAnalysis based on LLM classification
        """
        # Build classification prompt
        prompt = f"""Analyze the following user query and classify it for routing to appropriate research agents.

User Query: "{query}"

Classify the query type as ONE of:
- simple_fact: Single concept definitions or straightforward questions
- simple_search: Current information, news, or updates
- complex_research: Multi-faceted research requiring deep analysis
- time_based: Questions involving specific dates or time periods
- comparison: Comparing two or more things
- general: Default for unclear queries

Also determine:
- requires_planning: true if the query benefits from a structured research plan, false otherwise
- complexity: low, medium, or high

Respond ONLY with a JSON object in this exact format:
{{
    "query_type": "...",
    "requires_planning": true/false,
    "complexity": "low/medium/high"
}}"""

        try:
            # Use LLM for classification
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=150,
            )

            # Handle empty response
            if not response or not response.strip():
                raise ValueError("Empty response from LLM")

            # Try to extract JSON from response (LLM might include extra text)
            response_text = response.strip()

            # Try to find JSON object in the response
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group()

            # Parse JSON response
            classification = json.loads(response_text)

            # Map to QueryAnalysis
            query_type = classification.get("query_type", "general")
            requires_planning = classification.get("requires_planning", False)
            complexity = classification.get("complexity", "medium")

            # Determine required subagents based on classification
            if query_type == "time_based":
                required_subagents = ["tool_executor", "search_scraper"]
                if requires_planning:
                    required_subagents.insert(1, "planner")
            elif requires_planning:
                required_subagents = ["planner", "search_scraper"]
            else:
                required_subagents = ["search_scraper"]

            # Determine execution strategy
            if query_type == "time_based":
                execution_strategy = "sequential"  # Datetime must come first
            elif requires_planning:
                execution_strategy = "sequential"  # Planner must come first
            else:
                execution_strategy = "direct"  # No orchestration needed

            return QueryAnalysis(
                query_type=query_type,
                requires_planning=requires_planning,
                required_subagents=required_subagents,
                execution_strategy=execution_strategy,
                estimated_complexity=complexity,
                confidence=0.7,  # LLM classification is less confident than keyword
            )

        except (json.JSONDecodeError, KeyError, Exception) as e:
            # Fallback to safe default if LLM classification fails
            print(f"LLM classification failed: {e}, using fallback")
            return QueryAnalysis(
                query_type="general",
                requires_planning=False,
                required_subagents=["search_scraper"],
                execution_strategy="direct",
                estimated_complexity="medium",
                confidence=0.5,
            )
