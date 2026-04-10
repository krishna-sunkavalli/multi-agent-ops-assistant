"""
Azure AI Content Safety guardrails for Ops Assistant.

Provides two layers:
  1. Middleware functions for the orchestrator (check every input/output)
  2. A tool function for the Safety Agent (on-demand analysis)

Uses Azure AI Content Safety service (included in AI Services multi-service
resource) to detect hate speech, violence, self-harm, and sexual content.
"""

import json
import logging

log = logging.getLogger(__name__)

# ── Lazy-initialized client ─────────────────────────────────────────

_client = None
_initialized = False


def _init_client():
    """Lazy-init the ContentSafetyClient on first use."""
    global _client, _initialized
    if _initialized:
        return
    try:
        from azure.ai.contentsafety import ContentSafetyClient
        from azure.identity import DefaultAzureCredential
        from config.settings import CONTENT_SAFETY_ENDPOINT

        if not CONTENT_SAFETY_ENDPOINT:
            log.warning("CONTENT_SAFETY_ENDPOINT not set — guardrails disabled")
            _initialized = True
            return

        _client = ContentSafetyClient(
            endpoint=CONTENT_SAFETY_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        log.info("Content Safety client ready: %s", CONTENT_SAFETY_ENDPOINT)
    except Exception as e:
        log.warning("Content Safety init failed (non-fatal): %s", e)

    _initialized = True


# ── Category labels ──────────────────────────────────────────────────

_CATEGORY_LABELS = {
    "Hate": "Hate Speech",
    "SelfHarm": "Self-Harm",
    "Sexual": "Sexual Content",
    "Violence": "Violence",
}

# ── Middleware function (used by orchestrator) ───────────────────────


def check_safety(text: str, threshold: int = 4) -> dict:
    """
    Analyze text for harmful content.

    Returns:
        {
            "safe": bool,
            "categories": {"hate": 0, "selfharm": 0, "sexual": 0, "violence": 0},
            "flagged": ["Violence"],
            "available": bool,
        }

    Severity levels: 0=safe, 2=low, 4=medium, 6=high.
    Content at or above *threshold* is blocked.
    """
    _init_client()

    if not _client:
        log.warning("Content Safety client unavailable — guardrails not enforced for this request")
        return {"safe": True, "categories": {}, "flagged": [], "available": False}

    try:
        from azure.ai.contentsafety.models import AnalyzeTextOptions

        request = AnalyzeTextOptions(text=text[:10_000])  # API limit
        response = _client.analyze_text(request)

        categories = {}
        flagged = []
        is_safe = True

        for item in response.categories_analysis:
            cat_key = str(item.category).lower().replace(" ", "")
            categories[cat_key] = item.severity
            if item.severity >= threshold:
                is_safe = False
                label = _CATEGORY_LABELS.get(str(item.category), str(item.category))
                flagged.append(label)

        return {
            "safe": is_safe,
            "categories": categories,
            "flagged": flagged,
            "available": True,
        }
    except Exception as e:
        log.warning("Content safety check failed: %s", e)
        return {
            "safe": True,
            "categories": {},
            "flagged": [],
            "available": False,
            "error": str(e),
        }


# ── Tool function (used by Safety Agent) ─────────────────────────────


def analyze_content_safety(text: str) -> str:
    """
    Analyze text for harmful content using Azure AI Content Safety.
    Checks for: hate speech, violence, self-harm, and sexual content.
    Returns severity levels: 0 (safe), 2 (low), 4 (medium), 6 (high).
    Content at severity 4+ is blocked by the guardrails system.
    """
    result = check_safety(text, threshold=2)  # Lower threshold for analysis

    if not result.get("available"):
        return json.dumps(
            {
                "status": "Content Safety service not available",
                "note": "Azure AI Content Safety endpoint not configured",
            }
        )

    output = {
        "text_analyzed": text[:200] + ("..." if len(text) > 200 else ""),
        "overall_safe": result["safe"],
        "categories": result["categories"],
        "flagged_categories": result["flagged"],
        "severity_scale": "0=safe, 2=low, 4=medium, 6=high",
        "blocking_threshold": 4,
    }
    return json.dumps(output, indent=2)
