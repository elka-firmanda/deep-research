"""
ToolExecutorAgent - Subagent for executing utility tools.

Handles non-search tools like datetime, and can be extended
with additional utility tools in the future.
"""

from typing import Optional
from ..tools import DateTimeTool, BaseTool, ToolResult
from .base_agent import BaseAgent


class ToolExecutorAgent(BaseAgent):
    """
    Subagent responsible for executing utility tools.

    Currently supports:
    - get_current_datetime: Date/time operations

    Future extensions:
    - calculator: Mathematical computations
    - code_executor: Code execution
    - data_analyzer: Data processing
    """

    def __init__(
        self,
        timezone: str = "UTC",
        progress_callback: Optional[callable] = None
    ):
        """
        Initialize ToolExecutorAgent.

        Args:
            timezone: User's timezone for datetime operations
            progress_callback: Optional callback for progress events
        """
        super().__init__(progress_callback)
        self.timezone = timezone

        # Initialize available tools
        self.tools: dict[str, BaseTool] = {
            "get_current_datetime": DateTimeTool(),
            # Future tools can be added here:
            # "calculator": CalculatorTool(),
            # "code_executor": CodeExecutorTool(),
        }

    async def execute(
        self,
        tool_name: str,
        arguments: Optional[dict] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute a specific utility tool.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            **kwargs: Additional context (ignored for now)

        Returns:
            ToolResult with success/failure and data
        """
        # Create descriptive message based on tool
        tool_descriptions = {
            "get_current_datetime": f"Getting current date/time in {self.timezone}",
            "calculator": "Performing calculation",
        }
        detail = tool_descriptions.get(tool_name, f"Running {tool_name}")

        self._emit_progress(
            step="tool_executor_start",
            status="in_progress",
            detail=detail,
            progress=10,
            source="tool_executor_agent",
            agent_name="ToolExecutorAgent",
            agent_icon="🔧",
        )

        if tool_name not in self.tools:
            error_msg = f"Unknown tool: {tool_name}. Available tools: {list(self.tools.keys())}"
            self._emit_progress(
                step="tool_executor_error",
                status="failed",
                detail="Tool not found",
                progress=100,
                source="tool_executor_agent",
                agent_name="ToolExecutorAgent",
                agent_icon="🔧",
            )
            return ToolResult(
                success=False,
                data=None,
                error=error_msg,
            )

        try:
            # Get the tool
            tool = self.tools[tool_name]

            # Add timezone to arguments if it's the datetime tool
            if tool_name == "get_current_datetime" and arguments:
                if "timezone" not in arguments:
                    arguments["timezone"] = self.timezone

            # Execute the tool
            result = await tool.execute(**(arguments or {}))

            self._emit_progress(
                step="tool_executor_complete",
                status="completed",
                detail=f"Completed {tool_name}",
                progress=100,
                source="tool_executor_agent",
                agent_name="ToolExecutorAgent",
                agent_icon="🔧",
            )

            return result

        except Exception as e:
            error_msg = f"Error executing {tool_name}: {str(e)}"
            self._emit_progress(
                step="tool_executor_error",
                status="failed",
                detail=f"Error in {tool_name}",
                progress=100,
                source="tool_executor_agent",
                agent_name="ToolExecutorAgent",
                agent_icon="🔧",
            )
            return ToolResult(
                success=False,
                data=None,
                error=error_msg,
            )

    def get_available_tools(self) -> list[str]:
        """
        Get list of available tool names.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())

    def add_tool(self, name: str, tool: BaseTool):
        """
        Add a new tool to the executor.

        Args:
            name: Name to register the tool under
            tool: Tool instance
        """
        self.tools[name] = tool
