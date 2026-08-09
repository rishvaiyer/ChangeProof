"""Draft-and-approve write-back of ChangeProof decisions into DataHub.

Proposals are always generated as drafts. Nothing reaches DataHub until a human
approves a specific proposal id, and the approved proposal is rebuilt from the
analysis on the server rather than taken from the request body, so an approval
can never carry arbitrary text into the catalog.

Reads go through the official DataHub MCP server (see mcp_client). Writes go
through the GraphQL mutations GMS exposes, which the MCP server does not cover.
"""

import httpx

from .config import Settings
from .demo import DemoAnalysis
from .models import ChangeProposal, ProposalAction, WritebackResult

PENDING_CHANGE_TAG = "urn:li:tag:changeproof-pending-change"

RAISE_INCIDENT = """
mutation raiseIncident($input: RaiseIncidentInput!) { raiseIncident(input: $input) }
"""
ADD_TAG = """
mutation addTag($input: TagAssociationInput!) { addTag(input: $input) }
"""
UPDATE_DESCRIPTION = """
mutation updateDescription($input: DescriptionUpdateInput!) {
  updateDescription(input: $input)
}
"""


class WritebackUnavailableError(RuntimeError):
    pass


def build_proposals(analysis: DemoAnalysis) -> list[ChangeProposal]:
    """Derive the draft write-backs for an analysis. Deterministic and read-only."""

    request = analysis.request
    column = request.old_column or request.new_column or "the column"
    old_type = request.old_type or "unknown"
    new_type = request.new_type or "unknown"
    source_name = analysis.evidence.source_urn.split(",")[1].split(".")[-1]

    blast_radius = _format_blast_radius(analysis)
    proposals: list[ChangeProposal] = [
        ChangeProposal(
            proposal_id="incident-source",
            action=ProposalAction.RAISE_INCIDENT,
            target_urn=analysis.evidence.source_urn,
            target_name=source_name,
            title=f"Proposed schema change: {column} {old_type} to {new_type}",
            body=(
                f"ChangeProof analyzed a proposed change to {source_name}.{column} "
                f"({old_type} to {new_type}).\n\n"
                f"Confidence: {analysis.impact.confidence.value}\n"
                f"Strategy: {analysis.plan.strategy}\n\n"
                f"Observed downstream impact:\n{blast_radius}\n\n"
                f"{analysis.plan.summary}\n\n"
                "Raised by ChangeProof on human approval. Lineage is evidence of "
                "observed dependencies, not proof of every consumer."
            ),
            rationale=(
                "Records the proposed change against the source dataset so the "
                "review is visible to everyone downstream."
            ),
        )
    ]

    for asset in analysis.impact.impacted_assets:
        if not asset.critical:
            continue
        proposals.append(
            ChangeProposal(
                proposal_id=f"tag-{asset.name}",
                action=ProposalAction.ADD_TAG,
                target_urn=asset.urn,
                target_name=asset.name,
                title=f"Tag {asset.name} as pending an upstream change",
                body=PENDING_CHANGE_TAG,
                rationale=(
                    f"{asset.name} is tagged critical and sits {asset.hop} hops "
                    f"downstream of the edit."
                ),
            )
        )

    proposals.append(
        ChangeProposal(
            proposal_id="docs-source",
            action=ProposalAction.UPDATE_DOCS,
            target_urn=analysis.evidence.source_urn,
            target_name=source_name,
            title=f"Document the {analysis.plan.strategy} migration on {source_name}",
            body=(
                f"Pending change: {column} {old_type} to {new_type}.\n\n"
                "Rollout:\n"
                + _numbered(analysis.plan.rollout_steps)
                + "\n\nRollback:\n"
                + _numbered(analysis.plan.rollback_steps)
            ),
            rationale=(
                "Puts the migration plan where the next engineer reading this "
                "dataset will find it."
            ),
        )
    )

    return proposals


def _numbered(steps: list[str]) -> str:
    return "\n".join(f"{index}. {step}" for index, step in enumerate(steps, 1))


def _format_blast_radius(analysis: DemoAnalysis) -> str:
    if not analysis.impact.impacted_assets:
        return "  No downstream consumers observed in the lineage graph."
    return "\n".join(
        f"  {index}. {asset.name} (hop {asset.hop})"
        + (" [critical]" if asset.critical else "")
        for index, asset in enumerate(analysis.impact.impacted_assets, 1)
    )


