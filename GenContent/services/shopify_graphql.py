import requests
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import Config


def handle_graphql_response(result: Dict[str, Any], operation_name: str) -> Dict[str, Any]:
    """
    Helper to handle GraphQL response errors
    """
    if "errors" in result:
        print(f" {operation_name} GraphQL errors: {json.dumps(result['errors'], indent=2)}")
        return {"status": "error", "errors": result["errors"]}
    
    data = result.get("data", {})
    operation_result = data.get(operation_name, {})
    user_errors = operation_result.get("userErrors", [])
    
    if user_errors:
        print(f" {operation_name} userErrors: {json.dumps(user_errors, indent=2)}")
        return {"status": "error", "errors": user_errors}
    
    return {"status": "success", "data": operation_result}


def setup_inventory_for_variant(inventory_item_id: str, quantity: int) -> Dict[str, Any]:
    """
    Orchestrate full inventory setup: Get Location -> Activate -> Set Quantity
    """
    print(f" Setting up inventory: {quantity} units")
    
    # Step 1: Get primary location
    location_id = get_primary_location()
    if not location_id:
        print(f" Could not get location for inventory")
        return {"status": "error", "message": "Missing location"}

    # Step 2: Activate tracking
    activate_res = activate_inventory_tracking(inventory_item_id)
    if activate_res["status"] != "success":
        return activate_res
    
    print(f" Inventory tracking activated")

    # Step 3: Set quantity
    qty_res = set_inventory_quantities(inventory_item_id, location_id, quantity)
    if qty_res["status"] != "success":
        return qty_res
        
    print(f" Inventory quantity set: {quantity} units")
    return {"status": "success"}


def update_product_variant_bulk(
    product_gid: str,
    variant_gid: str,
    price: Optional[str] = None,
    sku: Optional[str] = None,
    inventory_management: bool = True
) -> Dict[str, Any]:
    """
    Update variant with price, SKU using bulk update API (2024-10)
    """
    mutation = """
              mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
                productVariantsBulkUpdate(productId: $productId, variants: $variants) {
                  productVariants {
                    id
                    price
                    sku
                    inventoryItem {
                      id
                      tracked
                    }
                  }
                  userErrors {
                    field
                    message
                  }
                }
              }
              """
    
    variant_input = {"id": variant_gid}
    if price: variant_input["price"] = price
    if sku: variant_input["sku"] = sku
    
    variables = {
        "productId": product_gid,
        "variants": [variant_input]
    }
    
    result = execute_graphql_query(mutation, variables)
    processed = handle_graphql_response(result, "productVariantsBulkUpdate")
    
    if processed["status"] == "error":
        return processed
    
    variant_data = processed["data"]
    
    # usage: inventory_item_id for next steps
    inventory_item_id = None
    if inventory_management:
        variants = variant_data.get("productVariants", [])
        if variants:
            inventory_item_id = variants[0].get("inventoryItem", {}).get("id")
    
    return {
        "status": "success",
        "variants": variant_data.get("productVariants"),
        "inventory_item_id": inventory_item_id
    }


def activate_inventory_tracking(inventory_item_id: str, location_id: str = None) -> Dict[str, Any]:
    """
    Activate inventory tracking (set tracked=true)
    """
    mutation = """
              mutation inventoryItemUpdate($id: ID!, $input: InventoryItemInput!) {
                inventoryItemUpdate(id: $id, input: $input) {
                  inventoryItem {
                    id
                    tracked
                  }
                  userErrors {
                    field
                    message
                  }
                }
              }
              """
    
    variables = {
        "id": inventory_item_id,
        "input": {"tracked": True}
    }
    
    result = execute_graphql_query(mutation, variables)
    processed = handle_graphql_response(result, "inventoryItemUpdate")
    
    if processed["status"] == "success":
        return {"status": "success", "inventoryItem": processed["data"].get("inventoryItem")}
    return processed


def set_inventory_quantities(inventory_item_id: str, location_id: str, quantity: int) -> Dict[str, Any]:
    """
    Set inventory quantity at a location
    """
    mutation = """
                mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
                  inventorySetQuantities(input: $input) {
                    inventoryAdjustmentGroup {
                      id
                    }
                    userErrors {
                      field
                      message
                    }
                  }
                }
            """
    
    variables = {
        "input": {
            "reason": "correction",
            "name": "available",
            "ignoreCompareQuantity": True,
            "quantities": [
                {
                    "inventoryItemId": inventory_item_id,
                    "locationId": location_id,
                    "quantity": quantity
                }
            ]
        }
    }
    
    result = execute_graphql_query(mutation, variables)
    return handle_graphql_response(result, "inventorySetQuantities")


