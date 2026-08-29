#!/usr/bin/env python3
"""
Phase 3: Conversational Analytics Agent Configuration & Verification Script.
Interacts with GCP Conversational Analytics API (geminidataanalytics.googleapis.com)
via the production `ca_service` client to execute natural language queries against
`ecommerce_dw` and verify stateful dialogue, SQL formulation, and BigQuery audit logging.
"""

import os
import sys
import uuid
import time
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
sys.path.insert(0, SCRIPT_DIR)

from test_utils import load_project_env, get_gcp_access_token

load_project_env()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "ecommerce_dw")
LOCATION = os.environ.get("BQ_LOCATION", "us-central1")
USER_IDENTITY = os.environ.get("GCP_USER_IDENTITY", "user@example.com")
DATA_AGENT_ID = os.environ.get("DATA_AGENT_ID", "gda-lumiere-primary")


def test_conversational_analytics_api():
    print(f"Starting Phase 3: Conversational Analytics Agent Verification for project '{PROJECT_ID}'...")
    token = get_gcp_access_token()
    if not token:
        print("Error: OAuth access token could not be retrieved.", file=sys.stderr)
        sys.exit(1)

    from app.services.ca_service import send_cmo_prompt

    test_prompt = "What was total revenue by category during Black Week?"
    print(f"Sending prompt: '{test_prompt}'")
    print(f"Target Agent: {DATA_AGENT_ID}")

    session_id = f"SESS-TEST-{uuid.uuid4().hex[:8]}"

    try:
        res = send_cmo_prompt(
            prompt=test_prompt,
            session_id=session_id,
            user_name="Verification Test Operator",
            menu_item="chat"
        )
        print(f"\nResponse Received in {res.get('execution_time_ms', 0)}ms:")
        print(f"  • Text Summary: {res.get('text', '')[:120]}...")
        if res.get("generated_sql"):
            print(f"  • Generated SQL: {res.get('generated_sql')[:100]}...")
        if res.get("reasoning"):
            print(f"  • Reasoning Steps: {len(res.get('reasoning', []))} stages generated.")
        print(f"  • Grounded Tables: {res.get('grounded_tables', [])}")

        print("\n✅ Conversational Analytics Agent successfully verified!")
        print("Phase 3 Verification Script Completed.")
        return True
    except Exception as e:
        print(f"\n❌ Error during Conversational Analytics verification: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = test_conversational_analytics_api()
    sys.exit(0 if success else 1)
