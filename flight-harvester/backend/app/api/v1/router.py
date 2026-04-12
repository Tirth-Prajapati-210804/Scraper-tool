from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.collection import router as collection_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(collection_router)
