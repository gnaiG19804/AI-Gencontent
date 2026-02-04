import requests
import json
import sys
import os
from pathlib import Path
from typing import List, Optional
import hashlib

# Fix import path để có thể chạy từ bất kỳ đâu
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage
from config.config import Config
from llms.llm import llm_taxonomy

# File cache path
CACHE_FILE = Path(__file__).parent.parent / "cached_categories.json"


def get_store_description_hash(store_description: str) -> str:
    """
    Tạo hash từ store description để so sánh
    """
    return hashlib.md5(store_description.encode()).hexdigest()


def load_cached_categories() -> Optional[List[str]]:
    """
    Load categories từ file cache nếu STORE_DESCRIPTION không đổi
    """
    if not CACHE_FILE.exists():
        print("📂 Chưa có file cache categories")
        return None
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        current_hash = get_store_description_hash(Config.STORE_DESCRIPTION or "")
        cached_hash = cache_data.get("store_description_hash")
        
        if current_hash == cached_hash:
            categories = cache_data.get("categories", [])
            print(f"✅ Load {len(categories)} categories từ cache (STORE_DESCRIPTION không đổi)")
            return categories
        else:
            print("⚠️  STORE_DESCRIPTION đã thay đổi, cần refresh categories")
            return None
            
    except Exception as e:
        print(f"❌ Lỗi đọc cache: {e}")
        return None


def save_categories_to_cache(categories: List[str]):
    """
    Lưu categories vào file cache kèm hash của STORE_DESCRIPTION
    """
    try:
        cache_data = {
            "store_description": Config.STORE_DESCRIPTION,
            "store_description_hash": get_store_description_hash(Config.STORE_DESCRIPTION or ""),
            "categories": categories,
            "timestamp": str(Path(__file__).stat().st_mtime)
        }
        
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Đã lưu {len(categories)} categories vào cache file: {CACHE_FILE.name}")
        
    except Exception as e:
        print(f"❌ Lỗi lưu cache: {e}")


def get_filtering_keywords(llm, store_description):
    """
    Dùng LLM để phân tích mô tả cửa hàng và đưa ra các từ khóa tiếng Anh
    để lọc danh mục Shopify.
    """
    print(f"🤖 AI đang suy nghĩ từ khóa cho: '{store_description}'...")
    
    prompt = Config.SYSTEM_PROMPT_TAXONOMY.format(store_description=store_description)
    
    try:
        messages = [HumanMessage(content=prompt)]
        response = llm.invoke(messages)
        content = response.content.strip()
        
        start = content.find('[')
        end = content.rfind(']') + 1
        if start != -1 and end > start:
            keywords = json.loads(content[start:end])
            print(f"✅ AI đề xuất từ khóa lọc: {keywords}")
            return keywords
        else:
            print("⚠️  LLM không trả về JSON đúng format, dùng keywords mặc định")
            return ["Apparel", "Clothing", "Fashion"] 
            
    except Exception as e:
        print(f"❌ Lỗi AI sinh từ khóa: {e}")
        return ["Apparel", "Clothing", "Fashion"]


