#!/usr/bin/env python3
"""
LumièreShop Automated Google Cloud API Enablement & IAM Role Provisioner
========================================================================
Enables all required Google Cloud service APIs and applies mandatory IAM policy
bindings to the project's Compute and Cloud Build Service Accounts to support
Gemini Conversational Analytics, BigQuery Data Agents, Knowledge Catalog, and Cloud Run.

Required APIs Enabled:
----------------------
 1. cloudaicompanion.googleapis.com      (Gemini Cloud Companion / Conversational Analytics)
 2. geminidataanalytics.googleapis.com   (Gemini Data Analytics REST Endpoint)
 3. aiplatform.googleapis.com            (Gemini Enterprise Agent Platform)
 4. bigquery.googleapis.com              (BigQuery Core Engine)
 5. bigqueryconnection.googleapis.com    (BigQuery External Connections)
 6. dataplex.googleapis.com              (Knowledge Catalog & Governance)
 7. datacatalog.googleapis.com           (Data Catalog Metadata Engine)
 8. run.googleapis.com                   (Google Cloud Run Managed Platform)
 9. cloudbuild.googleapis.com            (Google Cloud Build Automation)
10. artifactregistry.googleapis.com      (Artifact Registry Docker Repository)
11. storage.googleapis.com               (Cloud Storage Staging & Bundles)
12. serviceusage.googleapis.com          (Service Usage API & Quota Allocation)

IAM Roles Configured for Cloud Run Compute Service Account:
-----------------------------------------------------------
- roles/cloudaicompanion.user            (Invokes Gemini Conversational Analytics chat)
- roles/cloudaicompanion.admin           (Manages Gemini Cloud Companion contexts)
- roles/bigquery.admin                   (Full query execution across all 140 tables)
- roles/bigquery.dataEditor              (Modifies and queries dataset tables)
- roles/bigquery.jobUser                 (Submits BigQuery analytical jobs)
- roles/dataplex.viewer                  (Knowledge Catalog search & metadata inspection)
- roles/dataplex.metadataAdmin           (EntryLink and Glossary term management)
- roles/aiplatform.user                  (Gemini Enterprise Agent Platform model invocation)
- roles/serviceusage.serviceUsageConsumer(Consumes service quota under x-goog-user-project)
- roles/artifactregistry.writer          (Pushes container images)
- roles/artifactregistry.reader          (Pulls container images)
- roles/storage.admin                    (Reads build artifacts from Cloud Storage)
- roles/logging.logWriter                (Streams logs to Cloud Logging)

Usage:
------
  python3 scripts/setup_gcp_apis.py
  python3 scripts/setup_gcp_apis.py --project-id=YOUR_PROJECT_ID
"""

import os
import sys
import time
import argparse
import subprocess
import requests
from typing import List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)


def load_dotenv():
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))


load_dotenv()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "").strip()


def get_gcloud_path() -> str:
    for cmd in ["/google/data/ro/teams/cloud-sdk/gcloud", "gcloud"]:
        try:
            res = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return cmd
        except Exception:
            continue
    return "gcloud"


GCLOUD = get_gcloud_path()


