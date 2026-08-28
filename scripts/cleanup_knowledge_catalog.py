#!/usr/bin/env python3
"""
Knowledge Catalog & Data Agent Environment Reset Tool
=====================================================
Safely deletes all LumièreShop metadata and governance resources from
Google Cloud Knowledge Catalog (AspectTypes, Glossaries, Terms, Categories, DataScans)
and Gemini Enterprise Data Agents.

This script ensures a completely clean slate for fresh installations on any GCP project
or new BigQuery dataset, preventing resource name collisions or stale metadata bindings.

Resources Cleaned:
------------------
1. Knowledge Catalog AspectTypes (location: `global`):
   - `enterprise-data-context`
2. Knowledge Catalog Business Glossaries (location: `global`):
   - `ecommerce-glossary` (including all categories, terms, and EntryLinks)
3. Knowledge Catalog DataScans (location: regional `BQ_LOCATION`):
   - `profile-payment-logs`
   - `profile-daily-ad-perf`
   - `profile-ad-creatives`
   - `profile-shipping-lead-times`
   - `profile-catalog-recommender`
4. Gemini Enterprise Agent Platform Data Agents (location: `global`):
   - `DATA_AGENT_ID` (e.g. `gda-lumiere-primary` or custom ID)
   - `gda-lumiere-a` (Incident Triage)
   - `gda-lumiere-b` (Stockouts & Availability)
   - `gda-lumiere-c` (Intraday Pacing & Ad Spend)

Usage:
------
  # Interactive confirmation
  python3 scripts/cleanup_knowledge_catalog.py

  # Non-interactive / CI/CD force deletion
  python3 scripts/cleanup_knowledge_catalog.py --force
"""

import os
import sys
import subprocess
import argparse
import requests
import time
from typing import List, Dict, Any


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
DATASET_ID = os.environ.get("BQ_DATASET_ID", "ecommerce_dw")
LOCATION = "global"
BQ_LOCATION = os.environ.get("BQ_LOCATION", "us-central1").lower()
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


def delete_resource(url: str, headers: Dict[str, str], resource_type: str, resource_name: str) -> bool:
    """Sends HTTP DELETE request and logs the result."""
    try:
        r = requests.delete(url, headers=headers, timeout=20)
        if r.status_code in [200, 204]:
            print(f"  ✅ Deleted {resource_type}: {resource_name}")
            return True
        elif r.status_code == 404:
            print(f"  ℹ️ {resource_type} '{resource_name}' does not exist (already clean).")
            return True
        else:
            err_msg = r.text[:200].replace("\n", " ")
            print(f"  ⚠️ Could not delete {resource_type} '{resource_name}' (HTTP {r.status_code}): {err_msg}")
            return False
    except Exception as e:
        print(f"  ❌ Error deleting {resource_type} '{resource_name}': {e}")
        return False


def delete_all_entry_links(token: str, entry_locations: List[str]):
    """Purges all EntryLinks across BigQuery and Dataplex entryGroups."""
    headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": PROJECT_ID}
    print(f"\n[Step 1/5] Purging Knowledge Catalog EntryLinks across locations {entry_locations}...")
    
    deleted_links = 0
    for loc in entry_locations:
        for eg in ["@bigquery", "@dataplex"]:
            url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{loc}/entryGroups/{eg}/entryLinks?pageSize=300"
            page_token = ""
            while True:
                req_url = f"{url}&pageToken={page_token}" if page_token else url
                try:
                    r = requests.get(req_url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        links = data.get("entryLinks", [])
                        for l in links:
                            l_name = l.get("name", "")
                            if l_name:
                                link_id = l_name.split("/")[-1]
                                if delete_resource(f"https://dataplex.googleapis.com/v1/{l_name}", headers, "EntryLink", link_id):
                                    deleted_links += 1
                        page_token = data.get("nextPageToken", "")
                        if not page_token or not links:
                            break
                    else:
                        break
                except Exception:
                    break


def delete_all_glossary_terms(token: str, glossary_id: str):
    """Deletes all terms from the glossary using full pagination and local config enumeration."""
    headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": PROJECT_ID}
    base_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/glossaries/{glossary_id}"

    term_ids = set()

    # 1. Enumerate all term IDs from local config files
    for cfg_name in ["business_glossary.json", "business_glossary.yaml"]:
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", cfg_name)
        if os.path.exists(cfg_path):
            try:
                if cfg_name.endswith(".json"):
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        data = json.load(f).get("glossary", {})
                        for t in data.get("terms", []):
                            if t.get("id"):
                                term_ids.add(t["id"])
                elif cfg_name.endswith(".yaml"):
                    try:
                        import yaml
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f).get("glossary", {})
                            for t in data.get("terms", []):
                                if t.get("id"):
                                    term_ids.add(t["id"])
                    except Exception:
                        pass
            except Exception:
                pass

    # 2. Paginate over all terms from GCP API
    page_token = ""
    while True:
        url = f"{base_url}/terms?pageSize=300"
        if page_token:
            url += f"&pageToken={page_token}"
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                terms = data.get("terms", [])
                for t in terms:
                    t_name = t.get("name", "")
                    if t_name:
                        term_ids.add(t_name.split("/")[-1])
                page_token = data.get("nextPageToken", "")
                if not page_token or not terms:
                    break
            else:
                break
        except Exception:
            break

    print(f"  Found {len(term_ids)} glossary terms to purge...")
    for t_id in sorted(term_ids):
        delete_resource(f"{base_url}/terms/{t_id}", headers, "Glossary Term", t_id)


