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
DATASET_ID = os.environ.get("BIGQUERY_DATASET_ID", "ecommerce_dw")
LOCATION = "global"
BQ_LOCATION = os.environ.get("BIGQUERY_LOCATION", "europe-west4")
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
    check_res = requests.get(glossary_url, headers=headers)
    if check_res.status_code == 200:
        print(f"  Glossary `{GLOSSARY_ID}` already exists.")
    else:
        create_payload = {
            "displayName": glossary_data.get("display_name", "LumièreShop Executive Retail Glossary"),
            "description": glossary_data.get("description", "Enterprise semantic glossary for LumièreShop"),
        }
        create_res = requests.post(f"{base_url}?glossaryId={GLOSSARY_ID}", headers=headers, json=create_payload)
        print(f"  Glossary Creation Status: HTTP {create_res.status_code}")

    # 2. Create Categories
    categories = glossary_data.get("categories", [])
    print(f"\n2. Deploying {len(categories)} Glossary Categories in `{LOCATION}`...")
    for cat in categories:
        cat_id = cat["id"]
        cat_url = f"{glossary_url}/categories/{cat_id}"
        cat_check = requests.get(cat_url, headers=headers)
        cat_payload = {
            "parent": glossary_resource_name,
            "displayName": cat["display_name"],
            "description": cat["description"][:1000],
        }
        if cat_check.status_code == 200:
            requests.patch(f"{cat_url}?updateMask=displayName,description", headers=headers, json=cat_payload)
        else:
            requests.post(f"{glossary_url}/categories?categoryId={cat_id}", headers=headers, json=cat_payload)
    print(f"  Categories deployed: {len(categories)}")

    # 3. Create Terms with Clean Business Descriptions
    terms = glossary_data.get("terms", [])
    print(f"\n3. Deploying {len(terms)} Business Terms with Clean Descriptions in `{LOCATION}`...")
    created_term_count = 0
    for term in terms:
        term_id = term["id"]
        term_url = f"{glossary_url}/terms/{term_id}"
        term_check = requests.get(term_url, headers=headers)

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

        if term_check.status_code == 200:
            update_res = requests.patch(f"{term_url}?updateMask=displayName,description", headers=headers, json=term_payload)
            if update_res.status_code == 200:
                created_term_count += 1
        else:
            create_term_res = requests.post(f"{glossary_url}/terms?termId={term_id}", headers=headers, json=term_payload)
            if create_term_res.status_code in [200, 201]:
                created_term_count += 1

    print(f"  Terms deployed with clean descriptions: {created_term_count}/{len(terms)}")

    # 4. Provision Native Knowledge Catalog EntryLinks
    print(f"\n4. Provisioning Native Knowledge Catalog EntryLinks in `{BQ_LOCATION}`...")
    created_link_count = 0
    total_bindings = 0

    link_type = "projects/655216118709/locations/global/entryLinkTypes/definition"

    for term in terms:
        term_id = term["id"]
        term_target_name = f"projects/{project_number}/locations/global/entryGroups/@dataplex/entries/projects/{project_number}/locations/global/glossaries/{GLOSSARY_ID}/terms/{term_id}"
        bindings = term.get("bindings", [])
        
        # Deduplicate tables per term
        bound_tables = sorted(list(set([b["table"] for b in bindings if b.get("table")])))
        total_bindings += len(bound_tables)

        for table_name in bound_tables:
            link_id = f"link-{term_id}-{table_name}".replace("_", "-")
            bq_source_name = f"projects/{project_number}/locations/{BQ_LOCATION}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{DATASET_ID}/tables/{table_name}"
            
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
                link_res = requests.post(link_url, headers=headers, json=link_payload, timeout=10)
                if link_res.status_code in [200, 201]:
                    created_link_count += 1
                elif link_res.status_code == 409 or "already exists" in link_res.text:
                    created_link_count += 1
                else:
                    # Non-fatal notice
                    pass
            except Exception as e:
                print(f"  Notice creating link {link_id}: {e}")

    print(f"  EntryLinks provisioned: {created_link_count}/{total_bindings}")

    print("\n" + "=" * 80)
    print(f"Knowledge Catalog Glossary & Native EntryLinks Deployment Complete!")
    print(f"Summary: {len(categories)} Categories | {len(terms)} Clean Terms | {created_link_count} EntryLinks")
    print("=" * 80)


if __name__ == "__main__":
    deploy_glossary()
