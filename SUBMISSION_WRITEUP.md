# TrustLens AI ΓÇö Submission Write-Up

## Problem Statement

Digital fraud is a growing epidemic. Fake companies, phishing domains, forged offer letters, and advance-fee scams affect millions of job seekers, freelancers, and small businesses every year. When a person receives a suspicious job offer, a vendor proposal, or a freelance client inquiry, verifying its authenticity requires checking multiple disconnected sources simultaneously ΓÇö corporate registries, WHOIS databases, DNS records, SSL certificates, social sentiment, news archives, and document metadata. This process is slow, inconsistent, and demands specialist knowledge that most individuals do not have.

The result is that people fall back on intuition, and sophisticated scammers exploit exactly this gap. A domain registered yesterday can be made to look indistinguishable from a legitimate business. A forged offer letter from a convincing company name is almost impossible to detect without technical tools. The barrier to performing proper due diligence is simply too high for the average user.

**TrustLens AI** eliminates this barrier entirely. It acts as an always-available, automated digital fraud investigator that performs professional-grade due diligence in seconds, through a conversational interface, for anyone.

---

## Solution Overview

TrustLens AI is a backend-first Python application built on the **Google Agent Development Kit (ADK)**. It orchestrates a team of eight specialised AI agents arranged in a directed workflow graph to investigate an entity ΓÇö a company, a domain, a document, or a person ΓÇö from multiple independent angles simultaneously. All findings are synthesised into a single structured **Trust Score**, **Risk Score**, **Confidence Score**, and a professional investigation report delivered back to the user.

Users interact through the ADK Dev UI at `http://127.0.0.1:18081`. They can provide free-text queries, paste document content, supply domain names, or upload images of physical documents. The system handles all investigation logic autonomously and returns a complete Markdown report ΓÇö including an executive summary, categorised evidence, and specific recommended next steps ΓÇö within seconds.

---

## Architecture

TrustLens AI is structured as a **multi-layer, graph-based multi-agent system**.

### Technology Stack

| Layer | Component | Technology |
|---|---|---|
| AI Orchestration | ADK Workflow | `google.adk.workflow.Workflow` |
| Agents | 8 ├ù LlmAgent | `gemini-2.5-flash` via Gemini API |
| Tool Server | MCP Server | `FastMCP` (subprocess, stdio) |
| Session Storage | SQLite | ADK-managed `session.db` |
| Backend Server | ADK Web Server | FastAPI + Uvicorn (`:18081`) |
| Production Runtime | Vertex AI Agent Engine | `AdkApp` + `GcsArtifactService` |
| Telemetry | OpenTelemetry | `opentelemetry-instrumentation-google-genai` |
| Package Manager | uv | `pyproject.toml` + `uv.lock` |

### Workflow Graph

The entire investigation lifecycle is encoded as an explicit directed graph with named edges and conditional routing:

```
START
  ΓööΓöÇΓû║ security_checkpoint
         Γö£ΓöÇ[SECURITY_EVENT]ΓöÇΓû║ final_output
         ΓööΓöÇ[SAFE]ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓû║ coordinator
                                  Γöé
                          (AgentTool calls)
                        ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓö¼ΓöÇΓöÇΓö┤ΓöÇΓöÇΓö¼ΓöÇΓöÇΓöÇΓöÇΓöÇΓö¼ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ
                  company  website social document scam
                   _agent   _agent  _agent  _agent  _agent
                        ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓö┤ΓöÇΓöÇΓö¼ΓöÇΓöÇΓö┤ΓöÇΓöÇΓöÇΓöÇΓöÇΓö┤ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ
                                  Γöé
                         evidence_aggregator
                                  Γöé
                        risk_assessment_agent
                                  Γöé
                       pre_human_review_state
                                  Γöé
                        explainability_agent
                                  Γöé
                           human_review
                          ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓö┤ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ
                    [needs_review]        [auto-approved]
                     RequestInput              Γöé
                     (pauses UI)              Γöé
                          ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓö¼ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ
                                  Γöé
                           final_output
```

---

## ADK Concepts Used

### 1. ADK Workflow (`app/agent.py`)

The investigation is defined using `google.adk.workflow.Workflow` ΓÇö a directed graph engine that orchestrates both synchronous Python nodes and async LLM Agent nodes in a single pipeline. Edges between nodes can carry named routes (e.g., `SAFE`, `SECURITY_EVENT`), enabling deterministic conditional branching without any if-else logic scattered across the codebase. The workflow definition in `agent.py` is explicit and readable:

