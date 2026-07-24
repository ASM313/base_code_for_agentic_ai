from fastapi import APIRouter

from src.interface.auth import router as auth_router
from src.interface.interaction import router as chatbot_router
from src.interface.rag import router as rag_router
from src.interface.chatbot_public import router as chatbot_public_router
from src.system.logs import logger

api_router = APIRouter()

# Include routers
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])
api_router.include_router(rag_router, prefix="/rag", tags=["rag"])
api_router.include_router(chatbot_public_router, prefix="/public", tags=["public-chatbot"])


@api_router.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status information.
    """
    logger.info("health_check_called")
    return {"status": "healthy", "version": "1.0.0"}
