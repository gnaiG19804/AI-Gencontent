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
        # Check for permission errors globally
        for error in result["errors"]:
            if error.get("extensions", {}).get("code") == "ACCESS_DENIED":
                required = error.get("extensions", {}).get("requiredAccess", "unknown scope")
                print(f" [ERROR] {operation_name} FAILED: Missing permissions.")
                print(f"         Required scope: {required}")
                print(f"         Please update your Admin API Scopes in Shopify App settings.")
                return {"status": "error", "errors": result["errors"], "message": "Missing permissions"}
                
        print(f" {operation_name} GraphQL errors: {json.dumps(result['errors'], indent=2)}")
        return {"status": "error", "errors": result["errors"]}
    
    data = result.get("data", {})
    operation_result = data.get(operation_name, {})
    user_errors = operation_result.get("userErrors", [])
    
    if user_errors:
        print(f" {operation_name} userErrors: {json.dumps(user_errors, indent=2)}")
        return {"status": "error", "errors": user_errors}
    
    return {"status": "success", "data": operation_result}


def setup_inventory_for_variant(inventory_item_id: str, quantity: int, shop_url: str = None, access_token: str = None) -> Dict[str, Any]:
    """
    Orchestrate full inventory setup: Get Location -> Activate Tracking -> Stock at Location -> Set Quantity
    """
    print(f" Setting up inventory: {quantity} units")
    
    # Step 1: Get primary location
    location_id = get_primary_location(shop_url=shop_url, access_token=access_token)
    if not location_id:
        print(f" Could not get location for inventory")
        return {"status": "error", "message": "Missing location"}

    # Step 2: Activate tracking (global)
    activate_res = activate_inventory_tracking(inventory_item_id, shop_url=shop_url, access_token=access_token)
    if activate_res["status"] != "success":
        return activate_res
    
    print(f" Inventory tracking activated")

    # Step 3: Activate at location (Stock the item at this specific location)
    stock_res = activate_inventory_at_location(inventory_item_id, location_id, shop_url=shop_url, access_token=access_token)
    if stock_res["status"] != "success":
        # Ignore if already stocked? userErrors usually explain.
        pass
    else:
        print(f" Inventory stocked at location {location_id}")

    # Step 4: Set quantity
    qty_res = set_inventory_quantities(inventory_item_id, location_id, quantity, shop_url=shop_url, access_token=access_token)
    if qty_res["status"] != "success":
        return qty_res
        
    print(f" Inventory quantity set: {quantity} units")
    return {"status": "success"}


def activate_inventory_at_location(inventory_item_id: str, location_id: str, shop_url: str = None, access_token: str = None) -> Dict[str, Any]:
    """
    Connect an inventory item to a location (Required before setting quantity)
    """
    mutation = """
      mutation inventoryActivate($inventoryItemId: ID!, $locationId: ID!) {
        inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId) {
          inventoryLevel {
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
        "inventoryItemId": inventory_item_id,
        "locationId": location_id
    }
    result = execute_graphql_query(mutation, variables, shop_url=shop_url, access_token=access_token)
    return handle_graphql_response(result, "inventoryActivate")


def update_product_variant_bulk(
    product_gid: str,
    variant_gid: str,
    price: Optional[str] = None,
    sku: Optional[str] = None,
    cost: Optional[float] = None,
    weight: Optional[float] = None,
    weight_unit: str = "KILOGRAMS",
    taxable: bool = True,
    requires_shipping: bool = True,
    inventory_management: bool = True,
    shop_url: str = None,
    access_token: str = None
) -> Dict[str, Any]:
    """
    Update variant with price, SKU, cost, weight etc. using bulk update API (2024-10)
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
    
    variant_input = {
        "id": variant_gid,
        "taxable": taxable,
        "inventoryItem": {
            "requiresShipping": requires_shipping
        }
    }
    
    if price: variant_input["price"] = price
    if sku: variant_input["sku"] = sku
    if weight is not None:
        variant_input["inventoryItem"]["measurement"] = {
            "weight": {
                "value": weight,
                "unit": weight_unit
            }
        }
    
    variables = {
        "productId": product_gid,
        "variants": [variant_input]
    }
    
    print(f" DEBUG: Sending productVariantsBulkUpdate with weight={weight}, cost={cost}")
    # print(f" DEBUG: Variables JSON: {json.dumps(variables, indent=2)}")
    
    result = execute_graphql_query(mutation, variables, shop_url=shop_url, access_token=access_token)
    processed = handle_graphql_response(result, "productVariantsBulkUpdate")
    
    if processed["status"] == "error":
        return processed
    
    variant_data = processed["data"]
    
    # Update Cost (Inventory Item)
    inventory_item_id = None
    variants = variant_data.get("productVariants", [])
    if variants:
        inventory_item_id = variants[0].get("inventoryItem", {}).get("id")
        
    if inventory_item_id and cost is not None:
        print(f" Setting cost for variant: {cost}")
        cost_mutation = """
        mutation inventoryItemUpdate($id: ID!, $input: InventoryItemInput!) {
          inventoryItemUpdate(id: $id, input: $input) {
            inventoryItem { id unitCost { amount } }
            userErrors { field message }
          }
        }
        """
        execute_graphql_query(cost_mutation, {"id": inventory_item_id, "input": {"unitCost": {"amount": str(cost)}}}, shop_url=shop_url, access_token=access_token)
    
    return {
        "status": "success",
        "variants": variant_data.get("productVariants"),
        "inventory_item_id": inventory_item_id
    }


