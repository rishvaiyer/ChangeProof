import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from .ai_review import AiReviewUnavailable, review_analysis
from .demo import DemoAnalysis, DemoInputError, catalog_options
from .enterprise import analyze_enterprise_change
from .exports import ARTIFACT_EXPORTS, ARTIFACT_FIELDS, all_results_text, artifact_text, pdf_bytes
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
    signing_key = secrets.token_bytes(32)
    ai_last_request: dict[str, float] = {}
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

    def baseline_values() -> dict[str, str]:
        if analysis_provider is None and os.getenv(
            "CHANGE_PROOF_EVIDENCE_MODE", "bundled"
        ).strip().lower() == "datahub":
            return {"column": "artist_id", "old_type": "varchar", "new_type": "bigint"}
        return dict(DEFAULT_VALUES)

    def sign_values(values: dict[str, str]) -> str:
        payload = json.dumps(values, separators=(",", ":"), sort_keys=True).encode()
        encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        signature = hmac.new(signing_key, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def verify_values(token: str) -> dict[str, str]:
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = hmac.new(
                signing_key, encoded.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode())
            if set(payload) != set(DEFAULT_VALUES) or not all(
                isinstance(payload[key], str) for key in DEFAULT_VALUES
            ):
                raise ValueError
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=403, detail="Invalid analysis token") from exc
        return {key: payload[key] for key in DEFAULT_VALUES}

    def request_values(request: Request) -> dict[str, str]:
        if not any(key in request.query_params for key in DEFAULT_VALUES):
            return baseline_values()
        return {key: request.query_params.get(key, "") for key in DEFAULT_VALUES}

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
                "analysis_token": sign_values(values) if analysis else "",
                "nav_query": (
                    "" if values == baseline_values() else f"?{urlencode(values)}"
                ),
                "artifact_exports": ARTIFACT_EXPORTS,
                "ai_available": bool(os.getenv("OPENAI_API_KEY")),
            },
            status_code=status_code,
        )

    def default_page(request: Request, page: str) -> HTMLResponse:
        values = request_values(request)
        try:
            analysis = current_provider()(**values)
        except (RuntimeError, ValueError) as exc:
            return render_page(
                request,
                page="analyze",
                analysis=None,
                values=values,
                error=str(exc),
                status_code=503,
            )
        return render_page(
            request, page=page, analysis=analysis, values=values
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
    def artifact(request: Request, artifact_name: str) -> Response:
        if artifact_name not in ARTIFACT_FIELDS:
            raise HTTPException(status_code=404, detail="Artifact not found")
        analysis = current_provider()(**request_values(request))
        if analysis.artifacts is None:
            raise HTTPException(status_code=404, detail="No artifacts for this scenario")
        content = artifact_text(analysis, artifact_name)
        media_type = (
            "application/json" if artifact_name.endswith((".json", ".sarif")) else "text/plain"
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{artifact_name}"'},
        )

    @application.get("/exports/{export_name}")
    def export_result(request: Request, export_name: str) -> Response:
        if export_name in {"all-results.txt", "all-results.pdf"}:
            artifact_name = "all-results"
            export_format = export_name.rsplit(".", 1)[1]
        elif "." in export_name:
            artifact_name, export_format = export_name.rsplit(".", 1)
        else:
            raise HTTPException(status_code=404, detail="Export format not found")
        if export_format not in {"txt", "pdf"}:
            raise HTTPException(status_code=404, detail="Export format not found")
        if artifact_name != "all-results" and artifact_name not in ARTIFACT_FIELDS:
            raise HTTPException(status_code=404, detail="Artifact not found")

        analysis = current_provider()(**request_values(request))
        if analysis.artifacts is None:
            raise HTTPException(status_code=404, detail="No artifacts for this scenario")
        content = (
            all_results_text(analysis)
            if artifact_name == "all-results"
            else artifact_text(analysis, artifact_name)
        )
        filename = f"{artifact_name.rsplit('.', 1)[0]}.{export_format}"
        if export_format == "pdf":
            return Response(
                content=pdf_bytes("ChangeProof - " + artifact_name.replace("-", " "), content),
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @application.post("/ai-review", response_class=HTMLResponse)
    async def ai_review(request: Request) -> HTMLResponse:
        form = parse_qs((await request.body()).decode("utf-8"))
        values = verify_values((form.get("analysis_token") or [""])[0])
        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        if now - ai_last_request.get(client_key, 0) < 15:
            raise HTTPException(status_code=429, detail="AI review rate limit")
        ai_last_request[client_key] = now
        try:
            analysis = await run_in_threadpool(current_provider(), **values)
            review = await run_in_threadpool(review_analysis, analysis)
        except (AiReviewUnavailable, RuntimeError, ValueError) as exc:
            analysis = current_provider()(**values)
            return render_page(
                request,
                page="fixes",
                analysis=analysis,
                values=values,
                ai_error=str(exc),
                status_code=503,
            )
        return render_page(
            request,
            page="fixes",
            analysis=replace(analysis, ai_review=review),
            values=values,
        )

    @application.post("/writeback/apply", response_class=HTMLResponse)
    async def writeback_apply(request: Request) -> HTMLResponse:
        form = parse_qs((await request.body()).decode("utf-8"))
        values = verify_values((form.get("analysis_token") or [""])[0])
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
