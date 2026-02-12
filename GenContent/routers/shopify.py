"""
Shopify Routes
- POST /push-to-shopify - Push all products to Shopify
"""
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from services.genConten import genContent
from services.shopify_service import build_shopify_product_body, push_to_shopify
from utils.taxonomy_manager import get_or_refresh_categories
from utils.getPrice import google_shopping_prices, find_most_common_price, calculate_price
from llms.llm import llm_genContent
from config.config import Config
from core.state import uploaded_data
from core.logging import send_log

from models.model import BatchPushRequest # New model

router = APIRouter(tags=["Shopify"])


@router.post("/push-to-shopify")
async def push_products_to_shopify(req: BatchPushRequest = None):
    """
    Push sản phẩm lên Shopify.
    - Nếu có body (req): Đẩy danh sách sản phẩm đã có content (từ n8n).
    - Nếu không có body: Lấy từ uploaded_data (Legacy flow).
    """
    
    # Get credentials from Config
    shop_url = Config.SHOPIFY_STORE_URL
    access_token = Config.SHOPIFY_ACCESS_TOKEN
    
    if not shop_url or not access_token:
        raise HTTPException(status_code=500, detail="Thiếu thông tin Shopify trong Config. Vui lòng kiểm tra .env file.")

    MAX_CONCURRENT_REQUESTS = Config.MAX_CONCURRENT_REQUESTS
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    # Check Metafields Definitions before pushing
    from services.metafield_setup import ensure_metafield_definitions
    await ensure_metafield_definitions()

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

    # === CASE 1: DIRECT BATCH PUSH (FROM N8N) ===
    if req and req.items:
        async def process_push_item(idx: int, item):
            async with semaphore:
                try:
                    title = item.generated_content.get('title', 'Unknown')
                    await send_log(f"📦 [Batch-Push] ({idx+1}/{len(req.items)}) Đang đẩy: {title}", "info")
                    
                    # Build body
                    shopify_body = await asyncio.to_thread(
                        build_shopify_product_body,
                        generated_content=item.generated_content,
                        original_data=item.product_data,
                        shopify_categories=shopify_categories
                    )
                    
                    # Push
                    push_result = await asyncio.to_thread(
                        push_to_shopify,
                        product_body=shopify_body,
                        shop_url=shop_url,
                        access_token=access_token
                    )
                    
                    start_status = "success" if push_result["status"] == "success" else "error"
                    
                    
                    if start_status == "success":
                         await send_log(f"✅ Pushed: {title}", "success")
                    else:
                         await send_log(f"❌ Failed: {title} - {push_result.get('message')}", "error")

                    # Extract error message if any
                    err_msg = push_result.get("message")
                    if not err_msg and push_result.get("errors"):
                        first_err = push_result["errors"][0]
                        err_msg = first_err.get("message") or str(first_err)

                    # Build clean response
                    response_item = {
                        "status": start_status,
                        "product_id": push_result.get("product_id"),
                        "shopify_url": push_result.get("shopify_url"),
                    }
                    
                    if start_status == "error":
                        response_item["message"] = err_msg
                    
                    if item.metadata:
                        response_item["metadata"] = item.metadata
                        
                    return response_item
                except Exception as e:
                    return {"status": "error", "message": str(e)}

        tasks = [process_push_item(i, item) for i, item in enumerate(req.items)]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r["status"] == "success")
        failed_count = len(req.items) - success_count
        await send_log(f"✅ Batch Push Completed! Success: {success_count}, Failed: {failed_count}", "done")
        
        return {
            "status": "completed",
            "total": len(req.items),
            "success_count": success_count,
            "items": results
        }

    # === CASE 2: LEGACY FLOW (FROM UPLOADED DATA) ===
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file nào. Vui lòng upload CSV trước.")
    
    products = uploaded_data["products"]

    async def process_single_product(idx: int, product: Dict[str, Any], categories: list) -> Dict[str, Any]:
        try:
            # Step 1: Generate content
            await asyncio.sleep(0)
             # ... (existing logic continues below)
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
            
            # Step 2: Calculate price if cost_per_item exists
            pricing_info = None
            recommended_price = None
            
            if "cost_per_item" in product and product.get("cost_per_item"):
                try:
                    await send_log(f"💰 Tính giá cho sản phẩm [{idx+1}]...", "info")
                    
                    product_name = product.get("Product_name", generated.get("title", ""))
                    vintage = product.get("Vintage", "")
                    cost_per_item = float(product["cost_per_item"])
                    
                    # Logic mới: Nếu có 'unit_price', dùng luôn, không đi dò giá nữa
                    # Check keys: 'unit_price', 'price'
                    input_price = None
                    price_keys = ['unit_price', 'price', 'Price', 'Unit Price']
                    for k in price_keys:
                        if k in product and product[k]:
                             try:
                                 input_price = float(str(product[k]).replace(",", ""))
                                 break
                             except:
                                 pass
                    
                    if input_price:
                        await send_log(f"⚡ [Skip-Scan] Đã có giá nhập: ${input_price}. Bỏ qua dò giá Google.", "info")
                        recommended_price = input_price
                        pricing_info = {
                            "competitor_mode": 0,
                            "price_count": 0,
                            "recommended_price": input_price,
                            "strategy": "manual_input",
                            "margin_percent": 0
                        }
                    else:
                        # FORCE DISABLE: User requested to stop competitor pricing entirely
                        await send_log(f"⚠️ Không tìm thấy giá trong CSV. Bỏ qua dò giá Google (Logic cũ đã tắt).", "warning")
                        recommended_price = None
                        
                except Exception as pricing_error:
                    await send_log(f"⚠️ Lỗi tính giá [{idx+1}]: {str(pricing_error)}", "warning")
            
            # Step 3: Build Shopify product body
            await asyncio.sleep(0)
            shopify_body = await asyncio.to_thread(
                build_shopify_product_body,
                generated_content=generated,
                original_data=product,
                shopify_categories=categories,
                recommended_price=recommended_price
            )
            
            # Step 4: Push to Shopify
            await asyncio.sleep(0)
            push_result = await asyncio.to_thread(
                push_to_shopify,
                product_body=shopify_body,
                shop_url=shop_url,
                access_token=access_token
            )
            
            if push_result["status"] == "success":
                await send_log(f"✅ Product [{idx+1}] Success: {generated.get('title', 'Product')}", "success")
                response = {
                    "row_index": idx,
                    "status": "success",
                    "product_id": push_result["product_id"],
                    "shopify_url": push_result["shopify_url"],
                    "title": generated.get("title"),
                    "product_type": generated.get("product_type"),
                    "original_data": product
                }
                
                if pricing_info:
                    response["pricing_info"] = pricing_info
                    
                return response
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

    async def protected_process_single_product(idx, product):
        async with semaphore:
            return await process_single_product(idx, product, shopify_categories)

    # Run all tasks concurrently with throttling
    await send_log(f"🚀 Starting batch processing for {len(products)} products...", "info")
    results = await asyncio.gather(*[protected_process_single_product(i, p) for i, p in enumerate(products)])
    
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count
    
    await send_log(f"✅ Batch completed! Success: {success_count}, Failed: {failed_count}", "done")
    
    return {
        "status": "completed",
        "total_products": len(products),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results
    }
