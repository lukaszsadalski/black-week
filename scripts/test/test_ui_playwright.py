import os
import sys
import asyncio
from playwright.async_api import async_playwright

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from test_utils import load_project_env, ensure_test_server, ensure_playwright_chromium
load_project_env()

BASE_URL = ensure_test_server(8000)
ensure_playwright_chromium()

async def run():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:
            err_msg = str(e)
            if "missing dependencies" in err_msg.lower() or "host system is missing" in err_msg.lower() or "executable" in err_msg.lower():
                print("\n⚠️ [SKIPPED] Headless Linux VM detected without Chromium OS libraries.")
                print("  To enable browser tests on Linux, run: playwright install --with-deps chromium")
                print("  Or run headless BigQuery & Agent tests via: python3 scripts/test/run_all_tests.py --integration --audit\n")
                return
            raise e
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: console_logs.append(f"[PAGE_ERROR] {exc}"))

        print(f"Navigating to {BASE_URL}...")
        await page.goto(BASE_URL, wait_until="networkidle")

        print("\nInitial Console Logs:")
        for l in console_logs:
            print(" ", l)

        # Check if #comparePromptsBtn exists
        btn = page.locator("#comparePromptsBtn")
        is_btn_visible = await btn.is_visible()
        print(f"\n#comparePromptsBtn visible: {is_btn_visible}")

        # Check initial state of #promptStudioModal
        modal = page.locator("#promptStudioModal")
        is_modal_visible_before = await modal.is_visible()
        print(f"#promptStudioModal visible before click: {is_modal_visible_before}")

        # Click #comparePromptsBtn
        print("\nClicking #comparePromptsBtn...")
        await btn.click()
        await page.wait_for_timeout(500)

        # Check state of #promptStudioModal after click
        is_modal_visible_after = await modal.is_visible()
        modal_classes = await modal.get_attribute("class")
        modal_style = await modal.get_attribute("style")
        print(f"#promptStudioModal visible after click: {is_modal_visible_after}")
        print(f"Modal classes: {modal_classes}")
        print(f"Modal style: {modal_style}")

        # Evaluate computed style
        computed_display = await page.evaluate("() => window.getComputedStyle(document.getElementById('promptStudioModal')).display")
        print(f"Computed display of #promptStudioModal: {computed_display}")

        # Take screenshot
        await page.screenshot(path="screenshot_prompt_studio_click.png")
        print("Screenshot saved to screenshot_prompt_studio_click.png")

        print("\nConsole Logs after click:")
        for l in console_logs:
            print(" ", l)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
