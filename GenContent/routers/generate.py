"""
Content Generation Routes
- POST /generate - Generate content for all products
- POST /build-product - Build Shopify product preview
"""
from fastapi import APIRouter, HTTPException

from services.genConten import genContent
from services.shopify_service import build_shopify_product_body
from utils.taxonomy_manager import get_or_refresh_categories
from llms.llm import llm_genContent
from config.config import Config
from core.state import uploaded_data

router = APIRouter(tags=["Generate"])


@router.post("/generate")
async def generate_content():
    """Generate content cho tất cả sản phẩm bằng LLM"""
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file nào")
    
    products = uploaded_data["products"]
    results = []
    
    for idx, product in enumerate(products):
        try:
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


@router.post("/build-product")
async def build_product_preview():
    """Build Shopify product body preview"""
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
