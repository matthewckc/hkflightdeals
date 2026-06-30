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
        # 啟動模擬瀏覽器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="zh-TW"
        )
        page = await context.new_page()
        
        # 官方標準查詢 URL，強制設定繁體中文(hl=zh-TW)與港幣結算(curr=HKD)
        search_url = f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{dep_date}%20through%20{ret_date}&hl=zh-TW&curr=HKD"
        
        print(f"🔍 正在載入網址: {search_url}")
        
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=20000)
            
            # 多重選擇器保障：優先等候最新的 Google 航班列表項標籤
            selectors = ["li.pIav2d", "[role='listitem']", ".pI9YTe"]
            list_item_selector = None
            
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=4000)
                    list_item_selector = selector
                    print(f"🎯 成功定位到航班區塊標籤: {selector}")
                    break
                except:
                    continue
            
            if not list_item_selector:
                print("⚠️ 找不到已知的航班列表標籤，嘗試強行獲取所有區塊...")
                list_item_selector = "[role='listitem']"

            # 抓取頁面上所有的航班卡片
            flight_items = await page.locator(list_item_selector).all()
            print(f"📊 畫面上共找到 {len(flight_items)} 個航班選項")
            
            for item in flight_items:
                text_content = await item.inner_text()
                
                # 排除沒有價格的無效區塊
                if "HK$" not in text_content and "$" not in text_content:
                    continue
                
                print(f"📝 正在解析航班文本片段:\n--- \n{text_content.strip()} \n---")
                
                # 利用正則表達式，直接抓取 HK$ 或 $ 後面的數字作為價格
                price_match = re.search(r'(?:HK\$|\$)\s*([\d,]+)', text_content)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    price = int(price_str)
                    
                    # 判斷是否直飛
                    is_direct = "直飛" in text_content or "Nonstop" in text_content
                    
                    await browser.close()
                    return {
                        "origin": origin,
                        "destination": dest,
                        "departure_date": dep_date,
                        "return_date": ret_date,
                        "duration_days": (datetime.strptime(ret_date, "%Y-%m-%d") - datetime.strptime(dep_date, "%Y-%m-%d")).days,
                        "price": price,
                        "is_direct": is_direct,
                        "booking_url": search_url
                    }
                    
        except Exception as e:
            print(f"❌ 剖析失敗，錯誤回報: {str(e)}")
            
        await browser.close()
        return None

async def main():
    # 測試 HKG -> NRT 航線
    destinations = [{"code": "NRT", "region": "東北亞"}]
    origin = "HKG"
    today = datetime.today()

    # 設定出發與回程日期 (符合不少於3天、不多於14天原則)
    dep = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    ret = (today + timedelta(days=21)).strftime("%Y-%m-%d")
    
    print(f"🚀 啟動防震爬蟲：{origin} -> {destinations[0]['code']} ({dep} 至 {ret})")
    
    data = await scrape_google_flights(origin, destinations[0]["code"], dep, ret)
    if data and data["price"] > 0:
        data["region"] = destinations[0]["region"]
        try:
            supabase.table("flight_deals").insert(data).execute()
            print(f"✅ 成功寫入 Supabase！抓到最平價格: HKD ${data['price']}")
        except Exception as db_err:
            print(f"❌ Supabase 寫入錯誤: {str(db_err)}")
    else:
        print("ℹ️ 未能從網頁文字中解析出有效票價。")

if __name__ == "__main__":
    asyncio.run(main())
