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

async def scrape_google_flights(origin, dest, dep_date, ret_date, price_ceiling):
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

            # 抓取第一筆最平機票
            first_flight = await page.locator(list_item_selector).first
            text_content = await first_flight.inner_text()
            
            # 全網頁文本，用於捕捉 Google 官方的「價格偏低/低廉」提示
            page_text = await page.inner_text("body")
            has_low_badge = any(keyword in page_text for keyword in ["低於正常", "偏低", "低廉", "Less than usual", "Low price"])
            
            if "HK$" in text_content or "$" in text_content:
                price_match = re.search(r'(?:HK\$|\$)\s*([\d,]+)', text_content)
                if price_match:
                    price = int(price_match.group(1).replace(',', ''))
                    is_direct = "直飛" in text_content or "Nonstop" in text_content
                    
                    # ⚖️ 【核心平價過濾邏輯】
                    if price <= price_ceiling or has_low_badge:
                        await browser.close()
                        return {
                            "origin": origin, "destination": dest, "departure_date": dep_date, "return_date": ret_date,
                            "duration_days": (datetime.strptime(ret_date, "%Y-%m-%d") - datetime.strptime(dep_date, "%Y-%m-%d")).days,
                            "price": price, "is_direct": is_direct, "booking_url": search_url
                        }
                    else:
                        print(f"   ⏩ 略過: 價格 ${price} 未達平時低價標準 (基準線: ${price_ceiling})")
        except:
            pass
            
        await browser.close()
        return None

