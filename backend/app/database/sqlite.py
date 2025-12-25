import json
import uuid
import aiosqlite
from datetime import datetime
from typing import Optional, List
from .base import ChatStorage, Message, Conversation, MessageRole


class SQLiteChatStorage(ChatStorage):
    """SQLite implementation of chat storage (default/fallback)."""

    def __init__(self, database_path: str = "chat_history.db"):
        self.database_path = database_path
        self.db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Create connection and initialize tables."""
        self.db = await aiosqlite.connect(self.database_path)
        self.db.row_factory = aiosqlite.Row

        # Create tables
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """)

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT,
                metadata TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)

        # Create indexes
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
            ON messages(conversation_id)
        """)
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_updated_at 
            ON conversations(updated_at)
        """)

        # Enable foreign keys
        await self.db.execute("PRAGMA foreign_keys = ON")

        await self.db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self.db:
            await self.db.close()

    async def create_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Conversation:
        """Create a new conversation."""
        now = datetime.utcnow().isoformat()

        await self.db.execute(
            """
            INSERT INTO conversations (id, title, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET updated_at = ?
            """,
            (
                conversation_id,
                title,
                now,
                now,
                json.dumps(metadata) if metadata else None,
                now,
            ),
        )
        await self.db.commit()

        return Conversation(
            id=conversation_id,
            title=title,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            metadata=metadata,
        )

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        async with self.db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return Conversation(
                id=row["id"],
                title=row["title"],
                created_at=datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else datetime.utcnow(),
                updated_at=datetime.fromisoformat(row["updated_at"])
                if row["updated_at"]
                else datetime.utcnow(),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
        return None

    async def list_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Conversation]:
        """List conversations ordered by updated_at descending."""
        async with self.db.execute(
            """
            SELECT * FROM conversations 
            ORDER BY updated_at DESC 
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            Conversation(
                id=row["id"],
                title=row["title"],
                created_at=datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else datetime.utcnow(),
                updated_at=datetime.fromisoformat(row["updated_at"])
                if row["updated_at"]
                else datetime.utcnow(),
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
        now = datetime.utcnow().isoformat()

        # Build update query dynamically
        updates = ["updated_at = ?"]
        params = [now]

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        params.append(conversation_id)

        await self.db.execute(
            f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?", params
        )
        await self.db.commit()

        return await self.get_conversation(conversation_id)

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        cursor = await self.db.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Message:
        """Add a message to a conversation."""
        message_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Ensure conversation exists
        await self.db.execute(
            """
            INSERT INTO conversations (id, created_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET updated_at = ?
            """,
            (conversation_id, now, now, now),
        )

        # Insert message
        await self.db.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                role.value,
                content,
                now,
                json.dumps(metadata) if metadata else None,
            ),
        )
        await self.db.commit()

        return Message(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.fromisoformat(now),
            metadata=metadata,
        )

    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        before_id: Optional[str] = None,
    ) -> List[Message]:
        """Get messages for a conversation."""
        query = "SELECT * FROM messages WHERE conversation_id = ?"
        params = [conversation_id]

        if before_id:
            query += " AND created_at < (SELECT created_at FROM messages WHERE id = ?)"
            params.append(before_id)

        query += " ORDER BY created_at ASC"

        if limit:
            query += f" LIMIT {limit}"

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [
            Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=MessageRole(row["role"]),
                content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else datetime.utcnow(),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    async def delete_messages(self, conversation_id: str) -> int:
        """Delete all messages in a conversation."""
        cursor = await self.db.execute(
            "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
        )
        await self.db.commit()
        return cursor.rowcount

    async def generate_title(self, conversation_id: str, first_message: str) -> str:
        """Generate a title from the first message."""
        # Simple title generation - take first 50 chars
        title = first_message[:50].strip()
        if len(first_message) > 50:
            title += "..."

        await self.update_conversation(conversation_id, title=title)
        return title
