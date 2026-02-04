from langchain_groq import ChatGroq
from langchain.messages import SystemMessage
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import Config

import os
from dotenv import load_dotenv

load_dotenv()


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








