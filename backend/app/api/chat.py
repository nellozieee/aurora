"""Chat + conversation-history API.

Every chat turn goes through the Orchestrator: classify intent, select an
agent, retrieve relevant memory, run the agent's tool-calling loop (or a
plan -> steps -> review pipeline for complex requests), and persist the
result. Tool activity and intermediate reasoning are streamed to the
WebSocket client as typed events; the REST endpoint collects the same
stream and returns just the final message.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.events import AgentErrorEvent, AssistantDeltaEvent, FinalEvent
from app.ai.router import AIRouter, get_ai_router
from app.core.config import Settings, get_settings
from app.core.orchestrator import Orchestrator, get_orchestrator
from app.database.database import get_session, session_scope
from app.database.models import Conversation, Message
from app.memory.short_term import get_recent_messages
from app.vision.vision_analysis import VisionUnavailableError, analyze_image

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    # A data URL or bare base64 PNG/JPEG the user attached to this message.
    # Analyzed once up front and injected as context -- this is a one-shot
    # user-provided image, distinct from the Computer Agent's own
    # take_screenshot/analyze_screen tools for inspecting the live screen.
    image_base64: str | None = None


async def _describe_attached_image(
    image_base64: str, ai_router: AIRouter, settings: Settings, user_message: str
) -> str | None:
    import base64

    raw = image_base64.split(",", 1)[-1] if image_base64.startswith("data:") else image_base64
    try:
        image_bytes = base64.b64decode(raw)
    except Exception:
        return None

    prompt = user_message.strip() or None
    try:
        description = await analyze_image(ai_router, settings, image_bytes, prompt)
    except VisionUnavailableError:
        return None
    return f"[The user attached an image. Vision analysis of it]: {description}"


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    provider: str | None
    model: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: MessageOut
    agent: str | None = None
    intent: str | None = None


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationDetail(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]


def _derive_title(message: str) -> str:
    stripped = message.strip().replace("\n", " ")
    return stripped[:60] + ("..." if len(stripped) > 60 else "")


async def _load_or_create_conversation(
    session: AsyncSession, conversation_id: uuid.UUID | None, first_message: str
) -> Conversation:
    if conversation_id is not None:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation

    conversation = Conversation(title=_derive_title(first_message))
    session.add(conversation)
    await session.flush()
    return conversation


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    ai_router: AIRouter = Depends(get_ai_router),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    conversation = await _load_or_create_conversation(session, request.conversation_id, request.message)

    history = await get_recent_messages(session, conversation.id)
    user_message = Message(conversation_id=conversation.id, role="user", content=request.message)
    session.add(user_message)
    await session.flush()

    image_context = None
    if request.image_base64:
        image_context = await _describe_attached_image(request.image_base64, ai_router, settings, request.message)

    final_content: str | None = None
    final_provider = ""
    final_model = ""
    agent_name: str | None = None
    intent: str | None = None
    error_message: str | None = None

    async for event in orchestrator.handle_message(
        session,
        conversation.id,
        history,
        request.message,
        provider=request.provider,
        model=request.model,
        image_context=image_context,
    ):
        if event.type == "intent_classified":
            intent = event.intent
        elif event.type == "agent_selected":
            agent_name = event.agent
        elif isinstance(event, FinalEvent):
            final_content = event.content
            final_provider, final_model = event.provider, event.model
        elif isinstance(event, AgentErrorEvent):
            error_message = event.message

    if final_content is None:
        raise HTTPException(status_code=503, detail=error_message or "The assistant could not produce a response.")

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=final_content,
        provider=final_provider or None,
        model=final_model or request.model,
    )
    session.add(assistant_message)
    await session.commit()
    await session.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation.id,
        message=MessageOut.model_validate(assistant_message),
        agent=agent_name,
        intent=intent,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(session: AsyncSession = Depends(get_session)) -> list[ConversationSummary]:
    result = await session.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
    conversations = result.scalars().all()
    summaries = []
    for c in conversations:
        count_result = await session.execute(
            select(Message).where(Message.conversation_id == c.id)
        )
        summaries.append(
            ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=len(count_result.scalars().all()),
            )
        )
    return summaries


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ConversationDetail:
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_result = await session.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    messages = messages_result.scalars().all()

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await session.delete(conversation)
    await session.commit()


@router.websocket("/chat/ws")
async def chat_ws(
    websocket: WebSocket,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    ai_router: AIRouter = Depends(get_ai_router),
    settings: Settings = Depends(get_settings),
) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            try:
                request = ChatRequest.model_validate(payload)
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": f"Invalid request: {exc}"})
                continue

            async with session_scope() as session:
                try:
                    conversation = await _load_or_create_conversation(
                        session, request.conversation_id, request.message
                    )
                    history = await get_recent_messages(session, conversation.id)
                    user_message = Message(
                        conversation_id=conversation.id, role="user", content=request.message
                    )
                    session.add(user_message)
                    await session.flush()
                    await session.commit()
                except HTTPException as exc:
                    await websocket.send_json({"type": "error", "message": exc.detail})
                    continue

            await websocket.send_json(
                {"type": "conversation_started", "conversation_id": str(conversation.id)}
            )

            image_context = None
            if request.image_base64:
                image_context = await _describe_attached_image(
                    request.image_base64, ai_router, settings, request.message
                )

            final_content: str | None = None
            final_provider = ""
            error_message: str | None = None

            async with session_scope() as session:
                async for event in orchestrator.handle_message(
                    session, conversation.id, history, request.message,
                    provider=request.provider, model=request.model, image_context=image_context,
                ):
                    if isinstance(event, AssistantDeltaEvent):
                        await websocket.send_json({"type": "assistant_message_delta", "content": event.content})
                    elif isinstance(event, FinalEvent):
                        final_content = event.content
                        final_provider = event.provider
                    elif isinstance(event, AgentErrorEvent):
                        error_message = event.message
                        await websocket.send_json({"type": "error", "message": event.message})
                    else:
                        await websocket.send_json(event.model_dump(mode="json"))

            if final_content is None:
                if error_message is None:
                    await websocket.send_json(
                        {"type": "error", "message": "The assistant could not produce a response."}
                    )
                continue

            async with session_scope() as session:
                assistant_message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=final_content,
                    provider=final_provider or None,
                    model=request.model,
                )
                session.add(assistant_message)
                await session.commit()
                await session.refresh(assistant_message)

            await websocket.send_json(
                {
                    "type": "assistant_message",
                    "conversation_id": str(conversation.id),
                    "message_id": str(assistant_message.id),
                    "content": final_content,
                    "provider": final_provider,
                }
            )
    except WebSocketDisconnect:
        return
