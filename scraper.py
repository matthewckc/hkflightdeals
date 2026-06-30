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

async def scrape_google_flights(page, origin, dest, region, dep_date, ret_date, price_ceiling):
    search_url = f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{origin}%20on%20{dep_date}%20through%20{ret_date}&hl=zh-TW&curr=HKD"
    
    try:
        await page.goto(search_url, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(1500)
        
        selectors = ["li.pIav2d", "[role='listitem']", ".pI9YTe"]
        list_item_selector = None
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=4000)
                list_item_selector = selector
                break
            except:
                continue
        
        if not list_item_selector:
            return None

        first_flight = page.locator(list_item_selector).first
        text_content = await first_flight.inner_text()
        
        page_text = await page.inner_text("body")
        has_low_badge = any(keyword in page_text for keyword in ["低於正常", "偏低", "低廉", "Less than usual", "Low price"])
        
        if "HK$" in text_content or "$" in text_content:
            price_match = re.search(r'(?:HK\$|\$)\s*([\d,]+)', text_content)
            if price_match:
                price = int(price_match.group(1).replace(',', ''))
                is_direct = "直飛" in text_content or "Nonstop" in text_content
                
                if price <= price_ceiling or has_low_badge:
                    return {
                        "origin": origin, "destination": dest, "region": region,
                        "departure_date": dep_date, "return_date": ret_date,
                        "duration_days": (datetime.strptime(ret_date, "%Y-%m-%d") - datetime.strptime(dep_date, "%Y-%m-%d")).days,
                        "price": price, "is_direct": is_direct, "booking_url": search_url
                    }
    except Exception as e:
        print(f"   ❌ 監測異常: {str(e)}")
    return None

async def main():
    # ... [all_destinations 陣列保持不變] ...
    all_destinations = [
        # (您的目的地列表)
        {"code": "NRT", "name": "東京成田", "region": "東北亞", "ceil": 1800},
        {"code": "HND", "name": "東京羽田", "region": "東北亞", "ceil": 2200},
        {"code": "KIX", "name": "大阪", "region": "東北亞", "ceil": 1800},
        {"code": "OKA", "name": "沖繩", "region": "東北亞", "ceil": 1500},
        {"code": "HIJ", "name": "廣島", "region": "東北亞", "ceil": 2200},
        {"code": "TAK", "name": "高松", "region": "東北亞", "ceil": 2200},
        {"code": "NGO", "name": "名古屋", "region": "東北亞", "ceil": 2200},
        {"code": "FUK", "name": "福岡", "region": "東北亞", "ceil": 2200},
        {"code": "SDJ", "name": "仙台", "region": "東北亞", "ceil": 2200},
        {"code": "CTS", "name": "札幌", "region": "東北亞", "ceil": 2500},
        # ... (其餘地區設定)
    ]

    weekday = datetime.today().weekday()
    weekday_map = {0: ["台灣", "中國內地"], 1: ["東北亞"], 2: ["東南亞", "中東與其他"], 3: ["歐洲"], 4: ["大洋洲", "美洲"], 5: [], 6: []}
    target_regions = weekday_map.get(weekday, [])
    
    if weekday == 6:
        supabase.table("flight_deals").delete().neq("id", 0).execute()

    destinations = [d for d in all_destinations if d["region"] in target_regions]
    today = datetime.today()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0...", locale="zh-TW")
        page = await context.new_page()

        for dest in destinations:
            print(f"🛫 正在探測 【{dest['name']}】 未來 90 天行程...")
            
            # 💡 核心變更：每隔 7 天掃描一個出發日期，範圍 90 天
            for week_offset in range(0, 90, 7):
                dep_date = (today + timedelta(days=week_offset)).strftime("%Y-%m-%d")
                
                # 掃描幾個經典旅遊長度，避免過度頻繁請求
                for duration in [3, 5, 7, 10, 14]:
                    ret_date = (today + timedelta(days=week_offset + duration)).strftime("%Y-%m-%d")
                    
                    data = await scrape_google_flights(page, "HKG", dest["code"], dest["region"], dep_date, ret_date, dest["ceil"])
                    
                    if data:
                        try:
                            supabase.table("flight_deals").insert(data).execute()
                            print(f"   ➔ 🎉 找到平價: {dest['name']} | {dep_date} | HKD ${data['price']}")
                        except Exception as e:
                            print(f"   ❌ DB寫入失敗: {e}")
                    
                    # 💡 為了應付長週期掃描，這裡增加冷卻時間
                    await asyncio.sleep(2.5)
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
