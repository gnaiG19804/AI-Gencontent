"""
Pricing Routes
- GET /calculate-price - Calculate prices for all uploaded products
"""
import asyncio
import statistics
from fastapi import APIRouter, HTTPException

from utils.getPrice import google_shopping_prices, find_most_common_price, calculate_price
from core.logging import send_log
from config.config import Config
from models.model import BatchPricingRequest # Added model

router = APIRouter(tags=["Pricing"])



@router.post("/calculate-prices")
async def calculate_prices_batch(req: BatchPricingRequest):
    """
    Node n8n: Tính giá hàng loạt cho sản phẩm (nhận mảng từ n8n).
    """
    results = []
    sem = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS) # Concurrent Control

    async def process_price(idx: int, item):
         async with sem:
            try:
                product_name = item.product_name
                vintage = item.vintage
                cost_per_item = item.cost_per_item
                
                await send_log(f"💰 [Batch] ({idx+1}/{len(req.items)}) Đang tính giá cho: {product_name}", "info")
                
                # Step 1: Find Top 10 raw competitor prices
                prices = await asyncio.to_thread(
                    google_shopping_prices,
                    product_name,
                    vintage,
                    raw=True
                )
                
                floor_margin = Config.FLOOR_MARGIN
                floor_price = round(cost_per_item * floor_margin, 2)
                
                final_price = None
                strategy = "floor"
                
                if prices:
                    valid_competitors = sorted([p for p in prices if p > cost_per_item])
                    for p in valid_competitors:
                        suggested = round(p * 0.99, 2)
                        if suggested >= floor_price:
                            final_price = suggested
                            strategy = "competitive_step_up"
                            break
                
                if final_price is None:
                    final_price = floor_price
                    strategy = "floor"

                return {
                    "status": "success",
                    "product_name": product_name,
                    "vintage": vintage,
                    "recommended_price": final_price,
                    "strategy": strategy,
                }
                
            except Exception as e:
                return {
                    "status": "error",
                    "message": str(e),
                    "product_name": item.product_name,
                }

    # Parallel Execution
    tasks = [process_price(i, item) for i, item in enumerate(req.items)]
    results = await asyncio.gather(*tasks)
            
    return {
        "status": "success",
        "total": len(req.items),
        "results": results
    }