class DataHubWriteClient:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or Settings.from_env()
        self._client = client

    @property
    def endpoint(self) -> str:
        return f"{self._settings.datahub_gms_url.rstrip('/')}/api/graphql"

    def is_live(self) -> bool:
        try:
            with self._open() as client:
                response = client.get(
                    f"{self._settings.datahub_gms_url.rstrip('/')}/health", timeout=2.0
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def apply(self, proposal: ChangeProposal) -> WritebackResult:
        query, variables = _mutation_for(proposal)
        try:
            self._post(query, variables)
        except (httpx.HTTPError, RuntimeError) as exc:
            return WritebackResult(
                succeeded=False,
                applied=False,
                dataset_urn=proposal.target_urn,
                proposal_id=proposal.proposal_id,
                action=proposal.action,
                error=str(exc),
            )
        return WritebackResult(
            succeeded=True,
            applied=True,
            dataset_urn=proposal.target_urn,
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            properties_written={"title": proposal.title},
        )

    def _post(self, query: str, variables: dict[str, object]) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._settings.datahub_gms_token:
            headers["Authorization"] = f"Bearer {self._settings.datahub_gms_token}"

        with self._open() as client:
            response = client.post(
                self.endpoint,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()

        errors = payload.get("errors")
        if errors:
            raise RuntimeError(errors[0].get("message", "DataHub GraphQL error"))
        return payload.get("data") or {}

    def _open(self) -> httpx.Client:
        if self._client is not None:
            return _BorrowedClient(self._client)
        return httpx.Client()


class _BorrowedClient:
    """Lets an injected client be used in a with-block without closing it."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def __enter__(self) -> httpx.Client:
        return self._client

    def __exit__(self, *_exc_info: object) -> bool:
        return False


def _mutation_for(proposal: ChangeProposal) -> tuple[str, dict[str, object]]:
    if proposal.action is ProposalAction.RAISE_INCIDENT:
        return RAISE_INCIDENT, {
            "input": {
                "type": "OPERATIONAL",
                "title": proposal.title,
                "description": proposal.body,
                "resourceUrn": proposal.target_urn,
            }
        }
    if proposal.action is ProposalAction.ADD_TAG:
        return ADD_TAG, {
            "input": {"tagUrn": proposal.body, "resourceUrn": proposal.target_urn}
        }
    if proposal.action is ProposalAction.UPDATE_DOCS:
        return UPDATE_DESCRIPTION, {
            "input": {"description": proposal.body, "resourceUrn": proposal.target_urn}
        }
    raise WritebackUnavailableError(f"Unsupported proposal action: {proposal.action}")


class SimulatedWriteClient:
    """Records approved write-backs into an in-process demo catalog.

    Used when no DataHub is configured, so the hosted demo can show the whole
    approval flow end to end. It performs no network call and never claims a
    DataHub write; every result it returns is marked `simulated` and the UI
    labels it as such. The real GraphQL path is DataHubWriteClient.
    """

    def __init__(self) -> None:
        self.catalog: list[ChangeProposal] = []

    def is_live(self) -> bool:
        return True

    def apply(self, proposal: ChangeProposal) -> WritebackResult:
        self.catalog.append(proposal)
        return WritebackResult(
            succeeded=True,
            applied=True,
            simulated=True,
            dataset_urn=proposal.target_urn,
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            properties_written={"title": proposal.title},
        )


DEMO_CATALOG = SimulatedWriteClient()


def writeback_mode(settings: Settings | None = None) -> str:
    return (settings or Settings.from_env()).changeproof_writeback_mode.strip().lower()


def client_for_mode(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    mode = writeback_mode(settings)
    if mode == "simulated":
        return DEMO_CATALOG
    if mode == "datahub":
        return DataHubWriteClient(settings=settings)
    raise WritebackUnavailableError(f"Unknown CHANGE_PROOF_WRITEBACK_MODE: {mode}")


def apply_approved(
    *,
    analysis: DemoAnalysis,
    approved_ids: list[str],
    client=None,
) -> list[WritebackResult]:
    """Apply only the approved proposals, rebuilt from the analysis.

    The request supplies ids, never content. Unknown ids are ignored.
    """

    write_client = client if client is not None else client_for_mode()
    if not write_client.is_live():
        raise WritebackUnavailableError(
            "No DataHub instance is reachable, so nothing was written. "
            "The hosted demo runs on bundled metadata; run `make live-demo` to "
            "write back against a local DataHub."
        )

    by_id = {proposal.proposal_id: proposal for proposal in build_proposals(analysis)}
    selected = [by_id[pid] for pid in approved_ids if pid in by_id]
    return [write_client.apply(proposal) for proposal in selected]
