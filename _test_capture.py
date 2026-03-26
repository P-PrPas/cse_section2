import os
from dotenv import load_dotenv
load_dotenv()
from modules.ocsc_scraper import OcscScraperThread

s = OcscScraperThread(os.getenv('OCSC_USER'), os.getenv('OCSC_PASSWORD'))
s._playwright = __import__('playwright.sync_api').sync_api.sync_playwright().start()
s._browser = s._playwright.chromium.launch(headless=True)
s._context = s._browser.new_context(viewport={'width': 1280, 'height': 800})
s._page = s._context.new_page()

print("Logging in...")
s._login()

print("Searching ID...")
search_input = s._page.locator('input[type="text"], input[name*="id"], input[name*="card"]').first
search_input.fill('1104200154690')
search_btn = s._page.locator('button:has-text("ค้นหา"), input[value="ค้นหา"], a:has-text("ค้นหา")').first
if search_btn.count() > 0:
    search_btn.click()
else:
    search_input.press('Enter')

print("Waiting for results...")
s._page.wait_for_timeout(3000)

print("Dumping HTML...")
with open('search_result.html','w',encoding='utf-8') as f:
    f.write(s._page.content())
    
s._page.screenshot(path='search_result.png')
s._cleanup()
print("Done.")
