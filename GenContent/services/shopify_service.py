import requests
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import Config
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

def build_shopify_product_body(
    generated_content: Dict[str, Any],
    original_data: Dict[str, Any],
    shopify_categories: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Build Shopify product body chuẩn từ generated content và original CSV data
    """

    price = None
    price_keys = ['price', 'gia', 'gia_ban', 'cost', 'amount', 'giá']
    for key in original_data.keys():
        if key.lower().strip() in price_keys and original_data[key] is not None:
            try:
                price = float(str(original_data[key]).replace(",", ""))
            except:
                pass
            break
    
    # Extract SKU
    sku = None
    sku_keys = ['sku', 'code', 'ma', 'ma_san_pham', 'mã']
    for key in original_data.keys():
        if key.lower().strip().replace("_", "") in [k.replace("_", "") for k in sku_keys]:
            if original_data[key] is not None:
                sku = str(original_data[key])
                break
    
    # Find category ID based on product_type
    product_category_id = None
    product_type = generated_content.get("product_type", "")
    
    if shopify_categories and product_type:
        # Tìm category có name khớp với product_type
        for cat in shopify_categories:
            if cat["name"].lower() == product_type.lower():
                product_category_id = cat["id"]
                print(f" Matched category: {product_type} → ID: {product_category_id}")
                break
    
    # Handle new Content Engine fields
    description = generated_content.get("description", "")
    if not description:
        # Combine short and long if standard description is missing (new model)
        short_desc = generated_content.get("approved_short_description", "")
        long_desc = generated_content.get("approved_long_description", "")
        if short_desc or long_desc:
            description = f"<strong>{short_desc}</strong><br><br>{long_desc}"

    # Build product body
    product_body = {
        "product": {
            "title": generated_content.get("title", "Sản phẩm"),
            "body_html": description,
            "vendor": "Your Store",
            "product_type": product_type,
            "tags": generated_content.get("tags", ""),
            "status": "draft"  
        }
    }
    
    # Set Shopify Standard Product Category nếu có ID
    if product_category_id:
        product_body["product"]["product_category"] = {
            "product_taxonomy_node_id": product_category_id
        }
    
    # Build variant (price, sku, inventory)
    variant = {
        "inventory_management": "shopify",
        "inventory_policy": "deny"
    }
    
    if price is not None:
        variant["price"] = str(price)
    
    if sku:
        variant["sku"] = sku
    
    # Extract quantity for inventory management
    quantity = None
    quantity_keys = ['quantity', 'qty', 'stock', 'inventory', 'so_luong', 'số lượng', 'ton_kho']
    for key in original_data.keys():
        if key.lower().strip().replace("_", "").replace(" ", "") in [k.replace("_", "").replace(" ", "") for k in quantity_keys]:
            if original_data[key] is not None:
                try:
                    quantity = int(float(original_data[key]))
                except:
                    pass
                break
    
    if quantity is not None:
        variant["quantity"] = quantity
        print(f" DEBUG: Extracted quantity = {quantity} from CSV")
    else:
        print(f" DEBUG: No quantity found in CSV columns: {list(original_data.keys())}")
    
    # Add variant
    product_body["product"]["variants"] = [variant]
    
    # Build options từ các field còn lại (Color, Size...)
    options = []
    variant_options = []
    
    # Exclude price, sku, quantity, and name fields from options
    excluded_keys = price_keys + sku_keys + quantity_keys + ['name', 'title', 'tên', 'ten']
    
    for key, value in original_data.items():
        if value is not None and key.lower().strip() not in excluded_keys:
            options.append({
                "name": key,
                "values": [str(value)]
            })
            variant_options.append(str(value))
    
    # Add options và variant options
    if options:
        product_body["product"]["options"] = options
        if len(variant_options) > 0:
            product_body["product"]["variants"][0]["option1"] = variant_options[0] if len(variant_options) > 0 else None
            product_body["product"]["variants"][0]["option2"] = variant_options[1] if len(variant_options) > 1 else None
            product_body["product"]["variants"][0]["option3"] = variant_options[2] if len(variant_options) > 2 else None
    
    return product_body


def push_to_shopify(product_body: Dict[str, Any], shop_url: str = None, access_token: str = None) -> Dict[str, Any]:
    """
    Push product lên Shopify store using GraphQL API
    """
    from services.shopify_graphql import create_product_graphql, build_graphql_variants
    
    try:
        product = product_body.get("product", {})
        
        # Extract data
        title = product.get("title", "Untitled Product")
        description_html = product.get("body_html", "")
        vendor = product.get("vendor", "Your Store")
        product_type = product.get("product_type", "")
        tags_str = product.get("tags", "")
        tags = [tag.strip() for tag in tags_str.split(",")] if tags_str else []
        
        # Extract category ID
        category_id = None
        product_category = product.get("product_category", {})
        if product_category:
            category_id = product_category.get("product_taxonomy_node_id")
        
        # Convert variants to GraphQL format
        rest_variants = product.get("variants", [])
        graphql_variants = build_graphql_variants(rest_variants)
        
        # Create product via GraphQL
        result = create_product_graphql(
            title=title,
            description_html=description_html,
            vendor=vendor,
            product_type=product_type,
            tags=tags,
            category_id=category_id,
            variants=graphql_variants,
            status="DRAFT",
            shop_url=shop_url,
            access_token=access_token
        )
        
        if result["status"] == "success":
            # Log category if set
            if result.get("category"):
                cat = result["category"]
                print(f"Category set: {cat.get('name')} (ID: {cat.get('id')})")
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }
