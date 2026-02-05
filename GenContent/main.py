from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging
from typing import Dict, Any

from services.file_analyzer import analyze_csv
from services.genConten import genContent
from services.shopify_service import build_shopify_product_body, push_to_shopify
from utils.taxonomy_manager import get_or_refresh_categories
from llms.llm import llm_genContent
from config.config import Config

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Content Generator",
)

# CORS Configuration
# Allow all origins for development (Remix allows varied ports)
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploaded_data: Dict[str, Any] = {}

# --- SSE Log Infrastructure ---
log_queue = asyncio.Queue()

async def send_log(message: str, level: str = "info"):
    """Helper to push log to queue and print to console"""
    try:
        log_entry = json.dumps({
            "message": message,
            "level": level,
            "timestamp": asyncio.get_event_loop().time()
        })
        log_queue.put_nowait(log_entry) # Non-blocking put
    except Exception as e:
        print(f"Log Error: {e}")
    
    # Fallback print to ensure we see it in terminal
    print(f"[{level.upper()}] {message}") 

@app.get("/logs")
async def log_stream():
    """SSE Endpoint for real-time logs"""
    async def event_generator():
        while True:
            try:
                # Wait for new log with timeout to allow heartbeat
                data = await asyncio.wait_for(log_queue.get(), timeout=0.5)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                # Send keep-alive packet very frequently
                yield f": keep-alive\n\n"
            except Exception as e:
                print(f"Stream Error: {e}")
                # Don't break immediately, retry
                await asyncio.sleep(1)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
# ------------------------------


