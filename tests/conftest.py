import pytest


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Faz cada teste usar um banco temporário, sem tocar no ifpass.db real."""
    monkeypatch.setattr("app.db.DB_PATH", str(tmp_path / "teste.db"))
