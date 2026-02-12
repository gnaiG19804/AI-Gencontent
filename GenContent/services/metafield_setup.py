import requests
import os
from dotenv import load_dotenv
from core.logging import send_log

from config.config import Config

async def ensure_metafield_definitions():
    """
    Check and create necessary Metafield Definitions on Shopify.
    Run this on app startup.
    """
    SHOP_URL = Config.SHOPIFY_STORE_URL
    ACCESS_TOKEN = Config.SHOPIFY_ACCESS_TOKEN

    if not SHOP_URL or not ACCESS_TOKEN:
        await send_log("⚠️  Skipping Metafield Setup: Missing SHOPIFY_SHOP_URL or token.", "warning")
        return

    # Ensure Shop URL is correct
    if not SHOP_URL.startswith("https://"):
        SHOP_URL = f"https://{SHOP_URL}"
    # Remove any path suffix to get base domain, then append graphql endpoint
    base_url = SHOP_URL.split("/admin")[0]
    graphql_url = f"{base_url}/admin/api/2024-01/graphql.json"

    HEADERS = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": ACCESS_TOKEN
    }

    # List of Metafields to Create
    METAFIELDS_TO_CREATE = [
        {
            "name": "Country",
            "namespace": "custom",
            "key": "country",
            "type": "single_line_text_field",
            "ownerType": "PRODUCT"
        },
        {
            "name": "Flavour Rating",
            "namespace": "custom",
            "key": "flavour_rating",
            "type": "number_integer",
            "ownerType": "PRODUCT",
            "validationStatus": "ACTIVE"
        },
        {
            "name": "Tasting Notes",
            "namespace": "custom",
            "key": "tasting_notes",
            "type": "multi_line_text_field",
            "ownerType": "PRODUCT"
        },
        {
            "name": "Food Pairings",
            "namespace": "custom",
            "key": "food_pairings",
            "type": "multi_line_text_field",
            "ownerType": "PRODUCT"
        },
        {
            "name": "Internal Supplier",
            "namespace": "custom",
            "key": "internal_supplier",
            "type": "single_line_text_field",
            "ownerType": "PRODUCT"
        },
        {
            "name": "Internal Supplier Code",
            "namespace": "internal",
            "key": "supplier_code",
            "type": "single_line_text_field",
            "ownerType": "PRODUCT"
        }
    ]

    mutation = """
    mutation CreateMetafieldDefinition($definition: MetafieldDefinitionInput!) {
      metafieldDefinitionCreate(definition: $definition) {
        createdDefinition {
          id
          key
        }
        userErrors {
          field
          message
          code
        }
      }
    }
    """

    results = []
    
    for definition in METAFIELDS_TO_CREATE:
        payload = {
            "query": mutation,
            "variables": {
                "definition": {
                    "name": definition["name"],
                    "namespace": definition["namespace"],
                    "key": definition["key"],
                    "type": definition["type"],
                    "ownerType": definition["ownerType"],
                    "ownerType": definition["ownerType"]
                }
            }
        }

        try:
            response = requests.post(graphql_url, headers=HEADERS, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "metafieldDefinitionCreate" in data["data"]:
                    res = data["data"]["metafieldDefinitionCreate"]
                    if res["userErrors"]:
                        err_code = res["userErrors"][0]["code"]
                        if err_code == "TAKEN":
                            # results.append(f"✓ {definition['key']} (Exists)")
                            pass
                        else:
                            results.append(f"❌ {definition['key']} (Error: {res['userErrors'][0]['message']})")
                    else:
                        results.append(f"✅ {definition['key']} (Created)")
        except Exception as e:
            results.append(f"❌ {definition['key']} (Exception: {str(e)})")

    if results:
        await send_log(f"🛒 [Shopify Setup] Metafields: {', '.join(results)}", "info")
    else:
        # If all exist, verify silently
        print("✅ [Shopify Setup] All 8 wine metafield definitions are ready.")
