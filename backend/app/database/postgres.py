import json
import uuid
from datetime import datetime
from typing import Optional, List
from .base import ChatStorage, Message, Conversation, MessageRole

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False


class PostgresChatStorage(ChatStorage):
    """PostgreSQL implementation of chat storage."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "ai_agent",
        user: str = "postgres",
        password: str = "",
        **kwargs,
    ):
        if not ASYNCPG_AVAILABLE:
            raise ImportError(
                "asyncpg is required for PostgreSQL storage. Install with: pip install asyncpg"
            )

        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """Create connection pool and initialize tables."""
        self.pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            min_size=2,
            max_size=10,
        )

        # Create tables
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR(255) PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id VARCHAR(255) PRIMARY KEY,
                    conversation_id VARCHAR(255) REFERENCES conversations(id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
            """)

            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
                ON messages(conversation_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_updated_at 
                ON conversations(updated_at DESC)
            """)

    async def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()

    async def create_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Conversation:
        """Create a new conversation."""
        now = datetime.utcnow()

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at, metadata)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO UPDATE SET updated_at = $4
                """,
                conversation_id,
                title,
                now,
                now,
                json.dumps(metadata) if metadata else None,
            )

        return Conversation(
            id=conversation_id,
            title=title,
            created_at=now,
            updated_at=now,
            metadata=metadata,
        )

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM conversations WHERE id = $1", conversation_id
            )

        if row:
            return Conversation(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
        return None

    async def list_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Conversation]:
        """List conversations ordered by updated_at descending."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM conversations 
                ORDER BY updated_at DESC 
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

        return [
            Conversation(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    async def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Conversation]:
        """Update a conversation."""
        now = datetime.utcnow()

        async with self.pool.acquire() as conn:
            # Build update query dynamically
            updates = ["updated_at = $2"]
            params = [conversation_id, now]
            param_idx = 3

            if title is not None:
                updates.append(f"title = ${param_idx}")
                params.append(title)
                param_idx += 1

            if metadata is not None:
                updates.append(f"metadata = ${param_idx}")
                params.append(json.dumps(metadata))
                param_idx += 1

            query = f"UPDATE conversations SET {', '.join(updates)} WHERE id = $1 RETURNING *"
            row = await conn.fetchrow(query, *params)

        if row:
            return Conversation(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
        return None

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM conversations WHERE id = $1", conversation_id
            )
        return "DELETE 1" in result

    async def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Message:
        """Add a message to a conversation."""
        message_id = str(uuid.uuid4())
        now = datetime.utcnow()

        async with self.pool.acquire() as conn:
            # Ensure conversation exists
            await conn.execute(
                """
                INSERT INTO conversations (id, created_at, updated_at)
                VALUES ($1, $2, $2)
                ON CONFLICT (id) DO UPDATE SET updated_at = $2
                """,
                conversation_id,
                now,
            )

            # Insert message
            await conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, created_at, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                message_id,
                conversation_id,
                role.value,
                content,
                now,
                json.dumps(metadata) if metadata else None,
            )

        return Message(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=now,
            metadata=metadata,
        )

    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        before_id: Optional[str] = None,
    ) -> List[Message]:
        """Get messages for a conversation."""
        async with self.pool.acquire() as conn:
            query = "SELECT * FROM messages WHERE conversation_id = $1"
            params = [conversation_id]

            if before_id:
                query += (
                    " AND created_at < (SELECT created_at FROM messages WHERE id = $2)"
                )
                params.append(before_id)

            query += " ORDER BY created_at ASC"

            if limit:
                query += f" LIMIT {limit}"

            rows = await conn.fetch(query, *params)

        return [
            Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=MessageRole(row["role"]),
                content=row["content"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    async def delete_messages(self, conversation_id: str) -> int:
        """Delete all messages in a conversation."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM messages WHERE conversation_id = $1", conversation_id
            )
        # Parse "DELETE N" result
        try:
            return int(result.split()[-1])
        except:
            return 0

    async def generate_title(self, conversation_id: str, first_message: str) -> str:
        """Generate a title from the first message."""
        # Simple title generation - take first 50 chars
        title = first_message[:50].strip()
        if len(first_message) > 50:
            title += "..."

        await self.update_conversation(conversation_id, title=title)
        return title
