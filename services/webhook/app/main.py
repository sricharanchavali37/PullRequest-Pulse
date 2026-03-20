import logging

from fastapi import FastAPI

from app.routers import webhook, health

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)

app = FastAPI(title="PRPulse Webhook Service")

app.include_router(webhook.router)
app.include_router(health.router)
