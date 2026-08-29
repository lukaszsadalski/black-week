#!/usr/bin/env python3
"""
Gemini Enterprise Data Agents Cleanup & Reset Tool
=================================================
Lists and deletes all Gemini BigQuery Conversational Analytics Data Agents
in the target Google Cloud project (location: `global`).

Agents Managed:
---------------
1. Primary CMO Agent (`DATA_AGENT_ID` / `gda-lumiere-primary`)
2. Agent A (`gda-lumiere-a` - Incident Triage)
3. Agent B (`gda-lumiere-b` - Stockouts & Availability)
4. Agent C (`gda-lumiere-c` - Intraday Pacing & Ad Spend)
5. Any additional dynamic Data Agents discovered via the GCP API.

Usage:
------
  # Interactive confirmation
  python3 scripts/cleanup_data_agents.py

  # Non-interactive / CI/CD force deletion
  python3 scripts/cleanup_data_agents.py --force
"""

import os
import sys
import subprocess
import argparse
import requests
import time
from typing import List, Dict, Any, Optional


def load_dotenv():
    """Parses root-level .env file into os.environ."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_dotenv()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
LOCATION = "global"
DATA_AGENT_ID = os.environ.get("DATA_AGENT_ID") or os.environ.get("CA_DATA_AGENT_ID", "gda-lumiere-primary")


def get_access_token() -> str:
    """Retrieves GCP OAuth 2.0 access token via environment or gcloud CLI."""
    token = os.environ.get("GCP_ACCESS_TOKEN")
    if not token:
        gcloud_paths = ["/google/data/ro/teams/cloud-sdk/gcloud", "gcloud"]
        for gcloud_cmd in gcloud_paths:
            try:
                res = subprocess.run(
                    [gcloud_cmd, "auth", "print-access-token"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if res.returncode == 0 and res.stdout.strip():
                    token = res.stdout.strip()
                    break
            except Exception:
                continue
    return token or ""


def list_remote_data_agents(token: str, max_retries: int = 5) -> List[str]:
    """Queries Google Cloud API to list all active Data Agents in the project."""
    url = f"https://geminidataanalytics.googleapis.com/v1beta/projects/{PROJECT_ID}/locations/global/dataAgents"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": PROJECT_ID
    }
    discovered = []
    page_token = ""
    while True:
        req_url = f"{url}?pageToken={page_token}" if page_token else url
        for attempt in range(max_retries):
            try:
                r = requests.get(req_url, headers=headers, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    agents = data.get("dataAgents", [])
                    for a in agents:
                        a_name = a.get("name", "")
                        if a_name:
                            agent_id = a_name.split("/")[-1]
                            discovered.append(agent_id)
                    page_token = data.get("nextPageToken", "")
                    break
                elif r.status_code == 429 or (r.status_code == 403 and "quota" in r.text.lower()):
                    backoff = 3.0 * (1.5 ** attempt)
                    print(f"  ⏳ GCP rate limit encountered (HTTP {r.status_code}). Pausing {backoff:.1f}s before retry ({attempt + 1}/{max_retries})...")
                    time.sleep(backoff)
                    continue
                else:
                    break
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(2.0)
                else:
                    break

        if not page_token or not agents:
            break
    return list(dict.fromkeys(discovered))


def reset_data_agent(token: str, agent_id: str, max_retries: int = 5) -> bool:
    """Safely clears an agent's table groundings without triggering CCFE SOFT_DELETED tombstone."""
    url = f"https://geminidataanalytics.googleapis.com/v1beta/projects/{PROJECT_ID}/locations/global/dataAgents/{agent_id}?updateMask=displayName,description,dataAnalyticsAgent.publishedContext.datasourceReferences"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": PROJECT_ID
    }
    payload = {
        "displayName": f"LumiereShop Agent ({agent_id}) - Reset",
        "description": "Reset state: ungrounded for fresh deployment.",
        "dataAnalyticsAgent": {
            "publishedContext": {
                "datasourceReferences": {
                    "bq": {
                        "tableReferences": []
                    }
                }
            }
        }
    }
    for attempt in range(max_retries):
        try:
            r = requests.patch(url, headers=headers, json=payload, timeout=20)
            if r.status_code in [200, 201]:
                print(f"  ✅ Safely Reset Data Agent (ungrounded): {agent_id}")
                return True
            elif r.status_code == 404:
                print(f"  ℹ️ Data Agent '{agent_id}' does not exist (clean).")
                return True
            elif r.status_code == 429 or (r.status_code == 403 and "quota" in r.text.lower()):
                backoff = 3.0 * (1.5 ** attempt)
                print(f"    ⏳ GCP rate limit encountered (HTTP {r.status_code}). Pausing {backoff:.1f}s before retry...")
                time.sleep(backoff)
                continue
            else:
                err_msg = r.text[:200].replace("\n", " ")
                print(f"  ⚠️ Notice resetting Data Agent '{agent_id}' (HTTP {r.status_code}): {err_msg}")
                return False
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2.0)
            else:
                print(f"  ❌ Error resetting Data Agent '{agent_id}': {e}")
                return False
    return False


