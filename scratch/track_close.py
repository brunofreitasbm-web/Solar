import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    ctx.on("close", lambda: print("EVENT: Context closed!"))
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("crash", lambda: print("EVENT: Page crashed!"))
    page.on("close", lambda: print("EVENT: Page closed!"))
    
    try:
        page.goto('https://agenciavirtual.equatorialenergia.com.br/Login/', timeout=45000)
        print("Page URL after goto:", page.url)
        for i in range(10):
            print(f"Sec {i}: is_closed={page.is_closed()}")
            page.wait_for_timeout(1000)
        from pathlib import Path
        Path("scratch/body.txt").write_text(page.inner_text("body"), encoding="utf-8")
        print("Done successfully!")
    except Exception as e:
        print("Exception:", type(e), e)
    finally:
        try:
            ctx.close()
        except:
            pass
