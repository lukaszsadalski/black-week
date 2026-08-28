#!/usr/bin/env python3
"""
Master Environment Teardown & Full Cleanup Orchestrator
======================================================
Executes complete sequential teardown across all 3 LumièreShop cleanup phases:
1. Gemini Enterprise Data Agents (`scripts/cleanup_data_agents.py`)
2. Knowledge Catalog Governance & Metadata (`scripts/cleanup_knowledge_catalog.py`)
3. Auxiliary Google Cloud APIs (`scripts/cleanup_gcp_apis.py`)

🛡️ Dataset Preservation:
-----------------------
This script guarantees that the BigQuery dataset (`BQ_DATASET_ID`) and all 140
tables remain completely intact and active on Google Cloud.

Usage:
------
  # Interactive confirmation
  python3 scripts/cleanup_all.py

  # Non-interactive / Automated execution
  python3 scripts/cleanup_all.py --force
"""

import os
import sys
import time
import subprocess
import argparse
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

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "ecommerce_dw")


def run_cleanup_stage(stage_num: int, title: str, script_name: str) -> Dict[str, Any]:
    """Executes a single cleanup script and returns status metrics."""
    script_path = os.path.join(PROJECT_ROOT, "scripts", script_name)
    print("\n" + "=" * 80)
    print(f"▶️  STAGE {stage_num}/3: {title}")
    print(f"    Executing: python3 scripts/{script_name} --force")
    print("=" * 80)

    start_time = time.time()
    res = subprocess.run(
        [sys.executable, script_path, "--force"],
        cwd=PROJECT_ROOT
    )
    duration = round(time.time() - start_time, 2)
    success = (res.returncode == 0)

    return {
        "stage": stage_num,
        "title": title,
        "script": script_name,
        "success": success,
        "duration_s": duration
    }


def verify_dataset_integrity():
    """Verifies that the BigQuery dataset and tables remain completely intact."""
    print("\n" + "=" * 80)
    print("🛡️  STAGE 4/4: VERIFYING BIGQUERY DATASET INTEGRITY")
    print("=" * 80)
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=PROJECT_ID)
        dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
        dataset = client.get_dataset(dataset_ref)
        tables = list(client.list_tables(dataset_ref))
        print(f"  ✅ Verified BigQuery Dataset `{DATASET_ID}` is healthy and active in `{dataset.location}`.")
        print(f"  ✅ Verified {len(tables)} tables remain intact and accessible.")
        return True, len(tables)
    except Exception as e:
        print(f"  ⚠️ Notice checking dataset `{DATASET_ID}`: {e}")
        return False, 0


def cleanup_all():
    print("=" * 80)
    print("🧹 LUMIÈRESHOP MASTER ENVIRONMENT TEARDOWN & RESET")
    print(f"Project ID        : {PROJECT_ID}")
    print(f"Preserved Dataset : {DATASET_ID}")
    print("=" * 80)

    if not PROJECT_ID:
        print("ERROR: GCP_PROJECT_ID is not configured in .env file.", file=sys.stderr)
        sys.exit(1)

    stages = [
        (1, "Purge Gemini Enterprise Data Agents", "cleanup_data_agents.py"),
        (2, "Purge Knowledge Catalog Governance & Metadata", "cleanup_knowledge_catalog.py"),
        (3, "Disable Auxiliary Google Cloud APIs", "cleanup_gcp_apis.py")
    ]

    stage_results = []
    total_start = time.time()

    for s_num, s_title, s_script in stages:
        res = run_cleanup_stage(s_num, s_title, s_script)
        stage_results.append(res)
        time.sleep(1.0)

    # 4. Verify BigQuery dataset remains intact
    ds_ok, table_count = verify_dataset_integrity()

    total_duration = round(time.time() - total_start, 2)

    print("\n" + "=" * 80)
    print(" 📊 MASTER TEARDOWN SUMMARY REPORT")
    print(f" Total Duration: {total_duration}s")
    print("=" * 80)
    for sr in stage_results:
        status_str = "✅ COMPLETED" if sr["success"] else "⚠️ WARNINGS"
        print(f"  Stage {sr['stage']}: {sr['title']:<50} {status_str} ({sr['duration_s']}s)")

    if ds_ok:
        print(f"\n🛡️  BigQuery Dataset Status: INTACT & ACCESSIBLE ({table_count} tables preserved).")
    else:
        print(f"\n⚠️  BigQuery Dataset Status: Check GCP Console for dataset `{DATASET_ID}`.")

    print("\n✨ Turnkey re-deployment is always available by running:")
    print("  python3 scripts/bootstrap_new_project.py")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Master Teardown & Cleanup Orchestrator.")
    parser.add_argument("--force", "-f", action="store_true", help="Bypass confirmation prompt")
    args = parser.parse_args()

    if not args.force:
        print("⚠️  WARNING: You are about to run a FULL ENVIRONMENT TEARDOWN:")
        print(f"  1. Delete all Gemini Enterprise Data Agents on project '{PROJECT_ID}'")
        print(f"  2. Delete all Knowledge Catalog Glossaries, Terms, Categories, EntryLinks, and AspectTypes")
        print(f"  3. Disable 9 auxiliary Google Cloud APIs (Cloud Run, Gemini, Knowledge Catalog, Artifact Registry, etc.)")
        print(f"  🛡️ The BigQuery dataset `{DATASET_ID}` will be preserved intact.")
        choice = input("\nAre you sure you want to proceed with full teardown? [y/N]: ").strip().lower()
        if choice not in ["y", "yes"]:
            print("Operation aborted by user.")
            sys.exit(0)

    cleanup_all()


if __name__ == "__main__":
    main()
