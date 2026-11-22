import pytest

from app import create_app
from app.config import Config
from app.db import get_db_connection
from app.services import suap
from app.services.suap import SuapErro

URL = "/v1/acessos/validar"
MATRICULA = "202312345601"
SENHA = "senha-de-teste"
TOKEN_ACESSO = "token-acesso-de-teste"
CURSO_GUARABIRA = "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)"
CORPO_VALIDO = {"matricula": MATRICULA, "senha": SENHA, "catraca_id": "CATRACA-01"}


class ConfigTeste(Config):
    TESTING = True
    SUAP_BASE_URL = "https://suap.exemplo.invalido/api"
    SUAP_TIMEOUT_SEGUNDOS = 1
    CATRACAS_CADASTRADAS = {"CATRACA-01"}


@pytest.fixture
def cliente():
    return create_app(ConfigTeste).test_client()


@pytest.fixture
def suap_falso(monkeypatch):
    """SUAP falso: o teste define o aluno devolvido em estado["aluno"]."""
    estado = {"aluno": {"matricula": MATRICULA, "situacao": "Matriculado",
                        "curso_nome": CURSO_GUARABIRA}}
    monkeypatch.setattr(
        suap, "autenticar",
        lambda *a, **k: {"access": TOKEN_ACESSO, "refresh": "refresh-de-teste"},
    )
    monkeypatch.setattr(suap, "buscar_aluno", lambda *a, **k: estado["aluno"])
    return estado


def ler_historico():
    conn = get_db_connection()
    linhas = conn.execute("SELECT * FROM historico_acessos").fetchall()
    conn.close()
    return linhas


def test_registra_permitido(cliente, suap_falso):
    cliente.post(URL, json=CORPO_VALIDO)
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["matricula"] == MATRICULA
    assert linhas[0]["catraca_id"] == "CATRACA-01"
    assert linhas[0]["resultado"] == "Permitido"
    assert linhas[0]["detalhes_erro"] is None


def test_registra_negado(cliente, suap_falso):
    suap_falso["aluno"]["situacao"] = "Evadido"
    cliente.post(URL, json=CORPO_VALIDO)
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["catraca_id"] == "CATRACA-01"
    assert linhas[0]["resultado"] == "Negado"


def test_registra_catraca_normalizada(cliente, suap_falso):
    cliente.post(URL, json={**CORPO_VALIDO, "catraca_id": " catraca-01 "})
    assert ler_historico()[0]["catraca_id"] == "CATRACA-01"


def test_registra_erro_matricula_invalida(cliente, suap_falso):
    cliente.post(URL, json={**CORPO_VALIDO, "matricula": "123"})
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["matricula"] is None
    assert linhas[0]["catraca_id"] == "CATRACA-01"
    assert linhas[0]["resultado"] == "Erro"
    assert linhas[0]["detalhes_erro"] == "matricula_invalida"


def test_registra_erro_catraca_nao_cadastrada(cliente, suap_falso):
    cliente.post(URL, json={**CORPO_VALIDO, "catraca_id": "catraca-99"})
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["catraca_id"] == "CATRACA-99"
    assert linhas[0]["resultado"] == "Erro"
    assert linhas[0]["detalhes_erro"] == "catraca_nao_cadastrada"


def test_registra_erro_do_suap(cliente, monkeypatch):
    def falha(*args, **kwargs):
        raise SuapErro("timeout", "O SUAP demorou demais para responder.")

    monkeypatch.setattr(suap, "autenticar", falha)
    cliente.post(URL, json=CORPO_VALIDO)
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["resultado"] == "Erro"
    assert linhas[0]["detalhes_erro"] == "timeout"


def test_historico_nao_guarda_senha_nem_token(cliente, suap_falso, monkeypatch):
    cliente.post(URL, json=CORPO_VALIDO)  # Permitido
    suap_falso["aluno"] = None
    cliente.post(URL, json=CORPO_VALIDO)  # Negado
    monkeypatch.setattr(
        suap, "buscar_aluno",
        lambda *a, **k: (_ for _ in ()).throw(
            SuapErro("suap_indisponivel", "fora do ar", status_suap=503)
        ),
    )
    cliente.post(URL, json=CORPO_VALIDO)  # Erro

    linhas = ler_historico()
    assert len(linhas) == 3
    for linha in linhas:
        conteudo = " ".join(str(valor) for valor in tuple(linha))
        assert SENHA not in conteudo
        assert TOKEN_ACESSO not in conteudo