def get_primary_location() -> Optional[str]:
    """
    Get primary location GID
    """
    query = """
              {
                locations(first: 1) {
                  edges {
                    node {
                      id
                      name
          }
        }
      }
    }
    """
    result = execute_graphql_query(query)
    
    if "errors" in result or "data" not in result:
        return None
    
    locations = result.get("data", {}).get("locations", {}).get("edges", [])
    if locations:
        node = locations[0].get("node", {})
        print(f"📍 Using location: {node.get('name')} ({node.get('id')})")
        return node.get("id")
    
    return None


def execute_graphql_query(query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Execute GraphQL query/mutation
    """
    shop_url = Config.SHOPIFY_STORE_URL
    access_token = Config.SHOPIFY_ACCESS_TOKEN
    
    if not shop_url or not access_token:
        return {"errors": [{"message": "Missing config"}]}
    
    endpoint = f"https://{shop_url}/admin/api/2024-10/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }
    
    try:
        response = requests.post(endpoint, json={"query": query, "variables": variables or {}}, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"errors": [{"message": str(e)}]}


def create_product_graphql(
    title: str,
    description_html: str,
    vendor: str,
    product_type: str,
    tags: List[str],
    category_id: Optional[str] = None,
    variants: List[Dict[str, Any]] = None,
    status: str = "ACTIVE"
) -> Dict[str, Any]:
    """
    Create product and handle variants/inventory
    """
    mutation = """
                mutation productCreate($input: ProductInput!) {
                  productCreate(input: $input) {
                    product {
                      id
                      category { id name }
                      variants(first: 1) {
                        edges { node { id } }
                      }
                    }
                    userErrors {
                      field
                      message
                    }
                  }
                }
                """
    
    product_input = {
        "title": title,
        "descriptionHtml": description_html,
        "vendor": vendor,
        "productType": product_type,
        "tags": tags,
        "status": status
    }
    if category_id:
        product_input["category"] = category_id
    
    # 1. Create Product
    result = execute_graphql_query(mutation, {"input": product_input})
    processed = handle_graphql_response(result, "productCreate")
    
    if processed["status"] == "error":
        return processed
        
    product = processed["data"].get("product", {})
    product_gid = product.get("id")
    product_id = product_gid.split("/")[-1] if product_gid else None
    
    # Get created variant ID (default variant)
    variant_gid = None
    edges = product.get("variants", {}).get("edges", [])
    if edges:
        variant_gid = edges[0].get("node", {}).get("id")
    
    success_response = {
        "status": "success",
        "product_id": product_id,
        "product_gid": product_gid,
        "shopify_url": f"https://{Config.SHOPIFY_STORE_URL}/admin/products/{product_id}" if product_id else None,
        "message": "Product created successfully",
        "category": product.get("category")
    }
    
    # 2. Update Variant & Inventory
    if variant_gid and variants:
        v_data = variants[0]
        print(f" Updating variant: Price={v_data.get('price')}, SKU={v_data.get('sku')}")
        
        update_res = update_product_variant_bulk(
            product_gid=product_gid,
            variant_gid=variant_gid,
            price=v_data.get("price"),
            sku=v_data.get("sku"),
            inventory_management=True
        )
        
        if update_res["status"] == "success":
            print(f" Variant updated successfully")
            
            # 3. Setup Inventory (if quantity exists)
            inv_item_id = update_res.get("inventory_item_id")
            quantity = v_data.get("quantity")
            
            if inv_item_id and quantity is not None:
                inv_res = setup_inventory_for_variant(inv_item_id, int(quantity))
                if inv_res["status"] != "success":
                    print(f" Inventory setup failed: {inv_res}")
                    # Don't fail the whole product creation, just warn
        else:
            print(f" Variant update failed: {update_res.get('errors')}")

    return success_response


def build_graphql_variants(variants_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert variant data to GraphQL format helpers
    """
    graphql_variants = []
    
    for variant in variants_data:
        gql = {}
        if "price" in variant: gql["price"] = str(variant["price"])
        if "sku" in variant: gql["sku"] = variant["sku"]
        if "quantity" in variant: gql["quantity"] = variant["quantity"]
        
        options = []
        for i in range(1, 4):
            key = f"option{i}"
            if variant.get(key): options.append(str(variant[key]))
            
        if options: gql["options"] = options
        graphql_variants.append(gql)
    
    return graphql_variants
