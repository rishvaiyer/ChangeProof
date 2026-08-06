from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from changeproof.models import (
    ChangeProofReport,
    ChangeRequest,
    ChangeType,
    Confidence,
    DecisionStatus,
    GeneratedPatch,
    ImpactAssessment,
    LineageNode,
    MetadataEvidence,
    RemediationAction,
    RemediationPlan,
    ValidationResult,
    WritebackResult,
)


def _streams_request(change_type: ChangeType, **overrides: object) -> ChangeRequest:
    data: dict[str, object] = {
        "change_type": change_type,
        "dataset_urn": (
            "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)"
        ),
        "source_file": Path("models/staging/stg_streams.sql"),
    }
    data.update(overrides)
    return ChangeRequest(**data)


def _lineage_nodes() -> list[LineageNode]:
    return [
        LineageNode(
            urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.marts.fct_royalties,PROD)",
            name="fct_royalties",
            entity_type="dataset",
            hop=1,
            fields=["artist_id"],
            owners=["finance@sonicledger.demo"],
        ),
        LineageNode(
            urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.marts.artist_payouts,PROD)",
            name="artist_payouts",
            entity_type="dataset",
            hop=2,
            fields=["artist_id"],
            owners=["finance@sonicledger.demo"],
            critical=True,
        ),
    ]


@pytest.fixture
def rename_request() -> Callable[..., ChangeRequest]:
    def factory(**overrides: object) -> ChangeRequest:
        data = {
            "old_column": "artist_id",
            "new_column": "rights_holder_id",
        }
        data.update(overrides)
        return _streams_request(ChangeType.COLUMN_RENAME, **data)

    return factory


@pytest.fixture
def removal_request() -> Callable[..., ChangeRequest]:
    def factory(**overrides: object) -> ChangeRequest:
        data = {
            "old_column": "artist_id",
        }
        data.update(overrides)
        return _streams_request(ChangeType.COLUMN_REMOVAL, **data)

    return factory


@pytest.fixture
def fresh_complete_evidence() -> Callable[[], MetadataEvidence]:
    def factory() -> MetadataEvidence:
        return MetadataEvidence(
            source_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
            source_field="artist_id",
            column_lineage_available=True,
            downstream=_lineage_nodes(),
            owners=["analytics@sonicledger.demo"],
            assertions_passing=True,
            metadata_age_hours=4.0,
            missing=[],
        )

    return factory


@pytest.fixture
def complete_evidence(
    fresh_complete_evidence: Callable[[], MetadataEvidence],
) -> Callable[[], MetadataEvidence]:
    def factory() -> MetadataEvidence:
        return fresh_complete_evidence()

    return factory


@pytest.fixture
def stale_evidence(
    fresh_complete_evidence: Callable[[], MetadataEvidence],
) -> Callable[[], MetadataEvidence]:
    def factory() -> MetadataEvidence:
        evidence = fresh_complete_evidence()
        return evidence.model_copy(
            update={"metadata_age_hours": 48.0, "missing": ["fresh_metadata"]}
        )

    return factory


@pytest.fixture
def complete_impact(
    complete_evidence: Callable[[], MetadataEvidence],
) -> Callable[[], ImpactAssessment]:
    def factory() -> ImpactAssessment:
        evidence = complete_evidence()
        impacted_assets = evidence.downstream
        required_reviewers = sorted(
            {*evidence.owners, *{owner for node in impacted_assets for owner in node.owners}}
        )
        critical_assets = [node.name for node in impacted_assets if node.critical]
        return ImpactAssessment(
            confidence=Confidence.HIGH,
            reasons=[
                "Fresh column lineage is available.",
                "Owners are known for the source and downstream assets.",
            ],
            impacted_assets=impacted_assets,
            required_reviewers=required_reviewers,
            critical_assets=critical_assets,
        )

    return factory


@pytest.fixture
def automatic_plan() -> Callable[[], RemediationPlan]:
    def factory() -> RemediationPlan:
        return RemediationPlan(
            strategy="compatibility_alias",
            summary="Preserve the old field while dependents migrate.",
            actions=[
                RemediationAction(
                    asset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
                    asset_name="stg_streams",
                    action="Add a compatibility alias for the renamed column.",
                    reason="Keep downstream consumers working during migration.",
                    owner="analytics@sonicledger.demo",
                    generated_files=[Path("models/staging/stg_streams.sql")],
                    validation_checks=["dbt compile", "dbt test"],
                )
            ],
            rollout_steps=["Deploy alias", "Migrate dependents"],
            rollback_steps=["Restore the previous model"],
            unresolved_risks=[],
            requires_approval=False,
            supported_automatically=True,
        )

    return factory


