import pytest

from app import create_app
from app.config import Config
from app.services import suap
from app.services.suap import SuapErro, autorizado

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
    """Troca as chamadas ao SUAP por versões falsas (nunca acessa a internet).

    Devolve um dict para o teste escolher o aluno e registra o que foi chamado.
    """
    estado = {"aluno": None, "chamadas": []}

    def autenticar_falso(matricula, senha, config):
        estado["chamadas"].append(("autenticar", matricula, senha))
        return {"access": TOKEN_ACESSO, "refresh": "refresh-de-teste"}

    def buscar_aluno_falso(matricula, token, config):
        estado["chamadas"].append(("buscar_aluno", matricula, token))
        return estado["aluno"]

    monkeypatch.setattr(suap, "autenticar", autenticar_falso)
    monkeypatch.setattr(suap, "buscar_aluno", buscar_aluno_falso)
    return estado


def aluno(situacao="Matriculado", curso=CURSO_GUARABIRA, matricula=MATRICULA):
    return {"matricula": matricula, "situacao": situacao, "curso_nome": curso}


def validar(cliente, corpo=CORPO_VALIDO, **kwargs):
    return cliente.post(URL, json=corpo, **kwargs)


def sem(chave):
    return {k: v for k, v in CORPO_VALIDO.items() if k != chave}


@pytest.mark.parametrize(
    "dados_aluno, esperado",
    [
        (aluno(), True),
        (aluno(situacao="Evadido"), False),
        (aluno(situacao="Formado"), False),
        (aluno(curso="TECNOLOGIA EM ALIMENTOS (CAMPUS SOUSA)"), False),
        (None, False),  # matrícula não encontrada
        (aluno(matricula="999999999999"), False),  # dono do token não confere
    ],
)
def test_autorizacao(cliente, suap_falso, dados_aluno, esperado):
    suap_falso["aluno"] = dados_aluno
    r = validar(cliente)
    assert r.status_code == 200
    assert r.get_json() == {"autorizado": esperado}


def test_envia_credenciais_ao_suap_e_nao_devolve_segredos(cliente, suap_falso):
    suap_falso["aluno"] = aluno()
    r = validar(cliente)
    assert suap_falso["chamadas"] == [
        ("autenticar", MATRICULA, SENHA),
        ("buscar_aluno", MATRICULA, TOKEN_ACESSO),
    ]
    texto = r.get_data(as_text=True)
    assert SENHA not in texto
    assert TOKEN_ACESSO not in texto


def test_catraca_aceita_minuscula_e_espacos(cliente, suap_falso):
    suap_falso["aluno"] = aluno()
    r = validar(cliente, {**CORPO_VALIDO, "catraca_id": "  catraca-01 "})
    assert r.status_code == 200
    assert r.get_json() == {"autorizado": True}


@pytest.mark.parametrize(
    "corpo",
    [
        {**CORPO_VALIDO, "matricula": "20231234560"},
        {**CORPO_VALIDO, "matricula": "2023123456011"},
        {**CORPO_VALIDO, "matricula": "20231234560a"},
        {**CORPO_VALIDO, "matricula": ""},
        {**CORPO_VALIDO, "matricula": 202312345601},
        {**CORPO_VALIDO, "matricula": None},
        sem("matricula"),
        [MATRICULA],
    ],
)
def test_matricula_invalida(cliente, suap_falso, corpo):
    r = validar(cliente, corpo)
    assert r.status_code == 400
    assert r.get_json()["erro"] == "matricula_invalida"
    assert suap_falso["chamadas"] == []


def test_corpo_nao_json(cliente, suap_falso):
    r = cliente.post(URL, data="isso nao e json", content_type="text/plain")
    assert r.status_code == 400
    assert r.get_json()["erro"] == "matricula_invalida"


