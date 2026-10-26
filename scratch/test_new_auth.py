import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto

def testar():
    with sync_playwright() as p:
        ctx = _obter_contexto(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://agenciavirtual.equatorialenergia.com.br/", timeout=45000)
        page.wait_for_timeout(3000)
        
        url = page.url.lower()
        print("URL:", url)
        
        tem_token = page.evaluate("""() => {
            try {
                const keys = Object.keys(localStorage);
                const hasCognito = keys.some(k => k.includes('CognitoIdentityServiceProvider') && k.endsWith('.refreshToken'));
                const hasSession = Boolean(localStorage.getItem('$OS_Users$CA$ClientVars$UserId')) ||
                                   Boolean(localStorage.getItem('$OS_Users$$ClientVars$$SESSION_USER_ID')) ||
                                   Boolean(localStorage.getItem('$OS_Users$Home$ClientVars$CodigoSessao'));
                return hasCognito || hasSession;
            } catch(e) {
                return false;
            }
        }""")
        print("tem_token via evaluate:", tem_token)
        ctx.close()

testar()
