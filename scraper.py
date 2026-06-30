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
            await page.goto(search_url, wait_until="networkidle", timeout=12000)
            
            selectors = ["li.pIav2d", "[role='listitem']", ".pI9YTe"]
            list_item_selector = None
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2500)
                    list_item_selector = selector
                    break
                except:
                    continue
            
            if not list_item_selector:
                await browser.close()
                return None

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
    # 完整 70 個目的地數據庫
    all_destinations = [
        {"code": "PVG", "name": "上海", "region": "中國內地"}, {"code": "PEK", "name": "北京", "region": "中國內地"},
        {"code": "TPE", "name": "台北", "region": "台灣"}, {"code": "RMQ", "name": "台中", "region": "台灣"}, {"code": "KHH", "name": "高雄", "region": "台灣"},
        {"code": "NRT", "name": "東京成田", "region": "東北亞"}, {"code": "HND", "name": "東京羽田", "region": "東北亞"},
        {"code": "KIX", "name": "大阪", "region": "東北亞"}, {"code": "OKA", "name": "沖繩", "region": "東北亞"},
        {"code": "ICN", "name": "首爾", "region": "東北亞"}, {"code": "PUS", "name": "釜山", "region": "東北亞"},
        {"code": "CJU", "name": "濟州", "region": "東北亞"}, {"code": "ISG", "name": "石垣", "region": "東北亞"},
        {"code": "HIJ", "name": "廣島", "region": "東北亞"}, {"code": "TAK", "name": "高松", "region": "東北亞"},
        {"code": "NGO", "name": "名古屋", "region": "東北亞"}, {"code": "FUK", "name": "福岡", "region": "東北亞"},
        {"code": "SDJ", "name": "仙台", "region": "東北亞"}, {"code": "CTS", "name": "札幌", "region": "東北亞"},
        {"code": "BKK", "name": "曼谷", "region": "東南亞"}, {"code": "HKT", "name": "布吉", "region": "東南亞"},
        {"code": "CNX", "name": "清邁", "region": "東南亞"}, {"code": "HAN", "name": "河內", "region": "東南亞"},
        {"code": "SGN", "name": "胡志明", "region": "東南亞"}, {"code": "DAD", "name": "蜆港", "region": "東南亞"},
        {"code": "SIN", "name": "新加坡", "region": "東南亞"}, {"code": "KUL", "name": "吉隆坡", "region": "東南亞"},
        {"code": "PEN", "name": "檳城", "region": "東南亞"}, {"code": "CEB", "name": "宿霧", "region": "東南亞"},
        {"code": "DPS", "name": "峇里島", "region": "東南亞"}, {"code": "CGK", "name": "雅加達", "region": "東南亞"},
        {"code": "LHR", "name": "倫敦", "region": "歐洲"}, {"code": "MAN", "name": "曼徹斯特", "region": "歐洲"},
        {"code": "EDI", "name": "愛丁堡", "region": "歐洲"}, {"code": "BHX", "name": "伯明翰", "region": "歐洲"},
        {"code": "CDG", "name": "巴黎", "region": "歐洲"}, {"code": "FCO", "name": "羅馬", "region": "歐洲"},
        {"code": "MXP", "name": "米蘭", "region": "歐洲"}, {"code": "LIS", "name": "里斯本", "region": "歐洲"},
        {"code": "BCN", "name": "巴塞隆拿", "region": "歐洲"}, {"code": "MAD", "name": "馬德里", "region": "歐洲"},
        {"code": "VIE", "name": "維也納", "region": "歐洲"}, {"code": "ZRH", "name": "蘇黎世", "region": "歐洲"},
        {"code": "GVA", "name": "日內瓦", "region": "歐洲"}, {"code": "AMS", "name": "阿姆斯特丹", "region": "歐洲"},
        {"code": "BRU", "name": "布魯塞爾", "region": "歐洲"}, {"code": "IST", "name": "伊斯坦堡", "region": "歐洲"},
        {"code": "PRG", "name": "布拉格", "region": "歐洲"}, {"code": "BUD", "name": "布達佩斯", "region": "歐洲"},
        {"code": "ATH", "name": "雅典", "region": "歐洲"}, {"code": "MUC", "name": "慕尼黑", "region": "歐洲"},
        {"code": "FRA", "name": "法蘭克福", "region": "歐洲"}, {"code": "HEL", "name": "赫爾辛基", "region": "歐洲"},
        {"code": "CPH", "name": "哥本哈根", "region": "歐洲"}, {"code": "OSL", "name": "奧斯陸", "region": "歐洲"},
        {"code": "GOT", "name": "哥德堡", "region": "歐洲"}, {"code": "ARN", "name": "斯德哥爾摩", "region": "歐洲"},
        {"code": "SVO", "name": "莫斯科", "region": "歐洲"}, {"code": "LED", "name": "聖彼得堡", "region": "歐洲"},
        {"code": "SEA", "name": "西雅圖", "region": "美洲"}, {"code": "YVR", "name": "溫哥華", "region": "美洲"},
        {"code": "YYZ", "name": "多倫多", "region": "美洲"}, {"code": "SYD", "name": "悉尼", "region": "大洋洲"},
        {"code": "MEL", "name": "墨爾本", "region": "大洋洲"}, {"code": "PER", "name": "珀斯", "region": "大洋洲"},
        {"code": "BNE", "name": "布里斯本", "region": "大洋洲"}, {"code": "AKL", "name": "奧克蘭", "region": "大洋洲"},
        {"code": "DXB", "name": "杜拜", "region": "中東與其他"}, {"code": "DOH", "name": "多哈", "region": "中東與其他"},
        {"code": "MLE", "name": "馬爾代夫", "region": "中東與其他"}
    ]

    # 📅 判斷今天是星期幾 (Python 中 0=Mon, 1=Tue, ..., 6=Sun)
    weekday = datetime.today().weekday()
    
    # 建立星期幾對應的區域
    weekday_map = {
        0: ["台灣", "中國內地"],
        1: ["東北亞"],
        2: ["東南亞"],
        3: ["歐洲"],
        4: ["大洋洲"],
        5: ["中東與其他"],
        6: ["美洲"]
    }
    
    target_regions = weekday_map.get(weekday, [])
    print(f"📅 今天是星期 {weekday + 1}，排定執行的機票目標區域為: {target_regions}")

    # 🧹 核心洗牌機制：如果是星期日 (6)，在執行搜尋前，先清空資料庫中累積了一週的舊資料
    if weekday == 6:
        print("🧼 偵測到今日為【星期日】，啟動每週定時大清洗，清空全庫舊機票數據...")
        try:
            supabase.table("flight_deals").delete().neq("id", 0).execute()
            print("✅ 全庫歷史數據已成功清空！")
        except Exception as e:
            print(f"⚠️ 清空舊數據時出現提示: {e}")
    else:
        print("📥 今日非星期日，搜羅到的平價將會【滾雪球式累積】併入現有機票庫中。")

    # 篩選出今天需要掃描的目的地
    destinations = [d for d in all_destinations if d["region"] in target_regions]
    print(f"📊 今日待掃描的城市總數: {len(destinations)} 個")

    origin = "HKG"
    today = datetime.today()
    
    # 保持完美的 3-14 天內出行方案抽樣
    travel_plans = [
        {"out_days": 5, "duration": 4},   # 4天短途度假
        {"out_days": 12, "duration": 8},  # 8天深度遊
        {"out_days": 20, "duration": 12}  # 12天長途旅行
    ]

    for dest in destinations:
        print(f"🛫 正在探測 【{dest['name']} ({dest['code']})】...")
        
        for plan in travel_plans:
            dep = (today + timedelta(days=plan["out_days"])).strftime("%Y-%m-%d")
            ret = (today + timedelta(days=plan["out_days"] + plan["duration"])).strftime("%Y-%m-%d")
            
            data = await scrape_google_flights(origin, dest["code"], dep, ret)
            if data and data["price"] > 0:
                data["region"] = dest["region"]
                try:
                    supabase.table("flight_deals").insert(data).execute()
                    print(f"   ➔ 💰 成功寫入! {dep} ({plan['duration']}天) 價格: ${data['price']}")
                except Exception as db_err:
                    print(f"   ❌ 資料庫寫入失敗: {db_err}")
            
            await asyncio.sleep(1.5)

if __name__ == "__main__":
    asyncio.run(main())
