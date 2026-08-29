#!/usr/bin/env python3
"""
Composable Test Utilities & Shared Test Harness
===============================================
Provides standardized environment discovery, root directory traversal,
Google Cloud OAuth token discovery, and authenticated BigQuery client instantiation
for the entire `scripts/test/` test suite.

Design Philosophy:
------------------
  - Zero hardcoding of directory paths or project IDs.
  - Automatic upward directory traversal to locate `.env`.
  - Non-destructive environment variable injection (`setdefault`).
"""

import os
import sys
import subprocess
from typing import Optional
from google.cloud import bigquery
from google.oauth2 import credentials as oauth2_credentials

def get_project_root() -> str:
    """Finds the project root directory by traversing upwards."""
    current = os.path.dirname(os.path.abspath(__file__))
    while current and current != "/":
        if os.path.exists(os.path.join(current, ".env")) or os.path.exists(os.path.join(current, "README.md")):
            return current
        current = os.path.dirname(current)
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

def load_project_env():
    """Loads key-value pairs from .env into os.environ without overriding existing vars."""
    root = get_project_root()
    env_path = os.path.join(root, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip("'\""))

# Load immediately upon import
load_project_env()

def get_gcp_access_token() -> str:
    """Retrieves GCP access token from env or gcloud CLI."""
    token = os.environ.get("GCP_ACCESS_TOKEN")
    if not token:
        try:
            res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True)
            token = res.stdout.strip()
        except Exception:
            token = None
    return token

def get_bigquery_client(project_id: str = None) -> bigquery.Client:
    """Returns an authenticated BigQuery client."""
    pid = project_id or os.environ.get("GCP_PROJECT_ID", "")
    token = get_gcp_access_token()
    if token:
        creds = oauth2_credentials.Credentials(token)
        return bigquery.Client(project=pid, credentials=creds)
    return bigquery.Client(project=pid)


def ensure_test_server(port: int = 8000) -> str:
    """
    Ensures FastAPI server is actively responding on localhost,
    automatically launching a background thread server if not already running.
    """
    import time
    import requests
    base_url = os.environ.get("BASE_URL", f"http://127.0.0.1:{port}")
    try:
        r = requests.get(f"{base_url}/api/health", timeout=1)
        if r.status_code == 200:
            return base_url
    except Exception:
        pass

    try:
        import threading
        import uvicorn
        root = get_project_root()
        backend_path = os.path.join(root, "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        from app.main import app

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        server = uvicorn.Server(config)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()

        for _ in range(30):
            try:
                r = requests.get(f"http://127.0.0.1:{port}/api/health", timeout=1)
                if r.status_code == 200:
                    os.environ["BASE_URL"] = f"http://127.0.0.1:{port}"
                    return f"http://127.0.0.1:{port}"
            except Exception:
                time.sleep(0.1)
    except Exception as e:
        print(f"Warning: Could not start local background test server: {e}")

    return base_url


def ensure_playwright_chromium() -> bool:
    """
    Ensures Playwright Chromium browser binary and Linux OS dependencies are installed.
    Automatically triggers `playwright install --with-deps chromium` if missing.
    Returns True if Chromium can successfully launch in headless mode, False otherwise.
    """
    try:
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        try:
            browser = p.chromium.launch(headless=True)
            browser.close()
            p.stop()
            return True
        except Exception as e:
            try:
                p.stop()
            except Exception:
                pass
            err_msg = str(e)
            if "missing dependencies" in err_msg.lower() or "host system is missing" in err_msg.lower() or "executable" in err_msg.lower() or "install" in err_msg.lower():
                print("⚡ Headless Linux environment detected. Attempting to install Chromium with OS dependencies (`playwright install --with-deps chromium`)...")
                try:
                    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True, capture_output=True)
                    p2 = sync_playwright().start()
                    try:
                        browser = p2.chromium.launch(headless=True)
                        browser.close()
                        p2.stop()
                        return True
                    except Exception:
                        try:
                            p2.stop()
                        except Exception:
                            pass
                        return False
                except Exception:
                    return False
            return False
    except Exception as e:
        return False


