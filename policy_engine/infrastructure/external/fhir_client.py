"""FHIR R4 async client with OAuth2 and caching."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FHIRValidationError(Exception):
    """Raised when a FHIR resource fails R4 validation."""


@dataclass
class FHIRPatient:
    fhir_id: str
    resource_type: str = "Patient"
    name: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FHIRObservation:
    fhir_id: str
    resource_type: str = "Observation"
    subject_ref: Optional[str] = None
    status: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class FHIRClient:
    """Async FHIR R4 client with OAuth2 support."""

    def __init__(
        self,
        base_url: str,
        client_id: str = "",
        client_secret: str = "",
        token_url: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self._token: Optional[str] = None
        self._cache: Dict[str, Any] = {}

    async def _get_token(self) -> str:
        if self._token:
            return self._token
        if self.token_url and self.client_id:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        self.token_url,
                        data={
                            "grant_type": "client_credentials",
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                        },
                    )
                    resp.raise_for_status()
                    self._token = resp.json().get("access_token", "")
            except Exception as e:
                logger.warning("OAuth2 token fetch failed: %s", e)
                self._token = ""
        return self._token or ""

    async def _fetch(self, resource_type: str, resource_id: str) -> Dict[str, Any]:
        cache_key = f"{resource_type}/{resource_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        token = await self._get_token()
        try:
            import httpx
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/{resource_type}/{resource_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise FHIRValidationError(
                f"Failed to fetch {resource_type}/{resource_id}: {e}"
            )

        if data.get("resourceType") != resource_type:
            raise FHIRValidationError(
                f"Expected resourceType={resource_type}, got {data.get('resourceType')}"
            )

        self._cache[cache_key] = data
        return data

    async def get_patient(self, patient_id: str) -> FHIRPatient:
        data = await self._fetch("Patient", patient_id)
        name = ""
        if data.get("name"):
            n = data["name"][0]
            name = " ".join(n.get("given", []) + [n.get("family", "")])
        return FHIRPatient(
            fhir_id=data.get("id", patient_id),
            name=name.strip() or None,
            birth_date=data.get("birthDate"),
            gender=data.get("gender"),
            raw=data,
        )

    async def get_observation(self, obs_id: str) -> FHIRObservation:
        data = await self._fetch("Observation", obs_id)
        return FHIRObservation(
            fhir_id=data.get("id", obs_id),
            subject_ref=data.get("subject", {}).get("reference"),
            status=data.get("status"),
            raw=data,
        )

    async def get_diagnostic_report(self, report_id: str) -> Dict[str, Any]:
        return await self._fetch("DiagnosticReport", report_id)

    async def create_audit_event(
        self, action: str, patient_id: str, user_id: str
    ) -> Dict[str, Any]:
        return {
            "resourceType": "AuditEvent",
            "type": {"code": action},
            "agent": [{"who": {"reference": f"Practitioner/{user_id}"}}],
            "entity": [{"what": {"reference": f"Patient/{patient_id}"}}],
            "recorded": datetime.utcnow().isoformat(),
        }

    async def get_device(self, device_id: str) -> Dict[str, Any]:
        return await self._fetch("Device", device_id)

    async def get_provenance(self, provenance_id: str) -> Dict[str, Any]:
        return await self._fetch("Provenance", provenance_id)
