from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """A single message in a conversation."""

    id: Optional[str] = None
    conversation_id: str
    role: MessageRole
    content: str
    created_at: datetime = datetime.utcnow()
    metadata: Optional[dict] = None  # For tool calls, etc.


class Conversation(BaseModel):
    """A conversation/chat session."""

    id: str
    title: Optional[str] = None
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()
    metadata: Optional[dict] = None  # For settings, provider info, etc.


class ChatStorage(ABC):
    """Abstract base class for chat storage backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage (create tables, etc.)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the storage connection."""
        pass

    # Conversation methods
    @abstractmethod
    async def create_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Conversation:
        """Create a new conversation."""
        pass

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        pass

    @abstractmethod
    async def list_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Conversation]:
        """List conversations ordered by updated_at descending."""
        pass

    @abstractmethod
    async def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Conversation]:
        """Update a conversation."""
        pass

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        pass

    # Message methods
    @abstractmethod
    async def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Message:
        """Add a message to a conversation."""
        pass

    @abstractmethod
    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        before_id: Optional[str] = None,
    ) -> List[Message]:
        """Get messages for a conversation, ordered by created_at ascending."""
        pass

    @abstractmethod
    async def delete_messages(self, conversation_id: str) -> int:
        """Delete all messages in a conversation. Returns count deleted."""
        pass

    # Utility methods
    @abstractmethod
    async def generate_title(self, conversation_id: str, first_message: str) -> str:
        """Generate a title for a conversation based on the first message."""
        pass