def get_knowledge_catalog_indexing_status(project_id: str = None, dataset_id: str = None, token: str = None) -> dict:
    """
    Queries Google Cloud Knowledge Catalog searchEntries API to compute real-time
    metadata and semantic search vector indexing progress across tables and glossary terms.
    """
    import requests
    pid = project_id or os.environ.get("GCP_PROJECT_ID", "")
    did = dataset_id or os.environ.get("BQ_DATASET_ID", "ecommerce_dw")
    tok = token or get_gcp_access_token()
    
    if not pid or not tok:
        return {
            "indexed_tables": 0,
            "total_tables": 140,
            "table_percentage": 0.0,
            "indexed_terms": 0,
            "total_terms": 85,
            "term_percentage": 0.0,
            "status": "UNKNOWN",
            "message": "Missing GCP Project ID or authentication token."
        }

    headers = {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "x-goog-user-project": pid,
    }
    url = f"https://dataplex.googleapis.com/v1/projects/{pid}/locations/global:searchEntries"

    indexed_tables = set()
    indexed_terms = set()
    dataset_pattern = f"datasets/{did}/tables/"
    resource_pattern = f"/datasets/{did}/tables/"
    
    # 1. Page through all BigQuery table entries for project
    page_token = None
    for _ in range(10):  # Cap at 10 pages (1000 items)
        body = {
            "query": "system=BIGQUERY type=TABLE",
            "scope": f"projects/{pid}",
            "pageSize": 100
        }
        if page_token:
            body["pageToken"] = page_token
        try:
            r = requests.post(url, headers=headers, json=body, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            for item in data.get("results", []):
                dp_entry = item.get("dataplexEntry", {})
                name = dp_entry.get("name", "")
                resource = dp_entry.get("entrySource", {}).get("resource", "")
                if dataset_pattern in name:
                    indexed_tables.add(name.split(dataset_pattern)[-1])
                elif resource_pattern in resource:
                    indexed_tables.add(resource.split(resource_pattern)[-1])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        except Exception:
            break

    # 2. Count glossary terms for project
    term_page_token = None
    for _ in range(5):
        body = {
            "query": "system=DATAPLEX type=GLOSSARY_TERM",
            "scope": f"projects/{pid}",
            "pageSize": 100
        }
        if term_page_token:
            body["pageToken"] = term_page_token
        try:
            r = requests.post(url, headers=headers, json=body, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            for item in data.get("results", []):
                name = item.get("dataplexEntry", {}).get("name", "")
                if "/terms/" in name:
                    indexed_terms.add(name.split("/terms/")[-1])
            term_page_token = data.get("nextPageToken")
            if not term_page_token:
                break
        except Exception:
            break

    tbl_count = len(indexed_tables)
    term_count = len(indexed_terms)
    tbl_pct = round((tbl_count / 140.0) * 100, 1) if tbl_count <= 140 else 100.0
    term_pct = round((term_count / 85.0) * 100, 1) if term_count <= 85 else 100.0

    if tbl_count >= 140 and term_count >= 85:
        status = "COMPLETED"
        msg = "All 140 BigQuery tables and 85 Glossary Terms are fully indexed."
    elif tbl_count > 0 or term_count > 0:
        status = "IN_PROGRESS"
        msg = f"Vector indexing in progress: {tbl_count}/140 tables ({tbl_pct}%), {term_count}/85 terms ({term_pct}%)."
    else:
        status = "WARMING_UP"
        msg = "Vector indexing queued / warming up in Google Cloud."

    return {
        "indexed_tables": tbl_count,
        "total_tables": 140,
        "table_percentage": tbl_pct,
        "indexed_terms": term_count,
        "total_terms": 85,
        "term_percentage": term_pct,
        "status": status,
        "message": msg
    }



