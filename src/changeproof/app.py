import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from .ai_review import AiReviewUnavailable, review_analysis
from .demo import DemoAnalysis, DemoInputError, catalog_options
from .enterprise import analyze_enterprise_change
from .live import analyze_live_change
from .writeback import (
    WritebackUnavailableError,
    apply_approved,
    build_proposals,
    writeback_mode,
)

PACKAGE_DIR = Path(__file__).parent
DEFAULT_VALUES = {"column": "customer_id", "old_type": "varchar", "new_type": "bigint"}
PAGE_TEMPLATES = {
    "analyze": "analyze.html",
    "impact": "impact.html",
    "regions": "regions.html",
    "fixes": "fixes.html",
    "rollout": "rollout.html",
    "datahub": "datahub.html",
}

templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
AnalysisProvider = Callable[..., DemoAnalysis]


def provider_from_env() -> AnalysisProvider:
    mode = os.getenv("CHANGE_PROOF_EVIDENCE_MODE", "bundled").strip().lower()
    if mode in {"", "bundled"}:
        return analyze_enterprise_change
    if mode == "datahub":
        return analyze_live_change
    raise RuntimeError(f"Unknown CHANGE_PROOF_EVIDENCE_MODE: {mode}")


def create_app(analysis_provider: AnalysisProvider | None = None) -> FastAPI:
    application = FastAPI(title="ChangeProof", docs_url=None, redoc_url=None)
    application.mount(
        "/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static"
    )

    @application.middleware("http")
    async def revalidate_static(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    def current_provider() -> AnalysisProvider:
        return analysis_provider or provider_from_env()

    def render_page(
        request: Request,
        *,
        page: str,
        analysis: DemoAnalysis | None,
        values: dict[str, str],
        error: str | None = None,
        writeback_error: str | None = None,
        writeback_results: list | None = None,
        ai_error: str | None = None,
        status_code: int = 200,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name=PAGE_TEMPLATES[page],
            context={
                "analysis": analysis,
                "page": page,
                "error": error,
                "values": values,
                "catalog": catalog_options(),
                "proposals": build_proposals(analysis) if analysis else [],
                "writeback_error": writeback_error,
                "writeback_results": writeback_results or [],
                "simulated_mode": writeback_mode() == "simulated",
                "ai_error": ai_error,
            },
            status_code=status_code,
        )

    def default_page(request: Request, page: str) -> HTMLResponse:
        try:
            analysis = current_provider()(**DEFAULT_VALUES)
        except (RuntimeError, ValueError) as exc:
            return render_page(
                request,
                page="analyze",
                analysis=None,
                values=DEFAULT_VALUES,
                error=str(exc),
                status_code=503,
            )
        return render_page(
            request, page=page, analysis=analysis, values=DEFAULT_VALUES
        )

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "changeproof"}

    @application.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        return default_page(request, "analyze")

    @application.get("/impact", response_class=HTMLResponse)
    def impact(request: Request) -> HTMLResponse:
        return default_page(request, "impact")

    @application.get("/regions", response_class=HTMLResponse)
    def regions(request: Request) -> HTMLResponse:
        return default_page(request, "regions")

    @application.get("/fixes", response_class=HTMLResponse)
    def fixes(request: Request) -> HTMLResponse:
        return default_page(request, "fixes")

    @application.get("/rollout", response_class=HTMLResponse)
    def rollout(request: Request) -> HTMLResponse:
        return default_page(request, "rollout")

    @application.get("/datahub", response_class=HTMLResponse)
    def datahub(request: Request) -> HTMLResponse:
        return default_page(request, "datahub")

    @application.post("/analyze", response_class=HTMLResponse)
    async def analyze(request: Request) -> HTMLResponse:
        values = _form_values(await request.body())
        try:
            analysis = await run_in_threadpool(current_provider(), **values)
        except DemoInputError as exc:
            return render_page(
                request,
                page="analyze",
                analysis=None,
                values=values,
                error=str(exc),
                status_code=422,
            )
        except (RuntimeError, ValueError) as exc:
            return render_page(
                request,
                page="analyze",
                analysis=None,
                values=values,
                error=str(exc),
                status_code=503,
            )
        return render_page(request, page="impact", analysis=analysis, values=values)

    @application.get("/artifacts/{artifact_name}")
    def artifact(artifact_name: str) -> Response:
        analysis = current_provider()(**DEFAULT_VALUES)
        if analysis.artifacts is None:
            raise HTTPException(status_code=404, detail="No artifacts for this scenario")
        artifacts = {
            "impact-report.json": (
                analysis.artifacts.impact_report_json,
                "application/json",
            ),
            "discovery-query.sql": (
                analysis.artifacts.discovery_query_sql,
                "text/plain",
            ),
            "proposed-fixes.sql": (
                analysis.artifacts.proposed_fixes_sql,
                "text/plain",
            ),
            "validation-queries.sql": (
                analysis.artifacts.validation_queries_sql,
                "text/plain",
            ),
            "rollback.sql": (analysis.artifacts.rollback_sql, "text/plain"),
            "changeproof.sarif": (analysis.artifacts.sarif_json, "application/json"),
        }
        if artifact_name not in artifacts:
            raise HTTPException(status_code=404, detail="Artifact not found")
        content, media_type = artifacts[artifact_name]
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{artifact_name}"'},
        )

    @application.post("/ai-review", response_class=HTMLResponse)
    async def ai_review(request: Request) -> HTMLResponse:
        try:
            analysis = await run_in_threadpool(current_provider(), **DEFAULT_VALUES)
            review = await run_in_threadpool(review_analysis, analysis)
        except (AiReviewUnavailable, RuntimeError, ValueError) as exc:
            analysis = current_provider()(**DEFAULT_VALUES)
            return render_page(
                request,
                page="fixes",
                analysis=analysis,
                values=DEFAULT_VALUES,
                ai_error=str(exc),
                status_code=503,
            )
        return render_page(
            request,
            page="fixes",
            analysis=replace(analysis, ai_review=review),
            values=DEFAULT_VALUES,
        )

    @application.post("/writeback/apply", response_class=HTMLResponse)
    async def writeback_apply(request: Request) -> HTMLResponse:
        form = parse_qs((await request.body()).decode("utf-8"))
        values = {
            key: (form.get(key) or [DEFAULT_VALUES[key]])[0] for key in DEFAULT_VALUES
        }
        approved_ids = form.get("approve", [])
        try:
            analysis = await run_in_threadpool(current_provider(), **values)
        except DemoInputError as exc:
            return render_page(
                request,
                page="datahub",
                analysis=None,
                values=values,
                error=str(exc),
                status_code=422,
            )
        except (RuntimeError, ValueError) as exc:
            return render_page(
                request,
                page="datahub",
                analysis=None,
                values=values,
                error=str(exc),
                status_code=503,
            )

        if not approved_ids:
            return render_page(
                request,
                page="datahub",
                analysis=analysis,
                values=values,
                writeback_error="Select at least one proposal to write back.",
                status_code=422,
            )
        try:
            results = await run_in_threadpool(
                apply_approved, analysis=analysis, approved_ids=approved_ids
            )
        except WritebackUnavailableError as exc:
            return render_page(
                request,
                page="datahub",
                analysis=analysis,
                values=values,
                writeback_error=str(exc),
                status_code=503,
            )
        return render_page(
            request,
            page="datahub",
            analysis=analysis,
            values=values,
            writeback_results=results,
        )

    return application


def _form_values(body: bytes) -> dict[str, str]:
    form = parse_qs(body.decode("utf-8"))
    return {key: (form.get(key) or [""])[0] for key in DEFAULT_VALUES}


app = create_app()
