from fastapi import APIRouter

from app.api.routes import (
    audit,
    auth,
    database_connections,
    files,
    health,
    knowledge_bases,
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
