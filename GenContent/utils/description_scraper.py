import requests
from bs4 import BeautifulSoup
import re
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import Config
from utils.getPrice import build_search_query

SERP_KEY = Config.SERP_API_KEY

def get_competitor_links(product_name: str, vintage: str = None, limit: int = 3) -> List[str]:
    """
    Tìm kiếm sản phẩm tương tự dùng Google Search (organic) để có link trực tiếp.
    """
    query = build_search_query(product_name, vintage)
    # Thêm từ khóa để tìm trang chi tiết sản phẩm
    search_query = f"{query} product description review"
    
    params = {
        "engine": "google",
        "q": search_query,
        "api_key": SERP_KEY,
        "num": 10
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=15)
        print(f"📡 SerpAPI (Organic) Status: {r.status_code}")
        if r.status_code != 200:
            return []
        
        data = r.json()
        results = data.get("organic_results", [])
        print(f"📊 Found {len(results)} organic results from SerpAPI")
        
        links = []
        for item in results:
            link = item.get("link")
            title = item.get("title", "Unknown Title")
            
            # Bỏ qua các trang mạng xã hội hoặc kết quả không liên quan
            blacklist = ["facebook.com", "instagram.com", "twitter.com", "youtube.com", "google.com"]
            if link and not any(domain in link for domain in blacklist):
                links.append(link)
                print(f"✅ Found organic link: {link} (Title: {title})")
            
            if len(links) >= limit:
                break
            
        return links
    except Exception as e:
        print(f"❌ Error fetching competitor links: {e}")
        return []

def scrape_description(url: str) -> str:
    """
    Truy cập vào link và cố gắng lấy nội dung mô tả sản phẩm tinh vi hơn.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            print(f"   ❌ Status {r.status_code} for {url}")
            return ""
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Chiến thuật lấy description
        description = ""
        
        # 1. Thử lấy từ các Selector phổ biến của trang Wine/E-commerce
        potential_selectors = [
            ".pipProductDescription_content", # Wine.com
            ".product-description",
            ".product-details__description",
            ".view-more-text",
            ".short-description",
            "[data-test-id='product-description']",
            "#productDescription",
            "div[itemprop='description']",
            "section#description",
            "article" # Cố gắng lấy nguyên đoạn text trong bài viết
        ]
        
        for selector in potential_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator=' ', strip=True)
                if len(text) > 80: # Giảm ngưỡng xuống 80 để lấy được nhiều hơn
                    description = text
                    print(f"   🎯 Found desc via selector: {selector} ({len(text)} chars)")
                    break

        # 2. Nếu vẫn quá ngắn, thử lấy Meta Description
        if len(description) < 80:
            meta_desc = (
                soup.find("meta", attrs={"name": "description"}) or 
                soup.find("meta", attrs={"property": "og:description"}) or
                soup.find("meta", attrs={"name": "twitter:description"})
            )
            if meta_desc:
                m_text = meta_desc.get("content", "").strip()
                if len(m_text) > len(description):
                    description = m_text
                    print(f"   💡 Found desc via Meta tags ({len(m_text)} chars)")

        # 3. Fallback cuối cùng: Lấy text từ body nếu vẫn chưa có gì đáng kể
        if len(description) < 50:
            # Loại bỏ các thẻ script, style, nav, footer để làm sạch text
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            # Lấy 1 đoạn text dài ở giữa body (thường là nội dung chính)
            if len(text) > 100:
                description = text[:1200]
                print(f"   ⚠️ Fallback to raw body text ({len(description)} chars)")

        # Clean up text
        description = re.sub(r'\s+', ' ', description).strip()
        print(f"   ✅ Final Scraped length: {len(description)} chars")
        
        return description[:1200]
    except Exception as e:
        print(f"   ❌ Error scraping {url}: {e}")
        return ""

async def get_competitor_context(product_name: str, vintage: str = None) -> str:
    """
    Hàm tổng hợp: Tìm link -> Scrape -> Trả về context cho LLM.
    Sử dụng snippet từ kết quả tìm kiếm làm fallback nếu scrape thất bại.
    """
    query = build_search_query(product_name, vintage)
    search_query = f"{query} product description review"
    
    params = {
        "engine": "google",
        "q": search_query,
        "api_key": SERP_KEY,
        "num": 5
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=15)
        if r.status_code != 200:
            return ""
        
        data = r.json()
        results = data.get("organic_results", [])
        
        contexts = []
        for i, item in enumerate(results[:3]): # Lấy top 3
            link = item.get("link")
            snippet = item.get("snippet", "")
            title = item.get("title", "")
            
            print(f"🌐 Processing similarity #{i+1}: {link}")
            
            # Bỏ qua nếu là link google hoặc rác
            if not link or "google.com" in link:
                continue

            # Thử scrape nội dung chi tiết
            desc = scrape_description(link)
            
            # Logic fallback: Nếu scrape không ra gì hoặc bị chặn (403), dùng snippet
            final_content = ""
            method = ""
            if desc and len(desc) > 100:
                final_content = desc
                method = "FULL SCRAPE"
            elif snippet and len(snippet) > 20:
                final_content = f"{title}: {snippet}"
                method = "SNIPPET FALLBACK"
            
            if final_content:
                contexts.append(f"--- Competitor {i+1} ({method}) ---\n{final_content}")
                print(f"   ✅ Success using {method}")
            else:
                print(f"   ⏭️ Skipping competitor {i+1} (No content & no snippet)")
        
        if not contexts:
            return ""
        
        return "\n\n".join(contexts)
    except Exception as e:
        print(f"❌ Error in get_competitor_context: {e}")
        return ""

if __name__ == "__main__":
    # Test
    import asyncio
    async def test():
        context = await get_competitor_context("Chateau Margaux", "2018")
        print("\n=== CONTEXT FOUND ===\n")
        print(context)
    
    asyncio.run(test())
