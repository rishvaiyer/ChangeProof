from changeproof.config import Settings


def test_settings_from_env_reads_change_proof_model(monkeypatch) -> None:
    monkeypatch.setenv("CHANGE_PROOF_MODEL", "gpt-5.4.1-mini")

    settings = Settings.from_env()

    assert settings.changeproof_model == "gpt-5.4.1-mini"
