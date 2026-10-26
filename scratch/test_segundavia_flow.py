import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://agenciavirtual.equatorialenergia.com.br/SegundaVia/", timeout=45000)
    page.wait_for_timeout(6000)
    
    print("Page URL:", page.url)
    print("Page Title:", page.title())
    from pathlib import Path
    Path("scratch/segundavia_body.txt").write_text(page.inner_text("body"), encoding="utf-8")
    print("Wrote scratch/segundavia_body.txt")
    
    # Check elements on SegundaVia
    buttons = page.locator("button, a, input").all()
    print(f"Total elements: {len(buttons)}")
    for b in buttons:
        t = b.inner_text().strip().replace("\n", " ")
        if t:
            print(f"  [{b.evaluate('e => e.tagName')}] text='{t[:50]}'")
            
    ctx.close()
