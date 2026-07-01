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
        await page.wait_for_timeout(1000) # 因為阻擋了圖片，渲染變快，這裡可縮短為 1 秒
        
        selectors = ["li.pIav2d", "[role='listitem']", ".pI9YTe"]
        list_item_selector = None
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=4000)
                list_item_selector = selector
                break
            except: continue
        
        if not list_item_selector: return None

        first_flight = page.locator(list_item_selector).first
        text_content = await first_flight.inner_text()
        page_text = await page.inner_text("body")
        has_low_badge = any(keyword in page_text for keyword in ["低於正常", "偏低", "低廉", "Low price"])
        
        if "HK$" in text_content or "$" in text_content:
            price_match = re.search(r'(?:HK\$|\$)\s*([\d,]+)', text_content)
            if price_match:
                price = int(price_match.group(1).replace(',', ''))
                if price <= price_ceiling or has_low_badge:
                    return {
                        "origin": origin, "destination": dest, "region": region,
                        "departure_date": dep_date, "return_date": ret_date,
                        "duration_days": (datetime.strptime(ret_date, "%Y-%m-%d") - datetime.strptime(dep_date, "%Y-%m-%d")).days,
                        "price": price, "is_direct": "直飛" in text_content or "Nonstop" in text_content,
                        "booking_url": search_url
                    }
    except Exception as e:
        pass # 隱藏錯誤訊息保持日誌乾淨
    return None

