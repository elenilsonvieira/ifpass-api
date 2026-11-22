import pytest

from app.__init__ import create_app

@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Faz cada teste usar um banco temporário, sem tocar no ifpass.db real."""
    monkeypatch.setattr("app.db.DB_PATH", str(tmp_path / "teste.db"))

@pytest.fixture
def client():
    app = create_app()
    
    app.config.update(TESTING=True)

    with app.test_client() as cliente:
        yield cliente