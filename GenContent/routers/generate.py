"""
Content Generation Routes
- POST /generate - Generate content for all products
- POST /build-product - Build Shopify product preview
"""
from fastapi import APIRouter, HTTPException

from services.genConten import genContent
from services.shopify_service import build_shopify_product_body
from utils.taxonomy_manager import get_or_refresh_categories
from utils.description_scraper import get_competitor_context
from llms.llm import llm_genContent
from config.config import Config
from core.state import uploaded_data
from core.logging import send_log
from models.model import ContextRequest, GenerateSingleRequest, BatchContextRequest, BatchGenerateRequest, BatchEnrichRequest # Added BatchEnrichRequest
import asyncio # Import asyncio for Semaphore
from utils.getPrice import google_shopping_prices, calculate_price # Import pricing utils

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
            product_name = product.get("Product_name", "")
            vintage = product.get("Vintage", "")
            
            await send_log(f"✍️ [{idx+1}] Đang tìm mô tả tham khảo cho: {product_name}", "info")
            
            # Step 1: Get RAG context
            competitor_context = await get_competitor_context(product_name, vintage)
            
            if competitor_context:
                await send_log(f"📚 Đã tìm thấy mô tả tham khảo cho {product_name}", "success")
            else:
                await send_log(f"⚠️ Không tìm thấy mô tả tham khảo cho {product_name}, tiếp tục generate thường.", "info")

            # Step 2: Generate content
            generated = await genContent(
                model=llm_genContent,
                system_prompt=Config.SYSTEM_PROMPT_CONTENT,
                data=product,
                competitor_context=competitor_context
            )
            
            results.append({
                "row_index": idx,
                "original_data": product,
                "generated_content": generated
            })
        except Exception as e:
            await send_log(f"❌ Error generating {product.get('Product_name', 'Unknown')}: {str(e)}", "error")
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
            product_name = product.get("Product_name", "")
            vintage = product.get("Vintage", "")

            await send_log(f"✍️ [{idx+1}] Đang chuẩn bị preview cho: {product_name}", "info")
            
            # Step 1: Get RAG context
            competitor_context = await get_competitor_context(product_name, vintage)

            # Step 2: Generate content
            generated = await genContent(
                model=llm_genContent,
                system_prompt=Config.SYSTEM_PROMPT_CONTENT,
                data=product,
                competitor_context=competitor_context
            )
            
            if generated["status"] != "success":
                results.append({
                    "row_index": idx,
                    "status": "error",
                    "message": f"Generate error: {generated.get('message')}"
                })
                continue
            
            # Step 3: Build Shopify product body
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



@router.post("/fetch-contexts")
async def fetch_contexts_batch(req: BatchContextRequest):
    """
    Node n8n: Lấy mô tả đối thủ cho một MẢNG sản phẩm.
    """
    results = []
    sem = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS) # Concurrent Control

    async def process_context(idx: int, item):
        async with sem:
            try:
                await send_log(f"🔍 [Batch] ({idx+1}/{len(req.items)}) Đang tìm mô tả cho: {item.product_name}", "info")
                context = await get_competitor_context(item.product_name, item.vintage)
                return {
                    "product_name": item.product_name,
                    "vintage": item.vintage,
                    "competitor_context": context,
                    "status": "success",
                    "metadata": item.metadata # Trả lại metadata từng item
                }
            except Exception as e:
                return {
                    "product_name": item.product_name,
                    "vintage": item.vintage,
                    "status": "error",
                    "message": str(e),
                    "metadata": item.metadata
                }
    
    # Concurrent Execution
    tasks = [process_context(i, item) for i, item in enumerate(req.items)]
    results = await asyncio.gather(*tasks)

    return {
        "status": "success",
        "total": len(req.items),
        "results": results
    }

