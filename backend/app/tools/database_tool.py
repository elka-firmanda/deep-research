from typing import Optional, Dict, Any, List, Literal
import json
from .base import BaseTool, ToolResult


class DatabaseTool(BaseTool):
    """Database query tool for executing SQL queries against various database types."""

    name = "database_query"
    description = "Execute SQL queries against configured databases (PostgreSQL, MySQL, ClickHouse, BigQuery). Returns query results as structured data."

    def __init__(self, connections: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize database tool with connection configurations.

        Args:
            connections: List of database connection configurations
        """
        self.connections = connections or []
        self.connection_map = {conn.get('name'): conn for conn in self.connections}

    async def execute(
        self,
        query: str,
        connection_name: str,
        limit: int = 100,
    ) -> ToolResult:
        """
        Execute a SQL query against a specified database connection.

        Args:
            query: The SQL query to execute
            connection_name: Name of the database connection to use
            limit: Maximum number of rows to return
        """
        try:
            # Get connection config
            if connection_name not in self.connection_map:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Database connection '{connection_name}' not found. Available connections: {list(self.connection_map.keys())}"
                )

            conn_config = self.connection_map[connection_name]
            db_type = conn_config.get('type')

            # Execute query based on database type
            if db_type == 'postgres':
                result = await self._execute_postgres(conn_config, query, limit)
            elif db_type == 'mysql':
                result = await self._execute_mysql(conn_config, query, limit)
            elif db_type == 'clickhouse':
                result = await self._execute_clickhouse(conn_config, query, limit)
            elif db_type == 'bigquery':
                result = await self._execute_bigquery(conn_config, query, limit)
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Unsupported database type: {db_type}"
                )

            return ToolResult(success=True, data=result)

        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Database query error: {str(e)}")

    async def _execute_postgres(self, config: Dict[str, Any], query: str, limit: int) -> Dict[str, Any]:
        """Execute query against PostgreSQL database."""
        try:
            import asyncpg
        except ImportError:
            raise ImportError("asyncpg library is required for PostgreSQL. Install with: pip install asyncpg")

        # Add LIMIT clause if not present
        query_lower = query.lower()
        if 'limit' not in query_lower and 'select' in query_lower:
            query = f"{query.rstrip(';')} LIMIT {limit}"

        conn = await asyncpg.connect(
            host=config.get('host', 'localhost'),
            port=config.get('port', 5432),
            database=config.get('database'),
            user=config.get('username'),
            password=config.get('password'),
        )

        try:
            rows = await conn.fetch(query)
            columns = list(rows[0].keys()) if rows else []
            data = [dict(row) for row in rows]

            return {
                'columns': columns,
                'rows': data,
                'row_count': len(data),
                'query': query,
            }
        finally:
            await conn.close()

    async def _execute_mysql(self, config: Dict[str, Any], query: str, limit: int) -> Dict[str, Any]:
        """Execute query against MySQL database."""
        try:
            import aiomysql
        except ImportError:
            raise ImportError("aiomysql library is required for MySQL. Install with: pip install aiomysql")

        # Add LIMIT clause if not present
        query_lower = query.lower()
        if 'limit' not in query_lower and 'select' in query_lower:
            query = f"{query.rstrip(';')} LIMIT {limit}"

        conn = await aiomysql.connect(
            host=config.get('host', 'localhost'),
            port=config.get('port', 3306),
            db=config.get('database'),
            user=config.get('username'),
            password=config.get('password'),
        )

        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query)
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                return {
                    'columns': columns,
                    'rows': rows,
                    'row_count': len(rows),
                    'query': query,
                }
        finally:
            conn.close()

    async def _execute_clickhouse(self, config: Dict[str, Any], query: str, limit: int) -> Dict[str, Any]:
        """Execute query against ClickHouse database."""
        try:
            from clickhouse_driver import Client
        except ImportError:
            raise ImportError("clickhouse-driver library is required for ClickHouse. Install with: pip install clickhouse-driver")

        # Add LIMIT clause if not present
        query_lower = query.lower()
        if 'limit' not in query_lower and 'select' in query_lower:
            query = f"{query.rstrip(';')} LIMIT {limit}"

        # Note: clickhouse-driver is sync, we'll run it in a thread pool
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _sync_query():
            client = Client(
                host=config.get('host', 'localhost'),
                port=config.get('port', 9000),
                database=config.get('database', 'default'),
                user=config.get('username', 'default'),
                password=config.get('password', ''),
            )

            result = client.execute(query, with_column_types=True)
            data, columns_info = result
            columns = [col[0] for col in columns_info]
            rows = [dict(zip(columns, row)) for row in data]

            return {
                'columns': columns,
                'rows': rows,
                'row_count': len(rows),
                'query': query,
            }

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_query)

        return result

    async def _execute_bigquery(self, config: Dict[str, Any], query: str, limit: int) -> Dict[str, Any]:
        """Execute query against Google BigQuery."""
        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account
        except ImportError:
            raise ImportError("google-cloud-bigquery library is required for BigQuery. Install with: pip install google-cloud-bigquery")

        # Add LIMIT clause if not present
        query_lower = query.lower()
        if 'limit' not in query_lower and 'select' in query_lower:
            query = f"{query.rstrip(';')} LIMIT {limit}"

        # Parse service account credentials
        credentials_json = config.get('credentials_json')
        if not credentials_json:
            raise ValueError("BigQuery requires 'credentials_json' in connection config")

        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)

        client = bigquery.Client(
            credentials=credentials,
            project=config.get('project_id'),
        )

        # Execute query asynchronously using thread pool
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _sync_query():
            query_job = client.query(query)
            results = query_job.result()

            # Extract column names and rows
            columns = [field.name for field in results.schema]
            rows = [dict(row) for row in results]

            return {
                'columns': columns,
                'rows': rows,
                'row_count': len(rows),
                'query': query,
                'bytes_processed': query_job.total_bytes_processed,
            }

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_query)

        return result

    def get_schema(self) -> dict:
        available_connections = list(self.connection_map.keys())

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute. Use standard SQL syntax compatible with the target database.",
                    },
                    "connection_name": {
                        "type": "string",
                        "description": f"Name of the database connection to use. Available connections: {', '.join(available_connections) if available_connections else 'none configured'}",
                        "enum": available_connections if available_connections else ["no_connections"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of rows to return",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 10000,
                    },
                },
                "required": ["query", "connection_name"],
            },
        }
