"""
SSE Logging infrastructure for real-time logs
"""
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

# Log queue for SSE
log_queue = asyncio.Queue()


async def send_log(message: str, level: str = "info"):
    """Helper to push log to queue and print to console"""
    try:
        log_entry = json.dumps({
            "message": message,
            "level": level,
            "timestamp": asyncio.get_event_loop().time()
        })
        log_queue.put_nowait(log_entry)
    except Exception as e:
        print(f"Log Error: {e}")
    
    # Fallback print to ensure we see it in terminal
    print(f"[{level.upper()}] {message}")


@router.get("/logs")
async def log_stream():
    """SSE Endpoint for real-time logs"""
    async def event_generator():
        while True:
            try:
                data = await asyncio.wait_for(log_queue.get(), timeout=0.5)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                yield f": keep-alive\n\n"
            except Exception as e:
                print(f"Stream Error: {e}")
                await asyncio.sleep(1)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
