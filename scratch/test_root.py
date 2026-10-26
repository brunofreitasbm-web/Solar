import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('https://agenciavirtual.equatorialenergia.com.br/', timeout=45000)
    page.wait_for_timeout(4000)
    print("Page URL on root:", page.url)
    print("Page Title on root:", page.title())
    
    # Check if there is an Entrar button or if it automatically logs in or redirects
    btn_login = page.locator("button, a").all()
    for b in btn_login:
        t = b.inner_text().strip()
        if any(w in t.lower() for w in ['entrar', 'login', 'sair', 'olá', 'segunda via', 'fatura']):
            print(f"Button/link: '{t}' | href={b.get_attribute('href')}")
    
    ctx.close()
