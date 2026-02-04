from pydantic import BaseModel, Field
from typing import Optional, List


class GenerationMetadata(BaseModel):
    model_name: str = Field(description="Name of the LLM used")
    timestamp: str = Field(description="ISO 8601 timestamp of generation")
    retry_count: int = Field(default=0, description="Number of retries occurred")
    prompt_hash: Optional[str] = Field(default=None, description="Hash of the used system prompt")

class ShortDescriptionOutput(BaseModel):

    short_description: str = Field(description="A concise, catchy summary of the product (max 2 sentences)")

class LongDescriptionOutput(BaseModel):
    long_description: str = Field(description="Detailed product description including features and benefits (HTML supported)")

class AIContentEngineOutput(BaseModel):
    title: str = Field(description="SEO-optimized Product Title")
    approved_short_description: str = Field(description="Verified short description")
    approved_long_description: str = Field(description="Verified long description")
    tags: str = Field(description="Comma-separated tags")
    product_type: str = Field(description="Selected Shopify Product Category")
    metadata: GenerationMetadata = Field(description="Generation metadata")

ShopifyProduct = AIContentEngineOutput
