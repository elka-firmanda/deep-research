"""
Shared types and data structures for multi-agent orchestration system.
"""

from dataclasses import dataclass
from typing import Literal, Optional, Any
from enum import Enum


# Query types for classification
QueryType = Literal[
    "simple_fact",       # "What is...?", single concept questions
    "simple_search",     # "Latest AI news", current information
    "complex_research",  # Multi-faceted research questions
    "time_based",        # Questions involving dates/time
    "comparison",        # "Compare X vs Y"
    "general",          # Default/fallback
]

# Execution strategies for subagent coordination
ExecutionStrategy = Literal[
    "sequential",   # Execute subagents in order (e.g., Planner → SearchScraper)
    "parallel",     # Execute subagents concurrently
    "conditional",  # Execute based on runtime conditions
    "direct",       # Skip orchestration, direct execution
]


@dataclass
class QueryAnalysis:
    """
    Result of query analysis containing routing information.
    """
    query_type: QueryType
    requires_planning: bool
    required_subagents: list[str]  # ["planner", "search_scraper", "tool_executor"]
    execution_strategy: ExecutionStrategy
    estimated_complexity: Literal["low", "medium", "high"]
    confidence: float = 1.0  # Confidence in classification (0-1)


@dataclass
class SubagentContext:
    """
    Context passed to all subagents for shared state.
    """
    conversation_history: list[dict]  # Full message history
    current_query: str  # User's current request
    llm_provider: str  # LLM provider name
    llm_model: str  # Specific model ID
    timezone: str  # User's timezone
    previous_results: Optional[list['SubagentResult']] = None  # Results from earlier subagents


@dataclass
class SubagentResult:
    """
    Result from a subagent execution.
    """
    subagent: str  # Name of the subagent that produced this result
    success: bool  # Whether execution was successful
    data: Optional[Any] = None  # Result data (structure depends on subagent)
    error: Optional[str] = None  # Error message if failed
    metadata: Optional[dict] = None  # Additional metadata


class SubagentType(str, Enum):
    """Enum of available subagent types"""
    PLANNER = "planner"
    SEARCH_SCRAPER = "search_scraper"
    TOOL_EXECUTOR = "tool_executor"