async def main():
    # 完整 70 個目的地數據庫
    all_destinations = [
        # 台灣與中國內地
        {"code": "TPE", "name": "台北", "region": "台灣", "ceil": 1800}, 
        {"code": "RMQ", "name": "台中", "region": "台灣", "ceil": 1800}, 
        {"code": "KHH", "name": "高雄", "region": "台灣", "ceil": 1800},
        {"code": "PVG", "name": "上海", "region": "中國內地", "ceil": 1800}, 
        {"code": "PEK", "name": "北京", "region": "中國內地", "ceil": 1800},
        
        # 東北亞日韓
        {"code": "NRT", "name": "東京成田", "region": "東北亞", "ceil": 2600}, {"code": "HND", "name": "東京羽田", "region": "東北亞", "ceil": 2800},
        {"code": "KIX", "name": "大阪", "region": "東北亞", "ceil": 2600}, {"code": "OKA", "name": "沖繩", "region": "東北亞", "ceil": 1800},
        {"code": "ICN", "name": "首爾", "region": "東北亞", "ceil": 2200}, {"code": "PUS", "name": "釜山", "region": "東北亞", "ceil": 2000},
        {"code": "CJU", "name": "濟州", "region": "東北亞", "ceil": 2000}, {"code": "ISG", "name": "石垣", "region": "東北亞", "ceil": 2200},
        {"code": "HIJ", "name": "廣島", "region": "東北亞", "ceil": 2500}, {"code": "TAK", "name": "高松", "region": "東北亞", "ceil": 2500},
        {"code": "NGO", "name": "名古屋", "region": "東北亞", "ceil": 2500}, {"code": "FUK", "name": "福岡", "region": "東北亞", "ceil": 2400},
        {"code": "SDJ", "name": "仙台", "region": "東北亞", "ceil": 2800}, {"code": "CTS", "name": "札幌", "region": "東北亞", "ceil": 3500},
        
        # 東南亞
        {"code": "BKK", "name": "曼谷", "region": "東南亞", "ceil": 1800}, {"code": "HKT", "name": "布吉", "region": "東南亞", "ceil": 2000},
        {"code": "CNX", "name": "清邁", "region": "東南亞", "ceil": 2000}, {"code": "HAN", "name": "河內", "region": "東南亞", "ceil": 1500},
        {"code": "SGN", "name": "胡志明", "region": "東南亞", "ceil": 1500}, {"code": "DAD", "name": "蜆港", "region": "東南亞", "ceil": 1600},
        {"code": "SIN", "name": "新加坡", "region": "東南亞", "ceil": 2000}, {"code": "KUL", "name": "吉隆坡", "region": "東南亞", "ceil": 1500},
        {"code": "PEN", "name": "檳城", "region": "東南亞", "ceil": 1600}, {"code": "CEB", "name": "宿霧", "region": "東南亞", "ceil": 1600},
        {"code": "DPS", "name": "峇里島", "region": "東南亞", "ceil": 2500}, {"code": "CGK", "name": "雅加達", "region": "東南亞", "ceil": 1800},
        
        # 歐洲地區
        {"code": "LHR", "name": "倫敦", "region": "歐洲", "ceil": 5500}, {"code": "MAN", "name": "曼徹斯特", "region": "歐洲", "ceil": 5800},
        {"code": "EDI", "name": "愛丁堡", "region": "歐洲", "ceil": 6000}, {"code": "BHX", "name": "伯明翰", "region": "歐洲", "ceil": 5800},
        {"code": "CDG", "name": "巴黎", "region": "歐洲", "ceil": 5500}, {"code": "FCO", "name": "羅馬", "region": "歐洲", "ceil": 5200},
        {"code": "MXP", "name": "米蘭", "region": "歐洲", "ceil": 5200}, {"code": "LIS", "name": "里斯本", "region": "歐洲", "ceil": 5800},
        {"code": "BCN", "name": "巴塞隆拿", "region": "歐洲", "ceil": 5500}, {"code": "MAD", "name": "馬德里", "region": "歐洲", "ceil": 5500},
        {"code": "VIE", "name": "維也納", "region": "歐洲", "ceil": 5000}, {"code": "ZRH", "name": "蘇黎世", "region": "歐洲", "ceil": 5500},
        {"code": "GVA", "name": "日內瓦", "region": "歐洲", "ceil": 5500}, {"code": "AMS", "name": "阿姆斯特丹", "region": "歐洲", "ceil": 5600},
        {"code": "BRU", "name": "布魯塞爾", "region": "歐洲", "ceil": 5400}, {"code": "IST", "name": "伊斯坦堡", "region": "歐洲", "ceil": 4800},
        {"code": "PRG", "name": "布拉格", "region": "歐洲", "ceil": 5200}, {"code": "BUD", "name": "布達佩斯", "region": "歐洲", "ceil": 5200},
        {"code": "ATH", "name": "雅典", "region": "歐洲", "ceil": 5400}, {"code": "MUC", "name": "慕尼黑", "region": "歐洲", "ceil": 5400},
        {"code": "FRA", "name": "法蘭克福", "region": "歐洲", "ceil": 5500}, {"code": "HEL", "name": "赫爾辛基", "region": "歐洲", "ceil": 5400},
        {"code": "CPH", "name": "哥本哈根", "region": "歐洲", "ceil": 5200}, {"code": "OSL", "name": "奧斯陸", "region": "歐洲", "ceil": 5400},
        {"code": "GOT", "name": "哥德堡", "region": "歐洲", "ceil": 5600}, {"code": "ARN", "name": "斯德哥爾摩", "region": "歐洲", "ceil": 5400},
        {"code": "SVO", "name": "莫斯科", "region": "歐洲", "ceil": 6000}, {"code": "LED", "name": "聖彼得堡", "region": "歐洲", "ceil": 6000},
        
        # 大洋洲
        {"code": "SYD", "name": "悉尼", "region": "大洋洲", "ceil": 4500}, {"code": "MEL", "name": "墨爾本", "region": "大洋洲", "ceil": 4500},
        {"code": "PER", "name": "珀斯", "region": "大洋洲", "ceil": 4200}, {"code": "BNE", "name": "布里斯本", "region": "大洋洲", "ceil": 4800},
        {"code": "AKL", "name": "奧克蘭", "region": "大洋洲", "ceil": 5000},
        
        # 中東與其他
        {"code": "DXB", "name": "杜拜", "region": "中東與其他", "ceil": 4500}, {"code": "DOH", "name": "多哈", "region": "中東與其他", "ceil": 4800},
        {"code": "MLE", "name": "馬爾代夫", "region": "中東與其他", "ceil": 5500},
        
        # 美洲地區 (已剔除西雅圖)
        {"code": "YVR", "name": "溫哥華", "region": "美洲", "ceil": 6000}, {"code": "YYZ", "name": "多倫多", "region": "美洲", "ceil": 7000}
    ]

    # 📅 讀取當前星期幾 (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun)
    weekday = datetime.today().weekday()
    
    # 🌟 重新調整後的日程分配矩陣
    weekday_map = {
        0: ["台灣", "中國內地"],
        1: ["東北亞"],
        2: ["東南亞", "中東與其他"],  # 🤝 星期三：東南亞 + 中東與其他 合併執行
        3: ["歐洲"],
        4: ["大洋洲", "美洲"],        # 🤝 星期五：大洋洲 + 美洲 合併執行
        5: [],                       # ☕ 星期六：無排班
        6: []                       # 🧼 星期日：無排班（僅零時零分啟動清洗）
    }
    
    target_regions = weekday_map.get(weekday, [])
    print(f"📅 星期 {weekday + 1} 啟動！今日目標區域: {target_regions if target_regions else '無 (休息/純清洗日)'}")

    # 🧼 核心要求：逢星期日零時零分，無論今日有無掃描任務，必須準時清空全資料庫舊機票
    if weekday == 6:
        print("🧼 偵測到今日為【星期日】，啟動每週定時大清洗，清空全庫舊機票數據...")
        try:
            supabase.table("flight_deals").delete().neq("id", 0).execute()
            print("✅ 全庫歷史數據清空成功！蓄勢待發迎接新一週。")
        except Exception as e:
            print(f"⚠️ 清空舊數據提示: {e}")

    destinations = [d for d in all_destinations if d["region"] in target_regions]
    print(f"📊 今日預計掃描城市總數: {len(destinations)} 個")

    # 如果今天沒有被分配任何區域（例如週六、週日），程式會在這裡平穩結束
    if not destinations:
        print("📴 今日無掃描任務。程式順利結束。")
        return

    origin = "HKG"
    today = datetime.today()
    
    out_days_offset = 8
    dep = (today + timedelta(days=out_days_offset)).strftime("%Y-%m-%d")

    for dest in destinations:
        print(f"🛫 正在精細探測 【{dest['name']} ({dest['code']})】 3至14天的每一種假期組合...")
        
        for duration in range(3, 15):
            ret = (today + timedelta(days=out_days_offset + duration)).strftime("%Y-%m-%d")
            
            data = await scrape_google_flights(origin, dest["code"], dep, ret, dest["ceil"])
            if data:
                try:
                    supabase.table("flight_deals").insert(data).execute()
                    print(f"   ➔ 🎉 [真•平價] 找到 {duration} 天行程! 價格: HKD ${data['price']} 出發: {dep}")
                except Exception as db_err:
                    print(f"   ❌ 資料庫寫入失敗: {db_err}")
            
            await asyncio.sleep(1.8)

if __name__ == "__main__":
    asyncio.run(main())
