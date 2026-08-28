#!/usr/bin/env python3
"""
BigQuery Enterprise Dataset & Schema Summary Exporter
======================================================
Automated documentation generator that inspects BigQuery warehouse metadata across all
140 tables in `ecommerce_dw`, queries live row counts, extracts 5-part functional descriptions,
labels, column types, and compiles `docs/DATASET_DATA_AND_SCHEMA_SUMMARY.md` with embedded
Mermaid Entity-Relationship (ER) diagrams.

Usage:
------
  python3 scripts/export_dataset_summary.py
"""

import os
import sys
import re
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
from google.cloud import bigquery
from app.config import PROJECT_ID, DATASET_ID, LOCATION

def load_schema_and_metadata():
    client = bigquery.Client(project=PROJECT_ID, location=LOCATION)
    
    print("1. Querying table storage and row counts from __TABLES__...")
    table_query = f"""
    SELECT 
        t.table_id,
        t.row_count,
        t.size_bytes,
        t.type,
        TIMESTAMP_MILLIS(t.creation_time) AS created_time,
        TIMESTAMP_MILLIS(t.last_modified_time) AS modified_time
    FROM `{PROJECT_ID}.{DATASET_ID}.__TABLES__` AS t
    ORDER BY t.table_id ASC
    """
    table_rows = list(client.query(table_query).result())
    table_stats = {r.table_id: r for r in table_rows}
    print(f"   Found {len(table_stats)} tables in __TABLES__.")

    print("2. Querying table descriptions from INFORMATION_SCHEMA.TABLES...")
    desc_query = f"""
    SELECT table_name, option_value AS description
    FROM `{PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.TABLE_OPTIONS`
    WHERE option_name = 'description'
    """
    try:
        desc_rows = list(client.query(desc_query).result())
        table_descriptions = {r.table_name: r.description.strip('"\'') for r in desc_rows}
    except Exception as e:
        print(f"   Notice on table options: {e}")
        table_descriptions = {}

    print("3. Querying column details from INFORMATION_SCHEMA.COLUMN_FIELD_PATHS...")
    col_query = f"""
    SELECT 
        table_name,
        column_name,
        field_path,
        data_type,
        description
    FROM `{PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
    ORDER BY table_name, field_path
    """
    col_rows = list(client.query(col_query).result())
    
    table_columns = {}
    for c in col_rows:
        tname = c.table_name
        if tname not in table_columns:
            table_columns[tname] = []
        table_columns[tname].append({
            "name": c.column_name,
            "type": c.data_type,
            "description": c.description or ""
        })
    print(f"   Loaded columns across {len(table_columns)} tables.")

    return table_stats, table_descriptions, table_columns

