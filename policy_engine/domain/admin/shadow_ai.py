"""Shadow AI Discovery domain logic — pure Python."""
from dataclasses import dataclass
from typing import List, Optional
import fnmatch

AI_PROVIDER_DOMAINS = {
    "openai.com": "openai",
    "api.openai.com": "openai",
    "anthropic.com": "anthropic",
    "api.anthropic.com": "anthropic",
    "cohere.ai": "cohere",
    "api.cohere.ai": "cohere",
    "generativelanguage.googleapis.com": "google",
    "vertexai.googleapis.com": "google",
    "openai.azure.com": "azure_openai",
    "cognitiveservices.azure.com": "azure_openai",
    "huggingface.co": "huggingface",
    "api.huggingface.co": "huggingface",
    "together.ai": "together",
    "api.together.xyz": "together",
}

CLINICAL_DEPARTMENTS = {"icu", "ed", "er", "or", "radiology", "icu/ccu", "ccu", "nicu", "picu"}


def detect_ai_provider(hostname: str) -> Optional[str]:
    """Check exact match, then suffix match for subdomains."""
    hostname = hostname.lower().strip()
    # Exact match
    if hostname in AI_PROVIDER_DOMAINS:
        return AI_PROVIDER_DOMAINS[hostname]
    # Suffix match: check if hostname ends with ".{known_domain}"
    for domain, provider in AI_PROVIDER_DOMAINS.items():
        if hostname.endswith("." + domain):
            return provider
    return None


def assess_phi_risk(hostname: str, port: int, department: str) -> str:
    """Assess PHI risk level based on AI provider, port, and department."""
    provider = detect_ai_provider(hostname)
    if provider is None:
        return "none"
    if port == 443 and department.lower() in CLINICAL_DEPARTMENTS:
        return "high"
    if port == 443:
        return "medium"
    return "low"


@dataclass
class ShadowAIDetection:
    source_ip: str
    destination_host: str
    ai_provider: Optional[str]
    confidence_score: float
    phi_risk_level: str
    department: str


def is_allowlisted(hostname: str, allowlist: List[str]) -> bool:
    """Match hostname against list of exact hostnames or glob patterns (*.example.com)."""
    hostname = hostname.lower()
    for pattern in allowlist:
        pattern = pattern.lower()
        if fnmatch.fnmatch(hostname, pattern):
            return True
        if hostname == pattern:
            return True
    return False
