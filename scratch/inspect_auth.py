import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    try:
        page = ctx.new_page()
        page.goto("https://agenciavirtual.equatorialenergia.com.br/", timeout=45000)
        page.wait_for_timeout(3000)
        
        btn_login = page.locator(".btn-login, button:has-text('Entrar')").first
        if btn_login.is_visible():
            btn_login.click()
            page.wait_for_timeout(5000)
            print("URL on auth:", page.url)
            print("Title on auth:", page.title())
            Path("scratch/auth_page.html").write_text(page.content(), encoding="utf-8")
            
            # Check inputs and buttons on auth page
            inputs = page.locator("input").all()
            print(f"Inputs count: {len(inputs)}")
            for inp in inputs:
                name = inp.get_attribute("name") or inp.get_attribute("id") or inp.get_attribute("type")
                placeholder = inp.get_attribute("placeholder") or ""
                print(f"  Input: {name} (type={inp.get_attribute('type')}, placeholder={placeholder})")
            
            social = page.locator("a, button").all_inner_texts()
            print("Social / Buttons:", [s.strip() for s in social if s.strip()][:15])
    finally:
        ctx.close()
