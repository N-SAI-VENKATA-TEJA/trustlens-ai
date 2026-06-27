from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum
from datetime import datetime
import uuid

class InvestigationState(str, Enum):
    QUEUED = "Queued"
    INPUT_VALIDATION = "Input Validation"
    SECURITY_CHECK = "Security Check"
    PLANNING = "Planning"
    INVESTIGATION_RUNNING = "Investigation Running"
    EVIDENCE_COLLECTION = "Evidence Collection"
    EVIDENCE_VALIDATION = "Evidence Validation"
    RISK_ASSESSMENT = "Risk Assessment"
    EXPLANATION_GENERATION = "Explanation Generation"
    HUMAN_REVIEW = "Human Review"
    COMPLETED = "Completed"
    BLOCKED = "Blocked"

class SecurityEvent(BaseModel):
    event: Literal["security_scan"] = "security_scan"
    severity: Literal["INFO", "WARNING", "CRITICAL"] = "INFO"
    actions: List[str] = Field(default_factory=list)
    scrubbed_input: Optional[str] = None
    violation_reason: Optional[str] = None
    is_safe: bool = True

class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str
    category: str
    description: str
    confidence: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    severity: Literal["POSITIVE", "NEUTRAL", "NEGATIVE", "CRITICAL_RED_FLAG"] = "NEUTRAL"
    source: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    verification_status: Literal["UNVERIFIED", "VERIFIED", "CONFLICTED"] = "UNVERIFIED"
    supporting_data: Optional[str] = None
    risk_impact: int = 0  # e.g., +10 for positive, -50 for critical

class RiskAssessment(BaseModel):
    trust_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    recommendation: str
    uncertainties: List[str]
    evidence_weighting: str
    needs_review: bool

class InvestigationReport(BaseModel):
    executive_summary: str
    investigation_overview: str
    risk_assessment: RiskAssessment
    positive_findings: List[EvidenceItem]
    negative_findings: List[EvidenceItem]
    neutral_findings: List[EvidenceItem]
    scam_indicators: List[EvidenceItem]
    missing_information: List[str]
    suggested_next_steps: List[str]
    timeline: List[str]
    participating_agents: List[str]
    human_review_status: str
