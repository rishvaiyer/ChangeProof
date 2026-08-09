from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ChangeType(StrEnum):
    COLUMN_RENAME = "column_rename"
    COLUMN_REMOVAL = "column_removal"
    COLUMN_TYPE_CHANGE = "column_type_change"
    UNSUPPORTED = "unsupported"


class DecisionStatus(StrEnum):
    VERIFIED = "VERIFIED_WITHIN_OBSERVED_GRAPH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED_BY_INCOMPLETE_METADATA"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SqlMatchKind(StrEnum):
    CONVERT = "convert"
    CAST = "cast"
    JOIN = "join"
    PREDICATE = "predicate"
    ASSIGNMENT = "assignment"
    DYNAMIC_SQL = "dynamic_sql"


class RegionRisk(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    REVIEW = "REVIEW"


class SqlDependency(BaseModel):
    schema_name: str
    object_name: str
    object_type: str
    snippet: str
    match_kind: SqlMatchKind
    confidence: Confidence
    regions: list[str] = Field(default_factory=list)
    proposed_sql: str | None = None
    manual_review_reason: str | None = None


class RegionExposure(BaseModel):
    region: str
    asset_names: list[str] = Field(default_factory=list)
    sql_objects: list[str] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    policy_flags: list[str] = Field(default_factory=list)
    risk: RegionRisk


class ArtifactBundle(BaseModel):
    impact_report_json: str
    discovery_query_sql: str
    proposed_fixes_sql: str
    validation_queries_sql: str
    rollback_sql: str
    sarif_json: str


class AiReview(BaseModel):
    status: Literal["AI_REVIEWED"] = "AI_REVIEWED"
    summary: str
    fix_notes: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)


class ChangeRequest(BaseModel):
    change_type: ChangeType
    dataset_urn: str | None = None
    old_column: str | None = None
    new_column: str | None = None
    old_type: str | None = None
    new_type: str | None = None
    source_file: Path


class LineageNode(BaseModel):
    urn: str
    name: str
    entity_type: str
    hop: int = Field(ge=1)
    fields: list[str] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    critical: bool = False


class MetadataEvidence(BaseModel):
    source_urn: str
    source_field: str
    column_lineage_available: bool
    downstream: list[LineageNode] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    assertions_passing: bool | None
    metadata_age_hours: float
    missing: list[str] = Field(default_factory=list)


class ImpactAssessment(BaseModel):
    confidence: Confidence
    reasons: list[str] = Field(default_factory=list)
    impacted_assets: list[LineageNode] = Field(default_factory=list)
    required_reviewers: list[str] = Field(default_factory=list)
    critical_assets: list[str] = Field(default_factory=list)


class RemediationAction(BaseModel):
    asset_urn: str
    asset_name: str
    action: str
    reason: str
    owner: str | None = None
    generated_files: list[Path] = Field(default_factory=list)
    validation_checks: list[str] = Field(default_factory=list)


class RemediationPlan(BaseModel):
    strategy: str
    summary: str
    actions: list[RemediationAction] = Field(default_factory=list)
    rollout_steps: list[str] = Field(default_factory=list)
    rollback_steps: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
    requires_approval: bool
    supported_automatically: bool


class GeneratedPatch(BaseModel):
    workspace: Path
    changed_files: list[Path] = Field(default_factory=list)
    strategy: str


class ValidationResult(BaseModel):
    compile_passed: bool
    tests_passed: bool
    manifest_verified: bool
    commands: list[str] = Field(default_factory=list)
    output_excerpt: str


class ProposalAction(StrEnum):
    RAISE_INCIDENT = "raise_incident"
    ADD_TAG = "add_tag"
    UPDATE_DOCS = "update_docs"


class ChangeProposal(BaseModel):
    proposal_id: str
    action: ProposalAction
    target_urn: str
    target_name: str
    title: str
    body: str
    rationale: str


class WritebackResult(BaseModel):
    succeeded: bool
    dataset_urn: str
    properties_written: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    proposal_id: str | None = None
    action: ProposalAction | None = None
    applied: bool = False
    simulated: bool = False


class ChangeProofReport(BaseModel):
    run_id: str
    request: ChangeRequest
    evidence: MetadataEvidence | None
    impact: ImpactAssessment | None
    remediation: RemediationPlan
    patch: GeneratedPatch | None
    validation: ValidationResult | None
    writeback: WritebackResult | None
    status: DecisionStatus
    summary: str
