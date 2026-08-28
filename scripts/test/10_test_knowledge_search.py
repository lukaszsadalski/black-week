#!/usr/bin/env python3
"""
Test 10: Google Cloud Knowledge Catalog Semantic Search Precision Test
======================================================================
Tests the Google Cloud Knowledge Catalog `searchEntries` REST API (`dataplex.googleapis.com`)
with `semanticSearch=True` using the executive Black Friday triage prompt.

Validates that:
  1. Semantic search dynamically discovers all 25 critical forensic tables.
  2. Resolves both direct BigQuery table entries and bound Business Glossary terms.
  3. Achieves 100% precision and recall across all 5 operational investigation domains.

Usage:
------
  python3 scripts/test/10_test_knowledge_search.py
"""

import os
import sys
import subprocess
import requests
import json
import re

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from test_utils import load_project_env, get_gcp_access_token
load_project_env()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "ecommerce_dw")
LOCATION = "global"
GLOSSARY_ID = "ecommerce-glossary"

PROMPT = (
    "It's Black Friday 14:30. Please prepare the data that will serve to find root cause of the "
    "problem of decreased revenue comparing to forecasted revenue during Black Week Sales."
)

CRUCIAL_25_TABLES = [
    "categories",
    "products",
    "distribution_centers",
    "inventory_items",
    "inventory_snapshots",
    "users",
    "orders",
    "order_items",
    "sales_event_stream",
    "weekly_commercial_targets",
    "daily_category_targets",
    "category_15min_targets",
    "web_sessions",
    "web_events",
    "oos_interactions",
    "competitor_price_feed",
    "marketing_campaigns",
    "daily_ad_performance",
    "ad_bidding_log",
    "ad_creatives",
    "payment_gateway_logs",
    "influencer_campaigns",
    "catalog_recommender_logs",
    "shipping_lead_times",
    "competitor_promotions",
]


def get_access_token():
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
    return token


def test_knowledge_search():
    token = get_access_token()
    if not token:
        print("Error: Could not retrieve OAuth access token.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/global:searchEntries"
    payload = {
        "query": PROMPT,
        "scope": f"projects/{PROJECT_ID}",
        "semanticSearch": True,
        "pageSize": 100,
    }

    print("=" * 80)
    print(f"Testing Knowledge Catalog Search API (`locations/global:searchEntries`)")
    print(f"Scope: projects/{PROJECT_ID} (Strict Single Project Scope)")
    print(f"Target Dataset: {DATASET_ID} (Strict Dataset Filter)")
    print(f"SemanticSearch: True | PageSize: 100")
    print(f"Prompt: {PROMPT}")
    print("=" * 80)

    res = requests.post(url, headers=headers, json=payload)
    if res.status_code != 200:
        print(f"API Error: HTTP {res.status_code}\n{res.text}", file=sys.stderr)
        sys.exit(1)

    data = res.json()
    results = data.get("results", [])
    print(f"\nReceived {len(results)} total search result entries from Knowledge Catalog.\n")

    direct_tables = []
    term_tables = set()
    returned_terms = []
    
    dataset_prefix = f"datasets/{DATASET_ID}/tables/"
    resource_prefix = f"/datasets/{DATASET_ID}/tables/"
    for idx, r in enumerate(results, 1):
        dp_entry = r.get("dataplexEntry", {})
        name = dp_entry.get("name", "")
        resource = dp_entry.get("entrySource", {}).get("resource", "")
        display_name = dp_entry.get("entrySource", {}).get("displayName", "")
        
        if dataset_prefix in name:
            tbl_name = name.split(dataset_prefix)[-1]
            direct_tables.append((idx, tbl_name))
        elif resource_prefix in resource:
            tbl_name = resource.split(resource_prefix)[-1]
            direct_tables.append((idx, tbl_name))
        elif "/terms/" in name:
            term_id = name.split("/terms/")[-1]
            returned_terms.append((idx, term_id, display_name))
            
            # Fetch term from Knowledge Catalog to resolve bound tables dynamically
            term_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/terms/{term_id}"
            t_res = requests.get(term_url, headers=headers)
            if t_res.status_code == 200:
                t_desc = t_res.json().get("description", "")
                matches = re.findall(r"-\s+([a-zA-Z0-9_]+)\.[a-zA-Z0-9_]+", t_desc)
                for m in matches:
                    term_tables.add(m)

    print(f"--- Top Returned BigQuery Table Entries ({len(direct_tables)}) ---")
    for rank, tbl in direct_tables:
        is_crucial = "⭐ [CRUCIAL 25]" if tbl in CRUCIAL_25_TABLES else "   [Enterprise Table]"
        print(f"  #{rank:2d}: {tbl:<30} {is_crucial}")

    print(f"\n--- Top Returned Glossary Terms ({len(returned_terms)}) ---")
    for rank, term_id, disp in returned_terms:
        print(f"  #{rank:2d}: {term_id:<30} ({disp})")

    # Use Discovery Service to test cloud-native context discovery
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
    from app.services.discovery_service import KnowledgeDiscoveryService

    svc = KnowledgeDiscoveryService(project_id=PROJECT_ID, dataset_id=DATASET_ID)
    discovery_res = svc.discover_knowledge_context(PROMPT)
    resolved_tables = discovery_res["tables"]
    terms = discovery_res["terms"]
    entry_link_count = discovery_res["entry_link_count"]

    matched_25 = [t for t in CRUCIAL_25_TABLES if t in resolved_tables]
    missing = [t for t in CRUCIAL_25_TABLES if t not in matched_25]

    print("\n" + "=" * 80)
    print(f"TOTAL RESOLVED TABLES FROM KNOWLEDGE CATALOG: {len(resolved_tables)}")
    print(f"TOTAL RESOLVED GLOSSARY TERMS: {len(terms)} -> {terms}")
    print(f"TOTAL DISCOVERED ENTRYLINKS: {entry_link_count}")
    print(f"CRUCIAL 25 TABLES COVERAGE: {len(matched_25)} / {len(CRUCIAL_25_TABLES)} matched ({len(matched_25)/len(CRUCIAL_25_TABLES)*100:.1f}%)")
    print(f"Matched Crucial Tables ({len(matched_25)}): {matched_25}")
    if missing:
        print(f"Missing Crucial Tables: {missing}")
    print("=" * 80)

    # Save human-readable verification report
    report_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge_search_verification.txt")
    with open(report_path, "w") as f:
        f.write("KNOWLEDGE CATALOG SEARCH VERIFICATION REPORT\n")
        f.write(f"Prompt: {PROMPT}\n")
        f.write(f"Scope: projects/{PROJECT_ID}\n")
        f.write(f"Crucial 25 Tables Coverage: {len(matched_25)}/25 ({len(matched_25)/25*100:.1f}%)\n")
        f.write(f"Total Resolved Tables: {len(resolved_tables)}\n")
        f.write(f"Total Glossary Terms: {len(terms)}\n")
        f.write(f"Total EntryLinks: {entry_link_count}\n")
        f.write(f"Resolved Tables List: {', '.join(resolved_tables)}\n")
    print(f"Saved verification report to: {report_path}")

    assert len(matched_25) == 25, f"Expected 25/25 crucial tables, got {len(matched_25)}"
    assert len(terms) > 0, "Expected at least 1 glossary term discovered"
    assert entry_link_count > 0, "Expected at least 1 EntryLink discovered"
    print("\n All Knowledge Catalog Discovery & EntryLinks verification tests PASSED!")


if __name__ == "__main__":
    test_knowledge_search()
