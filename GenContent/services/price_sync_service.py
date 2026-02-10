import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import Config
from utils.getPrice import google_shopping_prices, calculate_price
from services.shopify_graphql import execute_graphql_query, update_product_variant_bulk


async def fetch_products_for_n8n(limit: int = 10, cursor: Optional[str] = None) -> Dict[str, Any]:
    """Fetch a batch of products from Shopify for N8N to process."""
    query = """
    query ($first: Int!, $cursor: String) {
      products(first: $first, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            id
            title
            variants(first: 10) {
              edges {
                node {
                  id
                  sku
                  price
                  inventoryItem {
                    unitCost {
                      amount
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    
    variables = {"first": limit, "cursor": cursor}
    result = execute_graphql_query(query, variables)
    
    if not result or "data" not in result:
        return {"products": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}
        
    data = result["data"]["products"]
    
    products = []
    for edge in data["edges"]:
        node = edge["node"]
        variants = []
        for v_edge in node["variants"]["edges"]:
            v = v_edge["node"]
            cost = 0.0
            if v.get("inventoryItem") and v["inventoryItem"].get("unitCost"):
                cost = float(v["inventoryItem"]["unitCost"]["amount"])
                
            variants.append({
                "id": v["id"],
                "sku": v["sku"],
                "price": float(v["price"]),
                "cost": cost
            })
            
        products.append({
            "id": node["id"],
            "title": node["title"],
            "variants": variants
        })
        
    return {
        "products": products,
        "pageInfo": data["pageInfo"]
    }


async def _search_google_prices(search_query: str, product_name: Optional[str] = None, vintage: Optional[Any] = None) -> Dict[str, Any]:
    """
    Internal helper: Search Google Shopping for competitor prices.
    Used by analyze_all_prices.
    """
    import re

    if product_name:
        query = f"{product_name} {vintage if vintage else ''}".strip()
    else:
        query = re.split(r'\s*[–—-]\s*', search_query)[0].strip()
        
        generic_prefixes = [
            r'^rượu vang đỏ\s+', r'^rượu vang trắng\s+', r'^rượu vang\s+', 
            r'^vang đỏ\s+', r'^vang trắng\s+', r'^vang\s+', r'^rượu\s+'
        ]
        for prefix in generic_prefixes:
            query = re.sub(prefix, '', query, flags=re.IGNORECASE).strip()
    
    prices = await asyncio.to_thread(google_shopping_prices, query, raw=False)
    
    if not prices:
        return {"lowest_price": None, "found_prices": [], "count": 0, "search_query": query}
        
    return {
        "lowest_price": min(prices),
        "found_prices": prices,
        "count": len(prices),
        "search_query": query
    }


async def analyze_all_prices(
    product_title: str, 
    product_name: Optional[str] = None, 
    vintage: Optional[Any] = None,
    cost: Optional[float] = None, 
    current_price: Optional[float] = None,
    product_id: Optional[str] = None,
    variant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified price analysis:
    1. Auto-extract product_name & vintage from title if missing.
    2. Scan Shopify Competitors (if defined).
    3. Scan Google Shopping + Organic.
    4. Return lowest price from ALL sources.
    """
    from services.shopify_storefront_service import get_competitor_domains, scan_competitor_file
    import re

    # --- Auto-extract name & vintage from title ---
    if not product_name or not vintage:
        base_part = re.split(r'\s*[–—-]\s*', product_title)[0].strip()
        
        if not vintage:
            match = re.search(r'\b(19\d{2}|20\d{2})\b', base_part)
            if match:
                vintage = match.group(1)
            else:
                match = re.search(r'\b(\d{1,2}Y)\b', base_part, re.IGNORECASE)
                if match:
                    vintage = match.group(1).upper()
        
        if not product_name:
            name_part = base_part
            if vintage:
                name_part = name_part.replace(str(vintage), "").strip()
            
            generic_prefixes = [
                r'^rượu vang đỏ\s+', r'^rượu vang trắng\s+', r'^rượu vang\s+', 
                r'^vang đỏ\s+', r'^vang trắng\s+', r'^vang\s+', r'^rượu\s+'
            ]
            for prefix in generic_prefixes:
                name_part = re.sub(prefix, '', name_part, flags=re.IGNORECASE).strip()
            
            product_name = name_part

    # --- Build search query ---
    main_query = f"{product_name} {vintage if vintage else ''}".strip() if product_name else \
                 re.split(r'\s*[–—-]\s*', product_title)[0].strip()

    # --- Run Shopify + Google scans CONCURRENTLY ---
    domains = get_competitor_domains()
    
    async def _shopify_scan():
        if domains:
            results = await asyncio.to_thread(scan_competitor_file, main_query)
            return results
        return []
    
    shopify_results, google_result = await asyncio.gather(
        _shopify_scan(),
        _search_google_prices(product_title, product_name, vintage)
    )
    
    shopify_prices = [item["price"] for item in shopify_results]
    google_prices = google_result.get("found_prices", [])

    # --- 3. Aggregate & return ---
    all_prices = shopify_prices + google_prices
    
    response = {
        "product_id": product_id,
        "variant_id": variant_id,
        "product_title": product_title,
        "product_name": product_name,
        "vintage": vintage,
        "search_query": main_query,
        "cost": cost,
        "current_price": current_price,
        "lowest_price": min(all_prices) if all_prices else None,
        "all_prices": all_prices,
        "sources": {
            "shopify": shopify_prices,
            "google": google_prices
        },
        "details": {
            "shopify_matches": shopify_results,
            "google_data": google_result
        }
    }
    
    if not all_prices:
        response["message"] = f"No prices found from any source for '{main_query}'"
        
    return response



