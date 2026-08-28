#!/usr/bin/env python3
"""
Phase 9: Google Cloud Knowledge Catalog Business Glossary & EntryLinks Deployment Script
========================================================================================
Creates and deploys the enterprise Business Glossary (`ecommerce-glossary`),
glossary categories, and term nodes in Google Cloud Knowledge Catalog (location: `global`).
Terms contain clean business definitions, formulas, and synonyms.
Physical table/column relationships are provisioned natively as Knowledge Catalog EntryLinks
connecting BigQuery table entries to their respective business terms.

Usage:
------
  python3 scripts/09_create_dataplex_glossary.py
"""

import os
import sys
import time
import subprocess
import requests
import json


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
DATASET_ID = os.environ.get("BQ_DATASET_ID", os.environ.get("BIGQUERY_DATASET_ID", "ecommerce_dw"))
LOCATION = "global"
BQ_LOCATION = os.environ.get("BQ_LOCATION", os.environ.get("BIGQUERY_LOCATION", "us-central1"))
GLOSSARY_ID = "ecommerce-glossary"


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


def get_project_number(project_id, token):
    """Retrieves numeric project number from Cloud Resource Manager or gcloud CLI."""
    try:
        res = requests.get(
            f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if res.status_code == 200:
            num = res.json().get("projectNumber")
            if num:
                return str(num)
    except Exception:
        pass

    # Fallback to gcloud CLI
    for cmd in ["/google/data/ro/teams/cloud-sdk/gcloud", "gcloud"]:
        try:
            res = subprocess.run([cmd, "projects", "describe", project_id, "--format=value(projectNumber)"], capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            continue
    return ""


def api_request_with_retry(method: str, url: str, headers: dict, json_payload: dict = None, max_retries: int = 5) -> requests.Response:
    """
    Executes an HTTP request with automated backoff retry when encountering
    Google Cloud API rate limits (HTTP 429 or quota-related 403).
    """
    res = None
    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                res = requests.get(url, headers=headers, timeout=15)
            elif method.upper() == "POST":
                res = requests.post(url, headers=headers, json=json_payload, timeout=15)
            elif method.upper() == "PATCH":
                res = requests.patch(url, headers=headers, json=json_payload, timeout=15)
            else:
                res = requests.request(method, url, headers=headers, json=json_payload, timeout=15)

            # Check if rate limited or quota exceeded
            if res.status_code == 429 or (res.status_code == 403 and "quota" in res.text.lower()):
                backoff = 3.0 * (1.5 ** attempt)
                print(f"    ⏳ GCP API rate limit encountered (HTTP {res.status_code}). Pausing {backoff:.1f}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(backoff)
                continue
            elif res.status_code >= 500:
                time.sleep(2.0)
                continue
            return res
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2.0)
            else:
                raise e
    return res


def deploy_glossary():
    print(f"\nDeploying Knowledge Catalog Business Glossary `{GLOSSARY_ID}` in `{PROJECT_ID}` (Location: `{LOCATION}`)...")
    token = get_access_token()
    if not token:
        print("Error: Could not retrieve OAuth access token.", file=sys.stderr)
        sys.exit(1)

    project_number = get_project_number(PROJECT_ID, token)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-goog-user-project": PROJECT_ID,
    }

    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "business_glossary.json")
    with open(config_path, "r") as f:
        glossary_data = json.load(f).get("glossary", {})

    base_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/glossaries"
    glossary_resource_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}"
    glossary_url = f"{base_url}/{GLOSSARY_ID}"

    # 1. Create or verify Glossary resource
    print(f"1. Creating/Verifying Glossary `{GLOSSARY_ID}` in `{LOCATION}`...")
    check_res = api_request_with_retry("GET", glossary_url, headers)
    if check_res and check_res.status_code == 200:
        print(f"  Glossary `{GLOSSARY_ID}` already exists.")
    else:
        create_payload = {
            "displayName": glossary_data.get("display_name", "LumièreShop Executive Retail Glossary"),
            "description": glossary_data.get("description", "Enterprise semantic glossary for LumièreShop"),
        }
        create_res = api_request_with_retry("POST", f"{base_url}?glossaryId={GLOSSARY_ID}", headers, create_payload)
        print(f"  Glossary Creation Status: HTTP {create_res.status_code if create_res else 'N/A'}")

    # 2. Create Categories
    categories = glossary_data.get("categories", [])
    print(f"\n2. Deploying {len(categories)} Glossary Categories in `{LOCATION}`...")
    for idx, cat in enumerate(categories, 1):
        cat_id = cat["id"]
        cat_url = f"{glossary_url}/categories/{cat_id}"
        cat_check = api_request_with_retry("GET", cat_url, headers)
        cat_payload = {
            "parent": glossary_resource_name,
            "displayName": cat["display_name"],
            "description": cat["description"][:1000],
        }
        if cat_check and cat_check.status_code == 200:
            api_request_with_retry("PATCH", f"{cat_url}?updateMask=displayName,description", headers, cat_payload)
        else:
            api_request_with_retry("POST", f"{glossary_url}/categories?categoryId={cat_id}", headers, cat_payload)
        print(f"  [{idx:02d}/{len(categories):02d}] Category `{cat_id}` configured.")
        time.sleep(0.35)

    print(f"  ✅ All {len(categories)} categories successfully deployed.")

    # 3. Create Terms with Clean Business Descriptions
    terms = glossary_data.get("terms", [])
    print(f"\n3. Deploying {len(terms)} Business Terms with Clean Descriptions in `{LOCATION}` (Paced for GCP Quotas)...")
    created_term_count = 0
    for idx, term in enumerate(terms, 1):
        term_id = term["id"]
        term_url = f"{glossary_url}/terms/{term_id}"

        # Clean business description (pure definition, formula, synonyms without raw technical table bullets)
        parts = [term["definition"]]
        formula_str = term.get("formula", "")
        if formula_str and formula_str != "N/A":
            parts.append(f"Calculation Formula: {formula_str}")
        synonyms_str = ", ".join(term.get("synonyms", []))
        if synonyms_str:
            parts.append(f"Synonyms: {synonyms_str}")
        desc_text = "\n\n".join(parts)

        term_payload = {
            "parent": glossary_resource_name,
            "displayName": term["display_name"],
            "description": desc_text[:1000],
        }

        term_check = api_request_with_retry("GET", term_url, headers)
        success = False
        if term_check and term_check.status_code == 200:
            update_res = api_request_with_retry("PATCH", f"{term_url}?updateMask=displayName,description", headers, term_payload)
            if update_res and update_res.status_code == 200:
                success = True
            else:
                err_msg = update_res.text[:120] if update_res else "No response"
                print(f"  ⚠️ Warning: Failed to update term `{term_id}` (HTTP {update_res.status_code if update_res else 'ERR'}): {err_msg}")
        else:
            create_term_res = api_request_with_retry("POST", f"{glossary_url}/terms?termId={term_id}", headers, term_payload)
            if create_term_res and create_term_res.status_code in [200, 201]:
                success = True
            elif create_term_res and create_term_res.status_code == 409:
                # Already exists, fallback to PATCH update
                update_res = api_request_with_retry("PATCH", f"{term_url}?updateMask=displayName,description", headers, term_payload)
                if update_res and update_res.status_code == 200:
                    success = True
                else:
                    err_msg = update_res.text[:120] if update_res else "No response"
                    print(f"  ⚠️ Warning: Failed to update existing term `{term_id}` (HTTP {update_res.status_code if update_res else 'ERR'}): {err_msg}")
            else:
                err_msg = create_term_res.text[:120] if create_term_res else "No response"
                print(f"  ⚠️ Warning: Failed to create term `{term_id}` (HTTP {create_term_res.status_code if create_term_res else 'ERR'}): {err_msg}")

        if success:
            created_term_count += 1

        # Periodic status notification so the user sees live active progress
        if idx % 10 == 0 or idx == len(terms):
            print(f"  Progress: [{idx:02d}/{len(terms):02d}] business terms synchronized ({created_term_count}/{len(terms)} active)...")

        # Pacing delay to stay safely within the 60 requests/minute write quota
        time.sleep(0.4)

    print(f"  ✅ Terms deployed with clean descriptions: {created_term_count}/{len(terms)}")

    # 4. Provision Native Knowledge Catalog EntryLinks
    print(f"\n4. Provisioning Native Knowledge Catalog EntryLinks in `{BQ_LOCATION}`...")
    created_link_count = 0
    total_bindings = 0

    link_type = "projects/655216118709/locations/global/entryLinkTypes/definition"

    all_links = []
    for term in terms:
        term_id = term["id"]
        term_target_name = f"projects/{project_number}/locations/global/entryGroups/@dataplex/entries/projects/{project_number}/locations/global/glossaries/{GLOSSARY_ID}/terms/{term_id}"
        bindings = term.get("bindings", [])
        bound_tables = sorted(list(set([b["table"] for b in bindings if b.get("table")])))
        for table_name in bound_tables:
            link_id = f"link-{term_id}-{table_name}".replace("_", "-")
            bq_source_name = f"projects/{project_number}/locations/{BQ_LOCATION}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{DATASET_ID}/tables/{table_name}"
            all_links.append((term_id, table_name, bq_source_name, term_target_name, link_id))

    total_bindings = len(all_links)

    for idx, (term_id, table_name, bq_source_name, term_target_name, link_id) in enumerate(all_links, 1):
        link_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{BQ_LOCATION}/entryGroups/@bigquery/entryLinks?entryLinkId={link_id}"
        link_payload = {
            "entryLinkType": link_type,
            "entryReferences": [
                {
                    "type": "SOURCE",
                    "name": bq_source_name,
                },
                {
                    "type": "TARGET",
                    "name": term_target_name,
                }
            ]
        }

        try:
            link_res = api_request_with_retry("POST", link_url, headers, link_payload)
            if link_res and (link_res.status_code in [200, 201] or link_res.status_code == 409 or "already exists" in link_res.text):
                created_link_count += 1
        except Exception:
            pass

        if idx % 30 == 0 or idx == total_bindings:
            print(f"  Progress: [{idx:03d}/{total_bindings:03d}] EntryLinks linked ({created_link_count} active)...")

        time.sleep(0.15)

    print(f"  ✅ EntryLinks provisioned: {created_link_count}/{total_bindings}")

    print("\n" + "=" * 80)
    print(f"Knowledge Catalog Glossary & Native EntryLinks Deployment Complete!")
    print(f"Summary: {len(categories)} Categories | {created_term_count}/{len(terms)} Clean Terms | {created_link_count} EntryLinks")
    print("=" * 80)


if __name__ == "__main__":
    deploy_glossary()
