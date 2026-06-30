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

# 💡 修正 1：參數新增 region，確保資料完整度
async def scrape_google_flights(page, origin, dest, region, dep_date, ret_date, price_ceiling):
    search_url = f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{origin}%20on%20{dep_date}%20through%20{ret_date}&hl=zh-TW&curr=HKD"
    
    try:
        await page.goto(search_url, wait_until="networkidle", timeout=15000)
        
        # 💡 優化：抵達網頁後強制靜止等待 1.5 秒，給 Google 豐富的動態組件完整的渲染時間
        await page.wait_for_timeout(1500)
        
        selectors = ["li.pIav2d", "[role='listitem']", ".pI9YTe"]
        list_item_selector = None
        for selector in selectors:
            try:
                # 💡 優化：將單個選擇器的超時拉長至 4000ms，對抗 GitHub 環境的網路延遲
                await page.wait_for_selector(selector, timeout=4000)
                list_item_selector = selector
                break
            except:
                continue
        
        if not list_item_selector:
            print(f"   ⚠️ 【{dest}】{dep_date} ({ret_date})：未能定位機票列表（可能該日期無航班或遭阻擋）")
            return None

        # 抓取第一筆最平機票
        first_flight = page.locator(list_item_selector).first
        text_content = await first_flight.inner_text()
        
        # 全網頁文本，用於捕捉 Google 官方的「價格偏低/低廉」提示
        page_text = await page.inner_text("body")
        has_low_badge = any(keyword in page_text for keyword in ["低於正常", "偏低", "低廉", "Less than usual", "Low price"])
        
        if "HK$" in text_content or "$" in text_content:
            price_match = re.search(r'(?:HK\$|\$)\s*([\d,]+)', text_content)
