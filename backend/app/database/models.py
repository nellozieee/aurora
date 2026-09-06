"""ORM models.

Models are added incrementally as each subsystem is implemented
(Memory in the memory phase, Task/Automation in the automation phase, etc.).
Importing this module registers all models on `Base.metadata`, which
Alembic's migration environment relies on for autogeneration.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.config import get_settings
from app.database.database import Base

__all__ = [
    "Base",
    "Conversation",
    "Message",
    "Memory",
    "AgentRun",
    "ToolExecution",
    "Automation",
    "Task",
]

# Memory types, per the master spec's memory-privacy classification:
# temporary | conversation | useful | persistent | sensitive
MemoryType = str


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text)
    memory_type: Mapped[str] = mapped_column(Text, default="useful")
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().memory_embedding_dimensions), nullable=True
    )
    memory_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class AgentRun(Base):
    """One orchestrator turn: which agent handled it, and how it went."""

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_conversation_id_started_at", "conversation_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    agent_name: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="running")  # running|completed|failed
    steps_taken: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    tool_executions: Mapped[list[ToolExecution]] = relationship(
        back_populates="agent_run", cascade="all, delete-orphan", order_by="ToolExecution.created_at"
    )


class ToolExecution(Base):
    """One tool call made during an agent run."""

    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE")
    )
    tool_name: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(default=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # ----- Audit fields (spec section 35) -----
    # request_id reuses the owning AgentRun's id: in this system one chat
    # turn / API call *is* one AgentRun, so there's no separate request
    # concept worth inventing. user_id is a placeholder constant ("local")
    # until a real multi-user auth phase exists -- this is a single-operator
    # local assistant today.
    request_id: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[str] = mapped_column(Text, default="local")
    arguments_hash: Mapped[str] = mapped_column(Text, default="")
    permission_status: Mapped[str] = mapped_column(Text, default="not_required")  # not_required|granted|denied

    agent_run: Mapped[AgentRun] = relationship(back_populates="tool_executions")


class Automation(Base):
    """A schedule: what to do, and when/how often to do it.

    trigger_type: once|interval|cron. action_type: reminder|chat_message.
    status: active|paused|cancelled|completed (completed only applies to
    'once' automations after they've fired).
    """

    __tablename__ = "automations"
    __table_args__ = (Index("ix_automations_status_next_run_at", "status", "next_run_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    trigger_type: Mapped[str] = mapped_column(Text)
    run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(nullable=True)
    cron_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_type: Mapped[str] = mapped_column(Text)
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(Text, default="active")
    next_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    tasks: Mapped[list[Task]] = relationship(
        back_populates="automation", cascade="all, delete-orphan", order_by="Task.created_at"
    )


class Task(Base):
    """One execution/firing of an Automation -- the audit trail + what the
    Tasks UI shows."""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_automation_id_created_at", "automation_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    automation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="created")
    # created|queued|running|paused|completed|failed|cancelled
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    automation: Mapped[Automation] = relationship(back_populates="tasks")