@app.post("/upload")
async def upload_and_analyze(file: UploadFile = File(...)):
    """
    Upload file CSV và tự động phân tích cấu trúc
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file CSV")
    
    content = await file.read()
    result = analyze_csv(content)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    uploaded_data["content"] = content
    uploaded_data["products"] = result["products"]
    uploaded_data["columns"] = result["columns"]
    
    return {
        "status": "success",
        "file_name": file.filename,
        "total_rows": result["total_rows"],
        "total_columns": result["total_columns"],
        "columns": result["columns"], 
        "products": result["products"], # Return FULL data
        "data_preview": result["products"][:5] # Keep legacy preview just in case mean return full
    }


@app.get("/data")
async def get_uploaded_data():
    """Xem toàn bộ data đã upload"""
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file nào")
    
    return {
        "columns": uploaded_data["columns"],
        "total_products": len(uploaded_data["products"]),
        "products": uploaded_data["products"]
    }

@app.post("/generate")
async def generate_content():
    """Generate content cho tất cả sản phẩm bằng LLM"""
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file nào")
    
    products = uploaded_data["products"]
    results = []
    
    for idx, product in enumerate(products):
        try:
            # Generate content cho từng sản phẩm
            generated = await genContent(
                model=llm_genContent,
                system_prompt=Config.SYSTEM_PROMPT_CONTENT,
                data=product
            )
            
            results.append({
                "row_index": idx,
                "original_data": product,
                "generated_content": generated
            })
        except Exception as e:
            results.append({
                "row_index": idx,
                "original_data": product,
                "generated_content": {
                    "status": "error",
                    "message": str(e)
                }
            })
    
    return {
        "status": "success",
        "total_products": len(products),
        "results": results
    }

@app.post("/build-product")
async def build_product_preview():
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file nào")
    
    products = uploaded_data["products"]
    results = []
    
    for idx, product in enumerate(products):
        try:
            # Step 1: Generate content
            generated = await genContent(
                model=llm_genContent,
                system_prompt=Config.SYSTEM_PROMPT_CONTENT,
                data=product
            )
            
            if generated["status"] != "success":
                results.append({
                    "row_index": idx,
                    "status": "error",
                    "message": f"Generate error: {generated.get('message')}"
                })
                continue
            
            # Step 2: Build Shopify product body
            shopify_categories = get_or_refresh_categories()
            shopify_body = build_shopify_product_body(
                generated_content=generated,
                original_data=product,
                shopify_categories=shopify_categories
            )
            
            results.append({
                "row_index": idx,
                "original_data": product,
                "generated_content": generated,
                "shopify_product_body": shopify_body
            })
            
        except Exception as e:
            results.append({
                "row_index": idx,
                "status": "error",
                "message": str(e)
            })
    
    return {
        "status": "success",
        "total_products": len(products),
        "results": results,
        "note": "Đây chỉ là preview, chưa push lên Shopify"
    }


from pydantic import BaseModel
from typing import Optional

class PushRequest(BaseModel):
    shop_url: Optional[str] = None
    access_token: Optional[str] = None

@app.post("/push-to-shopify")
async def push_products_to_shopify(request: PushRequest = None):
    """
    Push tất cả sản phẩm lên Shopify store
    Workflow: Upload → Generate → Build → Push
    """
    import asyncio
    
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file nào. Vui lòng upload CSV trước.")
    
    products = uploaded_data["products"]
    
    # Use provided credentials or fallback to Config
    shop_url = request.shop_url if request and request.shop_url else Config.SHOPIFY_STORE_URL
    access_token = request.access_token if request and request.access_token else Config.SHOPIFY_ACCESS_TOKEN
    
    if not shop_url or not access_token:
         raise HTTPException(status_code=400, detail="Missing Shopify Credentials. Please provide shop_url and access_token.")

    MAX_CONCURRENT_REQUESTS = Config.MAX_CONCURRENT_REQUESTS
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    # Pre-fetch categories ONCE
    try:
        shopify_categories = await asyncio.to_thread(
            get_or_refresh_categories, 
            shop_url=shop_url, 
            access_token=access_token
        )
    except Exception as e:
        await send_log(f"Failed to fetch categories: {e}", "error")
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")

    # Define async worker for a single product
    async def process_single_product(idx: int, product: Dict[str, Any], categories: list) -> Dict[str, Any]:
        try:
            # Step 1: Generate content (ASYNC)
            # Give event loop a breath
            await asyncio.sleep(0) 
            generated = await genContent(
                model=llm_genContent,
                system_prompt=Config.SYSTEM_PROMPT_CONTENT.format(LANGUAGE=Config.LANGUAGE),
                data=product
            )
            
            if generated["status"] != "success":
                return {
                    "row_index": idx,
                    "status": "error",
                    "message": f"Generate error: {generated.get('message')}",
                    "original_data": product
                }
            
            # Step 2: Build Shopify product body (BLOCKING -> Thread)
            await asyncio.sleep(0) # Yield
            
            shopify_body = await asyncio.to_thread(
                build_shopify_product_body,
                generated_content=generated,
                original_data=product,
                shopify_categories=categories
            )
            
            # Step 3: Push to Shopify (BLOCKING Network -> Thread)
            await asyncio.sleep(0) # Yield
            push_result = await asyncio.to_thread(
                push_to_shopify,
                product_body=shopify_body,
                shop_url=shop_url,
                access_token=access_token
            )
            
            if push_result["status"] == "success":
                await send_log(f" Product [{idx+1}] Success: {generated.get('title', 'Product')}", "success")
                return {
                    "row_index": idx,
                    "status": "success",
                    "product_id": push_result["product_id"],
                    "shopify_url": push_result["shopify_url"],
                    "title": generated.get("title"),
                    "product_type": generated.get("product_type"),
                    "original_data": product
                }
            else:
                await send_log(f"❌ Product [{idx+1}] Failed: {push_result.get('message')}", "error")
                return {
                    "row_index": idx,
                    "status": "error",
                    "message": push_result.get("message"),
                    "original_data": product,
                    "generated_content": generated
                }
                
        except Exception as e:
            await send_log(f"❌ Product [{idx+1}] Error: {str(e)}", "error")
            return {
                "row_index": idx,
                "status": "error",
                "message": str(e),
                "original_data": product
            }

    MAX_CONCURRENT_REQUESTS = Config.MAX_CONCURRENT_REQUESTS
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def protected_process_single_product(idx, product):
        async with semaphore:
            return await process_single_product(idx, product, shopify_categories)

    # Run all tasks concurrently with throttling
    await send_log(f" Starting batch processing for {len(products)} products...", "info")
    results = await asyncio.gather(*[protected_process_single_product(i, p) for i, p in enumerate(products)])
    
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count
    
    await send_log(f" Batch completed! Success: {success_count}, Failed: {failed_count}", "done")
    
    return {
        "status": "completed",
        "total_products": len(products),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results
    }


@app.get("/api/content")
async def health_check(): 
    return {"status": "ok", "message": "Connected!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)