@pytest.fixture
def manual_plan() -> Callable[[], RemediationPlan]:
    def factory() -> RemediationPlan:
        return RemediationPlan(
            strategy="deprecation_window",
            summary="Stage a removal behind owner approval.",
            actions=[
                RemediationAction(
                    asset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
                    asset_name="stg_streams",
                    action="Document the removal and audit downstream usage.",
                    reason="Removal needs explicit coordination.",
                    owner="analytics@sonicledger.demo",
                )
            ],
            rollout_steps=["Announce a deprecation window", "Audit downstream usage"],
            rollback_steps=["Restore the field"],
            unresolved_risks=["Downstream consumers may still depend on artist_id."],
            requires_approval=True,
            supported_automatically=False,
        )

    return factory


@pytest.fixture
def passing_validation() -> Callable[[], ValidationResult]:
    def factory() -> ValidationResult:
        return ValidationResult(
            compile_passed=True,
            tests_passed=True,
            manifest_verified=True,
            commands=["uv run dbt seed", "uv run dbt compile", "uv run dbt test"],
            output_excerpt="dbt seed, compile, and test completed successfully.",
        )

    return factory


@pytest.fixture
def successful_writeback() -> Callable[[], WritebackResult]:
    def factory() -> WritebackResult:
        return WritebackResult(
            succeeded=True,
            dataset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
            properties_written={
                "changeproof_run_id": "run-001",
                "changeproof_status": DecisionStatus.VERIFIED.value,
                "changeproof_change_type": ChangeType.COLUMN_RENAME.value,
                "changeproof_confidence": Confidence.HIGH.value,
                "changeproof_remediation_strategy": "compatibility_alias",
                "changeproof_validation": "passed",
                "changeproof_report_path": "examples/reports/run-001.md",
            },
        )

    return factory


@pytest.fixture
def failed_writeback() -> Callable[[], WritebackResult]:
    def factory() -> WritebackResult:
        return WritebackResult(
            succeeded=False,
            dataset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
            properties_written={},
            error="DataHub writeback failed.",
        )

    return factory


@pytest.fixture
def patch() -> GeneratedPatch:
    return GeneratedPatch(
        workspace=Path("examples/generated/rename_artist_id"),
        changed_files=[
            Path("models/staging/stg_streams.sql"),
            Path("models/schema.yml"),
        ],
        strategy="compatibility_alias",
    )


@pytest.fixture
def failed_process() -> Callable[..., CompletedProcess[str]]:
    def factory(*args: object, **kwargs: object) -> CompletedProcess[str]:
        command = kwargs.get("args") if "args" in kwargs else (args[0] if args else [])
        return CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="simulated failure",
        )

    return factory


@pytest.fixture
def orchestrator(
    rename_request: Callable[..., ChangeRequest],
    complete_evidence: Callable[[], MetadataEvidence],
    complete_impact: Callable[[], ImpactAssessment],
    automatic_plan: Callable[[], RemediationPlan],
    patch: GeneratedPatch,
    passing_validation: Callable[[], ValidationResult],
    successful_writeback: Callable[[], WritebackResult],
):
    class FakeMcpAdapter:
        def get_downstream_context(
            self,
            dataset_urn: str,
            source_field: str,
            max_hops: int = 3,
        ) -> MetadataEvidence:
            return complete_evidence()

    class FakeGeneratorAdapter:
        def generate_patch(
            self,
            request: ChangeRequest,
            evidence: MetadataEvidence,
            impact: ImpactAssessment,
            remediation: RemediationPlan,
            source_project: Path,
            output_root: Path,
        ) -> GeneratedPatch:
            return patch

    class FakeValidatorAdapter:
        def validate_patch(self, generated_patch: GeneratedPatch) -> ValidationResult:
            return passing_validation()

    class FakeWritebackAdapter:
        def writeback(self, *args: object, **kwargs: object) -> WritebackResult:
            return successful_writeback()

    class FakeOrchestrator:
        def __init__(self) -> None:
            self.mcp = FakeMcpAdapter()
            self.generator = FakeGeneratorAdapter()
            self.validator = FakeValidatorAdapter()
            self.writeback = FakeWritebackAdapter()

        def run(self, input_path: Path, output_root: Path) -> ChangeProofReport:
            request = rename_request()
            evidence = self.mcp.get_downstream_context(
                request.dataset_urn or "",
                request.old_column or "",
            )
            impact = complete_impact()
            remediation = automatic_plan()
            generated_patch = self.generator.generate_patch(
                request,
                evidence,
                impact,
                remediation,
                source_project=Path("demo/sonicledger"),
                output_root=output_root,
            )
            validation = self.validator.validate_patch(generated_patch)
            writeback = self.writeback.writeback()
            return ChangeProofReport(
                run_id="run-001",
                request=request,
                evidence=evidence,
                impact=impact,
                remediation=remediation,
                patch=generated_patch,
                validation=validation,
                writeback=writeback,
                status=DecisionStatus.VERIFIED,
                summary="Fake verified report.",
            )

    return FakeOrchestrator()
