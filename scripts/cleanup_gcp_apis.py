#!/usr/bin/env python3
"""
Google Cloud APIs Teardown & Reset Tool
=======================================
Disables auxiliary Google Cloud APIs enabled during LumièreShop onboarding,
while preserving `bigquery.googleapis.com` so that the BigQuery dataset and
140 tables remain completely intact.

APIs Disabled:
--------------
1. `dataplex.googleapis.com` (Knowledge Catalog governance & aspects)
2. `datacatalog.googleapis.com` (Data Catalog metadata search layer)
3. `geminidataanalytics.googleapis.com` (Gemini Data Analytics REST API)
4. `cloudaicompanion.googleapis.com` (Conversational AI Companion service)
5. `aiplatform.googleapis.com` (Gemini Enterprise Agent Platform)
6. `run.googleapis.com` (Cloud Run web deployment service)
7. `cloudbuild.googleapis.com` (Cloud Build container builder)
8. `artifactregistry.googleapis.com` (Artifact Registry Docker repository)
9. `bigqueryconnection.googleapis.com` (BigQuery Connection API)

APIs Preserved Active:
----------------------
- `bigquery.googleapis.com` (Preserves BigQuery dataset and 140 tables)
- `iam.googleapis.com` (Core GCP IAM management)
- `cloudresourcemanager.googleapis.com` (Core GCP Project metadata)

Usage:
------
  # Interactive confirmation
  python3 scripts/cleanup_gcp_apis.py

  # Non-interactive / Automated execution
  python3 scripts/cleanup_gcp_apis.py --force
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

APIS_TO_DISABLE = [
    ("dataplex.googleapis.com", "Knowledge Catalog Governance & Aspects"),
    ("datacatalog.googleapis.com", "Data Catalog Metadata Search"),
    ("geminidataanalytics.googleapis.com", "Gemini Data Analytics REST API"),
    ("cloudaicompanion.googleapis.com", "Conversational Companion Service"),
    ("aiplatform.googleapis.com", "Gemini Enterprise Agent Platform"),
    ("run.googleapis.com", "Cloud Run Web Hosting"),
    ("cloudbuild.googleapis.com", "Cloud Build Container Pipelines"),
    ("artifactregistry.googleapis.com", "Artifact Registry Docker Images"),
    ("bigqueryconnection.googleapis.com", "BigQuery Connection API")
]


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


def disable_api_service(service_name: str, description: str, token: str) -> bool:
    """Disables a specific GCP API service via Service Usage REST API or gcloud CLI."""
    print(f"  • Disabling {service_name:<35} ({description})...")
    
    # 1. Try REST API first (fast & direct)
    if token:
        url = f"https://serviceusage.googleapis.com/v1/projects/{PROJECT_ID}/services/{service_name}:disable"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-goog-user-project": PROJECT_ID
        }
        try:
            r = requests.post(url, headers=headers, json={}, timeout=30)
            if r.status_code in [200, 201]:
                print(f"    ✅ Disabled: {service_name}")
                return True
            elif r.status_code == 400 and "not enabled" in r.text.lower():
                print(f"    ℹ️ Already disabled: {service_name}")
                return True
        except Exception:
            pass

    # 2. Fallback to gcloud CLI
    for gcloud_cmd in ["/google/data/ro/teams/cloud-sdk/gcloud", "gcloud"]:
        try:
            cmd = [gcloud_cmd, "services", "disable", service_name, f"--project={PROJECT_ID}", "--quiet"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                print(f"    ✅ Disabled: {service_name}")
                return True
            elif "not enabled" in res.stderr.lower() or "not enabled" in res.stdout.lower():
                print(f"    ℹ️ Already disabled: {service_name}")
                return True
        except Exception:
            continue

    print(f"    ⚠️ Warning: Could not disable {service_name} (may require project owner permissions).")
    return False


def cleanup_gcp_apis():
    print("=" * 80)
    print("🔌 GOOGLE CLOUD APIS TEARDOWN & RESET")
    print(f"Target Project ID : {PROJECT_ID}")
    print(f"Dataset Preserved : {DATASET_ID} (via bigquery.googleapis.com)")
    print("=" * 80)

    if not PROJECT_ID:
        print("ERROR: GCP_PROJECT_ID is not configured in .env file.", file=sys.stderr)
        sys.exit(1)

    token = get_access_token()

    print(f"\nDisabling {len(APIS_TO_DISABLE)} auxiliary Google Cloud APIs...")
    disabled_count = 0
    for service_name, desc in APIS_TO_DISABLE:
        if disable_api_service(service_name, desc, token):
            disabled_count += 1
        time.sleep(0.3)

    print("\n" + "=" * 80)
    print(f"✨ API TEARDOWN SUMMARY: {disabled_count}/{len(APIS_TO_DISABLE)} APIs processed successfully.")
    print(f"🛡️  BigQuery dataset `{DATASET_ID}` remains active and accessible on `{PROJECT_ID}`.")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Disable auxiliary Google Cloud APIs for LumièreShop.")
    parser.add_argument("--force", "-f", action="store_true", help="Bypass confirmation prompt")
    args = parser.parse_args()

    if not args.force:
        print(f"⚠️  WARNING: You are about to DISABLE {len(APIS_TO_DISABLE)} Google Cloud APIs on project '{PROJECT_ID}'.")
        print(f"🛡️  The BigQuery dataset `{DATASET_ID}` and `bigquery.googleapis.com` will NOT be disabled.")
        choice = input("Are you sure you want to proceed? [y/N]: ").strip().lower()
        if choice not in ["y", "yes"]:
            print("Operation aborted by user.")
            sys.exit(0)

    cleanup_gcp_apis()


if __name__ == "__main__":
    main()