def build_niche_taxonomy(keywords):
    """
    Tải Shopify taxonomy và lọc theo keywords
    """
    # Shopify taxonomy sử dụng versioned releases (2024-10, 2024-07...)
    # URL mới: trong thư mục dist/
    url = "https://raw.githubusercontent.com/Shopify/product-taxonomy/main/dist/en/categories.json"
    
    print("📥 Đang tải và lọc danh mục Shopify...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse JSON
        text = response.text.strip()
        data = json.loads(text)
        
        # Shopify taxonomy format: {version, verticals: [{categories: [...]}]}
        if "verticals" not in data:
            print(f"⚠️  Không tìm thấy 'verticals' key. Keys: {list(data.keys())}")
            return []
        
        # Danh sách verticals cần bỏ qua (không liên quan đến clothing/fashion)
        exclude_verticals = [
            "Animals & Pet Supplies",
            "Business & Industrial", 
            "Hardware",
            "Vehicles & Parts",
            "Mature"
        ]
        
        # Extract all categories from relevant verticals only
        all_categories = []
        for vertical in data["verticals"]:
            vertical_name = vertical.get("name", "Unknown")
            
            # Skip excluded verticals
            if vertical_name in exclude_verticals:
                continue
                
            categories_in_vertical = vertical.get("categories", [])
            all_categories.extend(categories_in_vertical)
        
        print(f"Tìm thấy {len(all_categories)} categories từ {len(data['verticals']) - len([v for v in data['verticals'] if v.get('name') in exclude_verticals])} verticals (đã loại bỏ {len([v for v in data['verticals'] if v.get('name') in exclude_verticals])} verticals không liên quan)")
        
        # Filter by keywords với scoring để lấy top categories
        category_scores = []  # List of (name, id, score, matched_keywords)
        
        for cat in all_categories:
            name = cat.get("name", "")
            cat_id = cat.get("id", "")  # Extract category ID
            if not name:
                continue
            
            # Tính điểm relevance
            score = 0
            matched_keywords = []
            
            for keyword in keywords:
                if len(keyword) < 10:
                    # Exact word match cho keyword ngắn
                    if keyword.lower() in name.lower().split():
                        score += 2  # Điểm cao hơn cho exact match
                        matched_keywords.append(keyword)
                else:
                    # Substring match cho keyword dài
                    if keyword.lower() in name.lower():
                        score += 1
                        matched_keywords.append(keyword)
            
            # Bonus điểm nếu match nhiều keywords
            if len(matched_keywords) > 1:
                score += len(matched_keywords)
            
            # Ưu tiên categories ngắn gọn (thường là parent categories)
            if score > 0 and len(name.split()) <= 3:
                score += 0.5
            
            if score > 0:
                category_scores.append({
                    "name": name,
                    "id": cat_id,
                    "score": score,
                    "matched_keywords": matched_keywords
                })
        
        # Sort theo score giảm dần và lấy top 25
        category_scores.sort(key=lambda x: x["score"], reverse=True)
        top_categories = category_scores[:25]  # Chỉ lấy top 25 categories
        
        # Return list of dicts with name and id
        filtered_list = [{"name": cat["name"], "id": cat["id"]} for cat in top_categories]
        
        print(f"✅ Đã lọc xong! Từ {len(all_categories)} danh mục -> Còn {len(category_scores)} danh mục match -> Lấy top {len(filtered_list)} danh mục phù hợp nhất.")
        
        # Debug: Show top 5 với scores
        if top_categories:
            print("\n🏆 Top 5 categories (với điểm):")
            for i, cat in enumerate(top_categories[:5], 1):
                print(f"  {i}. {cat['name']} (ID: {cat['id']}, score: {cat['score']}, matched: {', '.join(cat['matched_keywords'])})")
        
        return filtered_list
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Lỗi tải từ GitHub: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi parse JSON: {e}")
        print(f"Response preview: {response.text[:200]}...")
        return []
    except Exception as e:
        print(f"❌ Lỗi tải taxonomy: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_or_refresh_categories() -> List[str]:
    """
    Main function: Load từ cache hoặc refresh nếu cần
    """
    # Bước 1: Thử load từ cache
    cached = load_cached_categories()
    if cached:
        return cached
    
    # Bước 2: Cache miss hoặc STORE_DESCRIPTION đổi -> Refresh
    print("\n🔄 Refreshing categories từ Shopify taxonomy...")
    
    if not Config.STORE_DESCRIPTION:
        print("⚠️  Chưa có STORE_DESCRIPTION, dùng default")
        default_categories = ["Apparel & Accessories", "Clothing", "Clothing Tops"]
        save_categories_to_cache(default_categories)
        return default_categories
    
    # LLM phân tích → keywords
    keywords = get_filtering_keywords(llm_taxonomy, Config.STORE_DESCRIPTION)
    
    # Filter taxonomy
    categories = build_niche_taxonomy(keywords)
    
    if not categories:
        print("⚠️  Không lấy được categories, dùng default")
        categories = ["Apparel & Accessories", "Clothing"]
    
    # Lưu vào cache
    save_categories_to_cache(categories)
    
    return categories


if __name__ == "__main__":
    # Test script
    print("=" * 60)
    print("TAXONOMY MANAGER - FILE CACHE TEST")
    print("=" * 60)
    
    categories = get_or_refresh_categories()
    
    print(f"\n📦 Kết quả: {len(categories)} categories")
    print("\nTop 10:")
    for i, cat in enumerate(categories[:10], 1):
        print(f"  {i}. {cat}")
    
    print(f"\n💾 Cache file location: {CACHE_FILE}")