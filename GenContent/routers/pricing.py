"""
Pricing Routes
- GET /calculate-price - Calculate prices for all uploaded products
"""
import asyncio
import statistics
from fastapi import APIRouter, HTTPException

from utils.getPrice import google_shopping_prices, find_most_common_price, calculate_price
from core.state import uploaded_data
from core.logging import send_log

router = APIRouter(tags=["Pricing"])


@router.get("/calculate-price")
async def calculate_price_preview():
    """
    Tính giá cho tất cả sản phẩm từ CSV đã upload
    """
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file CSV. Vui lòng upload trước.")
    
    products = uploaded_data["products"]
    results = []
    
    for idx, product in enumerate(products):
        try:
            # Check if cost_per_item exists
            if "cost_per_item" not in product or not product.get("cost_per_item"):
                results.append({
                    "row_index": idx,
                    "status": "skipped",
                    "message": "Thiếu cost_per_item",
                    "product_name": product.get("Product_name", "Unknown")
                })
                continue
            
            product_name = product.get("Product_name", "")
            vintage = product.get("Vintage", "")
            cost_per_item = float(product["cost_per_item"])
            
            await send_log(f"🔍 [{idx+1}] Đang tìm giá cho: {product_name}", "info")
            
            # Step 1: Find competitor prices
            prices = await asyncio.to_thread(
                google_shopping_prices,
                product_name,
                vintage
            )
            
            if not prices or len(prices) == 0:
                results.append({
                    "row_index": idx,
                    "status": "error",
                    "message": "Không tìm thấy giá đối thủ",
                    "product_name": product_name
                })
                continue
            
            # Step 2: Calculate mode and median
            mode_price = find_most_common_price(prices)
            median_price = statistics.median(prices)
            
            # Step 3: Calculate recommended price
            pricing = calculate_price(mode_price, cost_per_item)
            
            await send_log(
                f"💰 [{idx+1}] {product_name}: ${pricing['recommended_price']:.2f} ({pricing['strategy']})",
                "success"
            )
            
            results.append({
                "row_index": idx,
                "status": "success",
                "product_name": f"{product_name} {vintage}".strip(),
                "competitor_analysis": {
                    "mode_price": mode_price,
                    "median_price": round(median_price, 2),
                    "price_count": len(prices)
                },
                "pricing_recommendation": pricing
            })
            
        except Exception as e:
            await send_log(f"❌ [{idx+1}] Lỗi: {str(e)}", "error")
            results.append({
                "row_index": idx,
                "status": "error",
                "message": str(e),
                "product_name": product.get("Product_name", "Unknown")
            })
    
    success_count = sum(1 for r in results if r["status"] == "success")
    
    return {
        "status": "completed",
        "total_products": len(products),
        "success_count": success_count,
        "results": results
    }
