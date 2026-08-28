#!/usr/bin/env python3
"""
Phase 14: Historical Baseline Data Generator (Pre-Black Week Volume Calibration)
================================================================================
Generates 1.5 months of realistic baseline non-promotional transaction volume
(October 12, 2026 to November 22, 2026 — 42 days / 6 full weeks) and appends to BigQuery
without overwriting or modifying any existing Black Week records.

Enables Conversational Analytics and Gemini Data Agents to execute longitudinal
year-over-year and month-over-month trend queries ("How does Black Friday compare to normal weeks?").

Usage:
------
  python3 scripts/14_generate_historical_data.py
"""

import os
import sys
import uuid
import random
import tempfile
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
from google.cloud import bigquery
from app.config import PROJECT_ID, DATASET_ID, LOCATION

# Historical baseline bounds (42 days prior to Black Week)
HIST_START = datetime(2026, 10, 12, 0, 0, 0)
HIST_END = datetime(2026, 11, 22, 23, 59, 59)
TOTAL_HIST_SECONDS = int((HIST_END - HIST_START).total_seconds())

def get_bigquery_client():
    return bigquery.Client(project=PROJECT_ID, location=LOCATION)

def append_ndjson_to_bq(client, table_name, file_path):
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        ignore_unknown_values=True
    )
    print(f"   Appending to `{table_name}` from {os.path.basename(file_path)}...")
    with open(file_path, "rb") as source_file:
        job = client.load_table_from_file(source_file, table_ref, job_config=job_config)
        job.result()
    print(f"   ✅ Successfully appended to `{table_name}`.")

