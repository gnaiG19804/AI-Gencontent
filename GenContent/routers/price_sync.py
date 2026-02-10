from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from pydantic import BaseModel, model_validator
from services.price_sync_service import (
    fetch_products_for_n8n,
    calculate_target_price_logic,
    execute_price_update
)
from config.config import Config

router = APIRouter(prefix="/price-sync", tags=["Price Sync (N8N)"])

# --- Request Models ---

class CompetitorAnalysisRequest(BaseModel):
    product_id: Optional[str] = None
    variant_id: Optional[str] = None
    product_title: Optional[str] = None
    product_name: Optional[str] = None
    vintage: Optional[Any] = None
    cost: Optional[float] = None
    current_price: Optional[float] = None

    @model_validator(mode='before')
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Handle Product ID
            for key in ['product_id', 'id', 'Product_id']:
                if key in data and data[key]:
                    data['product_id'] = str(data[key])
                    break
            
            # 2. Extract variant from nested variants array
            variants = data.get('variants', [])
            first_variant = variants[0] if isinstance(variants, list) and len(variants) > 0 else {}

            if not data.get('variant_id'):
                for key in ['variant_id', 'id', 'Variant_id']:
                    if key in first_variant and first_variant[key]:
                        data['variant_id'] = str(first_variant[key])
                        break

            # 3. Handle Name & Vintage
            for key in ['product_name', 'name', 'tên', 'ten']:
                if key in data and data[key]:
                    data['product_name'] = str(data[key])
                    break
            
            for key in ['vintage', 'năm', 'nam']:
                if key in data and data[key]:
                    data['vintage'] = data[key]
                    break

            # 4. Handle Title (Fallback)
            for key in ['product_title', 'title', 'product_name', 'Product_title', 'Product_name']:
                if key in data and data[key] and str(data[key]).strip():
                    if 'product_title' not in data:
                        data['product_title'] = str(data[key])
                    break
            
            # 5. Handle Cost (from top-level or nested variant)
            cost_keys = ['cost', 'luc', 'LUC', 'cost_per_item', 'Cost']
            found_cost = None
            for key in cost_keys:
                if key in data and data[key] is not None:
                    found_cost = data[key]
                    break
                if key in first_variant and first_variant[key] is not None:
                    found_cost = first_variant[key]
                    break
            
            if found_cost is not None:
                val = str(found_cost).strip()
                try:
                    data['cost'] = float(val.replace(",", ""))
                except Exception:
                    pass

            # 6. Handle Price (from top-level or nested variant)
            price_keys = ['current_price', 'price', 'Price', 'Price_current']
            found_price = None
            for key in price_keys:
                if key in data and data[key] is not None:
                    found_price = data[key]
                    break
                if key in first_variant and first_variant[key] is not None:
                    found_price = first_variant[key]
                    break
            
            if found_price is not None:
                val = str(found_price).strip()
                try:
                    data['current_price'] = float(val.replace(",", ""))
                except Exception:
                    pass
        return data


class TargetPriceCalculationRequest(BaseModel):
    product_id: Optional[str] = None
    variant_id: Optional[str] = None
    product_title: Optional[str] = None
    competitor_price: float
    cost: float
    current_price: float

    @model_validator(mode='before')
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ['product_id', 'id', 'Product_id']:
                if key in data and data[key]:
                    data['product_id'] = str(data[key])
                    break
            
            for key in ['variant_id', 'Variant_id']:
                if key in data and data[key]:
                    data['variant_id'] = str(data[key])
                    break
            
            for key in ['product_title', 'title', 'Title', 'name']:
                if key in data and data[key]:
                    data['product_title'] = str(data[key])
                    break
        return data


class PriceUpdateRequest(BaseModel):
    product_id: str
    variant_id: str
    new_price: float

    @model_validator(mode='before')
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map product_id
            for key in ['product_id', 'id', 'Product_id']:
                if key in data and data[key]:
                    data['product_id'] = str(data[key])
                    break
            
            # Map variant_id (from nested variants if needed)
            if 'variants' in data and isinstance(data['variants'], list) and len(data['variants']) > 0:
                v = data['variants'][0]
                if isinstance(v, dict) and 'id' in v:
                    data['variant_id'] = str(v['id'])
            
            for key in ['variant_id', 'Variant_id']:
                if key in data and data[key]:
                    data['variant_id'] = str(data[key])
                    break

            # Map new_price
            for key in ['new_price', 'recommended_price', 'price_new']:
                if key in data and data[key] is not None:
                    try:
                        data['new_price'] = float(str(data[key]).replace(",", ""))
                        break
                    except Exception:
                        pass
        return data


# --- Endpoints ---

@router.get("/products")
async def get_products_batch(
    limit: int = Query(default=Config.MAX_CONCURRENT_REQUESTS, description="Batch size"),
    cursor: Optional[str] = Query(default=None, description="Pagination cursor")
):
    """
    Step 1: Fetch a batch of products from Shopify.
    """
    if not Config.PRICE_SYNC_ENABLED:
        raise HTTPException(status_code=403, detail="Price Sync feature is disabled.")
        
    return await fetch_products_for_n8n(limit=limit, cursor=cursor)


@router.post("/analyze-all")
async def analyze_all(req: CompetitorAnalysisRequest):
    """
    Step 2 (Unified): Scan ALL sources (Shopify Competitors + Google Shopping + Organic)
    and return the lowest price found.
    """
    from services.price_sync_service import analyze_all_prices
    
    result = await analyze_all_prices(
        product_title=req.product_title,
        product_name=req.product_name,
        vintage=req.vintage,
        cost=req.cost,
        current_price=req.current_price,
        product_id=req.product_id,
        variant_id=req.variant_id
    )
    return result


@router.post("/calculate-target")
async def calculate_target(req: TargetPriceCalculationRequest):
    """
    Step 3: Calculate recommended price using Step-up logic.
    Returns 'action': 'UPDATE' or 'SKIP'.
    """
    result = await calculate_target_price_logic(
        title=req.product_title,
        competitor_price=req.competitor_price,
        cost=req.cost,
        current_price=req.current_price,
        product_id=req.product_id,
        variant_id=req.variant_id
    )
    return result


@router.post("/execute-update")
async def execute_update(req: PriceUpdateRequest):
    """
    Step 4: Execute the price update on Shopify.
    """
    result = await execute_price_update(
        product_id=req.product_id,
        variant_id=req.variant_id,
        new_price=req.new_price
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
        
    return result


@router.get("/logs")
async def get_price_sync_logs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None
):
    """
    Get paginated price sync logs.
    """
    # Import inside function to avoid circular imports if models are initialized late
    from models.db_models import PriceSyncLog

    query = PriceSyncLog.all().order_by('-timestamp')
    
    if status and status != 'ALL':
        query = query.filter(status=status)
        
    total = await query.count()
    logs = await query.offset(offset).limit(limit)
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": logs
    }
