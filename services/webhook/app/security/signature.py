import hmac
import hashlib
import logging

from fastapi import Request, HTTPException

from app.config import GITHUB_WEBHOOK_SECRET

logger = logging.getLogger(__name__)


async def verify_signature(request: Request) -> None:
    """
    FastAPI dependency — verifies the HMAC-SHA256 signature GitHub sends
    on every webhook request.

    How it works:
      1. GitHub signs the raw request body using your webhook secret.
      2. It puts the result in the header: X-Hub-Signature-256: sha256=<hex>
      3. We compute the same signature ourselves using the same secret.
      4. If both match → request is genuine. If not → return 401.

    If GITHUB_WEBHOOK_SECRET is not set in .env, verification is skipped.
    This allows local testing without a GitHub App installed.
    """

    # Skip verification if no secret is configured (local dev / testing)
    if not GITHUB_WEBHOOK_SECRET:
        logger.warning(
            "GITHUB_WEBHOOK_SECRET not set — skipping signature verification. "
            "Set it in .env before connecting a real GitHub App."
        )
        return

    # Read the raw bytes BEFORE any JSON parsing
    # The signature is computed against the raw body — parsing changes the bytes
    raw_body: bytes = await request.body()

    # Get the signature header GitHub sent
    sig_header: str = request.headers.get("X-Hub-Signature-256", "")

    if not sig_header:
        logger.warning("Webhook received with no X-Hub-Signature-256 header")
        raise HTTPException(status_code=401, detail="Missing signature header")

    if not sig_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Invalid signature format")

    # Extract just the hex digest part
    received_digest: str = sig_header[len("sha256="):]

    # Compute expected signature using our secret
    expected_digest: str = hmac.new(
        key       = GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg       = raw_body,
        digestmod = hashlib.sha256,
    ).hexdigest()

    # Use compare_digest to prevent timing attacks
    # (normal string == stops at first mismatch, leaking info about the secret)
    if not hmac.compare_digest(received_digest, expected_digest):
        logger.warning("Webhook signature mismatch — request rejected")
        raise HTTPException(status_code=401, detail="Invalid signature")