def categorize_tables():
    # 25 Core Investigation Tables
    core_25 = [
        "weekly_commercial_targets",
        "daily_category_targets",
        "category_15min_targets",
        "categories",
        "products",
        "orders",
        "order_items",
        "sales_event_stream",
        "inventory_items",
        "inventory_snapshots",
        "oos_interactions",
        "distribution_centers",
        "marketing_campaigns",
        "daily_ad_performance",
        "ad_bidding_log",
        "ad_creatives",
        "influencer_campaigns",
        "competitor_price_feed",
        "competitor_promotions",
        "catalog_recommender_logs",
        "shipping_lead_times",
        "payment_gateway_logs",
        "web_sessions",
        "web_events",
        "users"
    ]

    domain_mapping = {
        "Core Investigation Cluster (Black Week Forensic Diagnostic Set)": core_25,
        "Domain H: Staging & Raw Ingestion (20 Tables)": [
            "stg_shopify_orders_raw", "stg_shopify_products_raw", "stg_shopify_customers_raw",
            "stg_klaviyo_email_events_raw", "stg_klaviyo_campaigns_raw", "stg_stripe_payment_intents_raw",
            "stg_stripe_disputes_raw", "stg_adyen_settlements_raw", "stg_ga4_clickstream_raw",
            "stg_ga4_traffic_sources_raw", "stg_meta_ad_insights_raw", "stg_google_ads_campaigns_raw",
            "stg_google_ads_search_terms_raw", "stg_criteo_retargeting_raw", "stg_wms_shipments_raw",
            "stg_sap_erp_inventory_feed_raw", "stg_sap_erp_purchase_orders_raw", "stg_zendesk_tickets_raw",
            "stg_zendesk_satisfaction_raw", "stg_trustpilot_reviews_raw"
        ],
        "Domain I: Returns, Refunds & Reverse Logistics (10 Tables)": [
            "product_returns", "return_inspections", "return_shipping_labels", "return_reasons_lookup",
            "customer_refunds", "replacement_orders", "restocking_fee_logs", "warranty_claims",
            "store_credit_issuances", "accounts_payable_disbursements"
        ],
        "Domain J: Customer Support, CRM & Voice of Customer (12 Tables)": [
            "support_tickets", "ticket_messages", "support_agents", "ticket_categories",
            "csat_surveys", "nps_feedback_responses", "live_chat_sessions", "live_chat_messages",
            "customer_escalations", "call_center_recordings_metadata", "knowledge_base_articles",
            "agent_interaction_logs"
        ],
        "Domain K: Supply Chain, Procurement & Multi-DC Warehousing (14 Tables)": [
            "purchase_orders", "purchase_order_line_items", "suppliers_master", "supplier_lead_time_history",
            "supplier_quality_scorecards", "inbound_dock_appointments", "cross_dock_transfer_orders",
            "warehouse_zones", "warehouse_aisles_and_racks", "pallet_inventory_locations",
            "forklift_telemetry_logs", "warehouse_labor_shifts", "freight_carrier_contracts",
            "customs_and_duties_declarations"
        ],
        "Domain L: Finance, General Ledger, Tax & Accounting (12 Tables)": [
            "chart_of_accounts", "general_ledger_journal_entries", "gl_journal_lines",
            "accounts_payable_invoices", "accounts_receivable_invoices", "bank_account_reconciliation",
            "currency_exchange_rates_daily", "vat_tax_jurisdictions", "vat_period_filing_reports",
            "payment_gateway_fee_schedules", "intercompany_transfer_pricing", "warehouse_refurbishments"
        ],
        "Domain M: Loyalty, Customer Retention & Rewards (10 Tables)": [
            "loyalty_members", "loyalty_points_ledger", "loyalty_tier_definitions",
            "loyalty_reward_redemptions", "gift_card_master", "gift_card_transactions",
            "referral_program_invites", "referral_reward_claims", "user_subscription_preferences",
            "coupon_redemption_audit"
        ],
        "Domain N: Lifecycle Marketing, Email & Push Telemetry (10 Tables)": [
            "email_send_queue_logs", "email_bounces_and_complaints", "email_campaign_templates",
            "sms_marketing_broadcasts", "sms_delivery_receipts", "mobile_app_push_campaigns",
            "push_notification_receipts", "affiliate_publishers_directory", "affiliate_commission_payouts",
            "discount_coupons_master"
        ],
        "Domain O: Product Information Management (PIM) & Merchandising (8 Tables)": [
            "product_attribute_definitions", "product_attribute_values", "product_media_gallery",
            "product_multilingual_translations", "product_size_charts", "product_brand_guidelines",
            "category_hierarchy_paths", "seo_meta_tags_registry"
        ],
        "Domain P: Retail Physical Stores & Omni-Channel POS (8 Tables)": [
            "physical_store_locations", "pos_terminal_registers", "pos_store_transactions",
            "pos_transaction_items", "store_inventory_levels", "store_employee_rosters",
            "store_cash_drawer_counts", "click_and_collect_orders"
        ],
        "Domain Q: Non-Production, Sandboxes & QA Archives (11 Tables)": [
            "dev_customer_churn_feature_store", "dev_product_embedding_vectors", "sandbox_dynamic_pricing_sim_v1",
            "sandbox_search_ranking_ab_test", "qa_checkout_synthetic_fuzz_tests", "qa_load_test_sessions_backup",
            "legacy_orders_2023_archive", "legacy_products_deprecated", "test_fraud_mock_transactions",
            "test_carrier_webhook_payloads", "agent_worklog_shifts"
        ]
    }
    return domain_mapping

