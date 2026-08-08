import httpx
import pytest

from changeproof.config import Settings
from changeproof.demo import analyze_demo_change
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
