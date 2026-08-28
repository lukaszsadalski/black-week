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

async def test_full_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        console_errors = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        print("================================================================================")
        print("LOCAL UI END-TO-END AUTOMATED INTERACTION TEST (PORT 8000)")
        print(f"Target URL: {BASE_URL}")
        print("================================================================================")

        # 1. Open Localhost
        print(f"1. Navigating to {BASE_URL}...")
        await page.goto(BASE_URL, wait_until="networkidle")
        
        is_alert_visible = await page.locator("#alertView").is_visible()
        is_workspace_visible = await page.locator("#workspaceView").is_visible()
        is_modal_visible = await page.locator("#promptStudioModal").is_visible()
        print(f"   Screen 1 (#alertView) visible: {is_alert_visible}")
        print(f"   Screen 2 (#workspaceView) visible: {is_workspace_visible}")
        print(f"   Studio Modal (#promptStudioModal) visible: {is_modal_visible}")
        assert is_alert_visible and not is_workspace_visible and not is_modal_visible

        # 2. Click "Compare prompts" on Screen 1 sidebar
        print("\n2. Clicking 'Compare prompts' on Screen 1 sidebar...")
        btn = page.locator("#comparePromptsBtn")
        await btn.click()
        await page.wait_for_timeout(300)

        is_modal_visible_now = await page.locator("#promptStudioModal").is_visible()
        print(f"   Studio Modal visible immediately after 1 click: {is_modal_visible_now}")
        assert is_modal_visible_now, "FAILED: #promptStudioModal did not open on click!"

        # Take screenshot of open modal
        await page.screenshot(path="screenshot_prompt_studio_modal_open.png")
        print("   📸 Screenshot saved to screenshot_prompt_studio_modal_open.png")

        # 3. Test Candidate Inputs and Presets
        print("\n3. Testing Presets...")
        prompt_a_val = await page.locator("#studioPromptA").input_value()
        print(f"   Candidate Prompt A pre-filled: {prompt_a_val[:60]}...")
        assert len(prompt_a_val) > 10

        # Click preset button "Pacing vs. Logistics & SLAs"
        preset_btn = page.locator("button:has-text('Pacing vs. Logistics & SLAs')")
        await preset_btn.click()
        prompt_a_new = await page.locator("#studioPromptA").input_value()
        print(f"   Preset swapped Candidate Prompt A to: {prompt_a_new[:60]}...")

        # 4. Click Close Studio
        print("\n4. Testing Modal Close button...")
        close_btn = page.locator("#promptStudioModal button:has-text('Close Studio')")
        await close_btn.click()
        await page.wait_for_timeout(300)
        is_modal_closed = not await page.locator("#promptStudioModal").is_visible()
        print(f"   Studio Modal closed successfully: {is_modal_closed}")
        assert is_modal_closed

        # 5. Re-open Modal and Apply a Prompt
        print("\n5. Re-opening Modal to test 'Use Prompt in Workspace'...")
        await btn.click()
        await page.wait_for_timeout(300)
        assert await page.locator("#promptStudioModal").is_visible()

        # Run quick evaluation in modal
        print("   Clicking 'Run Comparative Evaluation'...")
        run_eval_btn = page.locator("#runEvaluationBtn")
        await run_eval_btn.click()
        
        # Wait for evaluation results
        print("   Waiting for Vertex AI Gemini evaluation results...")
        await page.wait_for_selector("#studioResultsContainer:not(.hidden)", timeout=25000)
        
        results_visible = await page.locator("#studioResultsContainer").is_visible()
        synthesis_text = await page.locator("#studioSynthesisText").inner_text()
        winner_badge = await page.locator("#winningPromptBadge").inner_text()
        print(f"   Results Container visible: {results_visible}")
        print(f"   Winner Badge: {winner_badge}")
        print(f"   Synthesis: {synthesis_text[:80]}...")
        assert results_visible and len(synthesis_text) > 10

        # Click "Use Prompt in Workspace"
        apply_btn = page.locator("button:has-text('Use Prompt')").first
        await apply_btn.click()
        await page.wait_for_timeout(500)

        # Modal should close and toast should appear
        is_modal_closed_after_apply = not await page.locator("#promptStudioModal").is_visible()
        print(f"   Modal closed after selecting prompt: {is_modal_closed_after_apply}")
        assert is_modal_closed_after_apply

        # 6. Click Default Workflow Button "Please prepare the data to analyze the issue"
        print("\n6. Clicking 'Please prepare the data to analyze the issue' on Screen 1...")
        prep_btn = page.locator("#prepareDataBtn")
        await prep_btn.click()

        print("   Waiting for preparation steps and transition to Screen 2...")
        await page.wait_for_selector("#workspaceView:not(.hidden)", timeout=15000)
        
        is_workspace_active = await page.locator("#workspaceView").is_visible()
        is_alert_hidden = not await page.locator("#alertView").is_visible()
        is_modal_still_hidden = not await page.locator("#promptStudioModal").is_visible()
        print(f"   Transitioned to Screen 2 (#workspaceView): {is_workspace_active}")
        print(f"   Screen 1 (#alertView) is hidden: {is_alert_hidden}")
        print(f"   Studio Modal is hidden (did not mistakenly open): {is_modal_still_hidden}")
        assert is_workspace_active and is_alert_hidden and is_modal_still_hidden

        # Take final screenshot
        await page.screenshot(path="screenshot_screen2_workspace_active.png")
        print("   📸 Screenshot saved to screenshot_screen2_workspace_active.png")

        print("\nConsole Errors Encountered:", console_errors)
        assert len(console_errors) == 0, f"Errors found: {console_errors}"

        print("\n🎉 ALL LOCAL UI WORKFLOW TESTS PASSED 100% PERFECTLY!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_full_flow())
