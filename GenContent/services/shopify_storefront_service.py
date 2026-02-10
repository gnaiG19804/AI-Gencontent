import os
import requests
import json
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional

# File path for competitor domains
COMPETITOR_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "competitors.txt")

def get_competitor_domains() -> List[str]:
    """Read competitor domains from text file."""
    domains = []
    if os.path.exists(COMPETITOR_FILE):
        with open(COMPETITOR_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if not line.startswith("http"):
                        line = "https://" + line
                    domains.append(line.rstrip("/"))
    return domains

def fetch_store_products(domain: str) -> List[Dict[str, Any]]:
    """Fetch all products from a Shopify store via products.json."""
    products = []
    page = 1
    
    # Limit pages to prevent timeouts (scan first 500 products usually enough)
    MAX_PAGES = 3 
    
    while True:
        url = f"{domain}/products.json?limit=250&page={page}"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
            r = requests.get(url, headers=headers, timeout=10)
            
            if r.status_code != 200:
                # print(f"⚠️ Failed to fetch {url}: {r.status_code}")
                break
                
            data = r.json()
            items = data.get("products", [])
            if not items:
                break
                
            products.extend(items)
            page += 1
            
            if page > MAX_PAGES: 
                break
                
        except Exception as e:
            print(f"❌ Error fetching {domain}: {e}")
            break
            
    return products

def calculate_similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0.0 to 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_match(target_title: str, products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find best matching product from list."""
    if not products:
        return None
        
    best_product = None
    best_score = 0.0
    
    target_clean = target_title.lower()
    
    for p in products:
        score = calculate_similarity(target_clean, p["title"])
        if score > best_score:
            best_score = score
            best_product = p
            
    if best_product and best_score > 0.4: # Low threshold, but let caller decide
        # Get lowest price
        prices = [float(v["price"]) for v in best_product.get("variants", [])]
        price = min(prices) if prices else 0
        
        return {
            "title": best_product["title"],
            "price": price,
            "handle": best_product["handle"],
            "score": round(best_score * 100, 1),
            "image": best_product["images"][0]["src"] if best_product.get("images") else None
        }
            
    return None

def scan_competitor_file(product_title: str) -> List[Dict[str, Any]]:
    """
    Scan all competitors listed in file for a product.
    Async wrapper to be called from API.
    """
    results = []
    domains = get_competitor_domains()
    
    if not domains:
        return []

    # Clean title for better matching (remove suffix)
    clean_title = product_title.split(" – ")[0].split(" - ")[0].strip()
    
    print(f"🔍 Competitor Scan: '{clean_title}' across {len(domains)} domains...")
    
    for domain in domains:
        try:
            products = fetch_store_products(domain)
            match = find_best_match(clean_title, products)
            
            if match:
                match["domain"] = domain
                match["link"] = f"{domain}/products/{match['handle']}"
                results.append(match)
                print(f"   ✅ Match found on {domain}: {match['title']} (${match['price']})")
        except Exception as e:
            print(f"   ⚠️ Error scanning {domain}: {e}")
            
    return results
