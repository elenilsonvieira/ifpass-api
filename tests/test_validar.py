import pytest

from app import create_app
from app.config import Config
from app.services import suap
from app.services.suap import SuapErro, autorizado

URL = "/v1/acessos/validar"
MATRICULA = "202312345601"
MATRICULA_SERVIDOR = "1000001"
TOKEN_SERVICO = "token-servico-de-teste"
CURSO_GUARABIRA = "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)"
CORPO_VALIDO = {"matricula": MATRICULA, "catraca_id": "CATRACA-01"}


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

    Devolve um dict para o teste escolher o aluno/servidor e registra o que
    foi chamado.
    """
    estado = {"aluno": None, "servidor": None, "chamadas": []}

    def token_falso(config):
        estado["chamadas"].append(("obter_token_servico",))
        return TOKEN_SERVICO

    def buscar_aluno_falso(matricula, token, config):
        estado["chamadas"].append(("buscar_aluno", matricula, token))
        return estado["aluno"]

    def buscar_servidor_falso(matricula, token, config):
        estado["chamadas"].append(("buscar_servidor", matricula, token))
        return estado["servidor"]

    monkeypatch.setattr(suap, "obter_token_servico", token_falso)
    monkeypatch.setattr(suap, "buscar_aluno", buscar_aluno_falso)
    monkeypatch.setattr(suap, "buscar_servidor", buscar_servidor_falso)
    return estado


def aluno(situacao="Matriculado", curso=CURSO_GUARABIRA, matricula=MATRICULA):
    return {"matricula": matricula, "situacao": situacao, "curso_nome": curso}


def servidor(nome_situacao="ATIVO PERMANENTE", codigo="01"):
    return {
        "matricula": MATRICULA_SERVIDOR,
        "nome": "Servidor Teste",
        "situacao_codigo": codigo,
        "situacao_nome": nome_situacao,
    }


def validar(cliente, corpo=CORPO_VALIDO, **kwargs):
    return cliente.post(URL, json=corpo, **kwargs)


def sem(chave):
    return {k: v for k, v in CORPO_VALIDO.items() if k != chave}


@pytest.mark.parametrize(
    "dados_aluno, esperado",
    [
        (aluno(), True),
        (aluno(curso="TECNOLOGIA EM ALIMENTOS (CAMPUS SOUSA)"), True),
        (aluno(situacao="Evadido"), False),
        (aluno(situacao="Formado"), False),
        (None, False),  # matrícula não encontrada
    ],
)
def test_autorizacao_aluno(cliente, suap_falso, dados_aluno, esperado):
    suap_falso["aluno"] = dados_aluno
    r = validar(cliente)
    assert r.status_code == 200
    assert r.get_json() == {"autorizado": esperado}


@pytest.mark.parametrize(
    "dados_servidor, esperado",
    [
        (servidor(), True),
        (servidor("CONT.PROF.SUBSTITUTO", "52"), True),
        (servidor("APOSENTADO", "01"), False),
        (None, False),  # matrícula não encontrada
    ],
)
def test_autorizacao_servidor(cliente, suap_falso, dados_servidor, esperado):
    suap_falso["servidor"] = dados_servidor
    r = validar(cliente, {**CORPO_VALIDO, "matricula": MATRICULA_SERVIDOR})
    assert r.status_code == 200
    assert r.get_json() == {"autorizado": esperado}


def test_usa_token_de_servico_e_roteia_pelo_tamanho(cliente, suap_falso):
    suap_falso["aluno"] = aluno()
    suap_falso["servidor"] = servidor()

    validar(cliente)
    assert suap_falso["chamadas"] == [
        ("obter_token_servico",),
        ("buscar_aluno", MATRICULA, TOKEN_SERVICO),
    ]

    suap_falso["chamadas"].clear()
    validar(cliente, {**CORPO_VALIDO, "matricula": MATRICULA_SERVIDOR})
    assert suap_falso["chamadas"] == [
        ("obter_token_servico",),
        ("buscar_servidor", MATRICULA_SERVIDOR, TOKEN_SERVICO),
    ]


def test_senha_enviada_e_ignorada_e_token_nao_vaza(cliente, suap_falso):
    suap_falso["aluno"] = aluno()
    r = validar(cliente, {**CORPO_VALIDO, "senha": "senha-por-engano"})
    assert r.status_code == 200
    assert r.get_json() == {"autorizado": True}
    texto = r.get_data(as_text=True)
    assert "senha-por-engano" not in texto
    assert TOKEN_SERVICO not in texto
    # A senha nunca chega ao SUAP.
    assert all("senha-por-engano" not in str(c) for c in suap_falso["chamadas"])


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
        {**CORPO_VALIDO, "matricula": "12345678"},
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
    # Catraca ausente vem antes de catraca não cadastrada.
    r = validar(cliente, {"matricula": MATRICULA})
    assert r.get_json()["erro"] == "catraca_ausente"
    r = validar(cliente, {"matricula": MATRICULA, "catraca_id": "CATRACA-99"})
    assert r.get_json()["erro"] == "catraca_nao_cadastrada"
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


@pytest.mark.parametrize(
    "etapa, matricula",
    [("buscar_aluno", MATRICULA), ("buscar_servidor", MATRICULA_SERVIDOR)],
)
@pytest.mark.parametrize("codigo, status_suap, esperado", ERROS_SUAP)
def test_erros_do_suap(cliente, monkeypatch, etapa, matricula,
                       codigo, status_suap, esperado):
    def falha(*args, **kwargs):
        raise SuapErro(codigo, "mensagem", status_suap=status_suap)

    monkeypatch.setattr(suap, "obter_token_servico", lambda config: TOKEN_SERVICO)
    monkeypatch.setattr(suap, etapa, falha)

    r = validar(cliente, {**CORPO_VALIDO, "matricula": matricula})

    assert r.status_code == esperado
    corpo = r.get_json()
    assert corpo["erro"] == codigo
    assert "autorizado" not in corpo  # falha do SUAP nunca vira "negado"
    assert TOKEN_SERVICO not in r.get_data(as_text=True)


def test_token_de_servico_expirado_vira_503(cliente, monkeypatch):
    def falha(config):
        raise SuapErro("token_servico_expirado", "expirado", status_suap=503)

    monkeypatch.setattr(suap, "obter_token_servico", falha)

    r = validar(cliente)

    assert r.status_code == 503
    assert r.get_json()["erro"] == "token_servico_expirado"


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
    assert autorizado(aluno(situacao="  MATRICULADO  ")) is True
    assert autorizado(aluno(curso="ALIMENTOS (CAMPUS SOUSA)")) is True
    assert autorizado(aluno(situacao="Evadido")) is False
    assert autorizado(aluno(situacao="")) is False
    assert autorizado(None) is False
