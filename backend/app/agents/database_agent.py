"""
DatabaseAgent - Subagent for database queries and analysis.

Handles SQL query generation and execution against configured databases.
Supports PostgreSQL, MySQL, ClickHouse, and BigQuery.
"""

from typing import Optional, List, Dict, Any
from ..tools import DatabaseTool, BaseTool, ToolResult
from ..core.llm_providers import get_llm_client
from .base_agent import BaseAgent


DEFAULT_SYSTEM_PROMPT = """You are a database query specialist. Your role is to:

1. **Understand user requests** and translate them into appropriate SQL queries
2. **Generate SQL queries** that are safe, efficient, and correct for the target database
3. **Analyze query results** and present them in a clear, human-readable format
4. **Explain findings** with context and insights

## Important Guidelines

- **SQL Safety**: Never use DELETE, DROP, TRUNCATE, or other destructive operations unless explicitly confirmed
- **Query Optimization**: Use appropriate WHERE clauses, JOINs, and indexes
- **Result Interpretation**: Explain what the data means, not just what it shows
- **Error Handling**: If a query fails, explain why and suggest corrections
- **Database-Specific SQL**: Adapt SQL syntax to the target database type (PostgreSQL, MySQL, ClickHouse, BigQuery)

## Response Format

When presenting query results:
1. State what you searched for
2. Show the SQL query used
3. Present the data in a readable format (tables, lists, or narrative)
4. Provide insights or observations about the data
5. Suggest follow-up queries if relevant

Always be precise and data-driven in your analysis."""