def generate_historical_data():
    random.seed(1337)
    np.random.seed(1337)

    client = get_bigquery_client()
    print("=" * 80)
    print("STARTING 1.5-MONTH HISTORICAL BASELINE DATA GENERATION (OCT 12 - NOV 22, 2026)")
    print(f"Target: `{PROJECT_ID}.{DATASET_ID}` | Location: `{LOCATION}`")
    print(f"Timeline: {HIST_START.strftime('%Y-%m-%d %H:%M:%S')} to {HIST_END.strftime('%Y-%m-%d %H:%M:%S')} UTC (42 Days / 6 Weeks)")
    print("=" * 80 + "\n")

    # 1. Fetch Products master list from BigQuery
    print("1. Fetching product catalog from BigQuery...")
    prod_query = f"SELECT product_id, category_id, name, retail_price, cost FROM `{PROJECT_ID}.{DATASET_ID}.products` ORDER BY product_id"
    prod_rows = list(client.query(prod_query).result())
    products = [{
        "product_id": r.product_id,
        "category_id": r.category_id,
        "name": r.name,
        "retail_price": float(r.retail_price),
        "cost": float(r.cost)
    } for r in prod_rows]
    print(f"   Loaded {len(products)} products across 4 categories.")

    # 2. Historical Weekly Commercial Targets (6 Historical Weeks x 4 Categories = 24 Rows)
    print("\n2. Generating Historical Weekly Commercial Targets...")
    weekly_targets = []
    target_id_counter = 101
    
    # Standard baseline weekly targets per category
    base_cat_weekly_targets = {
        1: {"revenue": 220000.0, "sessions": 70000, "cvr": 0.031}, # Beauty
        2: {"revenue": 240000.0, "sessions": 30000, "cvr": 0.034}, # Electronics
        3: {"revenue": 190000.0, "sessions": 28000, "cvr": 0.032}, # Fashion
        4: {"revenue": 180000.0, "sessions": 25000, "cvr": 0.030}, # Home
    }

    week_starts = [
        "2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02", "2026-11-09", "2026-11-16"
    ]

    for w_idx, w_start in enumerate(week_starts):
        # Slight seasonal growth ramp towards November
        seasonality_factor = 1.0 + (w_idx * 0.02)
        for cat_id, info in base_cat_weekly_targets.items():
            weekly_targets.append({
                "target_id": target_id_counter,
                "category_id": cat_id,
                "week_start_date": w_start,
                "target_revenue": float(round(info["revenue"] * seasonality_factor, 2)),
                "target_sessions": int(round(info["sessions"] * seasonality_factor)),
                "target_conversion_rate": info["cvr"]
            })
            target_id_counter += 1

    # 3. Historical Daily Category Targets (42 Days x 4 Categories = 168 Rows)
    print("3. Generating Historical Daily Category Targets...")
    daily_targets = []
    # Standard day-of-week weights (Sun=0.17, Mon=0.14, Tue=0.13, Wed=0.13, Thu=0.14, Fri=0.14, Sat=0.15)
    dow_weights = [0.14, 0.13, 0.13, 0.14, 0.14, 0.15, 0.17]

    for day in range(42):
        d_dt = HIST_START + timedelta(days=day)
        d_str = d_dt.strftime("%Y-%m-%d")
        w_factor = dow_weights[d_dt.weekday()]
        
        for cat_id, info in base_cat_weekly_targets.items():
            daily_rev = info["revenue"] * w_factor
            daily_sess = int(info["sessions"] * w_factor)
            daily_spend = daily_rev * 0.12 # Standard 12% marketing spend
            daily_roas = 4.8 if cat_id == 1 else (5.2 if cat_id == 2 else 4.5)

            daily_targets.append({
                "target_id": f"T-HIST-C{cat_id}-{d_str}",
                "category_id": cat_id,
                "date": d_str,
                "target_revenue": float(round(daily_rev, 2)),
                "target_sessions": daily_sess,
                "target_conversion_rate": info["cvr"],
                "target_aov": float(round(daily_rev / (daily_sess * info["cvr"]), 2)),
                "target_ad_spend": float(round(daily_spend, 2)),
                "target_roas": daily_roas
            })

    # 4. Historical Daily Ad Performance & Ad Bidding Logs
    print("4. Generating Historical Ad Performance & Bidding Logs...")
    ad_performance = []
    ad_bidding_logs = []
    ad_perf_id = 101
    ad_log_id = 101

    campaign_map = {
        1: ("Meta Ads - Beauty Luxury Skincare", 1),
        2: ("Google Search - Electronics Audio/Smart", 2),
        3: ("Meta Ads - Fashion Autumn Collection", 3),
        4: ("Google Shopping - Home Decor & Living", 4)
    }

    for day in range(42):
        d_dt = HIST_START + timedelta(days=day)
        d_str = d_dt.strftime("%Y-%m-%d")

        for camp_id, (camp_name, cat_id) in campaign_map.items():
            c_info = base_cat_weekly_targets[cat_id]
            w_factor = dow_weights[d_dt.weekday()]
            day_spend = float(round(c_info["revenue"] * w_factor * 0.12 * random.uniform(0.95, 1.05), 2))
            cpc = float(round(random.uniform(0.35, 0.42), 2))
            clicks = int(round(day_spend / cpc))
            impressions = clicks * random.randint(35, 48)
            conversions = int(round(clicks * c_info["cvr"] * random.uniform(0.98, 1.02)))

            ad_performance.append({
                "performance_id": ad_perf_id,
                "campaign_id": camp_id,
                "date": d_str,
                "impressions": impressions,
                "clicks": clicks,
                "spend": day_spend,
                "conversions": conversions,
                "average_cpc": cpc
            })
            ad_perf_id += 1

        # Weekly automated bidding health audit log
        if d_dt.weekday() == 0:
            for camp_id in range(1, 5):
                ad_bidding_logs.append({
                    "log_id": ad_log_id,
                    "campaign_id": camp_id,
                    "status_change": "BUDGET_NORMAL",
                    "trigger_details": f"Target ROAS maintained at 4.65x (threshold: 3.50x). Bidding pace steady.",
                    "logged_at": d_dt.strftime("%Y-%m-%dT06:00:00Z")
                })
                ad_log_id += 1

    # 5. Historical Daily Inventory Snapshots (42 Days x 600 SKUs = 25,200 Snapshots)
    print("5. Generating Historical Inventory Snapshots (Full Healthy Stock)...")
    inventory_snapshots = []
    snap_id = 10001

    for day in range(42):
        d_dt = HIST_START + timedelta(days=day)
        d_str = d_dt.strftime("%Y-%m-%dT08:00:00Z")
        
        for p in products:
            # During historical baseline, ALL SKUs including 1001-1003 are healthy in stock (>1,500 units)
            base_qty = 3200 - (day % 14) * 45
            inventory_snapshots.append({
                "snapshot_id": snap_id,
                "product_id": p["product_id"],
                "recorded_at": d_str,
                "stock_quantity": base_qty,
                "is_out_of_stock": False
            })
            snap_id += 1

    # 6. Historical Shipping Lead Times (42 Days x 2 DCs = 84 Rows)
    print("6. Generating Historical Shipping Lead Times...")
    shipping_lead_times = []
    lead_id = 101

    for day in range(42):
        d_dt = HIST_START + timedelta(days=day)
        d_str = d_dt.strftime("%Y-%m-%d")
        
        for dc_id, region in [(1, "Western Europe (FR/NL/BE)"), (2, "Central Europe (DACH)")]:
            shipping_lead_times.append({
                "lead_time_id": f"LT-HIST-{lead_id}",
                "dc_id": dc_id,
                "date": d_str,
                "carrier_name": "DHL Express" if dc_id == 2 else "Chronopost",
                "destination_region": region,
                "standard_lead_time_hours": 48,
                "actual_promised_lead_time_hours": 28,
                "capacity_utilization_pct": float(round(random.uniform(62.0, 78.0), 1)),
                "cart_abandonment_impact_pct": 0.0,
                "estimated_lost_revenue": 0.0
            })
            lead_id += 1

    # 7. Historical Orders, Order Items, Sales Events & Payments (~42,000 Orders, ~70,000 Items)
    print("7. Generating Historical Orders, Items, Sales Events & Payments...")
    orders = []
    order_items = []
    sales_event_stream = []
    payment_logs = []

    order_id = 100001
    order_item_id = 100001
    pay_log_id = 100001

    # We generate ~1,000 orders/day across 42 days (~42,000 orders total)
    # Total historical revenue: 6 weeks x ~€830k/week = ~€4,980,000.00
    target_weekly_rev_by_cat = {
        1: 220000.0, # Beauty
        2: 240000.0, # Electronics
        3: 190000.0, # Fashion
        4: 180000.0  # Home
    }

    # Pre-calculate category products and weight distribution
    cat_prods_map = {}
    cat_weights_map = {}
    for c_id in range(1, 5):
        c_prods = [p for p in products if p["category_id"] == c_id]
        cat_prods_map[c_id] = c_prods
        weights = 1.0 / (np.arange(1, len(c_prods) + 1) ** 0.85)
        cat_weights_map[c_id] = weights / weights.sum()

    for w_idx in range(6):
        w_start_dt = HIST_START + timedelta(days=w_idx * 7)
        
        for cat_id in range(1, 5):
            cat_target = target_weekly_rev_by_cat[cat_id] * (1.0 + w_idx * 0.02)
            # Healthy actual: 99.8% to 101.2% target completion
            cat_actual_target = cat_target * random.uniform(0.998, 1.012)
            
            c_prods = cat_prods_map[cat_id]
            c_weights = cat_weights_map[cat_id]
            n_prods = len(c_prods)

            current_rev = 0.0
            while current_rev < cat_actual_target:
                rand_sec = random.randint(0, 7 * 86400 - 1)
                order_dt = w_start_dt + timedelta(seconds=rand_sec)
                user_id = random.randint(1, 10000)

                item_roll = random.random()
                num_items = 1 if item_roll < 0.60 else (2 if item_roll < 0.88 else (3 if item_roll < 0.96 else 4))

                order_total = 0.0
                items_for_order = []

                for _ in range(num_items):
                    p_obj = np.random.choice(c_prods, p=c_weights)
                    price = float(p_obj["retail_price"])
                    qty = 1 if random.random() < 0.88 else 2
                    line_total = price * qty
                    order_total += line_total
                    items_for_order.append((p_obj["product_id"], qty, price))

                current_rev += order_total

                orders.append({
                    "order_id": order_id,
                    "user_id": user_id,
                    "order_status": "Completed",
                    "total_amount": float(round(order_total, 2)),
                    "tax_amount": float(round(order_total * 0.20, 2)),
                    "shipping_fee": 4.99 if order_total < 50.0 else 0.0,
                    "num_of_items": len(items_for_order),
                    "created_at": order_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                })

                for p_id, qty, price in items_for_order:
                    has_ret = random.random() < 0.048 # Standard 4.8% return rate
                    ret_dt = (order_dt + timedelta(days=random.randint(2, 5))).strftime("%Y-%m-%dT%H:%M:%SZ") if has_ret else None

                    order_items.append({
                        "order_item_id": order_item_id,
                        "order_id": order_id,
                        "user_id": user_id,
                        "product_id": p_id,
                        "inventory_item_id": p_id - (p_id // 1000 - 1) * 850,
                        "quantity": qty,
                        "sale_price": float(price),
                        "discount_amount": 0.0,
                        "created_at": order_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "shipped_at": (order_dt + timedelta(hours=14)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "delivered_at": (order_dt + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "returned_at": ret_dt
                    })

                    sales_event_stream.append({
                        "event_id": str(uuid.uuid4()),
                        "order_id": order_id,
                        "product_id": p_id,
                        "category_id": cat_id,
                        "quantity": qty,
                        "sale_price": float(price),
                        "discount_amount": 0.0,
                        "timestamp": order_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    })
                    order_item_id += 1

                # Payment gateway log (~93.5% successful payments)
                psp = random.choice(["Stripe", "Stripe", "PayPal", "Adyen"])
                method = "credit_card" if psp != "PayPal" else "paypal_wallet"
                payment_logs.append({
                    "gateway_log_id": f"GW-HIST-{pay_log_id}",
                    "session_id": f"SESS-HIST-{order_id % 1200000 + 1}",
                    "order_id": order_id,
                    "payment_provider": psp,
                    "payment_method": method,
                    "status": "SUCCESS",
                    "http_status_code": 200,
                    "latency_ms": random.randint(140, 320),
                    "error_code": None,
                    "total_amount": float(round(order_total, 2)),
                    "country": random.choice(["France", "Germany", "Netherlands", "Spain", "Italy", "Belgium"]),
                    "created_at": order_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                })
                pay_log_id += 1
                order_id += 1

    print(f"   Generated {len(orders):,} historical orders (€{sum(o['total_amount'] for o in orders):,.2f} total revenue).")

    # 8. Write and Append to BigQuery
    print("\n8. Streaming historical records to BigQuery Load Jobs...")
    temp_dir = tempfile.mkdtemp()
    
    datasets_to_upload = [
        ("weekly_commercial_targets", weekly_targets),
        ("daily_category_targets", daily_targets),
        ("daily_ad_performance", ad_performance),
        ("ad_bidding_log", ad_bidding_logs),
        ("inventory_snapshots", inventory_snapshots),
        ("shipping_lead_times", shipping_lead_times),
        ("orders", orders),
        ("order_items", order_items),
        ("sales_event_stream", sales_event_stream),
        ("payment_gateway_logs", payment_logs)
    ]

    import json
    for table_name, record_list in datasets_to_upload:
        if not record_list:
            continue
        file_path = os.path.join(temp_dir, f"{table_name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            for rec in record_list:
                f.write(json.dumps(rec) + "\n")
        append_ndjson_to_bq(client, table_name, file_path)

    print("\n🎉 ALL 1.5-MONTH HISTORICAL BASELINE DATA SUCCESSFULLY APPENDED TO BIGQUERY!")

if __name__ == "__main__":
    generate_historical_data()
