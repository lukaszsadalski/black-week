# Deployment & Operational Execution Guide

This document outlines the step-by-step instructions to deploy, run, seed, and verify the LumièreShop platform components across Google Cloud BigQuery, Google Cloud Knowledge Catalog, Google Cloud Gemini Data Analytics Agent, and Google Cloud Run.

---

## 1. Environment Setup & API Enablement

### Step 1.1: Enable All 10 Required Google Cloud APIs
```bash
gcloud services enable \
  bigquery.googleapis.com \
  dataplex.googleapis.com \
  datacatalog.googleapis.com \
  geminidataanalytics.googleapis.com \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=YOUR_GCP_PROJECT_ID
```

### Step 1.2: Configure Environment Variables (`.env`)
Verify the centralized `.env` configuration file:

```ini
# Google Cloud Platform & BigQuery Configuration
GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID
GCP_USER_IDENTITY=YOUR_EMAIL@yourdomain.com
BQ_DATASET_ID=ecommerce_dw
BQ_LOCATION=YOUR_GCP_REGION # e.g. us-central1 or preferred region

# Gemini Enterprise Agent Platform (Conversational Analytics API)
CA_API_HOST=https://geminidataanalytics.googleapis.com
CA_API_ENDPOINT=https://geminidataanalytics.googleapis.com/v1beta/projects/YOUR_GCP_PROJECT_ID/locations/global:chat
DATA_AGENT_ID=gda-lumiere-primary

# UI Screen Flow Configuration (Initial User Name Input Screen)
USER_NAME_SCREEN=on
```

Ensure gcloud is authenticated:
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_GCP_PROJECT_ID
```

---

## 2. Automated Turnkey Provisioning (Recommended)

To provision all 140 BigQuery tables, seed 19.3M calibrated records, deploy Knowledge Catalog glossaries & aspects, configure all 4 Data Agents, and run full test suites in one command:

```bash
python3 scripts/bootstrap_new_project.py
```

---

## 3. Step-by-Step Manual Initialization Pipeline

If executing stages individually:

### Step 3.1: Initialize Schema (26 Tables across Domains A–G)
```bash
python3 scripts/01_create_schema.py
```

### Step 3.2: Initialize Extended Enterprise Schema (104 Tables -> 130 Tables Total)
```bash
python3 scripts/11_create_extended_schema.py
```

### Step 3.3: Initialize Investigation Log Schemas (134 Tables)
```bash
python3 scripts/04_extend_log_schema.py
```

### Step 3.4: Apply Audit Logging Column Migrations
```bash
python3 scripts/15_add_user_name_to_logs.py
python3 scripts/17_add_menu_item_and_agent_no_to_logs.py
```

### Step 3.5: Annotate Table & Column Metadata Descriptions (100% Coverage)
```bash
python3 scripts/apply_bq_descriptions.py
```

### Step 3.6: Seed Calibrated Black Week Synthetic Data
```bash
python3 scripts/02_generate_data.py
```

### Step 3.7: Seed Extended Enterprise Domain Data
```bash
python3 scripts/12_generate_extended_data.py
```

### Step 3.8: Seed Multi-Week Historical Actuals
```bash
python3 scripts/14_generate_historical_data.py
```

### Step 3.9: Deploy Knowledge Catalog Business Glossary (15 Categories, 85 Terms, 188 EntryLinks)
```bash
python3 scripts/09_create_dataplex_glossary.py
```

### Step 3.10: Deploy Enterprise AspectType & Attach to All 140 BigQuery Tables
```bash
python3 scripts/13_setup_dataplex_aspects.py
```

### Step 3.11: Ground Gemini BigQuery Data Agents (Primary + 3 Compare Chats Agents)
```bash
python3 scripts/06_update_data_agent.py
```

### Step 3.12: Run Master Verification Suite
```bash
python3 scripts/test/run_all_tests.py --all
```

---

## 4. Local Development Execution

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend --reload
```

---

## 5. Google Cloud Run Production Deployment

```bash
# Set your target deployment region
export REGION=YOUR_GCP_REGION # e.g., us-central1 or preferred region
```

### Step 5.1: Create Docker Repository in Artifact Registry
```bash
gcloud artifacts repositories create lumiere-shop-repo \
  --repository-format=docker \
  --location=${REGION} \
  --description="Docker repository for LumièreShop" \
  --project=YOUR_GCP_PROJECT_ID
```

### Step 5.2: Grant IAM Roles to Cloud Run Service Account
```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_GCP_PROJECT_ID --format="value(projectNumber)")

for ROLE in roles/bigquery.dataEditor roles/bigquery.jobUser roles/dataplex.viewer roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="$ROLE"
done
```

