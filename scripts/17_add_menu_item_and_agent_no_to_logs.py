#!/usr/bin/env python3
"""
Phase 17: BigQuery Interaction Log Menu Item & Agent No Schema Extension Script
==============================================================================
Adds `menu_item` and `agent_no` columns to the `agent_interaction_logs` BigQuery table,
enabling full audit logging across single-agent and 3-agent comparative chats.

Columns:
  - menu_item: STRING ('chat', 'compare chats')
  - agent_no: STRING ('agentA', 'agentB', 'agentC', or NULL for single agent)

Usage:
------
  python3 scripts/17_add_menu_item_and_agent_no_to_logs.py
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


def extend_menu_item_and_agent_no_schema():
    print(f"\nExtending schema of `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` with `menu_item` and `agent_no` columns...")
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    table = client.get_table(table_ref)

    existing_field_names = {field.name for field in table.schema}
    schema = list(table.schema)
    fields_added = []

    if "menu_item" not in existing_field_names:
        schema.append(bigquery.SchemaField(
            "menu_item",
            "STRING",
            mode="NULLABLE",
            description="Interface menu context initiating the interaction ('chat' vs 'compare chats')."
        ))
        fields_added.append("menu_item")

    if "agent_no" not in existing_field_names:
        schema.append(bigquery.SchemaField(
            "agent_no",
            "STRING",
            mode="NULLABLE",
            description="Agent identifier in comparative multi-agent mode ('agentA', 'agentB', 'agentC', or NULL for single agent)."
        ))
        fields_added.append("agent_no")

    if fields_added:
        table.schema = schema
        client.update_table(table, ["schema"])
        print(f"  Successfully added columns {fields_added} to `agent_interaction_logs` table in BigQuery.")
    else:
        print("  Columns `menu_item` and `agent_no` already exist in `agent_interaction_logs`.")


if __name__ == "__main__":
    extend_menu_item_and_agent_no_schema()
