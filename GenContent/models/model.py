from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any


class ContextRequest(BaseModel):
    product_name: str
    vintage: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None # Trường thêm để n8n truyền ID, row_index...

    @model_validator(mode='before')
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if 'Product_name' in data and 'product_name' not in data:
                data['product_name'] = data.pop('Product_name')
            if 'Vintage' in data and 'vintage' not in data:
                data['vintage'] = data.pop('Vintage')
            # Nếu truyền cả cục product vào, metadata sẽ chứa các thông tin còn lại
            if 'metadata' not in data:
                 data['metadata'] = {k: v for k, v in data.items() if k not in ['product_name', 'vintage', 'Product_name', 'Vintage']}
        return data

class BatchContextRequest(BaseModel):
    items: List[ContextRequest]

class PricingRequest(BaseModel):
    product_name: str
    vintage: Optional[Any] = None
    cost_per_item: float
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if 'Product_name' in data and 'product_name' not in data:
                data['product_name'] = data.pop('Product_name')
            if 'Vintage' in data and 'vintage' not in data:
                data['vintage'] = data.pop('Vintage')
            if 'metadata' not in data:
                 data['metadata'] = {k: v for k, v in data.items() if k not in ['product_name', 'vintage', 'cost_per_item', 'Product_name', 'Vintage']}
        return data

class BatchPricingRequest(BaseModel):
    items: List[PricingRequest]

class EnrichRequest(BaseModel):
    product_name: str
    vintage: Optional[Any] = None
    cost_per_item: float
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if 'Product_name' in data and 'product_name' not in data:
                data['product_name'] = data.pop('Product_name')
            if 'Vintage' in data and 'vintage' not in data:
                data['vintage'] = data.pop('Vintage')
            if 'metadata' not in data:
                 data['metadata'] = {k: v for k, v in data.items() if k not in ['product_name', 'vintage', 'cost_per_item', 'Product_name', 'Vintage']}
        return data

class BatchEnrichRequest(BaseModel):
    items: List[EnrichRequest]

class GenerateSingleRequest(BaseModel):
    product_data: Dict[str, Any]
    competitor_context: Optional[str] = ""
    metadata: Optional[Dict[str, Any]] = None # Passthrough metadata

class BatchGenerateRequest(BaseModel):
    items: List[GenerateSingleRequest]

class ShopifyPushItem(BaseModel):
    product_data: Dict[str, Any]
    generated_content: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    @classmethod
    def handle_flat_structure(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Nếu truyền cục data phẳng (flat) từ n8n, tự động tách ra đúng cấu trúc
            if 'product_data' not in data and 'generated_content' not in data:
                # Các trường thuộc về Content
                gen_keys = {
                    'title', 'short_description', 'long_description', 
                    'approved_short_description', 'approved_long_description', 
                    'tags', 'product_type', 'status', 'country', 
                    'dry_sweet_rating', 'light_bold_rating', 'soft_acidic_rating', 
                    'smooth_tannic_rating', 'tasting_notes', 'food_pairings'
                }
                
                # Case-insensitive mapping for flat data
                gen_content = {}
                prod_data = {}
                gen_keys_lower = {k.lower() for k in gen_keys}
                
                for k, v in data.items():
                    if k == 'metadata': continue
                    if k.lower() in gen_keys_lower:
                        gen_content[k.lower()] = v
                    else:
                        prod_data[k] = v
                
                return {
                    "product_data": prod_data,
                    "generated_content": gen_content,
                    "metadata": data.get('metadata')
                }
        return data

class BatchPushRequest(BaseModel):
    items: List[ShopifyPushItem]

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