def set_product_metafields(owner_id: str, metafields_data: List[Dict[str, Any]], shop_url: str = None, access_token: str = None) -> Dict[str, Any]:
    """
    Set metafields for a product or variant using metafieldsSet mutation
    """
    mutation = """
    mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields {
          id
          namespace
          key
          value
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    
    metafields_input = []
    for mf in metafields_data:
        raw_val = mf.get("value")
        if raw_val is None or str(raw_val).strip().lower() == "none" or str(raw_val).strip() == "":
            print(f" [DEBUG] Skipping blank/None metafield: {mf['key']}")
            continue
            
        val = str(raw_val).strip()
        metafields_input.append({
            "ownerId": owner_id,
            "namespace": mf.get("namespace", "custom"),
            "key": mf["key"],
            "value": val,
            "type": mf.get("type", "single_line_text_field")
        })
    
    if not metafields_input:
        return {"status": "success", "message": "No non-blank metafields to set"}
        
    variables = {"metafields": metafields_input}
    result = execute_graphql_query(mutation, variables, shop_url=shop_url, access_token=access_token)
    return handle_graphql_response(result, "metafieldsSet")


def activate_inventory_tracking(inventory_item_id: str, shop_url: str = None, access_token: str = None) -> Dict[str, Any]:
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
    
    result = execute_graphql_query(mutation, variables, shop_url=shop_url, access_token=access_token)
    processed = handle_graphql_response(result, "inventoryItemUpdate")
    
    if processed["status"] == "success":
        return {"status": "success", "inventoryItem": processed["data"].get("inventoryItem")}
    return processed


def set_inventory_quantities(inventory_item_id: str, location_id: str, quantity: int, shop_url: str = None, access_token: str = None) -> Dict[str, Any]:
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
    
    result = execute_graphql_query(mutation, variables, shop_url=shop_url, access_token=access_token)
    return handle_graphql_response(result, "inventorySetQuantities")


def get_primary_location(shop_url: str = None, access_token: str = None) -> Optional[str]:
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
    result = execute_graphql_query(query, shop_url=shop_url, access_token=access_token)
    
    if "errors" in result:
        # Check for permission errors
        for error in result["errors"]:
            if error.get("extensions", {}).get("code") == "ACCESS_DENIED":
                print(f" [ERROR] Missing permissions to read locations. Please add 'read_locations' scope to your access token.")
                return None
        print(f" [DEBUG] get_primary_location failed. Result: {json.dumps(result, indent=2)}")
        return None
    
    if "data" not in result:
        return None
    
    locations = result.get("data", {}).get("locations", {}).get("edges", [])
    if locations:
        node = locations[0].get("node", {})
        print(f"📍 Using location: {node.get('name')} ({node.get('id')})")
        return node.get("id")
    
    return None


def execute_graphql_query(query: str, variables: Dict[str, Any] = None, shop_url: str = None, access_token: str = None) -> Dict[str, Any]:
    """
    Execute GraphQL query/mutation
    """
    shop_url = shop_url or Config.SHOPIFY_STORE_URL
    access_token = access_token or Config.SHOPIFY_ACCESS_TOKEN
    
    if not shop_url or not access_token:
        print(" [ERROR] Missing Shopify credentials in Config!")
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
    status: str = "ACTIVE",
    shop_url: str = None,
    access_token: str = None
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
    result = execute_graphql_query(mutation, {"input": product_input}, shop_url=shop_url, access_token=access_token)
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
            cost=v_data.get("cost"),
            weight=v_data.get("weight"),
            weight_unit=v_data.get("weight_unit", "KILOGRAMS"),
            taxable=v_data.get("taxable", True),
            requires_shipping=v_data.get("requires_shipping", True),
            inventory_management=True,
            shop_url=shop_url,
            access_token=access_token
        )
        
        if update_res["status"] == "success":
            print(f" Variant updated successfully")
            
            # 3. Setup Inventory (if quantity exists)
            inv_item_id = update_res.get("inventory_item_id")
            quantity = v_data.get("quantity")
            
            if inv_item_id and quantity is not None:
                inv_res = setup_inventory_for_variant(inv_item_id, int(quantity), shop_url=shop_url, access_token=access_token)
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
        if "cost" in variant: gql["cost"] = variant["cost"]
        if "weight" in variant: gql["weight"] = variant["weight"]
        if "weight_unit" in variant: gql["weight_unit"] = variant["weight_unit"]
        if "taxable" in variant: gql["taxable"] = variant["taxable"]
        if "requires_shipping" in variant: gql["requires_shipping"] = variant["requires_shipping"]
        
        options = []
        for i in range(1, 4):
            key = f"option{i}"
            if variant.get(key): options.append(str(variant[key]))
            
        if options: gql["options"] = options
        graphql_variants.append(gql)
    
    return graphql_variants
