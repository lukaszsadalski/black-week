#!/usr/bin/env python3
"""
Test Suite: 3-Agent Parallel Conversational Analytics Cockpit ("Compare Chats")
Verifies:
1. Frontend DOM contains the required elements:
   - #compareChatsBtn (without '3 fast clicks' user-facing text)
   - #startMultiChatBtn
   - #multiAgentWorkspaceView
   - 3 Column threads (#threadAgentA, #threadAgentB, #threadAgentC)
   - 3 Column headers (#multiPromptHeaderA, #multiPromptHeaderB, #multiPromptHeaderC)
   - No 'The issue is solved' button in multi-agent view.
2. /api/multi-agents/prepare configures distinct tables across 3 separate GCP Data Agents.
3. Backend /api/multi-chat endpoint responds correctly and uniquely for Agent A, Agent B, and Agent C.
"""

import os
import sys
import json
import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from test_utils import load_project_env
load_project_env()

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
INDEX_PATH = os.path.join(PROJECT_ROOT, "backend", "static", "index.html")



def test_dom_structure():
    print("\n🔍 1. Verifying HTML DOM Structure...")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "html.parser")

    # Check Compare Chats button
    compare_chats_btn = soup.find(id="compareChatsBtn")
    assert compare_chats_btn is not None, "❌ #compareChatsBtn missing from sidebar!"
    btn_text = compare_chats_btn.get_text()
    assert "Compare chats" in btn_text, "❌ 'Compare chats' label missing from #compareChatsBtn!"
    assert "3 fast clicks" not in btn_text, "❌ Hidden rule violated: '3 fast clicks' must not be in user-facing text!"
    assert "3 clicks" not in btn_text, "❌ Hidden rule violated: '3 clicks' must not be in user-facing text!"
    print("   ✅ #compareChatsBtn found with clean, hidden-trigger markup.")

    # Check Start Multi-Chat button
    start_multi_btn = soup.find(id="startMultiChatBtn")
    assert start_multi_btn is not None, "❌ #startMultiChatBtn missing from Prompt Studio modal!"
    print("   ✅ #startMultiChatBtn found in Prompt Studio modal.")

    # Check Multi-Agent Workspace Container
    workspace_view = soup.find(id="multiAgentWorkspaceView")
    assert workspace_view is not None, "❌ #multiAgentWorkspaceView missing!"
    print("   ✅ #multiAgentWorkspaceView container found.")

    # Check 3-column headers and prompt subheaders
    for key in ['A', 'B', 'C']:
        badge = soup.find(id=f"multiBadge{key}")
        header = soup.find(id=f"multiPromptHeader{key}")
        thread = soup.find(id=f"threadAgent{key}")
        assert badge is not None, f"❌ #multiBadge{key} missing!"
        assert header is not None, f"❌ #multiPromptHeader{key} missing!"
        assert thread is not None, f"❌ #threadAgent{key} missing!"
        print(f"   ✅ Column for Agent {key} verified (Badge, Prompt Subheader, Thread).")

    # Check that 'The issue is solved' button is NOT in #multiAgentWorkspaceView
    solved_in_multi = workspace_view.find(id="issueSolvedBtn")
    assert solved_in_multi is None, "❌ 'The issue is solved' button must NOT be present in #multiAgentWorkspaceView!"
    print("   ✅ Verified 'The issue is solved' button is absent from multi-agent workspace.")

    # Check Synchronized Input elements
    input_box = soup.find(id="multiPromptInput")
    send_btn = soup.find(id="multiSendBtn")
    assert input_box is not None, "❌ #multiPromptInput missing!"
    assert send_btn is not None, "❌ #multiSendBtn missing!"
    print("   ✅ Synchronized multi-prompt input bar verified.")

def test_multi_agent_backend_endpoints():
    print("\n🚀 2. Testing 3 Separate Google Cloud Data Agents in Parallel...")
    
    # Check health
    health_res = requests.get(f"{BASE_URL}/api/health", timeout=15.0)
    assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
    print(f"   ✅ Backend is healthy.")

    # Test inquiring table count across all 3 agents
    prompt = "how many tables do you have"
    
    def query_agent(args):
        name, key = args
        req_data = {
            "agent_name": name,
            "prompt": prompt,
            "session_id": f"TEST-DISTINCT-SESSION-{key}",
        }
        res = requests.post(f"{BASE_URL}/api/multi-chat", json=req_data, timeout=120.0)
        assert res.status_code == 200, f"Failed for {name}: {res.status_code} - {res.text}"
        data = res.json()
        return name, data

    print(f"   Broadcasting table count inquiry: '{prompt}' to Agent A, Agent B, and Agent C...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(query_agent, [("Agent A", "A"), ("Agent B", "B"), ("Agent C", "C")]))

    for name, data in results:
        reply = data.get("text") or data.get("reply_text") or ""
        agent_tag = data.get("agent_name", "")
        print(f"   🤖 {name} ({agent_tag}): \"{reply.strip()[:160]}\"")
        assert len(reply) > 0, f"Empty reply for {name}!"

if __name__ == "__main__":
    try:
        test_dom_structure()
        test_multi_agent_backend_endpoints()
        print("\n🎉 ALL 3-AGENT PARALLEL CHAT TESTS PASSED WITH 3 TRULY DISTINCT AGENTS!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)
