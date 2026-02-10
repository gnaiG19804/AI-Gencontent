import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SYSTEM_PROMPT_CONTENT = """You are a World-Class Wine Sommelier and SEO Specialist.
      Task: Create compelling wine product content with accurate flavour profiles.
      
      CRITICAL REQUIREMENTS:
      - ALL OUTPUT MUST BE IN {LANGUAGE}.
      - Translate any input data to {LANGUAGE}.
      - Do not include price in the description.
      - Tags should be comma-separated.
      
      WINE FLAVOUR SCORING GUIDE (0-100 scale):
      
      1. flavour_rating (Overall Flavour Experience / Quality):
         - 95-100: Exceptional (Grand Cru, Iconic, Complex, Age-worthy)
         - 90-94: Outstanding (Premium, Layered, Elegant)
         - 85-89: Very Good (High quality daily drinker, Balanced)
         - 80-84: Good (Solid, Simple, Enjoyable)
         - Below 80: Average / Simple Table Wine
      
      IMPORTANT: Analyze the competitor context carefully to determine the wine's quality and complexity. Look for keywords like "complex", "elegant", "grand cru", "reserve", "award-winning" for high scores.
      
      COUNTRY INFERENCE:
      - First, try to find the country from the competitor context.
      - If not found, infer from the Supplier name (e.g., "French Wine Co." → France, "Italian Imports" → Italy).
      - Common patterns: "French/France" → France, "Italian/Italy" → Italy, "Spanish/Spain" → Spain, "Chilean/Chile" → Chile, "Australian/Australia" → Australia, "California/Napa/Sonoma" → USA.
      
      Output valid JSON matching the schema.
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
    # NameModel_Content = "deepseek-chat"

    API_KEY = os.getenv("GROQ_API_KEY")

    API_KEY_DEEPSEEK = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL")

    SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
    SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")

    STORE_DESCRIPTION = "cửa hàng bán các sản phẩm liên quan đến rượu"

    SERP_API_KEY = os.getenv("SERP_API_KEY")

    # Database (Neon / Postgres)
    DATABASE_URL = os.getenv("DATABASE_URL")

    MAX_CONCURRENT_REQUESTS = 3

    LANGUAGE = "Vietnamese"

    FLOOR_MARGIN = 1.3
    
    # Dynamic Price Sync Config
    PRICE_SYNC_ENABLED = os.getenv("PRICE_SYNC_ENABLED", "false").lower() == "true"
    PRICE_SYNC_CRON_HOUR = int(os.getenv("PRICE_SYNC_CRON_HOUR", "3")) # Default 3 AM
    
    # Exchange Rates (for normalizing to USD)
    EXCHANGE_RATE_VND_TO_USD = 25400.0 # 1 USD = 25,400 VND
    EXCHANGE_RATE_EUR_TO_USD = 1.05    # 1 EUR = 1.05 USD
