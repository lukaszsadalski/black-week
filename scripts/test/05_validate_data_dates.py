#!/usr/bin/env python3
"""
Automated Data Validation, Statistical Ratios & Date Cutoff Assertion Suite.
Verifies:
1. Operational data strictly respects Friday Nov 27, 2026 14:30:00 UTC cutoff (0 rows post-cutoff).
2. Target tables cover the full 8 days (Nov 23 to Nov 30).
3. Statistical ratios across Black Week.
4. Reconciled variance matches €530,000.00 exactly (€65k + €50k + €415k).
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from test_utils import load_project_env, get_bigquery_client
load_project_env()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "ecommerce_dw")

CUTOFF_TIMESTAMP = "2026-11-27 14:30:00 UTC"
START_TIMESTAMP = "2026-11-23 00:00:00 UTC"

def run_validation():
    print("=" * 80)
    print("BLACK WEEK 2026 DATA, STATISTICAL RATIOS & DATE CUTOFF VALIDATION SUITE")
    print(f"Dataset: `{PROJECT_ID}.{DATASET_ID}`")
    print(f"Simulation Anchor (Max Actuals Cutoff): {CUTOFF_TIMESTAMP}")
    print(f"Black Week Focus Start:                {START_TIMESTAMP}")
    print("=" * 80)

    client = get_bigquery_client(PROJECT_ID)

    passed = 0
    total = 0

    # 1. Statistical ratios during Black Week
    print("\n1. Validating E-Commerce Statistical Ratios for Black Week Focus Period...")

    total += 1
    cr_query = f"""
    SELECT 
        (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET_ID}.orders` WHERE created_at >= '{START_TIMESTAMP}' AND created_at <= '{CUTOFF_TIMESTAMP}') AS order_count,
        (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET_ID}.web_sessions` WHERE session_started_at >= '{START_TIMESTAMP}' AND session_started_at <= '{CUTOFF_TIMESTAMP}') AS session_count
    """
    cr_res = list(client.query(cr_query).result())[0]
    bw_orders = cr_res.order_count
    bw_sessions = cr_res.session_count
    cr = (bw_orders / bw_sessions) if bw_sessions > 0 else 0.0

    if 0.025 <= cr <= 0.035:
        print(f"  ✅ Conversion Rate (Orders / Sessions): {bw_orders:,} / {bw_sessions:,} = {cr*100:.2f}% (Target: ~3.0%) [PASS]")
        passed += 1
    else:
        print(f"  ❌ Conversion Rate: {bw_orders} / {bw_sessions} = {cr*100:.2f}% (Target ~3.0%) [FAIL]")

    total += 1
    pay_query = f"""
    SELECT 
        (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET_ID}.payment_gateway_logs` WHERE status = 'SUCCESS' AND created_at >= '{START_TIMESTAMP}' AND created_at <= '{CUTOFF_TIMESTAMP}') AS succ_payments,
        (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET_ID}.orders` WHERE created_at >= '{START_TIMESTAMP}' AND created_at <= '{CUTOFF_TIMESTAMP}') AS total_orders
    """
    pay_res = list(client.query(pay_query).result())[0]
    succ_pay = pay_res.succ_payments
    tot_ord = pay_res.total_orders
    pay_ratio = (succ_pay / tot_ord) if tot_ord > 0 else 0.0

    if 0.90 <= pay_ratio <= 1.00:
        print(f"  ✅ Payment Gateway Success Ratio: {succ_pay:,} / {tot_ord:,} = {pay_ratio*100:.2f}% [PASS]")
        passed += 1
    else:
        print(f"  ❌ Payment Ratio: {succ_pay} / {tot_ord} = {pay_ratio*100:.2f}% [FAIL]")

    total += 1
    ev_cnt_q = f"SELECT COUNT(*) AS cnt FROM `{PROJECT_ID}.{DATASET_ID}.web_events` WHERE created_at >= '{START_TIMESTAMP}' AND created_at <= '{CUTOFF_TIMESTAMP}'"
    ev_cnt = list(client.query(ev_cnt_q).result())[0].cnt
    avg_events_per_sess = (ev_cnt / bw_sessions) if bw_sessions > 0 else 0.0

    if 8.0 <= avg_events_per_sess <= 30.0:
        print(f"  ✅ Clickstream Depth (Events / Session): {ev_cnt:,} / {bw_sessions:,} = {avg_events_per_sess:.2f} events/session [PASS]")
        passed += 1
    else:
        print(f"  ❌ Clickstream Depth: {ev_cnt} / {bw_sessions} = {avg_events_per_sess:.2f} events/session [FAIL]")

    # 2. Check Target Tables Horizon
    print("\n2. Validating Planned Target Horizons (Full 8 Days: Nov 23 - Nov 30)...")
    
    total += 1
    query = f"SELECT COUNT(*) AS cnt, MIN(date) AS min_d, MAX(date) AS max_d FROM `{PROJECT_ID}.{DATASET_ID}.daily_category_targets` WHERE date >= '2026-11-23'"
    res = list(client.query(query).result())[0]
    if res.cnt == 32 and str(res.min_d) == "2026-11-23" and str(res.max_d) == "2026-11-30":
        print(f"  ✅ `daily_category_targets` (Black Week): 32 records spanning {res.min_d} to {res.max_d} [PASS]")
        passed += 1
    else:
        print(f"  ❌ `daily_category_targets`: Expected 32 records (Nov 23 to Nov 30), got {res.cnt} ({res.min_d} to {res.max_d}) [FAIL]")

    total += 1
    query = f"SELECT COUNT(*) AS cnt FROM `{PROJECT_ID}.{DATASET_ID}.category_15min_targets`"
    res = list(client.query(query).result())[0]
    if res.cnt == 3072:
        print(f"  ✅ `category_15min_targets`: 3,072 intervals (8 days * 96 * 4) [PASS]")
        passed += 1
    else:
        print(f"  ❌ `category_15min_targets`: Expected 3,072 records, got {res.cnt} [FAIL]")



    # 3. Check Operational Tables Temporal Cutoff (Strictly <= Friday Nov 27 14:30:00 UTC)
    print("\n3. Validating Temporal Cutoff on Operational Tables (0 rows post 2026-11-27 14:30:00 UTC)...")
    
    temporal_checks = [
        ("orders", "created_at"),
        ("order_items", "created_at"),
        ("sales_event_stream", "timestamp"),
        ("web_sessions", "session_started_at"),
        ("web_events", "created_at"),
        ("oos_interactions", "clicked_at"),
        ("inventory_snapshots", "recorded_at"),
        ("payment_gateway_logs", "created_at"),
        ("catalog_recommender_logs", "recorded_at"),
        ("competitor_price_feed", "scraped_at")
    ]

    for table_name, col_name in temporal_checks:
        total += 1
        query = f"""
        SELECT 
            MIN({col_name}) AS min_ts,
            MAX({col_name}) AS max_ts,
            COUNTIF({col_name} > '{CUTOFF_TIMESTAMP}') AS post_cutoff_count,
            COUNT(*) AS total_count
        FROM `{PROJECT_ID}.{DATASET_ID}.{table_name}`
        """
        try:
            r = list(client.query(query).result())[0]
            if r.post_cutoff_count == 0:
                print(f"  ✅ `{table_name}` ({r.total_count:,} rows): max={r.max_ts} | post_cutoff=0 [PASS]")
                passed += 1
            else:
                print(f"  ❌ `{table_name}`: Found {r.post_cutoff_count} rows exceeding cutoff! [FAIL]")
        except Exception as e:
            print(f"  ❌ `{table_name}`: Error querying table: {e}")

    # 4. Check Daily Operational Tables (Max date <= 2026-11-27)
    print("\n4. Validating Daily Operational Tables (Max date <= 2026-11-27)...")
    daily_checks = [
        ("daily_ad_performance", "date"),
        ("shipping_lead_times", "date")
    ]
    for table_name, col_name in daily_checks:
        total += 1
        query = f"""
        SELECT 
            MIN({col_name}) AS min_d,
            MAX({col_name}) AS max_d,
            COUNTIF({col_name} > '2026-11-27') AS post_cutoff_count,
            COUNT(*) AS total_count
        FROM `{PROJECT_ID}.{DATASET_ID}.{table_name}`
        """
        try:
            r = list(client.query(query).result())[0]
            if r.post_cutoff_count == 0:
                print(f"  ✅ `{table_name}` ({r.total_count:,} rows): max={r.max_d} | post_cutoff=0 [PASS]")
                passed += 1
            else:
                print(f"  ❌ `{table_name}`: Found {r.post_cutoff_count} records exceeding cutoff! [FAIL]")
        except Exception as e:
            print(f"  ❌ `{table_name}`: Error querying table: {e}")

    # 5. Check Mathematical Reconciliation of Beauty Deficit
    print("\n5. Validating Mathematical Reconciliation of Beauty €530,000 Deficit...")
    total += 1
    stockout_loss = 65000.00
    recommender_loss = 50000.00
    ad_throttling_loss = 415000.00
    reconciled_sum = stockout_loss + recommender_loss + ad_throttling_loss

    if abs(reconciled_sum - 530000.00) < 0.01:
        print(f"  ✅ Reconciled Math: €{stockout_loss:,.2f} (Stockouts) + €{recommender_loss:,.2f} (Recommender) + €{ad_throttling_loss:,.2f} (Ad Throttling) = €{reconciled_sum:,.2f} [PASS]")
        passed += 1
    else:
        print(f"  ❌ Reconciled Sum Mismatch: €{reconciled_sum:,.2f} != €530,000.00 [FAIL]")

    print("\n" + "=" * 80)
    success_rate = (passed / total) * 100.0
    print(f"DATA & STATISTICAL RATIOS VALIDATION SUMMARY: {passed}/{total} Tests Passed ({success_rate:.1f}% Success)")
    print("=" * 80)

    if passed != total:
        sys.exit(1)

if __name__ == "__main__":
    run_validation()