async def calculate_target_price_logic(
    competitor_price: float, 
    cost: float, 
    current_price: float,
    title: Optional[str] = None,
    product_id: Optional[str] = None,
    variant_id: Optional[str] = None
) -> Dict[str, Any]:
    """Calculate recommended price using step-up logic."""
    pricing = calculate_price(competitor_price, cost)
    
    new_price = pricing["recommended_price"]
    should_update = abs(new_price - current_price) > 0.01

    action = "UPDATE" if should_update else "SKIP"
    
    # --- LOGGING TO DB ---
    try:
        from models.db_models import PriceSyncLog
        if product_id:
            await PriceSyncLog.create(
                product_id=product_id,
                variant_id=variant_id,
                product_title=title,
                old_price=current_price,
                new_price=new_price,
                competitor_price=competitor_price,
                cost=cost,
                action=action,
                reason=pricing["reason"],
                status="PENDING" if should_update else "SKIPPED"
            )
    except Exception as e:
        print(f"⚠️ DB Log Error: {e}")

    return {
        "product_id": product_id,
        "variant_id": variant_id,
        "product_title": title,
        "action": action,
        "new_price": new_price,
        "old_price": current_price,
        "strategy": pricing["strategy"],
        "reason": pricing["reason"],
        "margin": pricing["margin_percent"],
        "cost": cost,
        "competitor_price": competitor_price
    }


async def execute_price_update(product_id: str, variant_id: str, new_price: float) -> Dict[str, Any]:
    """Update the variant price on Shopify."""
    res = update_product_variant_bulk(
        product_gid=product_id,
        variant_gid=variant_id,
        price=str(new_price)
    )
    
    status = "SUCCESS"
    errors = None
    
    if res and res.get("productVariantUpdate", {}).get("userErrors"):
        status = "ERROR"
        errors = res['productVariantUpdate']['userErrors']
        
    # --- UPDATE LOG STATUS ---
    try:
        from models.db_models import PriceSyncLog
        # Find latest pending log for this variant
        log_entry = await PriceSyncLog.filter(
            variant_id=variant_id, 
            status="PENDING"
        ).order_by('-timestamp').first()
        
        if log_entry:
            log_entry.status = status
            if errors:
                log_entry.reason = f"Shopify Error: {str(errors)}"
            await log_entry.save()
            
    except Exception as e:
        print(f"⚠️ DB Log Update Error: {e}")

    if status == "ERROR":
        return {
            "status": "error", 
            "product_id": product_id,
            "variant_id": variant_id,
            "errors": errors
        }
        
    return {
        "status": "success", 
        "product_id": product_id,
        "variant_id": variant_id,
        "new_price": new_price
    }
