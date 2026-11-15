import pytest

from app import create_app
from app.config import Config
from app.db import get_db_connection

URL = "/v1/acessos/validar"
TOKEN = "segredo-de-teste"
CABECALHO = {"Authorization": f"Bearer {TOKEN}"}


class ConfigTeste(Config):
    SUAP_MODO = "simulado"
    TESTING = True


@pytest.fixture
def cliente():
    return create_app(ConfigTeste).test_client()


def ler_historico():
    conn = get_db_connection()
    linhas = conn.execute("SELECT * FROM historico_acessos").fetchall()
    conn.close()
    return linhas


def test_registra_permitido(cliente):
    cliente.post(URL, json={"matricula": "202312345601"}, headers=CABECALHO)
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["matricula"] == "202312345601"
    assert linhas[0]["resultado"] == "Permitido"


def test_registra_negado(cliente):
    cliente.post(URL, json={"matricula": "202312345602"}, headers=CABECALHO)
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["resultado"] == "Negado"


def test_registra_erro_sem_token(cliente):
    cliente.post(URL, json={"matricula": "202312345601"})
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["resultado"] == "Erro"
    assert linhas[0]["detalhes_erro"] == "token ausente"


def test_registra_erro_suap_indisponivel(cliente):
    cliente.post(URL, json={"matricula": "000000000000"}, headers=CABECALHO)
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["resultado"] == "Erro"
    assert linhas[0]["detalhes_erro"] == "SUAP indisponivel"


def test_historico_nao_guarda_token(cliente):
    cliente.post(URL, json={"matricula": "202312345601"}, headers=CABECALHO)
    cliente.post(URL, json={"matricula": "000000000000"}, headers=CABECALHO)
    for linha in ler_historico():
        assert TOKEN not in " ".join(str(valor) for valor in tuple(linha))
