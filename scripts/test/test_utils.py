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


def ensure_playwright_chromium():
    """
    Ensures Playwright Chromium browser binary is installed.
    Automatically triggers `playwright install chromium` if missing.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                return
            except Exception as e:
                err_msg = str(e)
                if "Executable doesn't exist" in err_msg or "playwright install" in err_msg or "executable" in err_msg.lower():
                    print("⚡ Playwright Chromium browser not found. Installing Chromium automatically...")
                    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Notice: Playwright browser check: {e}")


