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
