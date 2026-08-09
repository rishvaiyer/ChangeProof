import httpx
import pytest

from changeproof.config import Settings
from changeproof.demo import analyze_demo_change
from changeproof.enterprise import analyze_enterprise_change
from changeproof.models import ProposalAction
from changeproof.writeback import (
    PENDING_CHANGE_TAG,
    DataHubWriteClient,
    WritebackUnavailableError,
    apply_approved,
    build_proposals,
)


@pytest.fixture
def analysis():
    return analyze_demo_change(column="artist_id", old_type="varchar", new_type="bigint")


def test_proposals_cover_incident_docs_and_every_critical_asset(analysis):
    proposals = build_proposals(analysis)
    actions = [proposal.action for proposal in proposals]

    assert ProposalAction.RAISE_INCIDENT in actions
    assert ProposalAction.UPDATE_DOCS in actions

    tagged = {p.target_name for p in proposals if p.action is ProposalAction.ADD_TAG}
    critical = {a.name for a in analysis.impact.impacted_assets if a.critical}
    assert tagged == critical
    assert tagged, "demo scenario should have critical downstream assets"


def test_proposal_ids_are_unique_and_stable(analysis):
    first = build_proposals(analysis)
    second = build_proposals(analysis)

    ids = [proposal.proposal_id for proposal in first]
    assert len(ids) == len(set(ids))
    assert ids == [proposal.proposal_id for proposal in second]


def test_incident_body_carries_the_observed_blast_radius(analysis):
    incident = next(
        p for p in build_proposals(analysis) if p.action is ProposalAction.RAISE_INCIDENT
    )

    for asset in analysis.impact.impacted_assets:
        assert asset.name in incident.body
    assert "varchar" in incident.body and "bigint" in incident.body
    assert "not proof of every consumer" in incident.body


def test_enterprise_incident_includes_sql_regions_and_evidence_limits() -> None:
    enterprise = analyze_enterprise_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    )
    incident = next(
        proposal
        for proposal in build_proposals(enterprise)
        if proposal.action is ProposalAction.RAISE_INCIDENT
    )

    assert "Hidden SQL consumers" in incident.body
    assert "usp_reconcile_loyalty_customer" in incident.body
    assert "Regional exposure" in incident.body
    assert "WEST" in incident.body
    assert "Evidence limits" in incident.body
    assert "dynamic SQL" in incident.body


def test_tag_proposal_targets_the_pending_change_tag(analysis):
    tag_proposal = next(
        p for p in build_proposals(analysis) if p.action is ProposalAction.ADD_TAG
    )
    assert tag_proposal.body == PENDING_CHANGE_TAG


def _client(handler, *, gms_url="http://datahub.test") -> DataHubWriteClient:
    transport = httpx.MockTransport(handler)
    settings = Settings(datahub_gms_url=gms_url, datahub_gms_token="")
    return DataHubWriteClient(settings=settings, client=httpx.Client(transport=transport))


def test_apply_posts_a_graphql_mutation_and_reports_success(analysis):
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200)
        seen.append(__import__("json").loads(request.content))
        return httpx.Response(200, json={"data": {"raiseIncident": True}})

    proposal = next(
        p for p in build_proposals(analysis) if p.action is ProposalAction.RAISE_INCIDENT
    )
    result = _client(handler).apply(proposal)

    assert result.succeeded and result.applied
    assert result.proposal_id == proposal.proposal_id
    assert seen[0]["variables"]["input"]["resourceUrn"] == proposal.target_urn


def test_apply_surfaces_graphql_errors_without_claiming_success(analysis):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200)
        return httpx.Response(200, json={"errors": [{"message": "unauthorized"}]})

    proposal = build_proposals(analysis)[0]
    result = _client(handler).apply(proposal)

    assert not result.succeeded
    assert not result.applied
    assert "unauthorized" in result.error


def test_apply_approved_refuses_when_datahub_is_unreachable(analysis):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no datahub", request=request)

    with pytest.raises(WritebackUnavailableError) as excinfo:
        apply_approved(
            analysis=analysis, approved_ids=["incident-source"], client=_client(handler)
        )

    assert "nothing was written" in str(excinfo.value)


def test_apply_approved_only_applies_selected_ids(analysis):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200)
        calls.append(__import__("json").loads(request.content)["query"])
        return httpx.Response(200, json={"data": {}})

    results = apply_approved(
        analysis=analysis, approved_ids=["docs-source"], client=_client(handler)
    )

    assert len(results) == 1
    assert results[0].action is ProposalAction.UPDATE_DOCS
    assert len(calls) == 1


def test_apply_approved_ignores_unknown_ids(analysis):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200)
        raise AssertionError("no mutation should be sent for an unknown id")

    results = apply_approved(
        analysis=analysis, approved_ids=["not-a-real-proposal"], client=_client(handler)
    )
    assert results == []


def test_simulated_client_records_without_network(analysis):
    from changeproof.writeback import SimulatedWriteClient

    sim = SimulatedWriteClient()
    results = apply_approved(
        analysis=analysis,
        approved_ids=["incident-source", "docs-source"],
        client=sim,
    )

    assert len(results) == 2
    assert all(r.applied and r.simulated and r.succeeded for r in results)
    assert [p.proposal_id for p in sim.catalog] == ["incident-source", "docs-source"]


def test_simulated_client_still_honours_the_approval_gate(analysis):
    from changeproof.writeback import SimulatedWriteClient

    sim = SimulatedWriteClient()
    results = apply_approved(analysis=analysis, approved_ids=["forged"], client=sim)

    assert results == []
    assert sim.catalog == []


def test_mode_selects_the_client(monkeypatch):
    from changeproof.writeback import DataHubWriteClient, SimulatedWriteClient, client_for_mode

    monkeypatch.setenv("CHANGE_PROOF_WRITEBACK_MODE", "simulated")
    assert isinstance(client_for_mode(), SimulatedWriteClient)

    monkeypatch.setenv("CHANGE_PROOF_WRITEBACK_MODE", "datahub")
    monkeypatch.setenv("CHANGE_PROOF_ENABLE_REAL_WRITEBACK", "true")
    assert isinstance(client_for_mode(), DataHubWriteClient)


def test_real_writeback_requires_an_explicit_runtime_enable(monkeypatch):
    from changeproof.writeback import client_for_mode

    monkeypatch.setenv("CHANGE_PROOF_WRITEBACK_MODE", "datahub")
    monkeypatch.delenv("CHANGE_PROOF_ENABLE_REAL_WRITEBACK", raising=False)

    with pytest.raises(WritebackUnavailableError, match="nothing was written"):
        client_for_mode()


def test_unknown_mode_is_rejected(monkeypatch):
    from changeproof.writeback import client_for_mode

    monkeypatch.setenv("CHANGE_PROOF_WRITEBACK_MODE", "pretend")
    with pytest.raises(WritebackUnavailableError):
        client_for_mode()


def test_default_mode_is_datahub_not_simulated(monkeypatch):
    # Simulation must be opted into explicitly; a misconfigured deploy should
    # refuse honestly rather than silently pretend it wrote to DataHub.
    from changeproof.writeback import writeback_mode

    monkeypatch.delenv("CHANGE_PROOF_WRITEBACK_MODE", raising=False)
    assert writeback_mode() == "datahub"


def test_real_client_results_are_never_marked_simulated(analysis):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200)
        return httpx.Response(200, json={"data": {}})

    result = _client(handler).apply(build_proposals(analysis)[0])

    assert result.applied
    assert not result.simulated
