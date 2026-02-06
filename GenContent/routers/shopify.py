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

router = APIRouter(tags=["Shopify"])


@router.post("/push-to-shopify")
async def push_products_to_shopify():
    """
    Push tất cả sản phẩm lên Shopify store
    Workflow: Upload → Generate → Calculate Price → Build → Push
    """
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file nào. Vui lòng upload CSV trước.")
    
    products = uploaded_data["products"]
    
    # Get credentials from Config
    shop_url = Config.SHOPIFY_STORE_URL
    access_token = Config.SHOPIFY_ACCESS_TOKEN
    
    if not shop_url or not access_token:
        raise HTTPException(status_code=500, detail="Thiếu thông tin Shopify trong Config. Vui lòng kiểm tra .env file.")

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

    async def process_single_product(idx: int, product: Dict[str, Any], categories: list) -> Dict[str, Any]:
        try:
            # Step 1: Generate content
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
            
            # Step 2: Calculate price if cost_per_item exists
            pricing_info = None
            recommended_price = None
            
            if "cost_per_item" in product and product.get("cost_per_item"):
                try:
                    await send_log(f"💰 Tính giá cho sản phẩm [{idx+1}]...", "info")
                    
                    product_name = product.get("Product_name", generated.get("title", ""))
                    vintage = product.get("Vintage", "")
                    cost_per_item = float(product["cost_per_item"])
                    
                    prices = await asyncio.to_thread(
                        google_shopping_prices,
                        product_name,
                        vintage
                    )
                    
                    if prices and len(prices) > 0:
                        mode_price = find_most_common_price(prices)
                        pricing = calculate_price(mode_price, cost_per_item)
                        recommended_price = pricing["recommended_price"]
                        
                        pricing_info = {
                            "competitor_mode": mode_price,
                            "price_count": len(prices),
                            "recommended_price": recommended_price,
                            "strategy": pricing["strategy"],
                            "margin_percent": pricing["margin_percent"]
                        }
                        
                        await send_log(
                            f"💰 Giá đề xuất [{idx+1}]: ${recommended_price:.2f} ({pricing['strategy']})",
                            "success"
                        )
                    else:
                        await send_log(f"⚠️ Không tìm thấy giá đối thủ cho [{idx+1}]", "warning")
                        
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
