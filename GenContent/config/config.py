import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SYSTEM_PROMPT_CONTENT = """You are a professional SEO copywriter specializing in e-commerce product descriptions.
      Task: Create compelling, SEO-optimized product content.
      
      CRITICAL REQUIREMENT:
      - ALL OUTPUT MUST BE IN {LANGUAGE}.
      - Translate any input data to {LANGUAGE}.
      - Do not include price in the description.
      - Tags should be comma-separated.
      
      Output JSON format matching the schema.
    """

    SYSTEM_PROMPT_TAXONOMY = """
      You are an expert on Shopify Taxonomy.
      The user has a store with the description: "{store_description}".

      Task: List 5-10 BROAD Keywords in ENGLISH that will likely appear in Shopify Category Names suitable for this store.

      Example: If selling "Laptop gaming", keywords are: ["Computers", "Electronics", "Laptops"].

      REQUIREMENT:
      - Return only a JSON List of strings.
      - Do not provide any additional explanation.
    """
    NameModel = "moonshotai/kimi-k2-instruct-0905"
    # NameModel = "openai/gpt-oss-120b"
    NameModel_Content = "deepseek-chat"

    API_KEY = os.getenv("GROQ_API_KEY")

    API_KEY_DEEPSEEK = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL")

    SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
    SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")

    STORE_DESCRIPTION = "cửa hàng bán các sản phẩm liên quan đến rượu"

    SERP_API_KEY = os.getenv("SERP_API_KEY")

    MAX_CONCURRENT_REQUESTS = 3

    LANGUAGE = "Vietnamese"

    FLOOR_MARGIN = 1.3  

