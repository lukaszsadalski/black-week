import os
import asyncio
from playwright.async_api import async_playwright

html_content = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    body {
      margin: 0;
      padding: 30px;
      background: #0b0f19;
      display: flex;
      justify-content: center;
      align-items: center;
      font-family: 'Inter', sans-serif;
    }
    #container {
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 20px;
      padding: 32px 36px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
      max-width: 1320px;
      width: 100%;
    }
    .header {
      margin-bottom: 24px;
      border-bottom: 1px solid #1f2937;
      padding-bottom: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .title {
      font-size: 22px;
      font-weight: 800;
      color: #f9fafb;
      letter-spacing: -0.02em;
    }
    .subtitle {
      font-size: 13px;
      font-weight: 500;
      color: #9ca3af;
      margin-top: 4px;
    }
    .badge {
      background: rgba(59, 130, 246, 0.12);
      border: 1px solid rgba(59, 130, 246, 0.25);
      color: #60a5fa;
      font-size: 12px;
      font-weight: 600;
      padding: 4px 12px;
      border-radius: 9999px;
    }
    .mermaid {
      display: flex;
      justify-content: center;
    }
    .mermaid svg {
      max-width: 100% !important;
      height: auto !important;
    }
  </style>
</head>
<body>
  <div id="container">
    <div class="header">
      <div>
        <div class="title">✨ LumièreShop: System &amp; Data Architecture</div>
        <div class="subtitle">Google Cloud BigQuery • Knowledge Catalog • Conversational Analytics API • Vertex AI</div>
      </div>
      <div class="badge">Production Architecture (europe-west4)</div>
    </div>
    <pre class="mermaid">
flowchart TD
    subgraph UI ["🖥️ Single-Window Material Design 3 Frontend SPA"]
        User["👤 CMO / Executive Leadership"]
        Screen1["🚨 Screen 1: Google Workspace Alert\n-27% Target Shortfall / 4-Step Progressive Data Prep"]
        PromptStudio["✨ Prompt Comparison Studio (Modal)\nVertex AI Gemini 3.7 Flash Evaluation"]
        Screen2["🎨 Screen 2: CMO Conversational Workspace\nStateful Chat, Vega-Lite Visuals, 4-Stage Reasoning"]
        Screen3["📊 Screen 3: Root Cause Solution Summary Screen\nDiagnostic Telemetry &amp; Multi-Page PDF Export"]
    end

    subgraph Backend ["⚡ FastAPI Backend Application (Port 8080 / Cloud Run)"]
        API["FastAPI App Router (main.py)"]
        DiscService["🔍 KnowledgeDiscoveryService\nPure Cloud-Native Semantic Search &amp; Glossary"]
        PromptEval["🧠 PromptEvaluatorService\nVertex AI Gemini 3.7 Flash Parallel Scoring"]
        CAService["🤖 ConversationalAnalyticsService\nServer-Managed Conversations &amp; REST PATCH Scoping"]
    end

    subgraph GCP ["☁️ Google Cloud Platform (europe-west4 / global)"]
        KC["📂 Knowledge Catalog (dataplex.googleapis.com)\nSemantic Search &amp; 39 Business Glossary Terms"]
        VertexAI["🌟 Vertex AI Platform\nGemini 3.7 Flash (global) / Gemini 2.5 Flash"]
        GCP_Conv["💬 GCP Conversation Service\nprojects/.../locations/global/conversations/{uuid}"]
        CA_API["🤖 Gemini Data Analytics API (geminidataanalytics.googleapis.com)\nconversation_reference &amp; BigQuery Data Agent"]
        BQ["🗄️ BigQuery Data Warehouse (ecommerce_dw)\n140 Tables: 63 Gold, 47 Silver, 20 Bronze, 10 Sandbox"]
        AuditLog["📝 BigQuery agent_interaction_logs\n4-Stage Reasoning Trace, Slot ms, Job IDs"]
    end

    User --> Screen1
    Screen1 -->|3 Fast Clicks on Compare prompts| PromptStudio
    PromptStudio -->|POST /api/evaluate-prompts| PromptEval
    PromptEval --> KC
    PromptEval --> VertexAI
    PromptStudio -->|Launch Investigation with Prompt X| DiscService
    Screen1 -->|Click Please prepare the data...| DiscService
    DiscService -->|Semantic Search &amp; Glossary Traversal| KC
    DiscService -->|Dynamic publishedContext tableReferences PATCH| CA_API
    Screen1 -->|Smooth Transition - 3s Pause| Screen2
    PromptStudio -->|Direct Transition| Screen2
    Screen2 -->|Click New Thread| GCP_Conv
    Screen2 -->|POST /api/chat with prompt and conversation_id| CAService
    CAService -->|POST :chat with conversation_reference| CA_API
    CA_API -->|Retrieve Stateful Context| GCP_Conv
    CA_API -->|Dynamic SQL Generation &amp; Execution| BQ
    CAService -->|Async Audit Logging| AuditLog
    Screen2 -->|Click The issue is solved| Screen3
    </pre>
  </div>

  <script>
    mermaid.initialize({
      startOnLoad: true,
      theme: 'dark',
      themeVariables: {
        darkMode: true,
        background: '#111827',
        primaryColor: '#3b82f6',
        primaryTextColor: '#f9fafb',
        primaryBorderColor: '#60a5fa',
        lineColor: '#9ca3af',
        secondaryColor: '#6366f1',
        tertiaryColor: '#0b0f19',
        fontFamily: 'Inter, sans-serif',
        fontSize: '13px'
      }
    });
  </script>
</body>
</html>
"""

os.makedirs("scratch", exist_ok=True)
os.makedirs("docs/images", exist_ok=True)
render_html_path = "scratch/arch_render.html"

with open(render_html_path, "w") as f:
    f.write(html_content)

async def render():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 1150}, device_scale_factor=2)
        await page.goto("file://" + os.path.abspath(render_html_path))
        await page.wait_for_selector(".mermaid svg", timeout=15000)
        await asyncio.sleep(2)
        
        content = await page.content()
        assert "Syntax error" not in content, "Rendered HTML contains syntax error!"
        
        container = await page.query_selector("#container")
        out_path = "docs/images/architecture_diagram.png"
        await container.screenshot(path=out_path)
        print(f"Successfully rendered architecture diagram to {out_path} ({os.path.getsize(out_path)} bytes)")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(render())
