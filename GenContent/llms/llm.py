from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from langchain.messages import SystemMessage
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import Config

import os
from dotenv import load_dotenv

load_dotenv()


if not Config.API_KEY_DEEPSEEK:
    print("❌ [ERROR] DEEPSEEK_API_KEY is missing in .env or Config.")
    print("   Please add DEEPSEEK_API_KEY=sk-xxxxxxxx to your .env file.")
    print("   And verify you have: `from dotenv import load_dotenv; load_dotenv()` in config.py")
    sys.exit(1)

# llm_genContent = ChatOpenAI(
#     model=Config.NameModel_Content,
#     openai_api_key=Config.API_KEY_DEEPSEEK,
#     openai_api_base=Config.DEEPSEEK_BASE_URL
# )

llm_genContent = ChatGroq(
  model=Config.NameModel,
  api_key=Config.API_KEY
)

llm_taxonomy = ChatGroq(
  model=Config.NameModel,
  api_key=Config.API_KEY
)

llm_reviewer = ChatGroq(
  model=Config.NameModel,
  api_key=Config.API_KEY
)