```python
workflow = Workflow(
    name="trustlens_workflow",
    edges=[
        ('START', security_checkpoint),
        (security_checkpoint, {"SAFE": coordinator, "SECURITY_EVENT": final_output}),
        (coordinator, evidence_aggregator),
        (evidence_aggregator, risk_assessment_agent),
        (risk_assessment_agent, pre_human_review_state),
        (pre_human_review_state, explainability_agent),
        (explainability_agent, human_review),
        (human_review, final_output)
    ]
)
```

### 2. LlmAgent (`app/agent.py`)

We deployed **8 distinct `LlmAgent` instances**, each with a precisely scoped system instruction that enforces domain-specific reasoning and prevents hallucinations through over-generalisation. Each agent is isolated: it cannot call tools that belong to another agent's domain, and its instruction tells it exactly what to output. The agents are:

- **`coordinator`** ΓÇö Investigation orchestrator; routes to sub-agents and consolidates evidence
- **`company_agent`** ΓÇö Verifies corporate registration, history, and physical address
- **`website_agent`** ΓÇö Investigates domain age, WHOIS, SSL, DNS, and hosting
- **`social_agent`** ΓÇö Analyses public sentiment, news mentions, and review scores
- **`document_agent`** ΓÇö Examines documents and images for forgery indicators and metadata anomalies
- **`scam_agent`** ΓÇö Detects language-based fraud patterns (urgency, advance-fee, impossible promises)
- **`risk_assessment_agent`** ΓÇö Calculates quantitative risk scores from aggregated evidence (no investigation)
- **`explainability_agent`** ΓÇö Converts structured data into a professional Markdown investigation report

### 3. AgentTool (`app/agent.py`)

The `coordinator` uses `AgentTool` to call each specialised sub-agent as if it were a regular tool. This creates a true **hierarchical multi-agent architecture** where the coordinator decides at runtime which combination of agents is relevant to the user's specific input. For example, a query mentioning a company name and a domain triggers `company_agent` and `website_agent`; a plain suspicious text message may only trigger `scam_agent`. The coordinator wraps all five sub-agents:

```python
tools=[
    AgentTool(company_agent),
    AgentTool(website_agent),
    AgentTool(social_agent),
    AgentTool(document_agent),
    AgentTool(scam_agent),
    mcp_toolset
]
```

### 4. MCP Server (`app/mcp_server.py`)

We implemented a **Model Context Protocol (MCP) tool server** using `FastMCP`, launched as a subprocess by the ADK and connected via stdin/stdout JSON-RPC. This architecture keeps tool execution completely isolated from agent reasoning. The MCP server exposes **14 domain-specific investigation tools** across four categories:

| Category | Tools |
|---|---|
| Company | `search_company_registry` |
| Website | `whois_lookup`, `dns_lookup`, `ssl_inspection`, `website_metadata`, `check_domain_reputation`, `url_reputation` |
| Document | `pdf_metadata`, `document_hash`, `qr_decoder` |
| Social/Reputation | `search_social_sentiment`, `news_search`, `review_search`, `virus_scan` |

The `McpToolset` is shared across all investigation agents that need tool access. The `scam_agent` and the reasoning-only agents (`risk_assessment_agent`, `explainability_agent`) do not use the toolset, keeping their reasoning clean and uncontaminated by external data calls.

### 5. Pure Python Workflow Nodes (`@node`)

Three critical pipeline stages are implemented as deterministic Python `@node` functions rather than LLM agents ΓÇö a deliberate design choice to avoid non-determinism where structure and correctness matter most:

- **`security_checkpoint`** ΓÇö Synchronous node running before any LLM is called; performs security screening, PII scrubbing, and input routing
- **`evidence_aggregator`** ΓÇö Synchronous node that parses the coordinator's JSON output, extracts the evidence list, and stores it in session state
- **`pre_human_review_state`** ΓÇö Synchronous node that bridges the risk assessment output into session state so the `human_review` node can read the `needs_review` flag later
- **`final_output`** ΓÇö Terminal node that assembles the complete investigation report from session state fragments

### 6. Async Human-in-the-Loop (`human_review` @node)

The `human_review` node is an **async generator node** ΓÇö the most sophisticated node in the pipeline. It reads `ctx.state["risk_assessment"]["needs_review"]` to determine whether the investigation's confidence is sufficient for automatic delivery, or whether it requires human approval before publishing the report. When review is required, it `yield`s a `RequestInput` event, which physically **pauses the entire workflow** and presents a prompt in the Dev UI chat box. The ADK runner suspends execution at this node and waits. When the user responds (e.g., "Approved"), the runner resumes the node via `ctx.resume_inputs`, stores the human decision in session state, and forwards the report to `final_output`.

### 7. Session State (`ctx.state`)

The ADK's `ctx.state` dictionary, backed by SQLite, serves as the memory layer shared across all nodes in the workflow. Intermediate results ΓÇö the aggregated evidence list, the risk assessment JSON, the Markdown report draft, the human approval decision, and the investigation timeline ΓÇö are all stored and read through `ctx.state`. This eliminates the need for any custom database or message-passing infrastructure.

