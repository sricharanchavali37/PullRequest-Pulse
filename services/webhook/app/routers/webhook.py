from fastapi import APIRouter, Request
import redis.asyncio as redis

router = APIRouter()

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

@router.post("/webhook")
async def webhook_handler(request: Request):

    payload = await request.json()
    pr_number = payload.get("number")

    # verify redis connection
    await redis_client.ping()

    stream_id = await redis_client.xadd(
        "prpulse:events:raw",
        {
            "event_type": "pr.opened",
            "pr_number": pr_number
        }
    )

    print(f"XADD prpulse:events:raw | PR #{pr_number} | id={stream_id}")

    return {"status": "accepted"}