"""ComplyAdvantage AML screening client (BRD §5.3, Phase 15.2).

Integrates with ComplyAdvantage for:
  - Sanctions list matching
  - PEP (Politically Exposed Person) checking
  - Adverse media screening
  - Risk rating calculation

Implements retry logic with exponential backoff and circuit breaker
pattern for resilience against external service failures.

IMPORTANT: National IDs and names are hashed/redacted before logging.
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
from app.schemas.aml import (
    AMLMatchDetail,
    AMLResult,
    AMLRiskRating,
    AMLStatusEnum,
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
                "ComplyAdvantage circuit breaker is open — service is unavailable"
            )


class ComplyAdvantageClient:
    """Client for ComplyAdvantage AML screening API.

    Uses httpx for async HTTP calls with exponential backoff retry logic
    and a circuit breaker to prevent cascading failures.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout_seconds=60.0,
        )

    async def screen_individual(
        self,
        name: str,
        national_id: str,
        date_of_birth: str | None = None,
        nationality: str = "KE",
    ) -> AMLResult:
        """Screen an individual against AML databases.

        Args:
            name: Full name of the individual.
            national_id: National ID (hashed before logging).
            date_of_birth: Date of birth in YYYY-MM-DD format.
            nationality: ISO 3166-1 alpha-2 country code.

        Returns:
            AMLResult with screening status and risk details.

        Raises:
            CircuitBreakerOpen: If the circuit breaker is open.
            httpx.HTTPError: If all retries are exhausted.
        """
        id_hash = hash_national_id(national_id)
        await logger.ainfo(
            "aml_screening_started",
            subject_id_hash=id_hash,
            nationality=nationality,
        )

        self._circuit_breaker.check()

        # Build ComplyAdvantage request payload
        search_ref = str(uuid.uuid4())
        payload = self._build_payload(
            name=name,
            date_of_birth=date_of_birth,
            nationality=nationality,
            search_ref=search_ref,
        )

        # Execute with retry
        response_data = await self._execute_with_retry(
            endpoint="/searches",
            payload=payload,
        )

        # Map response to internal result
        result = self._map_response(response_data, search_ref)

        await logger.ainfo(
            "aml_screening_completed",
            subject_id_hash=id_hash,
            status=result.status.value,
            risk_rating=result.risk_rating.value,
            is_sanctioned=result.is_sanctioned,
            is_pep=result.is_pep,
        )

        return result

    def _build_payload(
        self,
        *,
        name: str,
        date_of_birth: str | None,
        nationality: str,
        search_ref: str,
    ) -> dict[str, Any]:
        """Build the ComplyAdvantage API request payload."""
        payload: dict[str, Any] = {
            "search_term": name,
            "client_ref": search_ref,
            "fuzziness": 0.6,
            "filters": {
                "types": ["sanction", "pep", "adverse-media"],
                "birth_year": None,
                "country_codes": [nationality],
            },
            "share_url": 0,
        }

        if date_of_birth:
            try:
                year = int(date_of_birth.split("-")[0])
                payload["filters"]["birth_year"] = year
            except (ValueError, IndexError):
                pass

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
        max_retries = self._settings.comply_advantage_max_retries
        base_url = self._settings.comply_advantage_base_url.rstrip("/")
        url = f"{base_url}{endpoint}"

        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._settings.comply_advantage_timeout_seconds,
                ) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={
                            "Authorization": f"Token {self._settings.comply_advantage_api_key}",
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
                    "aml_retry",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)

        # All retries exhausted
        self._circuit_breaker.record_failure()
        await logger.aerror("aml_all_retries_exhausted")

        if last_exception is not None:
            raise last_exception
        raise httpx.HTTPError("All retries exhausted for ComplyAdvantage")

    def _map_response(
        self,
        response_data: dict[str, Any],
        search_ref: str,
    ) -> AMLResult:
        """Map ComplyAdvantage API response to internal AMLResult."""
        content = response_data.get("content", {})
        data = content.get("data", {})

        # Extract hits
        hits = data.get("hits", [])
        total_hits = data.get("total_hits", len(hits))

        # Classify matches
        is_sanctioned = False
        is_pep = False
        adverse_media_found = False
        matches: list[AMLMatchDetail] = []

        for hit in hits:
            hit_types = hit.get("types", [])
            match_score = float(hit.get("match_score", 0.0)) / 100.0
            list_name = hit.get("doc", {}).get("name", "Unknown")

            for hit_type in hit_types:
                match_type_str = str(hit_type).lower()
                if "sanction" in match_type_str:
                    is_sanctioned = True
                    matches.append(AMLMatchDetail(
                        list_name=list_name,
                        match_score=match_score,
                        match_type="sanctions",
                    ))
                elif "pep" in match_type_str:
                    is_pep = True
                    matches.append(AMLMatchDetail(
                        list_name=list_name,
                        match_score=match_score,
                        match_type="pep",
                    ))
                elif "adverse" in match_type_str or "media" in match_type_str:
                    adverse_media_found = True
                    matches.append(AMLMatchDetail(
                        list_name=list_name,
                        match_score=match_score,
                        match_type="adverse_media",
                    ))

        # Calculate risk rating and score
        risk_rating, risk_score = self._calculate_risk(
            total_hits=total_hits,
            is_sanctioned=is_sanctioned,
            is_pep=is_pep,
            adverse_media_found=adverse_media_found,
        )

        # Determine status
        status = self._determine_status(
            is_sanctioned=is_sanctioned,
            is_pep=is_pep,
            risk_rating=risk_rating,
        )

        return AMLResult(
            status=status,
            risk_rating=risk_rating,
            risk_score=risk_score,
            is_sanctioned=is_sanctioned,
            is_pep=is_pep,
            adverse_media_found=adverse_media_found,
            matches=matches,
            provider_reference=search_ref,
            screened_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _calculate_risk(
        *,
        total_hits: int,
        is_sanctioned: bool,
        is_pep: bool,
        adverse_media_found: bool,
    ) -> tuple[AMLRiskRating, float]:
        """Calculate AML risk rating and normalized score.

        Scoring logic:
          - Sanctioned: HIGH (1.0)
          - PEP: at least MEDIUM (0.6+)
          - Adverse media only: MEDIUM (0.4)
          - No hits: LOW (0.0)
        """
        if is_sanctioned:
            return AMLRiskRating.HIGH, 1.0

        score = 0.0
        if is_pep:
            score += 0.6
        if adverse_media_found:
            score += 0.2
        if total_hits > 0 and not is_pep and not adverse_media_found:
            score = min(0.3 + total_hits * 0.05, 0.5)

        if score >= 0.6:
            return AMLRiskRating.HIGH, min(score, 1.0)
        if score >= 0.3:
            return AMLRiskRating.MEDIUM, score
        return AMLRiskRating.LOW, score

    @staticmethod
    def _determine_status(
        *,
        is_sanctioned: bool,
        is_pep: bool,
        risk_rating: AMLRiskRating,
    ) -> AMLStatusEnum:
        """Determine AML status from risk assessment."""
        if is_sanctioned:
            return AMLStatusEnum.FLAGGED
        if is_pep or risk_rating == AMLRiskRating.HIGH:
            return AMLStatusEnum.REVIEW
        if risk_rating == AMLRiskRating.MEDIUM:
            return AMLStatusEnum.REVIEW
        return AMLStatusEnum.CLEAR

    def get_raw_response_for_storage(
        self,
        response_data: dict[str, Any],
    ) -> str:
        """Serialize provider response for encrypted storage.

        The caller is responsible for encrypting this before persisting.
        """
        return json.dumps(response_data, default=str)
