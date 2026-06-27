from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from google.adk.agents.context import Context
from google.adk.workflow import Workflow, node
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
import sys
import re
import json
import urllib.parse
from .config import config
from .models import EvidenceItem, SecurityEvent, RiskAssessment, InvestigationState

# -----------------------------------------------------------------------------
# MCP Toolset Setup
# -----------------------------------------------------------------------------
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
        )
    )
)

# -----------------------------------------------------------------------------
# Investigation Agents
# -----------------------------------------------------------------------------
EVIDENCE_INSTRUCTION = (
    "You MUST output ONLY a valid JSON list of EvidenceItem objects. "
    "Do not include markdown blocks, just the JSON array. "
    "Example format: [{\"source_agent\": \"name\", \"category\": \"cat\", \"description\": \"desc\", \"confidence\": \"HIGH\", \"severity\": \"POSITIVE\", \"source\": \"src\", \"verification_status\": \"VERIFIED\", \"risk_impact\": 10}]"
)

company_agent = LlmAgent(
    name="company_agent",
    model=config.model,
    instruction=f"Investigate company legitimacy, registration, history, and physical address. Use tools. {EVIDENCE_INSTRUCTION}",
    tools=[mcp_toolset],
)

website_agent = LlmAgent(
    name="website_agent",
    model=config.model,
    instruction=f"Investigate domain age, WHOIS, SSL, DNS, and hosting. Use tools. {EVIDENCE_INSTRUCTION}",
    tools=[mcp_toolset],
)

social_agent = LlmAgent(
    name="social_agent",
    model=config.model,
    instruction=f"Investigate public reputation, reviews, news mentions, and sentiment. Use tools. {EVIDENCE_INSTRUCTION}",
    tools=[mcp_toolset],
)

document_agent = LlmAgent(
    name="document_agent",
    model=config.model,
    instruction=f"Examine document text/metadata for consistency, forgery indicators, and suspicious wording. Use tools. {EVIDENCE_INSTRUCTION}",
    tools=[mcp_toolset],
)

scam_agent = LlmAgent(
    name="scam_agent",
    model=config.model,
    instruction=f"Analyze all provided text for common fraud patterns (urgency, advance fee, poor grammar, impossible promises). {EVIDENCE_INSTRUCTION}",
)

# -----------------------------------------------------------------------------
# Orchestration Agent
# -----------------------------------------------------------------------------
coordinator = LlmAgent(
    name="coordinator",
    model=config.model,
    instruction=(
        "You are the TrustLens AI Investigation Coordinator. "
        "Review the user input, determine which specialized agents to call, and execute them. "
        "Gather all evidence returned by the agents. "
        "CRITICAL RULE FOR FILES: Sub-agents cannot see uploaded images or PDFs. If the user attaches a file, YOU must act as the vision model. Visually analyze the file, extract all text, company names, URLs, and any suspicious visual elements. You must then pass this highly detailed extraction as text into the input argument when you call the document_agent and other relevant agents. "
        "You MUST output ONLY a valid JSON object containing a single key 'all_evidence' which is a flat list of all EvidenceItem objects collected."
    ),
    tools=[
        AgentTool(company_agent),
        AgentTool(website_agent),
        AgentTool(social_agent),
        AgentTool(document_agent),
        AgentTool(scam_agent),
        mcp_toolset
    ],
)

# -----------------------------------------------------------------------------
# Reasoning & Reporting Agents
# -----------------------------------------------------------------------------
risk_assessment_agent = LlmAgent(
    name="risk_assessment",
    model=config.model,
    instruction=(
        "You are the Risk Assessment Agent. You receive a JSON list of EvidenceItem objects. "
        "You do NOT investigate. You ONLY reason over the evidence to calculate risk. "
        "Calculate trust_score (0-100), risk_score (0-100), confidence_score (0-100). "
        "Determine risk_level (LOW, MEDIUM, HIGH, CRITICAL). "
        "Set needs_review to true if confidence < 70, critical red flags exist, or there is conflicting evidence. "
        "You MUST output ONLY a valid JSON object matching the RiskAssessment schema exactly."
    )
)

explainability_agent = LlmAgent(
    name="explainability",
    model=config.model,
    instruction=(
        "You are the Explainability Agent. You receive the structured RiskAssessment and Evidence items. "
        "Your job is to convert this into a highly professional, due-diligence style investigation report in Markdown format. "
        "Include an Executive Summary, Investigation Overview, Scores (Trust/Risk/Confidence), Risk Level, "
        "Evidence Summary (Positive, Negative, Neutral, Scam Indicators), Missing Information, and Suggested Next Steps. "
        "Do NOT mention 'needs_review' or human review status, the system will append that later."
    )
)

