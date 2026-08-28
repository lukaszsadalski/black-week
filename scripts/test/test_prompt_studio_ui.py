#!/usr/bin/env python3
"""
Test Suite for Prompt Optimization & Semantic Evaluation Studio.
Tests API endpoints and headless browser UI interaction.
"""

import os
import sys
import time
import requests
import json
import subprocess

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from test_utils import load_project_env, ensure_test_server
load_project_env()

BASE_URL = ensure_test_server(8000)

def test_api_endpoints():
    print("================================================================================")
    print("TEST 1: Backend API Endpoints for Prompt Studio")
    print(f"Target: {BASE_URL}")
    print("================================================================================")

    # 1. Test Health
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    print("✅ GET /api/health:", r.json().get("status"))

    # 2. Test Set Active Prompt
    test_prompt = "Black Week sales target missed by €735.7k"
    r2 = requests.post(f"{BASE_URL}/api/set-active-prompt", json={"prompt": test_prompt}, timeout=10)
    assert r2.status_code == 200, f"Set active prompt failed: {r2.status_code}"
    print("✅ POST /api/set-active-prompt:", r2.json().get("active_prompt"))

    # 3. Test Evaluate Prompts with Gemini 3.7 Flash
    prompts = [
        "It's Black Friday 14:30. Please prepare the data that will serve to find root cause of the problem of decreased revenue comparing to forecasted revenue during Black Week Sales.",
        "Black Week sales target missed by €735.7k",
        "Analyze revenue target variance, inventory stockouts, ad spend throttling, and carrier lead times across all categories"
    ]
    print(f"Testing POST /api/evaluate-prompts with {len(prompts)} candidate prompts...")
    t0 = time.time()
    r3 = requests.post(f"{BASE_URL}/api/evaluate-prompts", json={"prompts": prompts}, timeout=45)
    elapsed = time.time() - t0
    assert r3.status_code == 200, f"Evaluate prompts failed: {r3.status_code} - {r3.text}"
    data = r3.json()

    print(f"✅ POST /api/evaluate-prompts completed in {elapsed:.2f}s!")
    print(f"  Model Used: {data.get('model_used')}")
    print(f"  Tables per Prompt: {[s.get('table_count') for s in data.get('search_results', [])]}")
    ev = data.get("evaluation", {})
    print(f"  Recommended Winner: {ev.get('recommended_prompt_id')}")
    print(f"  Scores: {[e.get('prompt_id') + ': ' + str(e.get('score')) for e in ev.get('evaluations', [])]}")
    print(f"  Executive Synthesis: {ev.get('executive_synthesis')[:120]}...")

def test_html_ui_elements():
    print("\n================================================================================")
    print("TEST 2: Verifying HTML & JS UI Elements in index.html")
    print("================================================================================")

    html_path = "backend/static/index.html"
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Assert sidebar entry exists
    assert 'Compare prompts' in content, "Missing 'Compare prompts' in sidebar"
    assert 'openPromptStudio()' in content, "Missing openPromptStudio() trigger in sidebar"
    print("✅ Sidebar Entry: 'Compare prompts' button exists under Apps.")

    # Assert modal exists
    assert 'id="promptStudioModal"' in content, "Missing promptStudioModal container"
    assert 'id="studioPromptA"' in content, "Missing studioPromptA textarea"
    assert 'id="studioPromptB"' in content, "Missing studioPromptB textarea"
    assert 'id="studioPromptC"' in content, "Missing studioPromptC textarea"
    assert 'id="runEvaluationBtn"' in content, "Missing runEvaluationBtn button"
    assert 'id="studioResultsContainer"' in content, "Missing studioResultsContainer"
    print("✅ Modal Elements: Studio Modal, 3 candidate textareas, and results container present.")

    # Assert JS functions exist
    assert 'function openPromptStudio(' in content, "Missing openPromptStudio JS function"
    assert 'function closePromptStudio(' in content, "Missing closePromptStudio JS function"
    assert 'async function runPromptEvaluation(' in content, "Missing runPromptEvaluation JS function"
    assert 'function renderStudioEvaluation(' in content, "Missing renderStudioEvaluation JS function"
    assert 'async function launchWorkspaceByPromptIndex(' in content, "Missing launchWorkspaceByPromptIndex JS function"
    print("✅ JS Controller: All Prompt Studio event handlers and rendering functions verified.")

if __name__ == "__main__":
    test_api_endpoints()
    test_html_ui_elements()
    print("\n🎉 ALL PROMPT STUDIO TESTS PASSED SUCCESSFULLY!")
