from fastapi import FastAPI
from app.routers import webhook, health

app = FastAPI(title="PRPulse Webhook Service")

app.include_router(webhook.router)
app.include_router(health.router)