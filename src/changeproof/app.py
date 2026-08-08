import os
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from .demo import DemoAnalysis, DemoInputError, analyze_demo_change
from .live import analyze_live_change
from .writeback import (
    WritebackUnavailableError,
    apply_approved,
    build_proposals,
)

PACKAGE_DIR = Path(__file__).parent
DEFAULT_VALUES = {"column": "artist_id", "old_type": "varchar", "new_type": "bigint"}

templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
AnalysisProvider = Callable[..., DemoAnalysis]


def provider_from_env() -> AnalysisProvider:
    mode = os.getenv("CHANGE_PROOF_EVIDENCE_MODE", "bundled").strip().lower()
    if mode in {"", "bundled"}:
        return analyze_demo_change
    if mode == "datahub":
        return analyze_live_change
    raise RuntimeError(f"Unknown CHANGE_PROOF_EVIDENCE_MODE: {mode}")


def create_app(analysis_provider: AnalysisProvider | None = None) -> FastAPI:
    application = FastAPI(title="ChangeProof", docs_url=None, redoc_url=None)
    application.mount(
        "/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static"
    )

    def current_provider() -> AnalysisProvider:
        return analysis_provider or provider_from_env()

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "changeproof"}

    @application.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        try:
            analysis = current_provider()(**DEFAULT_VALUES)
        except (RuntimeError, ValueError) as exc:
            return _render(
                request,
                analysis=None,
                values=DEFAULT_VALUES,
                error=str(exc),
                status_code=503,
            )
        return _render(request, analysis=analysis, values=DEFAULT_VALUES)

    @application.post("/analyze", response_class=HTMLResponse)
    async def analyze(request: Request) -> HTMLResponse:
        form = parse_qs((await request.body()).decode("utf-8"))
        values = {key: items[0] if items else "" for key, items in form.items()}
        try:
            analysis = await run_in_threadpool(
                current_provider(),
                column=values.get("column", ""),
                old_type=values.get("old_type", ""),
                new_type=values.get("new_type", ""),
            )
        except DemoInputError as exc:
            return _render(
                request,
                analysis=None,
                values=values,
                error=str(exc),
                status_code=422,
            )
        except (RuntimeError, ValueError) as exc:
            return _render(
                request,
                analysis=None,
                values=values,
                error=str(exc),
                status_code=503,
            )
        return _render(request, analysis=analysis, values=values)

    @application.post("/writeback/apply", response_class=HTMLResponse)
    async def writeback_apply(request: Request) -> HTMLResponse:
        form = parse_qs((await request.body()).decode("utf-8"))
        values = {
            key: items[0] if items else ""
            for key, items in form.items()
            if key in DEFAULT_VALUES
        }
        approved_ids = form.get("approve", [])

        try:
            analysis = await run_in_threadpool(
                current_provider(),
                column=values.get("column", ""),
                old_type=values.get("old_type", ""),
                new_type=values.get("new_type", ""),
            )
        except DemoInputError as exc:
            return _render(
                request, analysis=None, values=values, error=str(exc), status_code=422
            )
        except (RuntimeError, ValueError) as exc:
            return _render(
                request, analysis=None, values=values, error=str(exc), status_code=503
            )

        if not approved_ids:
            return _render(
                request,
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
            return _render(
                request,
                analysis=analysis,
                values=values,
                writeback_error=str(exc),
                status_code=503,
            )

        return _render(
            request, analysis=analysis, values=values, writeback_results=results
        )

    return application


def _render(
    request: Request,
    *,
    analysis: DemoAnalysis | None,
    values: dict[str, str],
    error: str | None = None,
    writeback_error: str | None = None,
    writeback_results: list | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "analysis": analysis,
            "error": error,
            "values": values,
            "proposals": build_proposals(analysis) if analysis else [],
            "writeback_error": writeback_error,
            "writeback_results": writeback_results or [],
        },
        status_code=status_code,
    )


app = create_app()