def infer_keys_and_relationships(table_name, columns):
    pk = []
    fks = []
    
    col_names = [c["name"] for c in columns]
    
    # Standard PK inference
    singular = table_name[:-1] if table_name.endswith("s") and not table_name.endswith("status") else table_name
    potential_pks = [f"{singular}_id", f"{table_name}_id", "id", "interaction_id", "session_id", "event_id", "entry_id", "log_id", "mapping_id"]
    
    for p in potential_pks:
        if p in col_names:
            pk.append(p)
            break
            
    # Composite PK checks
    if table_name == "order_items":
        pk = ["order_id", "order_item_id"]
    elif table_name == "weekly_commercial_targets":
        pk = ["category_id", "week_start_date"]
    elif table_name == "daily_category_targets":
        pk = ["category_id", "date"]
    elif table_name == "category_15min_targets":
        pk = ["category_id", "interval_start_time"]
    elif table_name == "daily_ad_performance":
        pk = ["campaign_id", "date"]
    elif table_name == "inventory_snapshots":
        pk = ["product_id", "distribution_center_id", "snapshot_hour"]

    # FK inference
    for c in col_names:
        if c.endswith("_id") and c not in pk:
            ref_entity = c[:-3]
            ref_table = f"{ref_entity}s"
            if ref_entity == "category":
                ref_table = "categories"
            elif ref_entity == "user" or ref_entity == "customer":
                ref_table = "users"
            elif ref_entity == "distribution_center":
                ref_table = "distribution_centers"
            elif ref_entity == "campaign":
                ref_table = "marketing_campaigns"
            elif ref_entity == "product":
                ref_table = "products"
            elif ref_entity == "order":
                ref_table = "orders"
            fks.append(f"{c} ➔ `{ref_table}.{c}`")
            
    return pk, fks