def delete_all_glossary_categories(token: str, glossary_id: str):
    """Deletes all categories from the glossary using full pagination and local config enumeration."""
    headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": PROJECT_ID}
    base_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/glossaries/{glossary_id}"

    cat_ids = set()

    # 1. Enumerate all category IDs from local config files
    for cfg_name in ["business_glossary.json", "business_glossary.yaml"]:
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", cfg_name)
        if os.path.exists(cfg_path):
            try:
                if cfg_name.endswith(".json"):
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        data = json.load(f).get("glossary", {})
                        for c in data.get("categories", []):
                            if c.get("id"):
                                cat_ids.add(c["id"])
                elif cfg_name.endswith(".yaml"):
                    try:
                        import yaml
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f).get("glossary", {})
                            for c in data.get("categories", []):
                                if c.get("id"):
                                    cat_ids.add(c["id"])
                    except Exception:
                        pass
            except Exception:
                pass

    # 2. Paginate over all categories from GCP API
    page_token = ""
    while True:
        url = f"{base_url}/categories?pageSize=300"
        if page_token:
            url += f"&pageToken={page_token}"
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                cats = data.get("categories", [])
                for c in cats:
                    c_name = c.get("name", "")
                    if c_name:
                        cat_ids.add(c_name.split("/")[-1])
                page_token = data.get("nextPageToken", "")
                if not page_token or not cats:
                    break
            else:
                break
        except Exception:
            break

    print(f"  Found {len(cat_ids)} glossary categories to purge...")
    for c_id in sorted(cat_ids):
        delete_resource(f"{base_url}/categories/{c_id}", headers, "Glossary Category", c_id)


def cleanup_knowledge_catalog():
    print("=" * 80)
    print("🧹 LUMIÈRESHOP KNOWLEDGE CATALOG & DATA AGENT CLEANUP")
    print(f"Target Project ID : {PROJECT_ID}")
    print(f"BigQuery Dataset  : {DATASET_ID}")
    print(f"Aspect Location   : {LOCATION}")
    print(f"Scan Location     : {BQ_LOCATION}")
    print("=" * 80)

    if not PROJECT_ID:
        print("ERROR: GCP_PROJECT_ID is not configured in .env file.", file=sys.stderr)
        sys.exit(1)

    token = get_access_token()
    if not token:
        print("ERROR: Could not retrieve GCP access token. Please run `gcloud auth application-default login`.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-goog-user-project": PROJECT_ID
    }

    # --------------------------------------------------------------------------
    # 1. Delete EntryLinks
    # --------------------------------------------------------------------------
    entry_locs = list(dict.fromkeys([BQ_LOCATION, "us-central1", "europe-west4", "global"]))
    delete_all_entry_links(token, entry_locs)

    # --------------------------------------------------------------------------
    # 2. Delete Business Glossaries, Terms, and Categories
    # --------------------------------------------------------------------------
    print("\n[Step 2/5] Purging Knowledge Catalog Business Glossaries & Terms...")
    glossary_id = "ecommerce-glossary"
    delete_all_glossary_terms(token, glossary_id)
    delete_all_glossary_categories(token, glossary_id)
    glossary_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/glossaries/{glossary_id}"
    delete_resource(glossary_url, headers, "Business Glossary", glossary_id)

    # --------------------------------------------------------------------------
    # 3. Delete Custom AspectTypes
    # --------------------------------------------------------------------------
    print("\n[Step 3/5] Purging Custom AspectTypes...")
    aspect_type_id = "enterprise-data-context"
    aspect_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/aspectTypes/{aspect_type_id}"
    delete_resource(aspect_url, headers, "AspectType", aspect_type_id)

    # --------------------------------------------------------------------------
    # 4. Delete DataScans (Data Profiling)
    # --------------------------------------------------------------------------
    print(f"\n[Step 4/5] Purging Knowledge Catalog DataScans across {entry_locs}...")
    data_scans = [
        "profile-payment-logs",
        "profile-daily-ad-perf",
        "profile-ad-creatives",
        "profile-shipping-lead-times",
        "profile-catalog-recommender"
    ]
    for loc in entry_locs:
        for scan_id in data_scans:
            scan_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{loc}/dataScans/{scan_id}"
            delete_resource(scan_url, headers, f"DataScan ({loc})", scan_id)

    # --------------------------------------------------------------------------
    # 5. Delete Gemini Data Agents
    # --------------------------------------------------------------------------
    print("\n[Step 5/5] Purging Gemini Enterprise Data Agents...")
    agent_ids = list(dict.fromkeys([
        DATA_AGENT_ID,
        "gda-lumiere-primary",
        "gda-lumiere-a",
        "gda-lumiere-b",
        "gda-lumiere-c"
    ]))
    for agent_id in agent_ids:
        if not agent_id:
            continue
        agent_url = f"https://geminidataanalytics.googleapis.com/v1beta/projects/{PROJECT_ID}/locations/global/dataAgents/{agent_id}"
        delete_resource(agent_url, headers, "Data Agent", agent_id)

    print("\n" + "=" * 80)
    print("✨ KNOWLEDGE CATALOG & DATA AGENT PURGE COMPLETE!")
    print("You can now safely re-run full turnkey provisioning:")
    print("  python3 scripts/bootstrap_new_project.py")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Purge Knowledge Catalog and Data Agent resources.")
    parser.add_argument("--force", "-f", action="store_true", help="Bypass confirmation prompt")
    args = parser.parse_args()

    if not args.force:
        print(f"⚠️  WARNING: You are about to DELETE all Knowledge Catalog Glossaries, AspectTypes, DataScans, and Data Agents on project '{PROJECT_ID}'.")
        choice = input("Are you sure you want to proceed? [y/N]: ").strip().lower()
        if choice not in ["y", "yes"]:
            print("Operation aborted by user.")
            sys.exit(0)

    cleanup_knowledge_catalog()


if __name__ == "__main__":
    main()

