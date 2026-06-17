from __future__ import annotations

from pathlib import Path

from nara_catalog.config import get_api_key, load_env_file


def test_load_env_file_handles_quotes_and_comments(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("# comment\nNARA_API_KEY='dummy-key'\nOTHER=value\n")

    assert load_env_file(path)["NARA_API_KEY"] == "dummy-key"


def test_get_api_key_prefers_environment(monkeypatch, tmp_path: Path) -> None:
    secret = tmp_path / "secret.env"
    secret.write_text("NARA_API_KEY=file-key\n")
    monkeypatch.setenv("NARA_API_KEY", "env-key")

    key, source = get_api_key(secret_file=str(secret), project_dir=tmp_path)

    assert key == "env-key"
    assert source == "environment:NARA_API_KEY"


def test_get_api_key_uses_project_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NARA_API_KEY", raising=False)
    (tmp_path / ".env").write_text("NARA_API_KEY=project-key\n")

    key, source = get_api_key(project_dir=tmp_path)

    assert key == "project-key"
    assert source == str(tmp_path / ".env")


def test_get_api_key_does_not_read_cwd_env_without_project_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NARA_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("nara_catalog.config.DEFAULT_SECRET_FILE", tmp_path / "missing-global.env")
    (tmp_path / ".env").write_text("NARA_API_KEY=project-key\n")

    key, _source = get_api_key()

    assert key is None
