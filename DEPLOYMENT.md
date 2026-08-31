# Deployment & Operational Execution Guide

This document outlines the step-by-step instructions to deploy, run, seed, and verify the LumièreShop platform components across Google Cloud BigQuery, Google Cloud Knowledge Catalog, Google Cloud Gemini Data Analytics Agent, and Google Cloud Run.

---

## 1. Environment Setup & API Enablement

### Step 1.1: Authenticate Google Cloud CLI & Set Project
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_GCP_PROJECT_ID
```

---

### Step 1.2: Enable All 12 Required Google Cloud APIs
```bash
gcloud services enable \
  bigquery.googleapis.com \
  bigqueryconnection.googleapis.com \
  dataplex.googleapis.com \
  datacatalog.googleapis.com \
  geminidataanalytics.googleapis.com \
  cloudaicompanion.googleapis.com \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=YOUR_GCP_PROJECT_ID
```

---

### Step 1.2b: Grant Developer Provisioning IAM Roles (If not Project Owner)
```bash
for ROLE in roles/bigquery.admin roles/dataplex.catalogAdmin roles/dataplex.aspectTypeOwner roles/dataplex.metadataWriter roles/datacatalog.admin roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
    --member="user:$(gcloud config get-value account)" \
    --role="$ROLE"
done
```

---

### Step 1.3: Configure Environment Variables (`.env`)
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
DATA_AGENT_ID=gda-blackweek-primary
DATA_AGENT_A_ID=gda-blackweek-a
DATA_AGENT_B_ID=gda-blackweek-b
DATA_AGENT_C_ID=gda-blackweek-c

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
### Turnkey Single-Command Cloud Run Deployment (Recommended)

```bash
python3 scripts/deploy_cloud_run.py
```

---

### Step-by-Step Manual Deployment

```bash
# 1. Resolve Project ID and Region dynamically from .env or active gcloud config
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  PROJECT_ID=$(grep -E '^GCP_PROJECT_ID=' .env | cut -d '=' -f2 | tr -d ' "\r\n')
fi

REGION=$(grep -E '^BQ_LOCATION=' .env | cut -d '=' -f2 | tr -d ' "\r\n')
REGION=${REGION:-"us-central1"}

echo "Deploying to Project: ${PROJECT_ID} in Region: ${REGION}"

# 2. Create Docker Repository in Artifact Registry (if not already created)
gcloud artifacts repositories create lumiere-shop-repo \
  --repository-format=docker \
  --location=${REGION} \
  --description="Docker repository for LumièreShop" \
  --project=${PROJECT_ID} || true

# 3. Grant required IAM roles to Cloud Run Compute Service Account
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")

for ROLE in roles/geminidataanalytics.dataAgentUser roles/geminidataanalytics.dataAgentStatelessUser roles/bigquery.admin roles/bigquery.dataEditor roles/bigquery.jobUser roles/dataplex.viewer roles/aiplatform.user roles/cloudaicompanion.user roles/storage.admin roles/artifactregistry.writer roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="$ROLE" \
    --quiet
done

# 4. Build and push container image via Cloud Build
gcloud builds submit \
  --tag=${REGION}-docker.pkg.dev/${PROJECT_ID}/lumiere-shop-repo/lumiere-app:latest \
  --project=${PROJECT_ID}

