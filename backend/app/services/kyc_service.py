"""Smile ID KYC verification client (BRD §5.3, Phase 15.1).

Integrates with Smile ID for:
  - National ID / Passport / Driver's License verification
  - Biometric face match verification
  - Liveness check (anti-spoofing)

Implements retry logic with exponential backoff and circuit breaker
pattern for resilience against external service failures.

IMPORTANT: National IDs are hashed before any logging or storage.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.config import Settings, get_settings
from app.schemas.kyc import (
    BiometricData,
    IDType,
    KYCResult,
    KYCStatusEnum,
)
from app.services.id_hasher import hash_national_id

logger = structlog.get_logger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and calls are blocked."""


class CircuitBreaker:
    """Simple circuit breaker for external service calls.

    States:
      - CLOSED: normal operation, requests pass through
      - OPEN: too many failures, requests are blocked
      - HALF_OPEN: after cooldown, allow a single test request
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        self._failure_count: int = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout_seconds
        self._last_failure_time: float = 0.0
        self._state: str = "CLOSED"

    @property
    def state(self) -> str:
        if self._state == "OPEN":
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._state = "HALF_OPEN"
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "CLOSED"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = "OPEN"

    def check(self) -> None:
        current_state = self.state
        if current_state == "OPEN":
            raise CircuitBreakerOpen(
                "Smile ID circuit breaker is open — service is unavailable"
            )


class SmileIDClient:
    """Client for Smile ID KYC verification API.

    Uses httpx for async HTTP calls with exponential backoff retry logic
    and a circuit breaker to prevent cascading failures.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout_seconds=60.0,
        )

    async def verify_identity(
        self,
        national_id: str,
        id_type: IDType = IDType.NATIONAL_ID,
        biometric_data: BiometricData | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        country: str = "KE",
    ) -> KYCResult:
        """Verify identity via Smile ID.

        Args:
            national_id: Document number (hashed before logging).
            id_type: Type of identity document.
            biometric_data: Optional biometric data for face match.
            first_name: First name on the document.
            last_name: Last name on the document.
            country: ISO 3166-1 alpha-2 country code.

        Returns:
            KYCResult with verification status and confidence scores.

        Raises:
            CircuitBreakerOpen: If the circuit breaker is open.
            httpx.HTTPError: If all retries are exhausted.
        """
        id_hash = hash_national_id(national_id)
        await logger.ainfo(
            "kyc_verification_started",
            subject_id_hash=id_hash,
            id_type=id_type.value,
        )

        self._circuit_breaker.check()

        # Build Smile ID request payload
        job_id = str(uuid.uuid4())
        payload = self._build_payload(
            national_id=national_id,
            id_type=id_type,
            biometric_data=biometric_data,
            first_name=first_name,
            last_name=last_name,
            country=country,
            job_id=job_id,
        )

        # Execute with retry
        response_data = await self._execute_with_retry(
            endpoint="/v1/id_verification",
            payload=payload,
        )

        # Map response to internal result
        result = self._map_response(response_data, job_id)

        await logger.ainfo(
            "kyc_verification_completed",
            subject_id_hash=id_hash,
            status=result.status.value,
            confidence=result.confidence_score,
        )

        return result

    def _build_payload(
        self,
        *,
        national_id: str,
        id_type: IDType,
        biometric_data: BiometricData | None,
        first_name: str | None,
        last_name: str | None,
        country: str,
        job_id: str,
    ) -> dict[str, Any]:
        """Build the Smile ID API request payload."""
        id_type_map: dict[IDType, str] = {
            IDType.NATIONAL_ID: "NATIONAL_ID",
            IDType.PASSPORT: "PASSPORT",
            IDType.DRIVERS_LICENSE: "DRIVERS_LICENSE",
        }

        payload: dict[str, Any] = {
            "partner_id": self._settings.smile_id_partner_id,
            "job_id": job_id,
            "job_type": 5,  # Enhanced KYC
            "country": country,
            "id_type": id_type_map[id_type],
            "id_number": national_id,
            "callback_url": "",
        }

        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name

        if biometric_data:
            payload["job_type"] = 1  # Biometric KYC
            payload["image"] = biometric_data.selfie_image_base64
            if biometric_data.id_image_base64:
                payload["id_image"] = biometric_data.id_image_base64

        return payload

    async def _execute_with_retry(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an HTTP request with exponential backoff retry.

        Retries up to ``max_retries`` times with exponential backoff
        (1s, 2s, 4s, ...) on transient failures (5xx, timeouts).
        """
        max_retries = self._settings.smile_id_max_retries
        base_url = self._settings.smile_id_base_url.rstrip("/")
        url = f"{base_url}{endpoint}"

        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._settings.smile_id_timeout_seconds,
                ) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {self._settings.smile_id_api_key}",
                            "Content-Type": "application/json",
                        },
                    )

                if response.status_code < 500:
                    self._circuit_breaker.record_success()
                    response.raise_for_status()
                    return response.json()  # type: ignore[no-any-return]

                # Server error — retry
                last_exception = httpx.HTTPStatusError(
                    f"Server error: {response.status_code}",
                    request=response.request,
                    response=response,
                )

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc

            # Exponential backoff
            if attempt < max_retries:
                backoff = 2**attempt
                await logger.awarning(
                    "kyc_retry",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)

        # All retries exhausted
        self._circuit_breaker.record_failure()
        await logger.aerror("kyc_all_retries_exhausted")

        if last_exception is not None:
            raise last_exception
        raise httpx.HTTPError("All retries exhausted for Smile ID")

    def _map_response(
        self,
        response_data: dict[str, Any],
        job_id: str,
    ) -> KYCResult:
        """Map Smile ID API response to internal KYCResult."""
        # Smile ID returns various result codes
        result_code = response_data.get("ResultCode", "")
        result_text = response_data.get("ResultText", "")
        actions = response_data.get("Actions", {})

        # Determine status from Smile ID response
        verify_action = actions.get("Verify_ID_Number", "")
        selfie_action = actions.get("Selfie_Check", "")
        liveness_action = actions.get("Liveness_Check", "")

        # Confidence from response
        confidence_value = float(response_data.get("ConfidenceValue", 0.0))
        confidence_score = min(confidence_value / 100.0, 1.0)

        # Face match score
        face_match_raw = response_data.get("FaceMatchConfidence")
        face_match_score: float | None = None
        if face_match_raw is not None:
            face_match_score = min(float(face_match_raw) / 100.0, 1.0)

        # Liveness
        liveness_passed: bool | None = None
        if liveness_action:
            liveness_passed = liveness_action.lower() == "passed"

        # Overall status mapping
        if result_code in ("1012", "1020") or verify_action.lower() == "verified":
            status = KYCStatusEnum.VERIFIED
        elif result_code in ("1013", "1014"):
            status = KYCStatusEnum.PENDING
        else:
            status = KYCStatusEnum.FAILED

        return KYCResult(
            status=status,
            confidence_score=confidence_score,
            face_match_score=face_match_score,
            liveness_passed=liveness_passed,
            provider_reference=job_id,
            verified_at=datetime.now(timezone.utc) if status == KYCStatusEnum.VERIFIED else None,
            failure_reason=result_text if status == KYCStatusEnum.FAILED else None,
        )

    def get_raw_response_for_storage(
        self,
        response_data: dict[str, Any],
    ) -> str:
        """Serialize provider response for encrypted storage.

        The caller is responsible for encrypting this before persisting.
        """
        return json.dumps(response_data, default=str)