@router.post("/enrich-batch")
async def enrich_batch_products(req: BatchEnrichRequest):
    """
    Node n8n (Combined): Lấy thông tin RAG và Giá CÙNG LÚC (Song song).
    Thay thế cho 2 node fetch-contexts và calculate-prices riêng lẻ.
    """
    results = []
    sem = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS)

    async def process_enrich(idx: int, item):
        async with sem:
            try:
                product_name = item.product_name
                vintage = item.vintage
                cost_per_item = item.cost_per_item
                
                await send_log(f"⚡ [Enrich] ({idx+1}/{len(req.items)}) Đang xử lý song song Giá & RAG cho: {product_name}", "info")

                # Define tasks
                rag_task = get_competitor_context(product_name, vintage)
                
                # Check for explicit unit_price in metadata
                input_price = None
                if item.metadata:
                    price_keys = ['unit_price', 'price', 'Price', 'Unit Price']
                    for k in price_keys:
                        if k in item.metadata and item.metadata[k]:
                             try:
                                 input_price = float(str(item.metadata[k]).replace(",", ""))
                                 break
                             except:
                                 pass

                if input_price:
                    # Logic khi có giá (Skip Google)
                    await send_log(f"⚡ [Enrich] Đã có giá nhập: ${input_price}. Bỏ qua dò giá.", "info")
                    context = await rag_task
                    prices = [] # No competitor prices
                    
                    final_price = input_price
                    strategy = "manual_input"
                else:
                    # FORCE DISABLE: User requested to stop competitor pricing entirely
                    await send_log(f"⚠️ Không tìm thấy giá trong CSV. Bỏ qua dò giá Google (Logic cũ đã tắt).", "warning")
                    context = await rag_task
                    prices = []
                    
                    # Still calculate floor price if cost exists
                    floor_margin = Config.FLOOR_MARGIN
                    if cost_per_item:
                         floor_price = round(cost_per_item * floor_margin, 2)
                         final_price = floor_price
                         strategy = "floor_only"
                    else:
                         final_price = None
                         strategy = "missing_cost"
                            
                # Merge metadata back into original_data to preserve extra fields like Supplier
                original_data_full = {
                    "product_name": product_name,
                    "vintage": vintage,
                    "cost_per_item": cost_per_item,
                }
                # Add all extra fields from metadata
                if item.metadata:
                    original_data_full.update(item.metadata)
                    
                return {
                    "product_name": product_name,
                    "vintage": vintage,
                    "status": "success",
                    "competitor_context": context,
                    "recommended_price": final_price,
                    "price_strategy": strategy,
                    "cost_per_item": cost_per_item, # Add this to make it available at top level
                    "metadata": item.metadata,
                    "original_data": original_data_full 
                }
            except Exception as e:
                return {
                    "product_name": item.product_name,
                    "status": "error",
                    "message": str(e),
                    "metadata": item.metadata
                }

    tasks = [process_enrich(i, item) for i, item in enumerate(req.items)]
    results = await asyncio.gather(*tasks)

    return {
        "status": "success",
        "total": len(req.items),
        "results": results
    }

@router.post("/generate-batch")
async def generate_batch_content(req: BatchGenerateRequest):
    """
    Node n8n 3: Sinh nội dung MẢNG sản phẩm (Concurrency controlled).
    """
    results = []
    sem = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS) # Sử dụng config

    async def process_item(item: GenerateSingleRequest, idx: int):
        async with sem:
            try:
                product_name = item.product_data.get("Product_name", "Unknown")
                await send_log(f"✍️ [Batch-Gen] Đang viết bài cho ({idx+1}/{len(req.items)}): {product_name}", "info")
                
                # IMPORTANT: Format the system prompt with config language
                formatted_prompt = Config.SYSTEM_PROMPT_CONTENT.format(LANGUAGE=Config.LANGUAGE)
                
                generated = await genContent(
                    model=llm_genContent,
                    system_prompt=formatted_prompt,
                    data=item.product_data,
                    competitor_context=item.competitor_context
                )
                
                # Extract cost_per_item from product_data (check multiple possible field names)
                cost_per_item = None
                cost_keys = ['cost_per_item', 'Cost', 'cost', 'LUC', 'luc']
                for key in cost_keys:
                    if key in item.product_data and item.product_data[key] is not None:
                        try:
                            cost_per_item = float(str(item.product_data[key]).replace(",", ""))
                            break
                        except:
                            pass
                
                return {
                    "status": "success",
                    "product_name": product_name,
                    "generated_content": generated,
                    "product_data": item.product_data,
                    "cost_per_item": cost_per_item,  # Explicitly return cost
                    "metadata": item.metadata
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": str(e),
                    "product_name": item.product_data.get("Product_name", "Unknown"),
                }

    # Chạy song song tất cả items
    tasks = [process_item(item, i) for i, item in enumerate(req.items)]
    results = await asyncio.gather(*tasks)
    
    return {
        "status": "success",
        "total": len(req.items),
        "results": results
    }
