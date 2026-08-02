from fastapi import APIRouter

from app.api.routes import (
    audit,
    auth,
    chat,
    conversations,
    database_connections,
    files,
    health,
    knowledge_bases,
    messages,
    permissions,
    roles,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(audit.router)
api_router.include_router(database_connections.router)
api_router.include_router(permissions.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(files.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
api_router.include_router(messages.router)