def delete_data_agent(token: str, agent_id: str, max_retries: int = 5) -> bool:
    """Deletes a single Data Agent via the Gemini Data Analytics REST API with exponential backoff."""
    url = f"https://geminidataanalytics.googleapis.com/v1beta/projects/{PROJECT_ID}/locations/global/dataAgents/{agent_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": PROJECT_ID
    }
    for attempt in range(max_retries):
        try:
            r = requests.delete(url, headers=headers, timeout=20)
            if r.status_code in [200, 204]:
                print(f"  ✅ Deleted Data Agent: {agent_id}")
                return True
            elif r.status_code == 404:
                print(f"  ℹ️ Data Agent '{agent_id}' does not exist (already clean).")
                return True
            elif r.status_code == 429 or (r.status_code == 403 and "quota" in r.text.lower()):
                backoff = 3.0 * (1.5 ** attempt)
                print(f"    ⏳ GCP rate limit encountered (HTTP {r.status_code}). Pausing {backoff:.1f}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(backoff)
                continue
            else:
                err_msg = r.text[:200].replace("\n", " ")
                print(f"  ⚠️ Could not delete Data Agent '{agent_id}' (HTTP {r.status_code}): {err_msg}")
                return False
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2.0)
            else:
                print(f"  ❌ Error deleting Data Agent '{agent_id}': {e}")
                return False
    return False


def cleanup_data_agents(hard_delete: bool = False):
    print("=" * 80)
    action_str = "HARD PURGE (DELETE)" if hard_delete else "SAFE RESET (UNGROUND CONTEXT)"
    print(f"🧹 GEMINI ENTERPRISE DATA AGENTS CLEANUP: {action_str}")
    print(f"Target Project ID : {PROJECT_ID}")
    print(f"Agent Location    : {LOCATION}")
    print("=" * 80)

    if not PROJECT_ID:
        print("ERROR: GCP_PROJECT_ID is not configured in .env file.", file=sys.stderr)
        sys.exit(1)

    token = get_access_token()
    if not token:
        print("ERROR: Could not retrieve GCP access token. Please run `gcloud auth application-default login`.", file=sys.stderr)
        sys.exit(1)

    # 1. Discover all remote agents + add known project agent IDs
    known_agents = [
        DATA_AGENT_ID,
        "gda-lumiere-primary",
        "gda-lumiere-a",
        "gda-lumiere-b",
        "gda-lumiere-c"
    ]
    remote_agents = list_remote_data_agents(token)
    all_agents = list(dict.fromkeys([a for a in (known_agents + remote_agents) if a]))

    print(f"\nFound {len(all_agents)} Data Agent candidate(s) to process:")
    for a in all_agents:
        source = "(Discovered via GCP API)" if a in remote_agents else "(Project Standard ID)"
        print(f"  • {a:<30} {source}")

    print(f"\nExecuting {'deletions' if hard_delete else 'safe context resets'}...")
    processed_count = 0
    for agent_id in all_agents:
        if hard_delete:
            if delete_data_agent(token, agent_id):
                processed_count += 1
        else:
            if reset_data_agent(token, agent_id):
                processed_count += 1
        time.sleep(0.35)

    print("\n" + "=" * 80)
    print(f"✨ DATA AGENT CLEANUP COMPLETE: {processed_count}/{len(all_agents)} processed!")
    print("To re-provision and ground all 4 agents from scratch, run:")
    print("  python3 scripts/06_update_data_agent.py")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Clean up or reset Gemini Enterprise BigQuery Data Agents.")
    parser.add_argument("--force", "-f", action="store_true", help="Bypass confirmation prompt")
    parser.add_argument("--hard-delete", action="store_true", help="Execute destructive DELETE (causes CCFE soft-delete tombstone)")
    args = parser.parse_args()

    if not args.force:
        action = "HARD DELETE" if args.hard_delete else "SAFE RESET"
        print(f"⚠️  WARNING: You are about to execute {action} for all Gemini BigQuery Data Agents on project '{PROJECT_ID}'.")
        choice = input("Are you sure you want to proceed? [y/N]: ").strip().lower()
        if choice not in ["y", "yes"]:
            print("Operation aborted by user.")
            sys.exit(0)

    cleanup_data_agents(hard_delete=args.hard_delete)


if __name__ == "__main__":
    main()