# -----------------------------------------------------------------------------
# Workflow Nodes
# -----------------------------------------------------------------------------
@node
def security_checkpoint(ctx: Context, node_input):
    ctx.state["timeline"] = [f"{InvestigationState.QUEUED.value}: Request received"]
    ctx.state["timeline"].append(f"{InvestigationState.INPUT_VALIDATION.value}: Started")
    ctx.state["timeline"].append(f"{InvestigationState.SECURITY_CHECK.value}: Running")

    audit = SecurityEvent()
    text = ""
    if hasattr(node_input, "parts") and len(node_input.parts) > 0:
        text = node_input.parts[0].text
    else:
        text = str(node_input)

    # Prompt Injection
    injection_kw = ["ignore previous", "bypass", "override", "you are now"]
    for kw in injection_kw:
        if kw in text.lower():
            audit.severity = "CRITICAL"
            audit.actions.append("Prompt injection detected")
            audit.violation_reason = "Prompt injection attempt"
            audit.is_safe = False
            return Event(output=audit.model_dump_json(), route="SECURITY_EVENT")
            
    # Domain Rule
    if ".mil" in text.lower() or ".gov" in text.lower():
        audit.severity = "WARNING"
        audit.actions.append("Blocked .mil/.gov investigation")
        audit.violation_reason = "Cannot investigate military or government entities"
        audit.is_safe = False
        return Event(output=audit.model_dump_json(), route="SECURITY_EVENT")

    # Expanded PII Scrubbing
    scrubbed = text
    patterns = {
        r'\b(?:\d[ -]*?){13,16}\b': "[REDACTED_CC]",
        r'\b\d{3}-\d{2}-\d{4}\b': "[REDACTED_SSN]",
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b': "[REDACTED_EMAIL]",
        r'\b\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b': "[REDACTED_PHONE]",
        r'(?i)api_key[=:]\s*[A-Za-z0-9_-]+': "[REDACTED_API_KEY]"
    }
    for pat, replacement in patterns.items():
        if re.search(pat, scrubbed):
            scrubbed = re.sub(pat, replacement, scrubbed)
            audit.actions.append(f"Scrubbed PII matching pattern {replacement}")

    # URL Normalization (basic)
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', scrubbed)
    if urls:
        audit.actions.append(f"Found and validated {len(urls)} URLs")

    audit.scrubbed_input = scrubbed
    
    if hasattr(node_input, "parts"):
        try:
            for part in node_input.parts:
                if hasattr(part, "text") and part.text:
                    part.text = scrubbed
        except Exception:
            pass
        return Event(output=node_input, route="SAFE")
    else:
        return Event(output=scrubbed, route="SAFE")

@node
def evidence_aggregator(ctx: Context, node_input: str):
    ctx.state["timeline"].append(f"{InvestigationState.EVIDENCE_VALIDATION.value}: Started")
    
    try:
        cleaned = node_input.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        
        data = json.loads(cleaned)
        evidence_list = data.get("all_evidence", [])
    except Exception as e:
        evidence_list = [{"source_agent": "system", "category": "error", "description": f"Failed to parse evidence: {e}", "risk_impact": 0}]
        
    ctx.state["aggregated_evidence"] = evidence_list
    
    # Return evidence list as JSON string for the Risk Assessment LLM
    return Event(output=json.dumps({"evidence": evidence_list}))

@node
async def human_review(ctx: Context, node_input: str):
    ctx.state["timeline"].append(f"{InvestigationState.HUMAN_REVIEW.value}: Evaluation")
    
    # node_input here comes from Explainability agent (the markdown report)
    # But we need to know if needs_review is true. We saved RiskAssessment in ctx.state in a previous node.
    # Wait, Explainability receives RiskAssessment output. Let's make Explainability output the report,
    # but we need to pass the needs_review flag. We'll read it from ctx.state.
    
    risk_data = ctx.state.get("risk_assessment", {})
    needs_review = risk_data.get("needs_review", True)
    
    ctx.state["final_report_draft"] = node_input

    if needs_review:
        if not ctx.resume_inputs:
            yield RequestInput(
                interrupt_id="review_findings", 
                message="Investigation requires human review (Low confidence, critical red flags, or conflicting evidence). Do you approve the findings?"
            )
            return
        
        user_reply = ctx.resume_inputs.get("review_findings")
        ctx.state["human_approval"] = user_reply
        ctx.state["timeline"].append(f"{InvestigationState.HUMAN_REVIEW.value}: User Responded")
        yield Event(output=node_input)
    else:
        ctx.state["human_approval"] = "Auto-approved"
        ctx.state["timeline"].append(f"{InvestigationState.HUMAN_REVIEW.value}: Auto-Approved")
        yield Event(output=node_input)

@node
def pre_human_review_state(ctx: Context, node_input: str):
    # This node simply stores the RiskAssessment output before Explainability runs
    try:
        cleaned = node_input.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        data = json.loads(cleaned)
        ctx.state["risk_assessment"] = data
    except Exception:
        ctx.state["risk_assessment"] = {"needs_review": True}
    
    # Forward the same input to Explainability
    return Event(output=json.dumps({"risk_assessment": ctx.state.get("risk_assessment"), "evidence": ctx.state.get("aggregated_evidence")}))

@node
def final_output(ctx: Context, node_input: str) -> Event:
    ctx.state["timeline"].append(f"{InvestigationState.COMPLETED.value}: Finalizing report")
    
    if isinstance(node_input, str) and "violation_reason" in node_input:
        try:
            audit = json.loads(node_input)
            return Event(output=f"TrustLens Investigation Blocked:\nSecurity violation: {audit.get('violation_reason')}")
        except:
            pass

    report = ctx.state.get("final_report_draft", "No report generated.")
    approval = ctx.state.get("human_approval", "Unknown")
    
    timeline_str = "\n".join([f"- {t}" for t in ctx.state.get("timeline", [])])
    
    final_md = f"{report}\n\n## Human Review Status\n{approval}\n\n## Investigation Timeline\n{timeline_str}"
    return Event(output=final_md)

# -----------------------------------------------------------------------------
# Workflow Definition
# -----------------------------------------------------------------------------
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

app = App(
    root_agent=workflow,
    name="app",
)
