import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('https://agenciavirtual.equatorialenergia.com.br/', timeout=45000)
    page.wait_for_timeout(3000)
    ls = page.evaluate("() => ({...localStorage})")
    print("LocalStorage keys on agenciavirtual:")
    for k, v in ls.items():
        print(f"  {k} = {v}")
    
    cookies = ctx.cookies()
    print(f"\nTotal cookies: {len(cookies)}")
    for c in cookies:
        if "equatorial" in c["domain"]:
            print(f"  Cookie: {c['domain']} | {c['name']} | val_len={len(c['value'])}")
    ctx.close()
