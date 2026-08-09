import importlib.resources
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_installed_package_exposes_declared_triage_static_srs_asset():
    with (ROOT / "pyproject.toml").open("rb") as pyproject:
        package_data = tomllib.load(pyproject)["tool"]["setuptools"]["package-data"]

    assert "static/*.txt" in package_data["changeproof"]
    asset = importlib.resources.files("changeproof").joinpath(
        "static/astervale-ar-incident-srs.txt"
    )

    assert asset.is_file()
    assert "AsterVale Living accounts-receivable incident SRS" in asset.read_text()
