from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .demo import DemoAnalysis, analyze_demo_change

PACKAGE_DIR = Path(__file__).parent
DEFAULT_VALUES = {"column": "artist_id", "old_type": "varchar", "new_type": "bigint"}

app = FastAPI(title="ChangeProof", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "changeproof"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    analysis = analyze_demo_change(**DEFAULT_VALUES)
    return _render(request, analysis=analysis, values=DEFAULT_VALUES)


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request) -> HTMLResponse:
    form = parse_qs((await request.body()).decode("utf-8"))
    values = {key: items[0] if items else "" for key, items in form.items()}
    try:
        analysis = analyze_demo_change(
            column=values.get("column", ""),
            old_type=values.get("old_type", ""),
            new_type=values.get("new_type", ""),
        )
    except ValueError as exc:
        return _render(
            request,
            analysis=None,
            values=values,
            error=str(exc),
            status_code=422,
        )
    return _render(request, analysis=analysis, values=values)


def _render(
    request: Request,
    *,
    analysis: DemoAnalysis | None,
    values: dict[str, str],
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"analysis": analysis, "error": error, "values": values},
        status_code=status_code,
    )