### Step 5.3: Build & Push Container Image
```bash
gcloud builds submit \
  --tag=${REGION}-docker.pkg.dev/YOUR_GCP_PROJECT_ID/lumiere-shop-repo/lumiere-app:latest \
  --project=YOUR_GCP_PROJECT_ID
```

### Step 5.4: Deploy Service to Cloud Run
```bash
gcloud run deploy lumiere-shop-app \
  --image=${REGION}-docker.pkg.dev/YOUR_GCP_PROJECT_ID/lumiere-shop-repo/lumiere-app:latest \
  --region=${REGION} \
  --project=YOUR_GCP_PROJECT_ID \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID,BQ_DATASET_ID=ecommerce_dw,BQ_LOCATION=${REGION},CA_API_HOST=https://geminidataanalytics.googleapis.com,CA_API_ENDPOINT=https://geminidataanalytics.googleapis.com/v1beta/projects/YOUR_GCP_PROJECT_ID/locations/global:chat,DATA_AGENT_ID=gda-lumiere-primary,USER_NAME_SCREEN=on
```

### Production Architecture & Feature Highlights
- **UI Header & Modal Control Refinements**: Clean navigation with "Summary & Exit" action button and "Close" modal controls.
- **Screen 0 Operator Entry**: Configurable initial screen (`USER_NAME_SCREEN=on`) with validation and session-wide auditing.
- **Compare Chats Multi-Agent Auditing & Table Rendering**: 100-row table capacity, vertical scrolling with sticky headers, dynamic row count badges, and BigQuery logging tagged with `menu_item` and `agent_no`.
- **Knowledge Catalog EntryLinks**: Native EntryLinks resolution between BigQuery tables and Glossary Terms, returning `table_count`, `term_count`, and `entry_link_count` with single-call search discovery (15 categories, 85 terms, 188 EntryLinks).
- **Multilingual Support**: Material Design 3 language selector on Screen 1 supporting 25 European & global languages in alphabetical order. Defaults to English (`en`).
- **Full Candidate Prompt Localization**: All candidate prompt presets (Revenue Incident, Logistics & SLAs, Marketing & ROAS) and scenario tabs in Prompt Studio and Compare Chats modals are fully localized across all 25 languages.
- **Prompt Scoring Calibration**: Differentiated scoring engine (50–98) based on retrieved table counts and domain breadth.
- **Server-Managed Stateful Context**: Enabled via Google Cloud `conversation_reference` and nested `data_agent_context`.
- **Prompt Studio Access**: Clicking *"Compare prompts"* 3 times rapidly under Apps in the left sidebar opens the Prompt Comparison Studio.
- **3-Agent Parallel Cockpit**: Clicking *"Compare chats"* 3 times rapidly under Apps in the left sidebar opens the 3-Agent side-by-side comparative workspace with dedicated Google Cloud Data Agents (`gda-lumiere-a`, `gda-lumiere-b`, `gda-lumiere-c`).

### Verify Live Cloud Run Service
```bash
# Set your deployed service URL
SERVICE_URL="https://YOUR_SERVICE_URL.run.app"

# 1. Health Check
curl -s "${SERVICE_URL}/api/health"

# 2. Reset / Initialize Server-Managed Stateful Conversation
curl -s -X POST "${SERVICE_URL}/api/conversation/reset" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "PROD-SESSION-001"}'

# 3. Parallel Prompt Evaluation via Gemini Enterprise Agent Platform (Gemini 3.7 Flash)
curl -s -X POST "${SERVICE_URL}/api/evaluate-prompts" \
  -H "Content-Type: application/json" \
  -d '{"prompts": ["Black Week sales target missed by €735.7k", "Why did revenue decrease comparing to forecast on Black Friday?"]}'

# 4. Data Preparation & Grounding
curl -s -X POST "${SERVICE_URL}/api/prepare-data" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Black Week sales target missed by €735.7k"}'

# 5. Stateful Multi-Turn Chat Query (Turn 1)
curl -s -X POST "${SERVICE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Which category is missing its revenue target the most this week?", "session_id": "PROD-SESSION-001"}'

# 6. Stateful Follow-Up (Turn 2 - Pronoun resolution without sending Turn 1 history)
curl -s -X POST "${SERVICE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What were the primary ad campaigns for that category?", "session_id": "PROD-SESSION-001"}'
```

---

## 7. BigQuery Table Export & Archival

To export all tables from `ecommerce_dw` (excluding `agent_interaction_logs`) to individual CSV files with a generated `README.md` catalog and compressed `.tar.gz` bundle:

```bash
python3 scripts/export_bq_tables_to_csv.py
```

Outputs:
- **Archive Package**: `exports/ecommerce_dw_tables.tar.gz`
- **CSV Directory**: `exports/ecommerce_dw_csv/`
- **Export Catalog**: `exports/ecommerce_dw_csv/README.md`