### 8. ADK Dev UI & Agents CLI

The `make playground` command (`uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents`) launches the ADK's built-in development UI, which provides a real-time graph visualisation panel showing each node's execution state (highlighted green when active), an Events tab streaming every intermediate agent output, and a Trace tab showing the complete OpenTelemetry span for each run. This was used extensively during development to debug agent routing and evidence quality.

---

## Security Design

The `security_checkpoint` node implements a **zero-trust gateway** that runs before any LLM is invoked. It operates in four stages:

1. **Prompt Injection Detection**: Scans for manipulation keywords ΓÇö `"ignore previous"`, `"bypass"`, `"override"`, `"you are now"` ΓÇö and immediately routes to `final_output` via `SECURITY_EVENT` if detected, returning a block message without any LLM call.

2. **Domain Blocklisting**: Hard-blocks any investigation involving `.mil` or `.gov` domains, preventing the system from being used as a reconnaissance tool against military or government infrastructure.

3. **PII Scrubbing**: Five regex patterns redact sensitive identifiers before they ever reach the Gemini API:
   - Credit card numbers ΓåÆ `[REDACTED_CC]`
   - Social Security Numbers ΓåÆ `[REDACTED_SSN]`
   - Email addresses ΓåÆ `[REDACTED_EMAIL]`
   - Phone numbers ΓåÆ `[REDACTED_PHONE]`
   - API keys in query strings ΓåÆ `[REDACTED_API_KEY]`

4. **Multimodal Preservation**: If the input contains an uploaded image (a multimodal `parts` object), the checkpoint patches only the text part in-place with the scrubbed content and returns the full multimodal object ΓÇö preserving the image for the coordinator's vision analysis.

---

## Data Models (`app/models.py`)

All inter-agent data exchange uses typed Pydantic models:

- **`EvidenceItem`**: The atomic unit of evidence. Each item carries `source_agent`, `category`, `description`, `confidence` (LOW/MEDIUM/HIGH/CRITICAL), `severity` (POSITIVE/NEUTRAL/NEGATIVE/CRITICAL_RED_FLAG), `verification_status`, and a numeric `risk_impact` score.

- **`RiskAssessment`**: The structured output of `risk_assessment_agent`. Contains `trust_score`, `risk_score`, `confidence_score` (all 0ΓÇô100), `risk_level` (LOW/MEDIUM/HIGH/CRITICAL), `recommendation`, `uncertainties`, `evidence_weighting`, and the critical `needs_review` boolean that gates human review.

- **`SecurityEvent`**: Produced by `security_checkpoint` on violations. Carries the `violation_reason` that `final_output` surfaces to the user.

- **`InvestigationState`**: A string enum used exclusively for labelling the `timeline` list in session state, providing a readable audit trail of every pipeline stage executed during an investigation.

---

## End-to-End Example: Job Offer Fraud Detection

**User input**: *"Investigate this offer letter from NovaTech Innovations. They want a Γé╣5000 security deposit for my laptop before joining. The website is novatech-careers.com."*

1. **`security_checkpoint`**: No injection keywords, no blocked domains. PII scrubbed (none found). Routes `SAFE` to coordinator.
2. **`coordinator`**: Identifies company name ("NovaTech Innovations"), domain ("novatech-careers.com"), and suspicious payment request. Decides to call `company_agent`, `website_agent`, and `scam_agent`.
3. **`company_agent`** ΓåÆ calls `search_company_registry("NovaTech Innovations")` via MCP ΓåÆ finds no legitimate registration ΓåÆ returns `CRITICAL_RED_FLAG` EvidenceItem.
4. **`website_agent`** ΓåÆ calls `whois_lookup("novatech-careers.com")` ΓåÆ finds domain registered 2 days ago ΓåÆ returns `CRITICAL_RED_FLAG` EvidenceItem. Also calls `ssl_inspection` and `dns_lookup`.
5. **`scam_agent`** ΓåÆ no tools; reasons over text ΓåÆ detects advance-fee language ("security deposit"), urgency framing, promises of employment ΓÇö returns multiple `NEGATIVE` and `CRITICAL_RED_FLAG` EvidenceItems.
6. **`evidence_aggregator`**: Parses the consolidated JSON from coordinator, stores 7 EvidenceItems in `ctx.state["aggregated_evidence"]`.
7. **`risk_assessment_agent`**: Weighs evidence ΓÇö 4 critical red flags, 3 negative items, 0 positive items ΓåÆ `trust_score: 8`, `risk_score: 95`, `confidence_score: 62`, `risk_level: CRITICAL`, `needs_review: true` (confidence below 70 threshold).
8. **`pre_human_review_state`**: Stores the RiskAssessment in `ctx.state["risk_assessment"]`.
9. **`explainability_agent`**: Generates a professional Markdown report with Executive Summary, Evidence Summary table, and Suggested Next Steps (do not pay, report to cyber crime cell, verify via official channels).
10. **`human_review`**: Reads `needs_review: true`. Yields `RequestInput`, pausing workflow. UI displays: *"Investigation requires human reviewΓÇª Do you approve?"* User types "Yes." Workflow resumes, stores approval.
11. **`final_output`**: Assembles final Markdown: report + Human Review Status + Investigation Timeline. Delivered to browser via SSE.

