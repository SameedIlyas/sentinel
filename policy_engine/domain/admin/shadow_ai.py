"""Shadow AI Discovery domain logic — pure Python.

The provider host list is the heart of detection — anything not in this list
slips through as "unknown". Tier 3 expanded the list to cover every major
public LLM provider and the popular self-host frontends ("character.ai",
"perplexity.ai", etc.) per the customer-research review in the Tier 3
roadmap.

Hostname matching is exact OR suffix-of-domain ("api.foo.com" matches the
key "foo.com"). Add ports / paths to the *ingest classifier*, not here.
"""
from dataclasses import dataclass
from typing import List, Optional
import fnmatch

AI_PROVIDER_DOMAINS = {
    # OpenAI
    "openai.com": "openai",
    "api.openai.com": "openai",
    "platform.openai.com": "openai",
    "chat.openai.com": "openai",
    "chatgpt.com": "openai",

    # Anthropic
    "anthropic.com": "anthropic",
    "api.anthropic.com": "anthropic",
    "claude.ai": "anthropic",
    "console.anthropic.com": "anthropic",

    # Google
    "generativelanguage.googleapis.com": "google",
    "vertexai.googleapis.com": "google",
    "aiplatform.googleapis.com": "google",
    "gemini.google.com": "google",
    "bard.google.com": "google",
    "ai.google.dev": "google",

    # Azure OpenAI
    "openai.azure.com": "azure_openai",
    "cognitiveservices.azure.com": "azure_openai",

    # AWS Bedrock
    "bedrock-runtime.amazonaws.com": "aws_bedrock",
    "bedrock.amazonaws.com": "aws_bedrock",

    # Cohere
    "cohere.ai": "cohere",
    "api.cohere.ai": "cohere",
    "api.cohere.com": "cohere",
    "dashboard.cohere.com": "cohere",

    # Mistral
    "mistral.ai": "mistral",
    "api.mistral.ai": "mistral",
    "console.mistral.ai": "mistral",
    "chat.mistral.ai": "mistral",

    # Meta / Llama hosts (third-party)
    "huggingface.co": "huggingface",
    "api-inference.huggingface.co": "huggingface",
    "huggingface.com": "huggingface",
    "replicate.com": "replicate",
    "api.replicate.com": "replicate",

    # Together / Groq / Perplexity / DeepSeek / etc.
    "together.ai": "together",
    "api.together.xyz": "together",
    "api.together.com": "together",
    "groq.com": "groq",
    "api.groq.com": "groq",
    "perplexity.ai": "perplexity",
    "api.perplexity.ai": "perplexity",
    "www.perplexity.ai": "perplexity",
    "deepseek.com": "deepseek",
    "api.deepseek.com": "deepseek",
    "chat.deepseek.com": "deepseek",
    "openrouter.ai": "openrouter",

    # xAI
    "x.ai": "xai",
    "api.x.ai": "xai",
    "grok.x.ai": "xai",

    # Consumer-facing chat front-ends often used as shadow scribes
    "character.ai": "character_ai",
    "you.com": "you",
    "poe.com": "poe",
    "pi.ai": "pi",
    "copilot.microsoft.com": "microsoft_copilot",
    "github.com/copilot": "github_copilot",  # path-suffix; matched via host fallback only

    # Healthcare / domain-specific
    "ambience.ai": "ambience_health",
    "abridge.com": "abridge",
    "nabla.com": "nabla",
    "suki.ai": "suki",
    "augmedix.com": "augmedix",
    "deepscribe.ai": "deepscribe",

    # Coding / agent frameworks (often used as shadow tools)
    "cursor.com": "cursor",
    "codeium.com": "codeium",
    "tabnine.com": "tabnine",
}

# Clinical-department slugs that elevate PHI-risk scoring.
CLINICAL_DEPARTMENTS = {
    "icu", "ed", "er", "or", "radiology", "icu/ccu", "ccu", "nicu", "picu",
    "oncology", "cardiology", "obgyn", "ob/gyn", "emergency", "surgery",
    "neurology", "psychiatry", "pediatrics", "pediatric", "maternity",
    "pathology", "lab", "laboratory", "pharmacy",
}


def detect_ai_provider(hostname: str) -> Optional[str]:
    """Check exact match, then suffix match for subdomains."""
    if not hostname:
        return None
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
    department_lc = (department or "").lower()
    if port == 443 and department_lc in CLINICAL_DEPARTMENTS:
        return "high"
    if port == 443:
        return "medium"
    return "low"


def score_confidence(
    *,
    bytes_transferred: int = 0,
    method: str = "GET",
    user_agent: Optional[str] = None,
    repeated_in_window: int = 1,
    department: str = "",
) -> float:
    """Score detection confidence in [0.0, 1.0].

    Heuristic-based — without payload inspection, we infer from metadata:
      - large transfers (> 1 KB) are more likely real LLM requests, not just
        DNS/TLS handshakes;
      - POST is more typical of LLM API calls than GET;
      - repeated calls from the same source raise confidence;
      - user-agents containing "python", "curl", "node" suggest API usage
        (vs the noisy browser navigation traffic that hits the marketing
        page once).
    """
    confidence = 0.5
    if bytes_transferred >= 1024:
        confidence += 0.2
    if (method or "").upper() in ("POST", "PUT", "PATCH"):
        confidence += 0.15
    if repeated_in_window >= 5:
        confidence += 0.1
    if user_agent:
        ua_lc = user_agent.lower()
        if any(token in ua_lc for token in (
            "python", "node", "java", "okhttp", "go-http", "curl",
            "openai", "anthropic", "axios", "requests/",
        )):
            confidence += 0.1
    if (department or "").lower() in CLINICAL_DEPARTMENTS:
        confidence += 0.05
    return max(0.0, min(1.0, round(confidence, 3)))


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
    if not hostname:
        return False
    hostname = hostname.lower()
    for pattern in allowlist:
        pattern = (pattern or "").lower()
        if not pattern:
            continue
        if fnmatch.fnmatch(hostname, pattern):
            return True
        if hostname == pattern:
            return True
    return False
