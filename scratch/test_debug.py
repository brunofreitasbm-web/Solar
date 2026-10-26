import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    print("Initial pages count:", len(ctx.pages))
    
    def on_page(page):
        print(">> New page opened:", page.url)
        page.on("close", lambda: print("<< Page closed:", page.url))
    
    ctx.on("page", on_page)
    ctx.on("close", lambda: print("<< Context closed!"))
    
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("close", lambda: print("<< Main page closed!"))
    
    try:
        print("Navigating to URL...")
        resp = page.goto('https://agenciavirtual.equatorialenergia.com.br/SegundaVia/', timeout=45000)
        print("Resp status:", resp.status if resp else "None")
        print("Page URL after goto:", page.url)
        for i in range(10):
            print(f"Tick {i}: pages={len(ctx.pages)}, url={page.url if not page.is_closed() else 'CLOSED'}")
            import time
            time.sleep(1)
    except Exception as e:
        print("Exception during test:", type(e), e)
    finally:
        try:
            ctx.close()
        except:
            pass
