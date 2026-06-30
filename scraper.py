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
    all_destinations =