async def main():
    # 完整 70 個目的地數據庫（💡 已依照指示更新東北亞低價標準）
    all_destinations = [
        # 台灣與中國內地
        {"code": "TPE", "name": "台北", "region": "台灣", "ceil": 1400}, 
        {"code": "RMQ", "name": "台中", "region": "台灣", "ceil": 1400}, 
        {"code": "KHH", "name": "高雄", "region": "台灣", "ceil": 1400},
        {"code": "PVG", "name": "上海", "region": "中國內地", "ceil": 1400}, 
        {"code": "PEK", "name": "北京", "region": "中國內地", "ceil": 1600},
        
        # 東北亞日韓
        {"code": "NRT", "name": "東京成田", "region": "東北亞", "ceil": 1800}, 
        {"code": "HND", "name": "東京羽田", "region": "東北亞", "ceil": 2200},
        {"code": "KIX", "name": "大阪", "region": "東北亞", "ceil": 1800}, 
        {"code": "OKA", "name": "沖繩", "region": "東北亞", "ceil": 1500},
        {"code": "ICN", "name": "首爾", "region": "東北亞", "ceil": 1800}, 
        {"code": "PUS", "name": "釜山", "region": "東北亞", "ceil": 1600},
        {"code": "CJU", "name": "濟州", "region": "東北亞", "ceil": 1600}, 
        {"code": "ISG", "name": "石垣", "region": "東北亞", "ceil": 1800},
        {"code": "HIJ", "name": "廣島", "region": "東北亞", "ceil": 2200}, 
        {"code": "TAK", "name": "高松", "region": "東北亞", "ceil": 2200},
        {"code": "NGO", "name": "名古屋", "region": "東北亞", "ceil": 2200}, 
        {"code": "FUK", "name": "福岡", "region": "東北亞", "ceil": 2200},
        {"code": "SDJ", "name": "仙台", "region": "東北亞", "ceil": 2200}, 
        {"code": "CTS", "name": "札幌", "region": "東北亞", "ceil": 2500},
        
        # 東南亞
        {"code": "BKK", "name": "曼谷", "region": "東南亞", "ceil": 1300}, 
        {"code": "HKT", "name": "布吉", "region": "東南亞", "ceil": 1500},
        {"code": "CNX", "name": "清邁", "region": "東南亞", "ceil": 1500}, 
        {"code": "HAN", "name": "河內", "region": "東南亞", "ceil": 1200},
        {"code": "SGN", "name": "胡志明", "region": "東南亞", "ceil": 1200}, 
        {"code": "DAD", "name": "蜆港", "region": "東南亞", "ceil": 1300},
        {"code": "SIN", "name": "新加坡", "region": "東南亞", "ceil": 1600}, 
        {"code": "KUL", "name": "吉隆坡", "region": "東南亞", "ceil": 1200},
        {"code": "PEN", "name": "檳城", "region": "東南亞", "ceil": 1300}, 
        {"code": "CEB", "name": "宿霧", "region": "東南亞", "ceil": 1300},
        {"code": "DPS", "name": "峇里島", "region": "東南亞", "ceil": 2200}, 
        {"code": "CGK", "name": "雅加達", "region": "東南亞", "ceil": 1500},
        
        # 歐洲地區
        {"code": "LHR", "name": "倫敦", "region": "歐洲", "ceil": 5200}, 
        {"code": "MAN", "name": "曼徹斯特", "region": "歐洲", "ceil": 5500},
        {"code": "EDI", "name": "愛丁堡", "region": "歐洲", "ceil": 5800}, 
        {"code": "BHX", "name": "伯明翰", "region": "歐洲", "ceil": 5500},
        {"code": "CDG", "name": "巴黎", "region": "歐洲", "ceil": 5200}, 
        {"code": "FCO", "name": "羅馬", "region": "歐洲", "ceil": 4900},
        {"code": "MXP", "name": "米蘭", "region": "歐洲", "ceil": 4900}, 
        {"code": "LIS", "name": "里斯本", "region": "歐洲", "ceil": 5500},
        {"code": "BCN", "name": "巴塞隆拿", "region": "歐洲", "ceil": 5200}, 
        {"code": "MAD", "name": "馬德里", "region": "歐洲", "ceil": 5200},
        {"code": "VIE", "name": "維也納", "region": "歐洲", "ceil": 4800}, 
        {"code": "ZRH", "name": "蘇黎世", "region": "歐洲", "ceil": 5200},
        {"code": "GVA", "name": "日內瓦", "region": "歐洲", "ceil": 5200}, 
        {"code": "AMS", "name": "阿姆斯特丹", "region": "歐洲", "ceil": 5300},
        {"code": "BRU", "name": "布魯塞爾", "region": "歐洲", "ceil": 5200}, 
        {"code": "IST", "name": "伊斯坦堡", "region": "歐洲", "ceil": 4500},
        {"code": "PRG", "name": "布拉格", "region": "歐洲", "ceil": 4900}, 
        {"code": "BUD", "name": "布達佩斯", "region": "歐洲", "ceil": 4900},
        {"code": "ATH", "name": "雅典", "region": "歐洲", "ceil": 5000}, 
        {"code": "MUC", "name": "慕尼黑", "region": "歐洲", "ceil": 5200},
        {"code": "FRA", "name": "法蘭克福", "region": "歐洲", "ceil": 5200}, 
        {"code": "HEL", "name": "赫爾辛基", "region": "歐洲", "ceil": 5200},
        {"code": "CPH", "name": "哥本哈根", "region": "歐洲", "ceil": 4900}, 
        {"code": "OSL", "name": "奧斯陸", "region": "歐洲", "ceil": 5000},
        {"code": "GOT", "name": "哥德堡", "region": "歐洲", "ceil": 5200}, 
        {"code": "ARN", "name": "斯德哥爾摩", "region": "歐洲", "ceil": 5000},
        {"code": "SVO", "name": "莫斯科", "region": "歐洲", "ceil": 5800}, 
        {"code": "LED", "name": "聖彼得堡", "region": "歐洲", "ceil": 5800},
        
        # 大洋洲
        {"code": "SYD", "name": "悉尼", "region": "大洋洲", "ceil": 4200}, 
        {"code": "MEL", "name": "墨爾本", "region": "大洋洲", "ceil": 4200},
        {"code": "PER", "name": "珀斯", "region": "大洋洲", "ceil": 3900}, 
        {"code": "BNE", "name": "布里斯本", "region": "大洋洲", "ceil": 4500},
        {"code": "AKL", "name": "奧克蘭", "region": "大洋洲", "ceil": 4600},
        
        # 中東與其他
        {"code": "DXB", "name": "杜拜", "region": "中東與其他", "ceil": 4200}, 
        {"code": "DOH", "name": "多哈", "region": "中東與其他", "ceil": 4500},
        {"code": "MLE", "name": "馬爾代夫", "region": "中東與其他", "ceil": 5000},
        
        # 美洲地區
        {"code": "YVR", "name": "溫哥華", "region": "美洲", "ceil": 5600}, 
        {"code": "YYZ", "name": "多倫多", "region": "美洲", "ceil": 6500}
    ]

    # 💡 核心變更 1：接收 GitHub 傳遞的區域變數
    env_region = os.environ.get("TARGET_REGION")
    
    if env_region:
        target_regions = [env_region]
        print(f"🚀 啟動矩陣模式！當前分配任務區域: {env_region}")
    else:
        # 若為本地測試，則預設執行東北亞
        target_regions = ["東北亞"]
        print("💻 本地測試模式啟動。")

    # 💡 核心變更 2：防止多台機器同時刪除資料庫 (限定只有「台灣」這台機器負責在週日打掃)
    weekday = datetime.today().weekday()
    if weekday == 6 and "台灣" in target_regions:
        print("🧼 星期日大清洗：由【台灣】區負責執行全庫清空...")
        try:
            supabase.table("flight_deals").delete().neq("id", 0).execute()
        except: pass

    destinations = [d for d in all_destinations if d["region"] in target_regions]
    if not destinations: return

    today = datetime.today()
    durations = [3, 5, 7, 10, 14]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0...", locale="zh-TW")
        page = await context.new_page()

        # 💡 核心變更 3：攔截無用資源，極限壓縮載入時間
        async def intercept_route(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", intercept_route)

        for dest in destinations:
            print(f"🛫 探測 【{dest['name']}】...")
            for week_offset in range(0, 90, 7):
                dep_date = (today + timedelta(days=8 + week_offset)).strftime("%Y-%m-%d")
                
                for dur in durations:
                    ret_date = (today + timedelta(days=8 + week_offset + dur)).strftime("%Y-%m-%d")
                    data = await scrape_google_flights(page, "HKG", dest["code"], dest["region"], dep_date, ret_date, dest["ceil"])
                    if data:
                        try:
                            supabase.table("flight_deals").insert(data).execute()
                            print(f"   ➔ 🎉 找到: {dur}天 | ${data['price']} ({dep_date})")
                        except: pass
                    
                    await asyncio.sleep(2) # 保持基本冷卻
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