class DatabaseAgent(BaseAgent):
    """
    Subagent responsible for database operations.

    Capabilities:
    - Generate SQL queries from natural language
    - Execute queries against multiple database types
    - Analyze and present results
    - Provide data insights
    """

    def __init__(
        self,
        database_connections: Optional[List[Dict[str, Any]]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ):
        """
        Initialize DatabaseAgent.

        Args:
            database_connections: List of database connection configurations
            provider: LLM provider (openai, anthropic, openrouter)
            model: Model name to use
            system_prompt: Custom system prompt (uses default if None)
            progress_callback: Optional callback for progress events
        """
        super().__init__(progress_callback)
        self.database_connections = database_connections or []
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        # Initialize database tool
        self.database_tool = DatabaseTool(connections=self.database_connections)

        # Initialize LLM client if provider specified
        self.llm_client = None
        if self.provider:
            self.llm_client = get_llm_client(self.provider, self.model)

    async def query(
        self,
        user_query: str,
        connection_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process a natural language query about database data.

        Args:
            user_query: Natural language question or request
            connection_name: Specific database connection to use (optional)
            **kwargs: Additional context

        Returns:
            Dict with 'response' (analysis) and 'data' (raw query results)
        """
        self._emit_progress(
            step="database_agent_start",
            status="in_progress",
            detail=f"Analyzing query: {user_query[:50]}...",
            progress=10,
            source="database_agent",
            agent_name="DatabaseAgent",
            agent_icon="🗄️",
        )

        if not self.database_connections:
            error_msg = "No database connections configured. Please add database connections in settings."
            self._emit_progress(
                step="database_agent_error",
                status="failed",
                detail="No database connections",
                progress=100,
                source="database_agent",
                agent_name="DatabaseAgent",
                agent_icon="🗄️",
            )
            return {
                'response': error_msg,
                'data': None,
                'error': error_msg,
            }

        try:
            # If no specific connection specified, use the first one
            if not connection_name and self.database_connections:
                connection_name = self.database_connections[0].get('name')

            # Use LLM to generate SQL and analyze results if available
            if self.llm_client:
                response = await self._llm_query(user_query, connection_name)
            else:
                # Fallback: require explicit SQL query
                response = await self._direct_query(user_query, connection_name)

            self._emit_progress(
                step="database_agent_complete",
                status="completed",
                detail="Query executed successfully",
                progress=100,
                source="database_agent",
                agent_name="DatabaseAgent",
                agent_icon="🗄️",
            )

            return response

        except Exception as e:
            error_msg = f"Database query error: {str(e)}"
            self._emit_progress(
                step="database_agent_error",
                status="failed",
                detail="Query execution failed",
                progress=100,
                source="database_agent",
                agent_name="DatabaseAgent",
                agent_icon="🗄️",
            )
            return {
                'response': error_msg,
                'data': None,
                'error': error_msg,
            }

    async def _llm_query(self, user_query: str, connection_name: str) -> Dict[str, Any]:
        """Use LLM to generate SQL and analyze results."""

        # Get connection info for context
        conn_info = next((c for c in self.database_connections if c.get('name') == connection_name), None)
        db_type = conn_info.get('type') if conn_info else 'unknown'

        self._emit_progress(
            step="database_generate_sql",
            status="in_progress",
            detail=f"Generating SQL for {db_type}",
            progress=30,
            source="database_agent",
            agent_name="DatabaseAgent",
            agent_icon="🗄️",
        )

        # Build prompt for SQL generation
        sql_prompt = f"""Database Type: {db_type}
Connection: {connection_name}

User Request: {user_query}

Generate a SQL query to fulfill this request. Return ONLY the SQL query, no explanation or markdown.
Make sure the query is safe (read-only) and optimized for the {db_type} database."""

        # Get SQL from LLM
        sql_query = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": sql_prompt}
            ],
            temperature=0.1,  # Low temperature for precise SQL generation
        )

        # Clean up the SQL (remove markdown code blocks if present)
        sql_query = sql_query.strip()
        if sql_query.startswith('```'):
            lines = sql_query.split('\n')
            sql_query = '\n'.join(lines[1:-1] if len(lines) > 2 else lines[1:])
        sql_query = sql_query.strip()

        self._emit_progress(
            step="database_execute_query",
            status="in_progress",
            detail=f"Executing: {sql_query[:50]}...",
            progress=60,
            source="database_agent",
            agent_name="DatabaseAgent",
            agent_icon="🗄️",
        )

        # Execute the query
        result = await self.database_tool.execute(
            query=sql_query,
            connection_name=connection_name,
        )

        if not result.success:
            return {
                'response': f"Query failed: {result.error}\n\nGenerated SQL:\n```sql\n{sql_query}\n```",
                'data': None,
                'error': result.error,
                'sql': sql_query,
            }

        self._emit_progress(
            step="database_analyze_results",
            status="in_progress",
            detail="Analyzing query results",
            progress=80,
            source="database_agent",
            agent_name="DatabaseAgent",
            agent_icon="🗄️",
        )

        # Use LLM to analyze results
        analysis_prompt = f"""User Request: {user_query}

SQL Query:
```sql
{sql_query}
```

Query Results:
{self._format_results_for_llm(result.data)}

Analyze these results and provide a clear, insightful response to the user's request. Include:
1. Direct answer to their question
2. Key findings from the data
3. Any notable patterns or insights
4. The SQL query used (in a code block)"""

        analysis = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
        )

        return {
            'response': analysis,
            'data': result.data,
            'sql': sql_query,
        }

    async def _direct_query(self, sql_query: str, connection_name: str) -> Dict[str, Any]:
        """Execute SQL directly without LLM assistance."""

        self._emit_progress(
            step="database_execute_query",
            status="in_progress",
            detail=f"Executing query",
            progress=50,
            source="database_agent",
            agent_name="DatabaseAgent",
            agent_icon="🗄️",
        )

        result = await self.database_tool.execute(
            query=sql_query,
            connection_name=connection_name,
        )

        if not result.success:
            return {
                'response': f"Query failed: {result.error}",
                'data': None,
                'error': result.error,
            }

        # Format results as a simple text response
        response = f"Query executed successfully.\n\n"
        response += f"SQL:\n```sql\n{sql_query}\n```\n\n"
        response += f"Results: {result.data.get('row_count', 0)} rows returned"

        return {
            'response': response,
            'data': result.data,
            'sql': sql_query,
        }

    def _format_results_for_llm(self, data: Dict[str, Any]) -> str:
        """Format query results for LLM analysis."""
        if not data:
            return "No results"

        rows = data.get('rows', [])
        columns = data.get('columns', [])
        row_count = data.get('row_count', 0)

        if row_count == 0:
            return "No rows returned"

        # Format as markdown table for readability
        output = f"Total rows: {row_count}\n\n"

        # Limit to first 20 rows for LLM context
        display_rows = rows[:20]

        if columns and display_rows:
            # Table header
            output += "| " + " | ".join(columns) + " |\n"
            output += "| " + " | ".join(["---"] * len(columns)) + " |\n"

            # Table rows
            for row in display_rows:
                values = [str(row.get(col, '')) for col in columns]
                output += "| " + " | ".join(values) + " |\n"

            if row_count > 20:
                output += f"\n... and {row_count - 20} more rows"

        return output

    def get_available_connections(self) -> List[str]:
        """Get list of available database connection names."""
        return [conn.get('name') for conn in self.database_connections if conn.get('name')]
