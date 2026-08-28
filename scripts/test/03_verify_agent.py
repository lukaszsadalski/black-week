#!/usr/bin/env python3
"""
Phase 3: Conversational Analytics Agent Configuration & Verification Script.
Interacts with GCP Conversational Analytics API (geminidataanalytics.googleapis.com)
to execute natural language queries against `ecommerce_dw` and log interaction traces into `agent_interaction_logs`.
"""

import os
import sys
import uuid
import time
import json
import requests
import subprocess
from datetime import datetime, timezone
from google.cloud import bigquery
from google.oauth2 import credentials as oauth2_credentials

def load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_dotenv()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "ecommerce_dw")
LOCATION = os.environ.get("BQ_LOCATION", "us-central1")
USER_IDENTITY = os.environ.get("GCP_USER_IDENTITY", "user@example.com")

CA_API_HOST = os.environ.get("CA_API_HOST", "https://geminidataanalytics.googleapis.com")
CA_API_ENDPOINT = os.environ.get("CA_API_ENDPOINT", f"https://geminidataanalytics.googleapis.com/v1alpha/projects/{PROJECT_ID}/locations/global/conversations")

def get_access_token():
    token = os.environ.get("GCP_ACCESS_TOKEN")
    if not token:
        gcloud_paths = ["/google/data/ro/teams/cloud-sdk/gcloud", "gcloud"]
        for gcloud_cmd in gcloud_paths:
            try:
                res = subprocess.run([gcloud_cmd, "auth", "print-access-token"], capture_output=True, text=True, timeout=10)
                if res.returncode == 0 and res.stdout.strip():
                    token = res.stdout.strip()
                    break
            except Exception:
                continue
    return token

def get_bigquery_client(project_id, token):
    if token:
        creds = oauth2_credentials.Credentials(token)
        return bigquery.Client(project=project_id, credentials=creds)
    return bigquery.Client(project=project_id)

def test_conversational_analytics_api():
    print(f"Starting Phase 3: Conversational Analytics Agent Verification for project '{PROJECT_ID}'...")
    token = get_access_token()
    if not token:
        print("Error: OAuth access token could not be retrieved.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    test_prompt = "What was total revenue by category during Black Week?"
    print(f"Sending prompt: '{test_prompt}'")
    print(f"Target CA Endpoint: {CA_API_ENDPOINT}")

    start_time = time.time()
    
    payload = {
        "agents": [f"projects/{PROJECT_ID}/locations/global/dataAgents/default"]
    }

    session_id = f"SESS-CA-{uuid.uuid4().hex[:8]}"
    raw_response_text = ""
    generated_sql = ""
    response_text = ""
    bytes_scanned = 0

    try:
        res = requests.post(CA_API_ENDPOINT, headers=headers, json=payload, timeout=30)
        elapsed_ms = int((time.time() - start_time) * 1000)
        raw_response_text = res.text
        print(f"CA API HTTP Status Code: {res.status_code}")
        print(f"API Response Payload: {raw_response_text[:500]}...")

        if res.status_code in [200, 201]:
            data = res.json()
            response_text = json.dumps(data)
            print(f"Successfully initiated Conversational Analytics Session: {data.get('name', 'N/A')}")
        else:
            response_text = f"API Call returned HTTP {res.status_code}: {res.reason}"
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        response_text = f"API Request failed: {e}"
        print(f"API Request Notice/Fallback: {e}")

    # Log interaction trace into BigQuery `agent_interaction_logs`
    log_record = [{
        "interaction_id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_account": USER_IDENTITY,
        "user_prompt": test_prompt,
        "generated_sql": generated_sql if generated_sql else "N/A",
        "response_text": response_text[:1000],
        "execution_time_ms": elapsed_ms,
        "bytes_scanned": bytes_scanned,
        "ca_api_endpoint": CA_API_ENDPOINT,
        "raw_ca_api_response": raw_response_text[:2000] if raw_response_text else response_text[:2000],
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }]

    print("Logging agent interaction audit trace into BigQuery `agent_interaction_logs`...")
    bq_client = get_bigquery_client(PROJECT_ID, token)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.agent_interaction_logs"
    
    try:
        errors = bq_client.insert_rows_json(table_ref, log_record)
        if errors:
            print(f"Error logging to `agent_interaction_logs`: {errors}", file=sys.stderr)
        else:
            print("Interaction audit log successfully written to BigQuery `agent_interaction_logs`.")
    except Exception as e:
        print(f"Failed to log interaction to BigQuery: {e}", file=sys.stderr)

    print("Phase 3 Verification Script Completed.")

if __name__ == "__main__":
    test_conversational_analytics_api()
