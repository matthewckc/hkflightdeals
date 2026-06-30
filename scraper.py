import os
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from supabase import create_client, Client

# 連接雲端 Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

async def scrape_google_flights(origin, dest, dep_date, ret_date):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 構造 Google Flights 的直接搜尋 URL 
        url = f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{origin}%20on%20{dep_date}%20through%20{ret_date}"
        await page.goto(url)
        
        try:
            # 等待航班卡片載入 (Google Flights 的常規區塊)
            await page.wait_for_selector('.pI9YTe', timeout=8000)
            first_flight = await page.query_selector('.pI9YTe')
            
            if first_flight:
                # 抓取價格
                price_text = await first_flight.query_selector('.YMlAec')
                price = int(''.join(filter(str.isdigit, await price_text.inner_text()))) if price_text else 0
                
                # 抓取是否直飛
                stops_text = await first_flight.query_selector('.Efby9d')
                is_direct = "直飛" in (await stops_text.inner_text()) if stops_text else False
                
                await browser.close()
                return {
                    "origin": origin, "destination": dest, "departure_date": dep_date, "return_date": ret_date,
                    "duration_days": (datetime.strptime(ret_date, "%Y-%m-%d") - datetime.strptime(dep_date, "%Y-%m-%d")).days,
                    "price": price, "is_direct": is_direct, "booking_url": url
                }
        except:
            pass
        await browser.close()
        return None

async def main():
    # 定義你想監控的熱門目的地
    destinations = [
        {"code": "NRT", "region": "東北亞"},
        {"code": "KIX", "region": "東北亞"},
        {"code": "BKK", "region": "東南亞"},
        {"code": "LHR", "region": "歐洲"}
    ]
    origin = "HKG" # 出發地設定
    today = datetime.today()

    for dest in destinations:
        # 搜尋未來 1 到 15 天內出發的組合
        for start_offset in range(1, 15): 
            dep = (today + timedelta(days=start_offset)).strftime("%Y-%m-%d")
            # 限制行程日子：不少於 3 天，不多於 14 天
            for duration in range(3, 15): 
                ret = (today + timedelta(days=start_offset + duration)).strftime("%Y-%m-%d")
                
                data = await scrape_google_flights(origin, dest["code"], dep, ret)
                if data and data["price"] > 0:
                    data["region"] = dest["region"]
                    # 寫入雲端資料庫
                    supabase.table("flight_deals").insert(data).execute()
                await asyncio.sleep(1) # 避免過快被 Google 擋

if __name__ == "__main__":
    asyncio.run(main())