@pytest.mark.parametrize(
    "corpo",
    [sem("senha"), {**CORPO_VALIDO, "senha": ""}, {**CORPO_VALIDO, "senha": 123}],
)
def test_senha_ausente(cliente, suap_falso, corpo):
    r = validar(cliente, corpo)
    assert r.status_code == 400
    assert r.get_json()["erro"] == "senha_ausente"
    assert suap_falso["chamadas"] == []


@pytest.mark.parametrize(
    "corpo",
    [
        sem("catraca_id"),
        {**CORPO_VALIDO, "catraca_id": ""},
        {**CORPO_VALIDO, "catraca_id": "   "},
        {**CORPO_VALIDO, "catraca_id": 1},
    ],
)
def test_catraca_ausente(cliente, suap_falso, corpo):
    r = validar(cliente, corpo)
    assert r.status_code == 400
    assert r.get_json()["erro"] == "catraca_ausente"
    assert suap_falso["chamadas"] == []


def test_catraca_nao_cadastrada(cliente, suap_falso):
    r = validar(cliente, {**CORPO_VALIDO, "catraca_id": "CATRACA-99"})
    assert r.status_code == 403
    assert r.get_json()["erro"] == "catraca_nao_cadastrada"
    assert suap_falso["chamadas"] == []


def test_ordem_das_validacoes(cliente, suap_falso):
    # Tudo errado: a matrícula é verificada primeiro.
    r = validar(cliente, {"matricula": "1"})
    assert r.get_json()["erro"] == "matricula_invalida"
    # Sem senha e sem catraca: a senha vem antes da catraca.
    r = validar(cliente, {"matricula": MATRICULA})
    assert r.get_json()["erro"] == "senha_ausente"
    # Catraca ausente vem antes de catraca não cadastrada.
    r = validar(cliente, {"matricula": MATRICULA, "senha": SENHA})
    assert r.get_json()["erro"] == "catraca_ausente"
    assert suap_falso["chamadas"] == []


# (código do erro, status HTTP devolvido pelo SUAP, status esperado na resposta)
ERROS_SUAP = [
    ("autenticacao_recusada", 400, 401),
    ("autenticacao_recusada", 401, 401),
    ("acesso_negado", 403, 403),
    ("limite_requisicoes", 429, 503),
    ("suap_indisponivel", 500, 503),
    ("suap_indisponivel", 503, 503),
    ("timeout", None, 503),
    ("erro_conexao", None, 503),
    ("recurso_nao_encontrado", 404, 502),
    ("resposta_invalida", 200, 502),
]


@pytest.mark.parametrize("etapa", ["autenticar", "buscar_aluno"])
@pytest.mark.parametrize("codigo, status_suap, esperado", ERROS_SUAP)
def test_erros_do_suap(cliente, monkeypatch, etapa, codigo, status_suap, esperado):
    def falha(*args, **kwargs):
        raise SuapErro(codigo, "mensagem", status_suap=status_suap)

    # Se a falha for na consulta, a autenticação funciona normalmente.
    monkeypatch.setattr(
        suap, "autenticar", lambda *a, **k: {"access": TOKEN_ACESSO, "refresh": "r"}
    )
    monkeypatch.setattr(suap, etapa, falha)

    r = validar(cliente)

    assert r.status_code == esperado
    corpo = r.get_json()
    assert corpo["erro"] == codigo
    assert "autorizado" not in corpo  # falha do SUAP nunca vira "negado"
    assert SENHA not in r.get_data(as_text=True)


def test_metodo_nao_permitido(cliente):
    r = cliente.get(URL)
    assert r.status_code == 405
    assert r.is_json


def test_rota_inexistente(cliente):
    r = cliente.get("/v1/nada")
    assert r.status_code == 404
    assert r.is_json


def test_autorizado_unitario():
    assert autorizado(aluno()) is True
    assert autorizado(aluno(situacao="matriculado")) is True
    assert autorizado(aluno(curso=CURSO_GUARABIRA.lower())) is True
    assert autorizado(aluno(situacao="Evadido")) is False
    assert autorizado(aluno(curso="ALIMENTOS (CAMPUS SOUSA)")) is False
    assert autorizado(None) is False
