import os
from google.cloud import bigquery

def load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_dotenv()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "ecommerce_dw")

client = bigquery.Client(project=PROJECT_ID)
sql = f"""
SELECT interaction_id, session_id, user_prompt, job_id, bytes_scanned, bytes_billed, slot_milliseconds, referenced_tables, result_row_count, step_count, has_chart, chart_type, followup_questions, data_agent_id, http_status_code
FROM `{PROJECT_ID}.{DATASET_ID}.agent_interaction_logs`
ORDER BY created_at DESC
LIMIT 1
"""
rows = list(client.query(sql).result())
if rows:
    row = dict(rows[0])
    print("Latest Logged Extended Metadata Record in BigQuery:")
    for k, v in row.items():
        print(f"  {k}: {v}")
else:
    print("No log rows found.")
