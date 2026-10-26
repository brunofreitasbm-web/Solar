import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('https://agenciavirtual.equatorialenergia.com.br/Login/', timeout=45000)
    page.wait_for_timeout(4000)
    from pathlib import Path
    Path("scratch/body.txt").write_text(page.inner_text("body"), encoding="utf-8")
    print("Wrote scratch/body.txt successfully")
    ctx.close()
