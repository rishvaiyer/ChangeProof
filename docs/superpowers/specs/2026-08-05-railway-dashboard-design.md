# ChangeProof Railway Dashboard Design

## Goal

Deploy a public, recruiter-ready ChangeProof demo to a new Railway project. The demo must show how a proposed schema change affects downstream assets and recommend a safer rollout.

## Scope

- Add a FastAPI web application with a public dashboard and health endpoint.
- Let a visitor choose or enter a supported SonicLedger schema change.
- Show the affected datasets, hop distance, owners, criticality, risk explanation, and proposed remediation plan.
- Use bundled SonicLedger metadata in hosted demo mode so the public app is reliable without exposing the local DataHub instance.
- Preserve the existing live DataHub MCP adapter and tests for local evidence-backed demonstrations.
- Create a new Railway project and service. Do not modify existing Railway services.

## Architecture

The FastAPI application owns HTTP routing and delegates analysis to the existing ChangeProof classifier, impact scorer, and remediation planner. A small demo-evidence provider supplies the same typed `MetadataEvidence` contract used by the DataHub MCP client. This keeps the dashboard independent of metadata transport while preserving the real local DataHub path.

The initial UI is server-rendered HTML with lightweight CSS and JavaScript. It avoids a separate frontend build and minimizes Railway memory and deployment complexity.

## User Flow

1. The visitor opens the dashboard and sees the SonicLedger royalty-pipeline scenario.
2. The visitor submits a proposed schema change, initially `artist_id` from `varchar` to `bigint`.
3. The server classifies the change, scores downstream impact, and builds a safe rollout plan.
4. The page displays an impact summary, affected asset cards, and ordered remediation steps.
5. The page labels the evidence source as bundled demo metadata. It must not imply that hosted Railway is connected to the user's local DataHub.

## HTTP Contract

- `GET /`: render the dashboard and default scenario.
- `POST /analyze`: validate form input and render the analysis result.
- `GET /healthz`: return a small JSON health response for Railway verification.

Invalid or unsupported input returns a clear validation message without a server error. Unexpected analysis failures are logged server-side and produce a generic user-facing error without secrets.

## Deployment

- Add a Railway-compatible start command that binds Uvicorn to `0.0.0.0:$PORT`.
- Deploy from the clean `codex/changeproof-implementation` checkout to a new Railway project named `changeproof` or the nearest available name.
- No DataHub token or OpenAI key is required for the deterministic hosted demo.
- Verify the exact deployed revision through Railway logs and test `/`, `/analyze`, and `/healthz` on the public domain.

## Testing

- Route tests cover the dashboard, successful analysis, invalid input, and health endpoint.
- Existing unit and integration tests remain green.
- Ruff remains clean.
- Live deployment verification checks HTTP status, expected dashboard copy, analysis output, and health JSON.

## Deferred Work

- Hosted DataHub or DataHub Cloud connectivity.
- Authentication, persistence, multi-user projects, and write-back approval workflows.
- Rich client-side graph visualization and OpenAI-generated remediation text.