def generate_markdown(table_stats, table_descriptions, table_columns, domain_mapping):
    total_tables = len(table_stats)
    total_rows = sum(r.row_count for r in table_stats.values())
    total_bytes = sum(r.size_bytes for r in table_stats.values())
    total_mb = total_bytes / (1024 * 1024)
    total_gb = total_bytes / (1024 * 1024 * 1024)

    lines = []
    lines.append("# LumièreShop: Enterprise Data Warehouse Architecture & Schema Reference")
    lines.append("")
    lines.append("> **Dataset**: `ecommerce_dw` | **GCP Project**: `<YOUR_GCP_PROJECT_ID>` | **Location**: `<YOUR_GCP_REGION>`  ")
    lines.append(f"> **Scale**: **{total_tables} Tables** | **{total_rows:,} Total Rows** | **{total_mb:,.2f} MB ({total_gb:.2f} GB)** Storage")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📊 1. Executive Data Warehouse Summary")
    lines.append("")
    lines.append("The LumièreShop BigQuery Data Warehouse (`ecommerce_dw`) models an omnichannel European luxury beauty and retail enterprise.")
    lines.append("The dataset is partitioned into:")
    lines.append("1. **Core Diagnostic Cluster (25 Tables)**: High-resolution transactional and telemetry tables powering the Black Week 2026 revenue incident root-cause discovery.")
    lines.append("2. **Enterprise Extended Domains (115 Tables)**: Full-scope operational, accounting, logistics, marketing, machine learning, and security systems (Domains A through Q).")
    lines.append("")
    lines.append("### 📈 Storage & Volume Breakdown by Table (All 140 Tables)")
    lines.append("")
    lines.append("| Table Name | Record Count | Data Size | Primary Key | Operational Role & Domain |")
    lines.append("| :--- | :---: | :---: | :--- | :--- |")
    
    # Sort all tables by record count descending
    sorted_tables = sorted(table_stats.values(), key=lambda x: x.row_count, reverse=True)
    for t in sorted_tables:
        tname = t.table_id
        count_str = f"**{t.row_count:,}**"
        size_str = f"{t.size_bytes / (1024*1024):.2f} MB" if t.size_bytes > 1024*1024 else f"{t.size_bytes / 1024:.1f} KB"
        cols = table_columns.get(tname, [])
        pk, fks = infer_keys_and_relationships(tname, cols)
        pk_str = ", ".join(pk) if pk else "*(Surrogate)*"
        desc = table_descriptions.get(tname, "").split(".")[0] or "Enterprise operational table"
        lines.append(f"| `{tname}` | {count_str} | {size_str} | `{pk_str}` | {desc} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🗺️ 2. Core Relational Architecture Diagrams")
    lines.append("")
    lines.append("The following Mermaid diagrams illustrate the physical foreign key linkages across the core operational clusters:")
    lines.append("")
    lines.append("### 💳 A. Commercial Revenue & Order Transaction Flow")
    lines.append("")
    lines.append("```mermaid")
    lines.append("erDiagram")
    lines.append("    CATEGORIES ||--o{ PRODUCTS : categorizes")
    lines.append("    PRODUCTS ||--o{ ORDER_ITEMS : contains")
    lines.append("    ORDERS ||--o{ ORDER_ITEMS : includes")
    lines.append("    USERS ||--o{ ORDERS : places")
    lines.append("    ORDERS ||--o{ PAYMENT_GATEWAY_LOGS : settles")
    lines.append("    CATEGORIES ||--o{ WEEKLY_COMMERCIAL_TARGETS : benchmarks")
    lines.append("    CATEGORIES ||--o{ DAILY_CATEGORY_TARGETS : benchmarks")
    lines.append("    CATEGORIES ||--o{ CATEGORY_15MIN_TARGETS : benchmarks")
    lines.append("    PRODUCTS ||--o{ SALES_EVENT_STREAM : streams")
    lines.append("")
    lines.append("    CATEGORIES {")
    lines.append("        int64 category_id PK")
    lines.append("        string name")
    lines.append("    }")
    lines.append("    PRODUCTS {")
    lines.append("        int64 product_id PK")
    lines.append("        int64 category_id FK")
    lines.append("        string name")
    lines.append("        numeric retail_price")
    lines.append("    }")
    lines.append("    ORDERS {")
    lines.append("        int64 order_id PK")
    lines.append("        int64 user_id FK")
    lines.append("        string status")
    lines.append("        numeric total_amount")
    lines.append("        timestamp created_at")
    lines.append("    }")
    lines.append("    ORDER_ITEMS {")
    lines.append("        int64 order_item_id PK")
    lines.append("        int64 order_id FK")
    lines.append("        int64 product_id FK")
    lines.append("        int64 quantity")
    lines.append("        numeric item_price")
    lines.append("    }")
    lines.append("    PAYMENT_GATEWAY_LOGS {")
    lines.append("        int64 log_id PK")
    lines.append("        int64 order_id FK")
    lines.append("        string gateway_status")
    lines.append("        numeric amount")
    lines.append("    }")
    lines.append("```")
    lines.append("")
    lines.append("### 📢 B. Paid Advertising & Automated Bidding Engine")
    lines.append("")
    lines.append("```mermaid")
    lines.append("erDiagram")
    lines.append("    CATEGORIES ||--o{ MARKETING_CAMPAIGNS : targets")
    lines.append("    MARKETING_CAMPAIGNS ||--o{ DAILY_AD_PERFORMANCE : aggregates")
    lines.append("    MARKETING_CAMPAIGNS ||--o{ AD_BIDDING_LOG : audits")
    lines.append("    MARKETING_CAMPAIGNS ||--o{ AD_CREATIVES : employs")
    lines.append("    CATEGORIES ||--o{ INFLUENCER_CAMPAIGNS : promotes")
    lines.append("")
    lines.append("    MARKETING_CAMPAIGNS {")
    lines.append("        int64 campaign_id PK")
    lines.append("        int64 target_category_id FK")
    lines.append("        string campaign_name")
    lines.append("        string bidding_strategy")
    lines.append("        numeric target_roas")
    lines.append("    }")
    lines.append("    DAILY_AD_PERFORMANCE {")
    lines.append("        int64 campaign_id PK,FK")
    lines.append("        date date PK")
    lines.append("        numeric spend")
    lines.append("        int64 clicks")
    lines.append("        numeric reported_roas")
    lines.append("    }")
    lines.append("    AD_BIDDING_LOG {")
    lines.append("        int64 log_id PK")
    lines.append("        int64 campaign_id FK")
    lines.append("        string status_change")
    lines.append("        string trigger_details")
    lines.append("        timestamp logged_at")
    lines.append("    }")
    lines.append("```")
    lines.append("")
    lines.append("### 📦 C. Supply Chain Stockouts & Fulfillment")
    lines.append("")
    lines.append("```mermaid")
    lines.append("erDiagram")
    lines.append("    PRODUCTS ||--o{ INVENTORY_ITEMS : stores")
    lines.append("    DISTRIBUTION_CENTERS ||--o{ INVENTORY_ITEMS : houses")
    lines.append("    PRODUCTS ||--o{ INVENTORY_SNAPSHOTS : tracks")
    lines.append("    PRODUCTS ||--o{ OOS_INTERACTIONS : logs")
    lines.append("    DISTRIBUTION_CENTERS ||--o{ SHIPPING_LEAD_TIMES : routes")
    lines.append("")
    lines.append("    INVENTORY_ITEMS {")
    lines.append("        int64 inventory_item_id PK")
    lines.append("        int64 product_id FK")
    lines.append("        int64 distribution_center_id FK")
    lines.append("        int64 available_stock")
    lines.append("    }")
    lines.append("    OOS_INTERACTIONS {")
    lines.append("        int64 interaction_id PK")
    lines.append("        int64 product_id FK")
    lines.append("        int64 user_id FK")
    lines.append("        numeric estimated_lost_revenue")
    lines.append("        timestamp clicked_at")
    lines.append("    }")
    lines.append("    SHIPPING_LEAD_TIMES {")
    lines.append("        int64 route_id PK")
    lines.append("        int64 origin_dc_id FK")
    lines.append("        int64 promised_lead_hours")
    lines.append("        int64 actual_lead_hours")
    lines.append("    }")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 3. Core Investigation Tables Deep-Dive (25 Tables)")
    lines.append("")
    lines.append("Detailed column schemas, primary keys, foreign keys, and exact record counts for all 25 tables in the core diagnostic cluster:")
    lines.append("")

    core_tables_list = domain_mapping["Core Investigation Cluster (Black Week Forensic Diagnostic Set)"]
    for tname in core_tables_list:
        stat = table_stats.get(tname)
        if not stat:
            continue
        count_str = f"{stat.row_count:,}"
        size_str = f"{stat.size_bytes / (1024*1024):.2f} MB" if stat.size_bytes > 1024*1024 else f"{stat.size_bytes / 1024:.1f} KB"
        desc = table_descriptions.get(tname, "Core operational analytics table.")
        cols = table_columns.get(tname, [])
        pk, fks = infer_keys_and_relationships(tname, cols)
        
        lines.append(f"### 📋 `{tname}`")
        lines.append(f"- **Business Meaning**: {desc}")
        lines.append(f"- **Record Count**: **{count_str} rows** ({size_str})")
        lines.append(f"- **Primary Key (PK)**: `{' + '.join(pk) if pk else 'None'}`")
        if fks:
            lines.append(f"- **Foreign Keys (FK)**: {', '.join(fks)}")
        lines.append("")
        lines.append("| Column Name | Data Type | Field Meaning & Calculation Formula |")
        lines.append("| :--- | :--- | :--- |")
        for c in cols:
            col_desc = c['description'] or f"Column `{c['name']}` attribute"
            lines.append(f"| `{c['name']}` | `{c['type']}` | {col_desc} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 🏢 4. Extended Enterprise Domains Reference (115 Tables)")
    lines.append("")
    lines.append("The remaining 115 enterprise tables provide deep historical, omnichannel, and operational coverage across 17 functional business domains:")
    lines.append("")

    for domain_name, tables in domain_mapping.items():
        if domain_name.startswith("Core Investigation"):
            continue
        lines.append(f"### 📂 {domain_name}")
        lines.append("")
        lines.append("| Table Name | Record Count | Primary Key | Foreign Key Links | Business Description |")
        lines.append("| :--- | :---: | :--- | :--- | :--- |")
        for tname in tables:
            stat = table_stats.get(tname)
            if not stat:
                continue
            count_str = f"**{stat.row_count:,}**"
            cols = table_columns.get(tname, [])
            pk, fks = infer_keys_and_relationships(tname, cols)
            pk_str = ", ".join(pk) if pk else "None"
            fk_str = "<br/>".join(fks[:2]) if fks else "*(None)*"
            desc = table_descriptions.get(tname, "Extended enterprise operational table.")
            lines.append(f"| `{tname}` | {count_str} | `{pk_str}` | {fk_str} | {desc} |")
        lines.append("")

    return "\n".join(lines)

def main():
    print("Starting BigQuery metadata export...")
    table_stats, table_descriptions, table_columns = load_schema_and_metadata()
    domain_mapping = categorize_tables()
    
    print("Formatting markdown document...")
    markdown_content = generate_markdown(table_stats, table_descriptions, table_columns, domain_mapping)
    
    out_path = "docs/DATASET_DATA_AND_SCHEMA_SUMMARY.md"
    os.makedirs("docs", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    print(f"✅ Successfully wrote {out_path} ({len(markdown_content):,} bytes, {len(table_stats)} tables).")

if __name__ == "__main__":
    main()
