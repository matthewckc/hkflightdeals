import os
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from supabase import create_client, Client

# 初始化 Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

async def scrape_google_flights(origin, dest, dep_date, ret_date):
    async with async_playwright() as p:
        # 模擬真實瀏覽器的 User-Agent，降低被擋機率
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # 修正為 Google 官方標準的查詢跳轉網址
        search_url = f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{dep_date}%20through%20{ret_date}"
        
        print(f"🔍 正在嘗試載入網址: {search_url}")
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            
            # 檢查頁面標題，看是否被 Google 判定為異常流量或卡在同意頁面
            title = await page.title()
            print(f"📄 目前網頁標題: {title}")
            
            if "Unusual traffic" in title or "異常流量" in title:
                print("❌ 糟糕！該 IP 已被 Google 判定為機器人並封鎖（觸發驗證碼）。")
                await browser.close()
                return None
                
            # 等待航班元素出現 (放寬等待時間至 12 秒)
            await page.wait_for_selector('.pI9YTe', timeout=12000)
            first_flight = await page.query_selector('.pI9YTe')
            
            if first_flight:
                price_text = await first_flight.query_selector('.YMlAec')
                price_val = await price_text.inner_text() if price_text else "找不到價格"
                print(f"💰 成功抓取到價格文字: {price_val}")
                
                price = int(''.join(filter(str.isdigit, price_val))) if price_text else 0
                
                stops_text = await first_flight.query_selector('.Efby9d')
                is_direct = "直飛" in (await stops_text.inner_text()) if stops_text else False
                
                await browser.close()
                return {
                    "origin": origin, "destination": dest, "departure_date": dep_date, "return_date": ret_date,
                    "duration_days": (datetime.strptime(ret_date, "%Y-%m-%d") - datetime.strptime(dep_date, "%Y-%m-%d")).days,
                    "price": price, "is_direct": is_direct, "booking_url": search_url
                }
        except Exception as e:
            # 這裡會精準印出到底卡在什麼地方
            print(f"⚠️ 航線 {dest} 抓取失敗，原因: {str(e)}")
            
        await browser.close()
        return None

async def main():
    # 先用一組最熱門的航線進行測試，避免一開始跑太多被鎖
    destinations = [{"code": "NRT", "region": "東北亞"}]
    origin = "HKG"
    today = datetime.today()

    # 測試未來第 7 天出發，玩 5 天的組合
    dep = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    ret = (today + timedelta(days=12)).strftime("%Y-%m-%d")
    
    print(f"🚀 開始執行單一航線測試：{origin} -> {destinations[0]['code']} ({dep} 至 {ret})")
    
    data = await scrape_google_flights(origin, destinations[0]["code"], dep, ret)
    if data and data["price"] > 0:
        data["region"] = destinations[0]["region"]
        try:
            supabase.table("flight_deals").insert(data).execute()
            print("✅ 成功寫入 Supabase 資料庫！")
        except Exception as db_err:
            print(f"❌ Supabase 寫入失敗: {str(db_err)}")
    else:
        print("ℹ️ 本次未能成功取得有效機票數據。")

if __name__ == "__main__":
    asyncio.run(main())
