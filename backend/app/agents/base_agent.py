"""
Base classes and utilities for multi-agent system.
"""

from typing import Callable, Optional
from abc import ABC, abstractmethod
from .types import SubagentResult


class BaseAgent(ABC):
    """
    Abstract base class for all agents (Master and Subagents).

    Provides common functionality for progress callbacks,
    error handling, and state management.
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[dict], None]] = None
    ):
        """
        Initialize base agent.

        Args:
            progress_callback: Optional callback for progress events
        """
        self.progress_callback = progress_callback

    def _emit_progress(
        self,
        step: str,
        status: str = "in_progress",
        detail: str = "",
        progress: int = 0,
        source: Optional[str] = None,
    ):
        """
        Emit a progress event.

        Args:
            step: Current step name
            status: Status of the step (in_progress, completed, failed)
            detail: Detailed description of what's happening
            progress: Progress percentage (0-100)
            source: Optional source identifier (e.g., "planner_agent")
        """
        if self.progress_callback:
            event = {
                "type": "progress",
                "step": step,
                "status": status,
                "detail": detail,
                "progress": progress,
            }
            if source:
                event["source"] = source

            self.progress_callback(event)

    def _create_subagent_callback(self, subagent_name: str) -> Callable[[dict], None]:
        """
        Create a progress callback wrapper for a subagent.

        This wrapper adds a "source" field to all events emitted by
        the subagent, allowing the frontend to identify which subagent
        is producing the progress updates.

        Args:
            subagent_name: Name of the subagent

        Returns:
            Wrapped callback function
        """
        def callback(event: dict):
            # Add source to track which subagent emitted the event
            event["source"] = subagent_name

            # Emit to parent callback
            if self.progress_callback:
                self.progress_callback(event)

        return callback

    async def _execute_subagent_safe(
        self,
        subagent: 'BaseAgent',
        subagent_name: str,
        execute_method: str = "execute",
        **kwargs
    ) -> SubagentResult:
        """
        Execute a subagent with error handling and progress wrapping.

        Args:
            subagent: The subagent instance to execute
            subagent_name: Name of the subagent (for error reporting)
            execute_method: Name of the method to call (default: "execute")
            **kwargs: Arguments to pass to the subagent's execute method

        Returns:
            SubagentResult with success/failure information
        """
        try:
            # Wrap subagent's progress callback
            wrapped_callback = self._create_subagent_callback(subagent_name)
            subagent.progress_callback = wrapped_callback

            # Execute the subagent
            method = getattr(subagent, execute_method)
            result = await method(**kwargs)

            if not result.success:
                # Subagent returned an error
                self._emit_progress(
                    step="subagent_error",
                    status="failed",
                    detail=f"{subagent_name} encountered an issue: {result.error}",
                    source="master_agent",
                )

            return SubagentResult(
                subagent=subagent_name,
                success=result.success,
                data=result.data,
                error=result.error,
            )

        except Exception as e:
            # Unexpected exception during execution
            error_msg = f"Unexpected error in {subagent_name}: {str(e)}"
            self._emit_progress(
                step="subagent_exception",
                status="failed",
                detail=error_msg,
                source="master_agent",
            )

            return SubagentResult(
                subagent=subagent_name,
                success=False,
                data=None,
                error=error_msg,
            )

    @abstractmethod
    async def execute(self, **kwargs):
        """
        Execute the agent's main logic.

        All agents must implement this method.
        """
        pass


def format_conversation_history(messages: list[dict], max_messages: int = 10) -> str:
    """
    Format conversation history for inclusion in prompts.

    Args:
        messages: List of message dictionaries
        max_messages: Maximum number of recent messages to include

    Returns:
        Formatted string representation of conversation history
    """
    if not messages:
        return "No previous conversation."

    # Take only the most recent messages
    recent_messages = messages[-max_messages:]

    formatted = []
    for msg in recent_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # Truncate very long messages
        if len(content) > 500:
            content = content[:500] + "..."

        formatted.append(f"{role.upper()}: {content}")

    return "\n".join(formatted)
