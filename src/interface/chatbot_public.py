"""
src/interface/chatbot_public.py

Public-facing chatbot proxy endpoint.

This route lets your frontend talk to the chatbot WITHOUT requiring
end-user login. It holds the chatbot API's Bearer token server-side
(loaded from settings/.env) and forwards conversations to your
internal chatbot endpoint.

Wire this into src/main.py with:
    from src.interface.chatbot_public import router as chatbot_public_router
    app.include_router(chatbot_public_router)
"""

from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config.settings import settings

router = APIRouter(prefix="/api/v1/public", tags=["public-chatbot"])


# ── Schemas ──────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class PublicChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)


class PublicChatResponse(BaseModel):
    messages: list[ChatMessage]


async def get_chatbot_service_token() -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login
        login_response = await client.post(
            f"{settings.INTERNAL_API_BASE_URL}/api/v1/auth/login",
            headers={
                "accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "username": settings.CHATBOT_USERNAME,
                "password": settings.CHATBOT_PASSWORD,
                "grant_type": "password",
            },
        )
        login_response.raise_for_status()

        login_token = login_response.json()["access_token"]

        # Create session
        session_response = await client.post(
            f"{settings.INTERNAL_API_BASE_URL}/api/v1/auth/session",
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {login_token}",
            },
        )
        session_response.raise_for_status()

        # This is the token your chatbot expects
        return session_response.json()["token"]["access_token"]

# ── Route ────────────────────────────────────────────────────────────
@router.post("/chatbot/chat", response_model=PublicChatResponse)
async def public_chat(payload: PublicChatRequest) -> PublicChatResponse:
    """
    Forwards website-widget messages to the internal chatbot endpoint,
    attaching the service-level Bearer token so the frontend never
    sees or needs it.
    """
    internal_url = f"{settings.INTERNAL_API_BASE_URL}/api/v1/chatbot/chat"

    try:
        service_token = await get_chatbot_service_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                internal_url,
                json={"messages": [m.model_dump() for m in payload.messages]},
                headers={
                    "Authorization": f"Bearer {service_token}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=503, detail="Chatbot service is unreachable"
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504, detail="Chatbot service timed out"
        ) from exc

    if resp.status_code == 401:
        raise HTTPException(
            status_code=502, detail="Service token rejected — check CHATBOT_SERVICE_TOKEN"
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502, detail=f"Chatbot service error: {resp.text}"
        )

    return PublicChatResponse(**resp.json())