def get_auth_token() -> Optional[str]:
    try:
        from backend.app.services.ca_service import get_access_token
        token = get_access_token()
        if token:
            return token
    except Exception:
        pass

    try:
        res = subprocess.run([GCLOUD, "auth", "print-access-token"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    return os.environ.get("GCP_ACCESS_TOKEN")


def get_project_number(project_id: str, token: Optional[str]) -> Optional[str]:
    # 1. Check .env
    env_num = os.environ.get("GCP_PROJECT_NUMBER")
    if env_num and env_num.isdigit():
        return env_num

    # 2. Try REST API
    if token:
        try:
            url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}"
            headers = {"Authorization": f"Bearer {token}"}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                p_num = str(res.json().get("projectNumber", ""))
                if p_num:
                    return p_num
        except Exception:
            pass

    # 3. Fallback to gcloud CLI
    try:
        res = subprocess.run(
            [GCLOUD, "projects", "describe", project_id, "--format=value(projectNumber)", "--quiet"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if res.returncode == 0 and res.stdout.strip() and res.stdout.strip().isdigit():
            return res.stdout.strip()
    except Exception:
        pass

    return None


REQUIRED_APIS = [
    ("cloudaicompanion.googleapis.com", "Gemini Cloud Companion API (Conversational Analytics)"),
    ("geminidataanalytics.googleapis.com", "Gemini Data Analytics API (REST Endpoint)"),
    ("aiplatform.googleapis.com", "Gemini Enterprise Agent Platform (Vertex AI)"),
    ("bigquery.googleapis.com", "Google Cloud BigQuery Core Engine"),
    ("bigqueryconnection.googleapis.com", "BigQuery Connection API"),
    ("dataplex.googleapis.com", "Knowledge Catalog Governance & Search API"),
    ("datacatalog.googleapis.com", "Google Cloud Data Catalog API"),
    ("run.googleapis.com", "Google Cloud Run Managed Container Platform"),
    ("cloudbuild.googleapis.com", "Google Cloud Build Automation"),
    ("artifactregistry.googleapis.com", "Google Cloud Artifact Registry"),
    ("storage.googleapis.com", "Google Cloud Storage API"),
    ("serviceusage.googleapis.com", "Google Cloud Service Usage API"),
]

COMPUTE_ROLES = [
    "roles/geminidataanalytics.dataAgentUser",
    "roles/geminidataanalytics.dataAgentStatelessUser",
    "roles/geminidataanalytics.dataAgentCreator",
    "roles/geminidataanalytics.dataAgentOwner",
    "roles/geminidataanalytics.admin",
    "roles/cloudaicompanion.user",
    "roles/cloudaicompanion.admin",
    "roles/bigquery.admin",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/dataplex.viewer",
    "roles/dataplex.metadataAdmin",
    "roles/aiplatform.user",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/artifactregistry.writer",
    "roles/artifactregistry.reader",
    "roles/storage.admin",
    "roles/logging.logWriter",
]

CLOUDBUILD_ROLES = [
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/storage.admin",
]


def enable_apis(project_id: str, token: Optional[str]):
    print(f"\n▶️  Enabling {len(REQUIRED_APIS)} Required Google Cloud APIs for '{project_id}'...")
    for api_service, label in REQUIRED_APIS:
        print(f"  • Enabling {api_service:36} ({label})...", end="", flush=True)
        enabled = False
        if token:
            try:
                url = f"https://serviceusage.googleapis.com/v1/projects/{project_id}/services/{api_service}:enable"
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                res = requests.post(url, headers=headers, timeout=20)
                if res.status_code in [200, 201]:
                    enabled = True
            except Exception:
                pass

        if not enabled:
            res = subprocess.run(
                [GCLOUD, "services", "enable", api_service, f"--project={project_id}", "--quiet"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if res.returncode == 0:
                enabled = True

        if enabled:
            print(" ✅ Active")
        else:
            print(" ⚠️ Notice / Skipped")


def configure_iam_roles(project_id: str, project_number: str):
    print(f"\n▶️  Configuring IAM Policy Bindings on Project '{project_id}' (Project Number: {project_number})...")
    compute_sa = f"serviceAccount:{project_number}-compute@developer.gserviceaccount.com"
    cb_sa = f"serviceAccount:{project_number}@cloudbuild.gserviceaccount.com"

    print(f"  1. Configuring {len(COMPUTE_ROLES)} roles for Compute Service Account ({compute_sa})...")
    for role in COMPUTE_ROLES:
        res = subprocess.run(
            [GCLOUD, "projects", "add-iam-policy-binding", project_id, f"--member={compute_sa}", f"--role={role}", "--quiet"],
            capture_output=True,
            text=True
        )
        status = "✅" if res.returncode == 0 else "⚠️"
        print(f"     {status} {role}")

    print(f"\n  2. Configuring {len(CLOUDBUILD_ROLES)} roles for Cloud Build Service Account ({cb_sa})...")
    for role in CLOUDBUILD_ROLES:
        res = subprocess.run(
            [GCLOUD, "projects", "add-iam-policy-binding", project_id, f"--member={cb_sa}", f"--role={role}", "--quiet"],
            capture_output=True,
            text=True
        )
        status = "✅" if res.returncode == 0 else "⚠️"
        print(f"     {status} {role}")


def main():
    parser = argparse.ArgumentParser(description="Enable APIs and configure IAM policy bindings for LumièreShop.")
    parser.add_argument("--project-id", default=PROJECT_ID, help="Target GCP Project ID")
    args = parser.parse_args()

    project_id = args.project_id
    if not project_id or project_id == "your-gcp-project-id":
        res = subprocess.run([GCLOUD, "config", "get-value", "project"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "(unset)":
            project_id = res.stdout.strip()
        else:
            print("❌ ERROR: Valid GCP_PROJECT_ID is not configured in .env or gcloud config.", file=sys.stderr)
            sys.exit(1)

    print("=" * 80)
    print("🚀 LUMIÈRESHOP GOOGLE CLOUD APIS & IAM PROVISIONER")
    print(f"Target Project ID : {project_id}")
    print("=" * 80)

    token = get_auth_token()
    enable_apis(project_id, token)

    project_number = get_project_number(project_id, token)
    if not project_number:
        print(f"\n⚠️ Notice: Could not automatically resolve Project Number for '{project_id}'.", file=sys.stderr)
        print("   If you know your project number, set GCP_PROJECT_NUMBER in .env and re-run.", file=sys.stderr)
    else:
        configure_iam_roles(project_id, project_number)

    print("\n" + "=" * 80)
    print("🎉 GOOGLE CLOUD ENVIRONMENT & IAM SETUP COMPLETE!")
    print("=" * 80)
    print("\n📌 Commercial GCP Project Checklist:")
    print("  1. Ensure 'Gemini for Google Cloud' (or Gemini in BigQuery) is enabled on your billing account.")
    print("  2. Verify that 'roles/cloudaicompanion.user' is granted to your Compute Service Account.")
    print("  3. Deploy Cloud Run via: python3 scripts/deploy_cloud_run.py\n")


if __name__ == "__main__":
    main()
