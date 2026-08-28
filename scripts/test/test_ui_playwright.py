import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: console_logs.append(f"[PAGE_ERROR] {exc}"))

        print("Navigating to http://localhost:8000...")
        await page.goto("http://localhost:8000", wait_until="networkidle")

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
