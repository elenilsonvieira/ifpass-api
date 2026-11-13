import pytest

from app import create_app
from app.config import Config
from app.services.suap import autorizado

URL = "/v1/acessos/validar"
CABECALHO = {"Authorization": "Token abc"}


class ConfigTeste(Config):
    SUAP_MODO = "simulado"
    TESTING = True


class ConfigReal(ConfigTeste):
    SUAP_MODO = "real"


@pytest.fixture
def cliente():
    return create_app(ConfigTeste).test_client()


def validar(cliente, json=None, headers=CABECALHO, **kwargs):
    return cliente.post(URL, json=json, headers=headers, **kwargs)


@pytest.mark.parametrize(
    "matricula, esperado",
    [
        ("202312345601", True),
        ("202312345602", False),
        ("202312345603", False),
        ("202312345604", False),
        ("999999999999", False),
    ],
)
def test_autorizacao(cliente, matricula, esperado):
    r = validar(cliente, {"matricula": matricula})
    assert r.status_code == 200
    assert r.get_json() == {"autorizado": esperado}


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer x"}, {"Authorization": "Token "}]
)
def test_token_ausente(cliente, headers):
    r = validar(cliente, {"matricula": "202312345601"}, headers=headers)
    assert r.status_code == 401
    assert r.get_json() == {"erro": "token ausente"}


@pytest.mark.parametrize(
    "corpo",
    [
        {"matricula": "20231234560"},
        {"matricula": "2023123456011"},
        {"matricula": "20231234560a"},
        {"matricula": ""},
        {"matricula": 202312345601},
        {"matricula": None},
        {"outro": "x"},
        ["202312345601"],
    ],
)
def test_matricula_invalida(cliente, corpo):
    r = validar(cliente, corpo)
    assert r.status_code == 400
    assert r.get_json() == {"erro": "matricula invalida"}


def test_corpo_nao_json(cliente):
    r = validar(cliente, data="isso nao e json", content_type="text/plain")
    assert r.status_code == 400


def test_token_recusado(cliente):
    r = validar(
        cliente,
        {"matricula": "202312345601"},
        headers={"Authorization": "Token invalido"},
    )
    assert r.status_code == 401
    assert r.get_json() == {"erro": "token recusado pelo SUAP"}


def test_suap_indisponivel(cliente):
    r = validar(cliente, {"matricula": "000000000000"})
    assert r.status_code == 503
    assert "autorizado" not in r.get_json()


def test_modo_real_nao_implementado():
    cliente = create_app(ConfigReal).test_client()
    r = validar(cliente, {"matricula": "202312345601"})
    assert r.status_code == 501
    assert r.get_json() == {"erro": "modo real nao implementado"}


def test_metodo_nao_permitido(cliente):
    r = cliente.get(URL)
    assert r.status_code == 405
    assert r.is_json


def test_rota_inexistente(cliente):
    r = cliente.get("/v1/nada")
    assert r.status_code == 404
    assert r.is_json


def test_autorizado_unitario():
    curso = "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)"
    assert autorizado({"situacao": "Matriculado", "curso_nome": curso}) is True
    assert autorizado({"situacao": "Matriculado", "curso_nome": curso.lower()}) is True
    assert autorizado({"situacao": "Evadido", "curso_nome": curso}) is False
    assert (
        autorizado(
            {"situacao": "Matriculado", "curso_nome": "ALIMENTOS (CAMPUS SOUSA)"}
        )
        is False
    )
    assert autorizado(None) is False