---

## Production Deployment

TrustLens AI includes a complete production deployment stack:

- **`app/agent_runtime_app.py`**: Extends `AdkApp` from the Vertex AI SDK to create an `AgentEngineApp`. In production, it initialises OpenTelemetry tracing, configures Google Cloud Logging, and switches artifact storage from `InMemoryArtifactService` to `GcsArtifactService` (writing to a GCS bucket). It also exposes a `register_feedback()` operation that accepts user ratings and logs them as structured entries to Cloud Logging.

- **`app/app_utils/telemetry.py`**: Configures OpenTelemetry prompt-response logging in `NO_CONTENT` mode ΓÇö traces are sent to GCS but actual prompt/response content is never stored, protecting user privacy by design.

- **`deployment/terraform/`**: Infrastructure-as-code for GCP deployment targeting Vertex AI Agent Engine, with separate modules for shared resources and single-project topology.

- **`agents-cli-manifest.yaml`**: Project manifest for the `agents-cli` tool, specifying `deployment_target: agent_runtime` (Vertex AI Agent Engine), `session_type: none` (ADK-managed sessions), and `cicd_runner: skip`.

---

## Demo Scenarios

### Scenario 1 ΓÇö Job Offer Fraud
**Input**: Description of a suspicious offer letter with an advance payment request and a newly registered domain.
**Expected**: Coordinator routes to `company_agent`, `website_agent`, `scam_agent`. Risk assessment outputs CRITICAL level with `needs_review: true`. Workflow pauses for human approval. Final report includes the full evidence breakdown.
**ADK Dev UI check**: Watch the Graph panel highlight each node in sequence. Open the Events tab to see each sub-agent's raw JSON evidence output in real time.

### Scenario 2 ΓÇö Security Block
**Input**: *"My SSN is 123-456-7890. Check if badguy.mil is safe."*
**Expected**: `security_checkpoint` strips the SSN to `[REDACTED_SSN]`, then detects `.mil` domain, immediately routes `SECURITY_EVENT` to `final_output`. No LLM is ever called.
**ADK Dev UI check**: The Graph panel traces directly from `security_checkpoint` to `final_output`, skipping all other nodes.

### Scenario 3 ΓÇö Visual Document Analysis
**Input**: Upload an image of a physical offer letter; type "Check if this document is genuine."
**Expected**: `security_checkpoint` preserves the multimodal content. Coordinator (as the vision model) extracts text, company name, visual inconsistencies, and suspicious elements from the image, then routes to `document_agent` and `scam_agent` with the extracted content as text.
**ADK Dev UI check**: Open the Events tab to see the Coordinator's internal reasoning as it interprets the image and constructs the input payload for sub-agents.

---

## Impact and Value

TrustLens AI demonstrates that Google ADK's multi-agent primitives ΓÇö `Workflow`, `LlmAgent`, `AgentTool`, `McpToolset`, and `RequestInput` ΓÇö can be combined to build a production-quality automated investigation system that is both technically rigorous and practically useful.

The system compresses what would take a skilled analyst 30ΓÇô60 minutes of manual research across a dozen tools into a **15-second automated pipeline**. It applies consistent, structured, evidence-based methodology to every investigation, producing auditable, explainable reports rather than opaque verdicts. It gives everyday users ΓÇö job seekers, freelancers, small business owners ΓÇö access to professional-grade due diligence that was previously available only to large enterprises with dedicated security teams.

By separating deterministic logic (security gating, evidence parsing, report assembly) from probabilistic reasoning (agent investigation, risk scoring, report narration), and by enforcing strict data contracts between stages via Pydantic models, TrustLens AI achieves a level of reliability and debuggability that is rare in LLM-powered systems. The architecture is designed to scale: new investigation domains can be added by creating a new `LlmAgent`, registering it as an `AgentTool` on the coordinator, and adding the relevant MCP tools ΓÇö without touching any other part of the pipeline.

TrustLens AI is not a prototype ΓÇö it is a complete, deployable digital trust platform built from the ground up on the Google ADK.
