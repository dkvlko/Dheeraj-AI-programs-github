import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import trafilatura

async def bing_search_raw(query: str) -> str:
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        await page.goto("https://www.bing.com", wait_until="networkidle")
        
        # Handle cookie banner if present
        try:
            accept_btn = page.locator('button:has-text("Accept")')
            if await accept_btn.count() > 0:
                await accept_btn.click()
                await page.wait_for_timeout(1000)
        except:
            pass
        
        # Wait for the textarea search box
        await page.wait_for_selector('textarea[name="q"]', state="visible", timeout=15000)
        
        # Fill and search
        await page.fill('textarea[name="q"]', query)
        await page.keyboard.press("Enter")
        
        # Wait for results to appear
        await page.wait_for_selector('ol#b_results', timeout=15000)
        
        raw_html = await page.content()
        await browser.close()
        return raw_html

def extract_readable_text(html: str) -> str:
    """Extract main content using Trafilatura"""
    # Extract text; include formatting (links, paragraphs)
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        include_links=True,
        include_formatting=True,
        output_format='txt'  # plain text; can also use 'markdown' or 'xml'
    )
    if text is None:
        return "No readable content extracted."
    return text

if __name__ == "__main__":
    query = "does the football teams change their sides after mid break"
    raw_html = asyncio.run(bing_search_raw(query))
    
    # Optionally save raw HTML for debugging
    with open("bing_raw.html", "w", encoding="utf-8") as f:
        f.write(raw_html)
    
    # Extract and print readable text
    readable_text = extract_readable_text(raw_html)
    print(readable_text[:5000])  # Print first 5000 chars
