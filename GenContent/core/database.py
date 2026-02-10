from tortoise.contrib.fastapi import register_tortoise
from fastapi import FastAPI
from config.config import Config

def init_db(app: FastAPI):
    """
    Initialize Tortoise ORM with the FastAPI app.
    Using 'aerich' compatible config structure if migration needed later,
    but for now simple register_tortoise.
    """
    if not Config.DATABASE_URL:
        print("⚠️ DATABASE_URL not found in env. Database logging will be disabled.")
        return

    # Fix for Neon/Postgres scheme and SSL
    from urllib.parse import urlparse, parse_qs
    
    # Clean scheme for consistent parsing
    clean_url = Config.DATABASE_URL.replace("postgresql://", "postgres://")
    parsed = urlparse(clean_url)
    
    # Check for SSL requirement in query params or default for Neon
    ssl_mode = "require"
    if parsed.query:
        params = parse_qs(parsed.query)
        if 'sslmode' in params:
            ssl_value = params['sslmode'][0]
            if ssl_value == 'disable':
                ssl_mode = False
            elif ssl_value == 'allow':
                ssl_mode = False # asyncpg doesn't support 'allow' well, use False or 'require'
                
    # Construct config dictionary for Tortoise
    config = {
        "connections": {
            "default": {
                "engine": "tortoise.backends.asyncpg",
                "credentials": {
                    "database": parsed.path.lstrip("/"),
                    "host": parsed.hostname,
                    "password": parsed.password,
                    "port": parsed.port or 5432,
                    "user": parsed.username,
                    "ssl": ssl_mode 
                }
            }
        },
        "apps": {
            "models": {
                "models": ["models.db_models"],
                "default_connection": "default",
            }
        },
    }

    try:
        register_tortoise(
            app,
            config=config,
            # generate_schemas=True, # Often flaky with asyncpg/manual config
            add_exception_handlers=True,
        )
        
        # Explicitly generate schemas on startup to be sure
        @app.on_event("startup")
        async def make_schemas():
            print("📦 Generating DB Schemas...")
            from tortoise import Tortoise
            await Tortoise.generate_schemas()
            print("✅ DB Schemas Generated!")
            
            # DEBUG: Check what DB we are actually connected to
            conn = Tortoise.get_connection("default")
            print(f"🔌 Connected to DB: {conn.database}")
            
            # DEBUG: List tables
            val = await conn.execute_query("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
            print(f"📊 Tables found in DB: {val[1]}")
            
    except Exception as e:
        print(f"⚠️ Failed to init DB: {e}")
