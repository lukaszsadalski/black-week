#!/usr/bin/env python3
"""
Phase 15: BigQuery Interaction Log User Name Schema Extension Script
====================================================================
Adds the `user_name` column to the `agent_interaction_logs` BigQuery table,
allowing every conversational interaction to be audited by individual user identity.

Usage:
------
  python3 scripts/15_add_user_name_to_logs.py
"""

import os
import sys
from google.cloud import bigquery


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
TABLE_ID = "agent_interaction_logs"


def extend_user_name_schema():
    print(f"\nExtending schema of `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` with `user_name` column...")
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    table = client.get_table(table_ref)

    existing_field_names = {field.name for field in table.schema}

    if "user_name" in existing_field_names:
        print("  Column `user_name` already exists in `agent_interaction_logs`.")
        return

    new_field = bigquery.SchemaField(
        "user_name",
        "STRING",
        mode="NULLABLE",
        description="User identifier or display name submitting the analytics inquiry."
    )

    schema = list(table.schema)
    schema.append(new_field)
    table.schema = schema
    client.update_table(table, ["schema"])

    print("  Successfully added `user_name` column to `agent_interaction_logs` table in BigQuery.")


if __name__ == "__main__":
    extend_user_name_schema()
