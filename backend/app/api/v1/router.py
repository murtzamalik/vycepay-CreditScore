"""V1 API router -- aggregates all v1 route modules."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, health
from app.api.v1.endpoints import aml as aml_endpoints
from app.api.v1.endpoints import batches as batches_endpoints
from app.api.v1.endpoints import billing as billing_endpoints
from app.api.v1.endpoints import data_rights as data_rights_endpoints
from app.api.v1.endpoints import feedback as feedback_endpoints
from app.api.v1.endpoints import kpis as kpis_endpoints
from app.api.v1.endpoints import kyc as kyc_endpoints
from app.api.v1.endpoints import mfa as mfa_endpoints
from app.api.v1.endpoints import models as models_endpoints
from app.api.v1.endpoints import partner as partner_endpoints
from app.api.v1 import scores

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(health.router)
v1_router.include_router(auth.router)
v1_router.include_router(mfa_endpoints.router)
v1_router.include_router(scores.router)
v1_router.include_router(batches_endpoints.router)
v1_router.include_router(feedback_endpoints.router)
v1_router.include_router(admin.router)
v1_router.include_router(kpis_endpoints.router)
v1_router.include_router(models_endpoints.router)
v1_router.include_router(partner_endpoints.router)
v1_router.include_router(billing_endpoints.billing_router)
v1_router.include_router(billing_endpoints.embed_admin_router)
v1_router.include_router(billing_endpoints.embed_public_router)
v1_router.include_router(data_rights_endpoints.router)
v1_router.include_router(kyc_endpoints.router)
v1_router.include_router(aml_endpoints.router)
