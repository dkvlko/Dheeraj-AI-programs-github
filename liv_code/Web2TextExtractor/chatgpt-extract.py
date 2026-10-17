import asyncio
from playwright.async_api import async_playwright
import trafilatura
from pathlib import Path


#FILE_PATH = "file:///home/dkvlko/Downloads/Telegram Desktop/IIT Physics Compendium Strategy.html"

def get_latest_file_url(directory: str) -> str:
    """
    Returns the latest created/modified file in the directory as a file:// URL
    """
    path = Path(directory)

    if not path.exists() or not path.is_dir():
        raise ValueError(f"Invalid directory: {directory}")

    # Get all files (ignore directories)
    files = [f for f in path.iterdir() if f.is_file()]

    if not files:
        raise ValueError("No files found in directory")

    # Pick the most recently modified file
    latest_file = max(files, key=lambda f: f.stat().st_mtime)

    # Convert to file:// URL
    return latest_file.resolve().as_uri()

directory = "/home/dkvlko/Downloads/Telegram Desktop"
FILE_PATH_GPT = get_latest_file_url(directory)

async def extract_text_gpt():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(FILE_PATH_GPT)
        # Load local HTML file
        await page.goto(FILE_PATH_GPT)

        # Wait for JS to render (adjust if needed)
        await page.wait_for_timeout(3000)

        # Get full rendered HTML
        html = await page.content()

        await browser.close()

        # Extract main text using trafilatura
        extracted = trafilatura.extract(html)

        return extracted

if __name__ == "__main__":
    text = asyncio.run(extract_text_gpt())
    print(text)
