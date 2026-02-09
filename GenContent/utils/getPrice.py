import requests
import statistics
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import Config

SERP_KEY = Config.SERP_API_KEY


# ---------- helpers ----------

def parse_price(text):
    if not text:
        return None
    m = re.search(r"\d+\.?\d*", text.replace(",", ""))
    return float(m.group()) if m else None


def clean_prices(prices):
    """trim 15–85 percentile to remove outliers"""
    if len(prices) < 5: 
        return prices

    prices = sorted(prices)

    lo = int(len(prices) * 0.15)
    hi = int(len(prices) * 0.85)

    return prices[lo:hi]


def build_search_query(product_name, vintage=None):
    """
    Xây dựng query tìm kiếm thông minh dựa trên tên sản phẩm và vintage.
    
    Args:
        product_name: Tên sản phẩm
        vintage: Năm sản xuất hoặc tuổi (ví dụ: "2018", "12Y")
    
    Returns:
        Query string đã được tối ưu
    """
    query_parts = [product_name]
    
    if vintage:
        vintage_str = str(vintage).strip()
        
        # Phát hiện loại sản phẩm dựa trên vintage
        if re.match(r'^\d{4}$', vintage_str):  # Năm 4 chữ số -> rượu vang
            query_parts.append(vintage_str)
            query_parts.append("wine")
        elif re.match(r'^\d+Y$', vintage_str, re.IGNORECASE):  # XXY -> whiskey
            # Chuyển "12Y" thành "12 year"
            years = re.match(r'^(\d+)Y$', vintage_str, re.IGNORECASE).group(1)
            query_parts.append(f"{years} year")
            query_parts.append("whiskey")
        else:
            # Trường hợp khác, chỉ thêm vintage
            query_parts.append(vintage_str)
    
    return " ".join(query_parts)


def calculate_price(competitor_median, cost_per_item, floor_margin=None):
    """
    Tính giá bán dựa trên giá đối thủ và chi phí sản phẩm.
    
    Args:
        competitor_median: Giá trung vị của đối thủ
        cost_per_item: Chi phí sản phẩm
        floor_margin: Tỷ lệ lợi nhuận tối thiểu (mặc định lấy từ Config)
    
    Returns:
        dict với recommended_price, strategy, và thông tin chi tiết
    """
    if floor_margin is None:
        floor_margin = Config.FLOOR_MARGIN
    
    # Option 1: Giá cạnh tranh (thấp hơn đối thủ 1%)
    competitive_price = competitor_median * 0.99
    
    # Option 2: Giá sàn (đảm bảo lợi nhuận tối thiểu)
    floor_price = cost_per_item * floor_margin
    
    # Chọn giá cao nhất trong 2 options
    final_price = max(competitive_price, floor_price)
    
    # Xác định strategy
    if final_price == competitive_price:
        strategy = "competitive"
        reason = f"Giảm 1% so với đối thủ (${competitor_median:.2f})"
    else:
        strategy = "floor"
        reason = f"Giữ lợi nhuận tối thiểu {(floor_margin-1)*100:.0f}%"
    
    return {
        "recommended_price": round(final_price, 2),
        "strategy": strategy,
        "reason": reason,
        "competitive_price": round(competitive_price, 2),
        "floor_price": round(floor_price, 2),
        "margin_percent": round(((final_price - cost_per_item) / cost_per_item) * 100, 1)
    }


