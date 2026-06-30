import os
import asyncio
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from supabase import create_client, Client

# 初始化 Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

async def scrape_google_flights(origin, dest, dep_date, ret_date):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="zh-TW"
        )
        page = await context.new_page()
        
        # 強制繁體中文與港幣結算
        search_url = f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{dep_date}%20through%20{ret_date}&hl=zh-TW&curr=HKD"
        
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=15000)
            
            # 多重標籤保障定位
            selectors = ["li.pIav2d", "[role='listitem']", ".pI9YTe"]
            list_item_selector = None
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    list_item_selector = selector
                    break
                except:
                    continue
            
            if not list_item_selector:
                await browser.close()
                return None

            # 抓取第一筆最推薦/最平的航班
            first_flight = await page.locator(list_item_selector).first
            text_content = await first_flight.inner_text()
            
            if "HK$" in text_content or "$" in text_content:
                price_match = re.search(r'(?:HK\$|\$)\s*([\d,]+)', text_content)
                if price_match:
                    price = int(price_match.group(1).replace(',', ''))
                    is_direct = "直飛" in text_content or "Nonstop" in text_content
                    
                    await browser.close()
                    return {
                        "origin": origin, "destination": dest, "departure_date": dep_date, "return_date": ret_date,
                        "duration_days": (datetime.strptime(ret_date, "%Y-%m-%d") - datetime.strptime(dep_date, "%Y-%m-%d")).days,
                        "price": price, "is_direct": is_direct, "booking_url": search_url
                    }
        except:
            pass
            
        await browser.close()
        return None

async def main():
    # 🌟 定義全球五大洲熱門監測目的地
    destinations = [
        {"code": "NRT", "region": "東北亞"}, # 東京
        {"code": "KIX", "region": "東北亞"}, # 大阪
        {"code": "ICN", "region": "東北亞"}, # 首爾
        {"code": "BKK", "region": "東南亞"}, # 曼谷
        {"code": "SIN", "region": "東南亞"}, # 新加坡
        {"code": "LHR", "region": "歐洲"},   # 倫敦
        {"code": "CDG", "region": "歐洲"},   # 巴黎
        {"code": "JFK", "region": "美洲"},   # 紐約
        {"code": "SYD", "region": "大洋洲"}  # 悉尼
    ]
    
    origin = "HKG"
    today = datetime.today()
    
    print("🧹 正在清空資料庫中的舊機票數據...")
    try:
        supabase.table("flight_deals").delete().neq("id", 0).execute()
        print("✅ 舊數據清空成功！")
    except Exception as e:
        print(f"⚠️ 清空舊數據時出現提示（可能原本就沒資料）: {e}")

    print("🚀 開始掃描全球航線平價機票...")
    
    # 為防 GitHub Actions 超時與 Google 封鎖，我們精選未來 3 週內出發，且行程在 3-14 天內的最優組合
    # 這裡採取 staggered (交錯步長) 掃描，兼顧數據量與穩定性
    for dest in destinations:
        print(f"🔍 正在搜羅前往 【{dest['region']} - {dest['code']}】 的航班...")
        
        for start_offset in [3, 7, 10, 14, 21]: # 未來不同的出發時間點
            dep = (today + timedelta(days=start_offset)).strftime("%Y-%m-%d")
            
            for duration in [3, 5, 7, 10, 14]: # 涵蓋 3 到 14 天內最主流的行程天數
                ret = (today + timedelta(days=start_offset + duration)).strftime("%Y-%m-%d")
                
                data = await scrape_google_flights(origin, dest["code"], dep, ret)
                if data and data["price"] > 0:
                    data["region"] = dest["region"]
                    try:
                        supabase.table("flight_deals").insert(data).execute()
                        print(f"   ➔ 找到平價! {dep} ({duration}天) 價格: HKD ${data['price']} {'[直飛]' if data['is_direct'] else ''}")
                    except Exception as db_err:
                        print(f"   ❌ 寫入資料庫失敗: {db_err}")
                
                # 禮貌間隔，避免請求過於頻繁
                await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
