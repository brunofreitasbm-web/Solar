import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('https://agenciavirtual.equatorialenergia.com.br/SegundaVia/', timeout=45000)
    page.wait_for_timeout(4000)
    
    print("Page URL:", page.url)
    inputs = page.locator("input").all()
    for inp in inputs:
        print("Input:", inp.get_attribute("name"), inp.get_attribute("type"), inp.get_attribute("id"), inp.get_attribute("placeholder"))
    
    buttons = page.locator("button, input[type='submit']").all()
    for btn in buttons:
        print("Button:", btn.get_attribute("id"), btn.get_attribute("type"), btn.inner_text().strip())
    
    ctx.close()