def find_most_common_price(prices, bin_size=5):
    """
    Tìm giá phổ biến nhất bằng cách nhóm giá vào các khoảng.
    
    Args:
        prices: Danh sách giá
        bin_size: Kích thước khoảng giá (mặc định $5)
    
    Returns:
        Giá phổ biến nhất (trung bình của khoảng có nhiều giá nhất)
    """
    if not prices:
        return None
    
    if len(prices) == 1:
        return prices[0]
    
    # Nhóm giá vào các khoảng (bins)
    from collections import defaultdict
    bins = defaultdict(list)
    
    for price in prices:
        # Tìm bin key (làm tròn xuống bội số của bin_size)
        bin_key = (price // bin_size) * bin_size
        bins[bin_key].append(price)
    
    # Tìm bin có nhiều giá nhất
    most_common_bin = max(bins.items(), key=lambda x: len(x[1]))
    bin_prices = most_common_bin[1]
    
    # Trả về trung bình của bin đó
    mode_price = sum(bin_prices) / len(bin_prices)
    
    return round(mode_price, 2)

def get_real_offers(api_url):

    try:
        # Append API key if not present
        if "api_key=" not in api_url:
             api_url += f"&api_key={SERP_KEY}"

        r = requests.get(api_url, timeout=10)
        
        if r.status_code != 200:
            print(f"   ⚠️ API Status: {r.status_code}")
            return

        data = r.json()
        
        # Check for error in data
        if "error" in data:
             print(f"   ⚠️ API Error: {data['error']}")
             return

        # Attempt to find sellers in various locations
        sellers = []
        
        # 1. Try inside 'product_results' (common for immersive product api)
        if "product_results" in data:
            pr = data["product_results"]
            sellers = pr.get("online_sellers", [])
            if not sellers:
                sellers = pr.get("prices", [])
            if not sellers: # Check for 'stores'
                sellers = pr.get("stores", [])
        
        # 2. Try top level (fallback)
        if not sellers:
             sellers = data.get("online_sellers", [])
        
        if not sellers:
             sellers = data.get("prices", [])

        if not sellers:
            print(f"   ⚠️ no seller offers found. Keys: {list(data.keys())}")
            if "product_results" in data:
                 print(f"   Keys in product_results: {list(data['product_results'].keys())}")
            return

        for s in sellers:
             # Try different key names for link/price
             link = s.get("link", s.get("direct_link"))
             print(f"   🏬 SELLER: {s.get('name')}")
             print(f"   💵 PRICE: {s.get('price')}")
             print(f"   🔗 LINK : {link}")
             print()

    except Exception as e:
        print("   ❌ offer fetch failed:", e)


# ---------- main ----------

def google_shopping_prices(product_name, vintage=None, raw=False):
    
    # Build optimized query
    query = build_search_query(product_name, vintage)
    print(f"🔍 OPTIMIZED QUERY: '{query}'\n")

    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERP_KEY,
        "num": 20
    }

    r = requests.get(
        "https://serpapi.com/search",
        params=params,
        timeout=20
    )

    if r.status_code != 200:
        print("❌ API ERROR:", r.status_code)
        return []

    data = r.json()

    if "error" in data:
        print("❌ SERP ERROR:", data["error"])
        return []

    results = data.get("shopping_results", [])

    print(f"\n🔎 QUERY: {query}")
    print(f"FOUND {len(results)} shopping results\n")

    prices = []

    for item in results:

        raw_price = item.get("price")
        source = item.get("source", "unknown")

        p = parse_price(raw_price)

        if not p:
            continue

        prices.append(p)
        
        link = item.get("product_link", item.get("link", "no link"))
        print(f"💰 {p} | {source} | 🔗 {link}")

        # Stop at 10 if raw mode is on
        if raw and len(prices) >= 10:
            break

        # OPTIONAL deep verify
        api2 = item.get("serpapi_immersive_product_api")
        if api2:
            print("   🔎 offers:")
            get_real_offers(api2)

    # -------- after loop --------

    print("\n📦 RAW COUNT:", len(prices))

    if raw:
        return prices

    clean = clean_prices(prices)

    print("🧹 CLEAN COUNT:", len(clean))

    if clean:
        print("📈 MEDIAN:", statistics.median(clean))
    else:
        print("⚠️ no prices after clean")

    return clean


# ---------- run ----------

if __name__ == "__main__":
    import csv
    
    # Read test data from CSV
    csv_path = Path(__file__).parent.parent / "test.csv"
    
    print("=" * 80)
    print("TESTING WITH DATA FROM test.csv")
    print("=" * 80 + "\n")
    
    if csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for i, row in enumerate(reader):
                if i >= 2:  # Test with first 2 products only
                    break
                    
                product_name = row.get('Product_name', '')
                vintage = row.get('Vintage', '')
                cost_per_item = float(row.get('cost_per_item', 0))
                
                print(f"\n{'='*80}")
                print(f"TEST #{i+1}: {product_name}")
                print(f"{'='*80}")
                print(f"💵 COST: ${cost_per_item:.2f}")
                
                prices = google_shopping_prices(product_name, vintage)
                print(f"\n✅ FINAL PRICES: {prices}")
                print(f"📊 COUNT: {len(prices)} prices found")
                
                if prices:
                    # Find most common price
                    mode_price = find_most_common_price(prices)
                    median = statistics.median(prices)
                    
                    print(f"💰 COMPETITOR MODE (phổ biến): ${mode_price:.2f}")
                    print(f"📊 COMPETITOR MEDIAN (trung vị): ${median:.2f}")
                    
                    # Calculate recommended price using MODE
                    pricing = calculate_price(mode_price, cost_per_item)
                    
                    print(f"\n{'─'*80}")
                    print(f"🎯 RECOMMENDED PRICE: ${pricing['recommended_price']:.2f}")
                    print(f"📊 STRATEGY: {pricing['strategy'].upper()}")
                    print(f"📝 REASON: {pricing['reason']}")
                    print(f"💹 MARGIN: {pricing['margin_percent']}%")
                    print(f"{'─'*80}")
                    print(f"   Competitive (99% mode): ${pricing['competitive_price']:.2f}")

                    print(f"   Floor (cost × 1.3): ${pricing['floor_price']:.2f}")
                else:
                    print("⚠️ Không tìm được giá đối thủ, không thể tính giá đề xuất")
    else:
        print(f"⚠️ CSV file not found: {csv_path}")
        print("\nFalling back to manual test...")
        prices = google_shopping_prices("Chateau Red Reserve", "2018")
        print("\nFINAL PRICES:", prices)

