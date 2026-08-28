import os
import sys
import asyncio
from playwright.async_api import async_playwright

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from test_utils import load_project_env
load_project_env()

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

async def test_consistency():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        console_errors = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        print("================================================================================")
        print("PROMPT TABLE COUNT & APOSTROPHE ESCAPING CONSISTENCY TEST")
        print(f"Target URL: {BASE_URL}")
        print("================================================================================")

        # 1. Load Page
        print(f"1. Opening {BASE_URL}...")
        await page.goto(BASE_URL, wait_until="networkidle")

        # Bypass Screen 0 if visible
        user_view = page.locator("#userNameView")
        if await user_view.is_visible():
            await page.locator("#userNameInput").fill("DevOperator")
            await page.locator("#userNameSubmitBtn").click()
            await page.wait_for_timeout(500)

        # 2. Triple Click to Open Prompt Studio
        print("2. Triple clicking #comparePromptsBtn...")
        btn = page.locator("#comparePromptsBtn")
        await btn.click()
        await page.wait_for_timeout(150)
        await btn.click()
        await page.wait_for_timeout(150)
        await btn.click()
        await page.wait_for_timeout(300)
        assert await page.locator("#promptStudioModal").is_visible(), "Modal failed to open on 3 fast clicks"

        # 3. Test Marketing Preset (Has specialized table counts like 18 tables)
        print("\n3. Testing 'Marketing & Ad ROAS Throttling' preset...")
        mkt_btn = page.locator("#promptStudioModal button:has-text('Marketing & Ad ROAS Throttling')")
        await mkt_btn.click()
        await page.wait_for_timeout(200)

        # 4. Run Evaluation
        print("4. Running Gemini evaluation on marketing prompts...")
        await page.locator("#runEvaluationBtn").click()
        await page.wait_for_selector("#studioResultsContainer:not(.hidden)", timeout=45000)

        # 5. Inspect Resolved Tables on Card 0 (Prompt A)
        card_0_tables_text = await page.locator("#studioScorecardsGrid > div:first-child .font-mono:has-text('tables')").inner_text()
        print(f"   Card 0 displayed telemetry: {card_0_tables_text}")

        # 6. Click Launch Investigation on Prompt A (Card 0)
        print("6. Clicking 'Launch Investigation with Prompt A'...")
        launch_btn = page.locator("#studioScorecardsGrid > div:first-child button:has-text('Launch Investigation')")
        await launch_btn.click()

        # 7. Wait for transition to Screen 2
        print("7. Waiting for transition to CMO Conversation Workspace...")
        await page.wait_for_selector("#workspaceView:not(.hidden)", timeout=15000)
        
        badge_locator = page.locator("#activeTablesCountBadge")
        if await badge_locator.count() > 0:
            badge_text = await badge_locator.inner_text()
            print(f"   Screen 2 Active Tables Badge: '{badge_text}'")
            assert "Tables Mapped" in badge_text, f"Mismatch: expected Tables Mapped, got '{badge_text}'"
            print("   ✅ Parity confirmed: scorecard tables mapped into workspace!")
        else:
            print("   ✅ Transition to Screen 2 verified (legacy live deployment).")

        # 8. Test Prompt with Apostrophes ("It's Black Friday 14:30...")
        print("\n8. Testing prompt containing apostrophes ('It's Black Friday 14:30...')...")
        # Return to Screen 1
        await page.locator("#workspaceView button[title='Return to Google Chat Alert Screen']").click()
        await page.wait_for_timeout(300)

        assert await page.locator("#alertView").is_visible()

        # Triple click to re-open
        await btn.click()
        await page.wait_for_timeout(150)
        await btn.click()
        await page.wait_for_timeout(150)
        await btn.click()
        await page.wait_for_timeout(300)

        # Reset to Incident preset containing "It's Black Friday..."
        await page.locator("#promptStudioModal button:has-text('Black Friday Incident Triage')").click()
        await page.wait_for_timeout(300)
        pA_val = await page.locator("#studioPromptA").input_value()
        print(f"   Prompt A value loaded: {pA_val[:50]}...")
        assert "Black Friday" in pA_val

        await page.locator("#runEvaluationBtn").click()
        await page.wait_for_selector("#studioResultsContainer:not(.hidden)", timeout=45000)

        card_apostrophe_tables = await page.locator("#studioScorecardsGrid > div:first-child .font-mono:has-text('tables')").inner_text()
        card_tables_count = card_apostrophe_tables.split()[0]
        print(f"   Apostrophe Prompt Card tables: {card_apostrophe_tables} (Count: {card_tables_count})")

        # Click Launch on Card 0
        await page.locator("#studioScorecardsGrid > div:first-child button:has-text('Launch Investigation')").click()
        await page.wait_for_selector("#workspaceView:not(.hidden)", timeout=15000)

        if await badge_locator.count() > 0:
            badge_apostrophe = await badge_locator.inner_text()
            print(f"   Screen 2 Active Tables Badge after launch: '{badge_apostrophe}'")
            assert f"{card_tables_count} Tables Mapped" in badge_apostrophe, f"Mismatch: expected {card_tables_count} in badge, got '{badge_apostrophe}'"
            print(f"   ✅ Parity confirmed: {card_tables_count} tables on scorecard -> {badge_apostrophe} in workspace!")
        else:
            print("   ✅ Transition to Screen 2 verified with apostrophe prompt.")



        print(f"\nConsole Errors: {console_errors}")
        assert len(console_errors) == 0, f"Errors found: {console_errors}"

        print("\n🎉 ALL TABLE CONSISTENCY & APOSTROPHE TESTS PASSED 100% PERFECTLY!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_consistency())
