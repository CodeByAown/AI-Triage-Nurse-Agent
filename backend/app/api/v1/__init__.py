from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.patients import router as patients_router
from app.api.v1.triage import router as triage_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.admin import router as admin_router
from app.api.v1.voice import router as voice_router
from app.api.v1.documents import router as documents_router
from app.api.v1.patient_history import router as patient_history_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(patients_router)
api_router.include_router(triage_router)
api_router.include_router(analytics_router)
api_router.include_router(admin_router)
api_router.include_router(voice_router)
api_router.include_router(documents_router)
api_router.include_router(patient_history_router)