# 5. Deploy to Cloud Run
gcloud run deploy lumiere-shop-app \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/lumiere-shop-repo/lumiere-app:latest \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=${PROJECT_ID},BQ_DATASET_ID=ecommerce_dw,BQ_LOCATION=${REGION},CA_API_HOST=https://geminidataanalytics.googleapis.com,CA_API_ENDPOINT=https://geminidataanalytics.googleapis.com/v1beta/projects/${PROJECT_ID}/locations/global:chat,DATA_AGENT_ID=gda-blackweek-primary,DATA_AGENT_A_ID=gda-blackweek-a,DATA_AGENT_B_ID=gda-blackweek-b,DATA_AGENT_C_ID=gda-blackweek-c,USER_NAME_SCREEN=on
```

### Production Architecture & Feature Highlights
- **Screen 1 Knowledge Catalog Prompt Container & Sales Bot Binding**: Step 1 dynamically displays the exact semantic search prompt dispatched to Knowledge Catalog inside a Material Design 3 container. The "Lumière Sales Bot" sidebar item is bound to the canonical Black Friday prompt.
- **In-Window Stateful Investigation Reset**: Clicking "Start New Investigation" on the Summary Screen generates a new stateful session (`currentSessionId`), clears the thread to the initial greeting, resets telemetry counters to 0, and keeps the user in the same workspace window without bouncing back to Screen 1.
- **Clean Workspace Entry**: Launching the single-agent workspace or 3-agent cockpit starts cleanly with 0 automated user messages in the chat stream.
- **Dynamic Knowledge Catalog Discovery Counts**: Null-coalesced live counts (`table_count`, `term_count`, `entry_link_count`) dynamically rendered across all 4 preparation steps without placeholder fallbacks.
- **UI Header & Modal Control Refinements**: Clean navigation with "Summary & Exit" action button and "Close" modal controls.
- **Screen 0 Operator Entry**: Configurable initial screen (`USER_NAME_SCREEN=on`) with validation and session-wide auditing.
- **Compare Chats Multi-Agent Auditing & Table Rendering**: 100-row table capacity, vertical scrolling with sticky headers, dynamic row count badges, and BigQuery logging tagged with `menu_item` and `agent_no`.
- **Knowledge Catalog EntryLinks**: Native EntryLinks resolution between BigQuery tables and Glossary Terms, returning `table_count`, `term_count`, and `entry_link_count` with single-call search discovery (15 categories, 85 terms, 188 EntryLinks).
- **Multilingual Support**: Material Design 3 language selector on Screen 1 supporting 25 European & global languages in alphabetical order. Defaults to English (`en`).
- **Full Candidate Prompt Localization**: All candidate prompt presets (Revenue Incident, Logistics & SLAs, Marketing & ROAS) and scenario tabs in Prompt Studio and Compare Chats modals are fully localized across all 25 languages.
- **Prompt Scoring Calibration**: Differentiated scoring engine (50–98) based on retrieved table counts and domain breadth.
- **Server-Managed Stateful Context**: Enabled via Google Cloud `conversation_reference` and nested `data_agent_context`.
- **Prompt Studio Access**: Clicking *"Compare prompts"* 3 times rapidly under Apps in the left sidebar opens the Prompt Comparison Studio.
- **3-Agent Parallel Cockpit**: Clicking *"Compare chats"* 3 times rapidly under Apps in the left sidebar opens the 3-Agent side-by-side comparative workspace with dedicated Google Cloud Data Agents (`gda-blackweek-a`, `gda-blackweek-b`, `gda-blackweek-c`).

### Verify Live Cloud Run Service
```bash
# Deployed live service URL on Google Cloud Run
SERVICE_URL="https://lumiere-shop-app-htjxtcbs5a-ez.a.run.app"

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

## 8. Environment Teardown & Cleanup Tools

To clean up resources after testing or to reset an environment on Google Cloud:

### Master Teardown (All 3 Cleanup Stages in One Command)
Executes sequential teardown across Gemini Data Agents, Knowledge Catalog governance resources, and disables auxiliary Google Cloud APIs, while preserving the BigQuery dataset and 140 tables intact:

```bash
# Interactive confirmation
python3 scripts/cleanup_all.py

# Non-interactive / Automated execution
python3 scripts/cleanup_all.py --force
```

### Standalone Cleanup Scripts
If executing cleanup stages individually:

1. **Purge Gemini Enterprise Data Agents**:
   ```bash
   python3 scripts/cleanup_data_agents.py --force
   ```
2. **Purge Knowledge Catalog Glossaries, Terms, Categories, EntryLinks, and AspectTypes**:
   ```bash
   python3 scripts/cleanup_knowledge_catalog.py --force
   ```
3. **Disable Auxiliary Google Cloud APIs (Preserves BigQuery Dataset)**:
   ```bash
   python3 scripts/cleanup_gcp_apis.py --force
   ```


