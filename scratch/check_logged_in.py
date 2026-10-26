import time
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    try:
        page = ctx.new_page()
        # Navigate to Equatorial
        page.goto("https://agenciavirtual.equatorialenergia.com.br/", timeout=45000)
        page.wait_for_timeout(5000)
        
        print("URL:", page.url)
        print("Title:", page.title())
        
        # Check if login button is present
        btn_login = page.locator(".btn-login, button:has-text('Entrar')")
        print("btn_login visible:", btn_login.first.is_visible() if btn_login.count() > 0 else False)
        
        # Check text on page
        body_text = page.inner_text("body")
        for word in ["Olá", "Bem-vindo", "Sair", "Contrato", "Unidade", "Marambaia", "Débitos", "Faturas", "Segunda via"]:
            if word.lower() in body_text.lower():
                print(f"Found keyword: {word}")
    finally:
        ctx.close()
