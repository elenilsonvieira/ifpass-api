"""Testes da validação na catraca só com matrícula (token de serviço do SUAP).

Usa apenas dados fictícios e nunca acessa a internet.
"""
import time

import jwt
import pytest

from app import create_app
from app.config import Config
from app.db import get_db_connection
from app.services import suap
from app.services.suap import SuapErro, autorizado, servidor_autorizado
from app.services.suap_token import SuapTokenManager, TokenServicoExpirado

URL = "/v1/acessos/validar"
ALUNO = "202410000001"
SERVIDOR = "1000001"
CATRACA = "CATRACA-01"


def gerar_token(segundos=3600, com_exp=True):
    """JWT de teste; `segundos` é o tempo até expirar (negativo = já expirado)."""
    payload = {"user_id": 1}
    if com_exp:
        payload["exp"] = int(time.time()) + segundos
    return jwt.encode(payload, "segredo-de-teste-com-32-bytes-ok", algorithm="HS256")


def criar_config(token):
    class ConfigTeste(Config):
        TESTING = True
        SUAP_BASE_URL = "https://suap.exemplo.invalido/api"
        SUAP_TIMEOUT_SEGUNDOS = 1
        CATRACAS_CADASTRADAS = {CATRACA}
        SUAP_TOKEN = token

    return ConfigTeste


@pytest.fixture(autouse=True)
def limpar_gerenciadores():
    suap._gerenciadores_token.clear()
    yield
    suap._gerenciadores_token.clear()


@pytest.fixture
def cliente():
    """App com um token de serviço válido configurado."""
    return create_app(criar_config(gerar_token())).test_client()


@pytest.fixture
def suap_falso(monkeypatch):
    """Simula o token de serviço e as consultas de aluno e servidor."""
    estado = {"aluno": None, "servidor": None}
    monkeypatch.setattr(suap, "obter_token_servico", lambda config: "token-falso")
    monkeypatch.setattr(suap, "buscar_aluno", lambda *a, **k: estado["aluno"])
    monkeypatch.setattr(suap, "buscar_servidor", lambda *a, **k: estado["servidor"])
    return estado


def aluno(situacao="Matriculado", curso="CURSO FICTICIO (CAMPUS QUALQUER)"):
    return {"matricula": ALUNO, "situacao": situacao, "curso_nome": curso}


def servidor(nome_situacao):
    return {
        "matricula": SERVIDOR,
        "nome": "Servidor Teste",
        "situacao_codigo": "99",
        "situacao_nome": nome_situacao,
    }


def corpo(matricula=ALUNO, catraca_id=CATRACA):
    return {"matricula": matricula, "catraca_id": catraca_id}


def ler_historico():
    conn = get_db_connection()
    linhas = conn.execute("SELECT * FROM historico_acessos").fetchall()
    conn.close()
    return linhas


# REGRA: ALUNO

@pytest.mark.parametrize(
    "curso",
    [
        "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)",
        "TECNOLOGIA EM ALIMENTOS (CAMPUS SOUSA)",
        "",
    ],
)
def test_aluno_matriculado_de_qualquer_campus(curso):
    assert autorizado(aluno(curso=curso)) is True


@pytest.mark.parametrize("situacao", ["matriculado", "  MATRICULADO ", "Matriculado"])
def test_aluno_matriculado_ignora_caixa_e_espacos(situacao):
    assert autorizado(aluno(situacao=situacao)) is True


@pytest.mark.parametrize(
    "situacao", ["Cancelado", "Evadido", "Formado", "Trancado", "", None]
)
def test_aluno_com_outra_situacao_negado(situacao):
    assert autorizado(aluno(situacao=situacao)) is False


def test_aluno_inexistente_negado():
    assert autorizado(None) is False


# REGRA: SERVIDOR

@pytest.mark.parametrize(
    "nome",
    [
        "ATIVO PERMANENTE",
        "CONT.PROF.SUBSTITUTO",
        "ativo permanente",
        "Cont.Prof.Substituto",
        "  ATIVO PERMANENTE  ",
        "\tcont.prof.substituto ",
    ],
)
def test_servidor_ativo_autorizado(nome):
    assert servidor_autorizado(servidor(nome)) is True


@pytest.mark.parametrize("nome", ["APOSENTADO", "EXCLUIDO", "ATIVO", "", "   ", None])
def test_servidor_com_outra_situacao_negado(nome):
    assert servidor_autorizado(servidor(nome)) is False


def test_servidor_sem_situacao_nome_negado():
    assert servidor_autorizado({"matricula": SERVIDOR}) is False


def test_servidor_inexistente_negado():
    assert servidor_autorizado(None) is False


def test_codigo_da_situacao_nao_decide():
    # Código "01" não libera sozinho; o nome é que vale.
    assert servidor_autorizado(
        {"situacao_codigo": "01", "situacao_nome": "APOSENTADO"}
    ) is False
    assert servidor_autorizado(
        {"situacao_codigo": "99", "situacao_nome": "ATIVO PERMANENTE"}
    ) is True


# ENDPOINT: MATRÍCULA E CATRACA

@pytest.mark.parametrize("matricula", [ALUNO, SERVIDOR])
def test_matricula_de_7_e_12_digitos_aceitas(cliente, suap_falso, matricula):
    suap_falso["aluno"] = aluno()
    suap_falso["servidor"] = servidor("ATIVO PERMANENTE")
    r = cliente.post(URL, json=corpo(matricula))
    assert r.status_code == 200
    assert r.get_json() == {"autorizado": True}


@pytest.mark.parametrize(
    "matricula", ["12345678", "20241000000", "10000a1", "abcdefg", "", "      "]
)
def test_matricula_invalida(cliente, suap_falso, matricula):
    r = cliente.post(URL, json=corpo(matricula))
    assert r.status_code == 400
    assert r.get_json()["erro"] == "matricula_invalida"


def test_catraca_ausente(cliente, suap_falso):
    r = cliente.post(URL, json={"matricula": ALUNO})
    assert r.status_code == 400
    assert r.get_json()["erro"] == "catraca_ausente"


def test_catraca_nao_cadastrada(cliente, suap_falso):
    r = cliente.post(URL, json=corpo(catraca_id="CATRACA-99"))
    assert r.status_code == 403
    assert r.get_json()["erro"] == "catraca_nao_cadastrada"


# ENDPOINT: TOKEN DE SERVIÇO (sem simular obter_token_servico)

@pytest.fixture
def aluno_matriculado(monkeypatch):
    monkeypatch.setattr(suap, "buscar_aluno", lambda *a, **k: aluno())


@pytest.mark.parametrize(
    "token",
    [
        "",
        "   ",
        "isto-nao-e-um-jwt",
        gerar_token(segundos=-60),
        gerar_token(com_exp=False),
    ],
    ids=["ausente", "so_espacos", "invalido", "expirado", "sem_exp"],
)
def test_token_de_servico_com_problema_vira_503(aluno_matriculado, token):
    cliente = create_app(criar_config(token)).test_client()

    r = cliente.post(URL, json=corpo())

    assert r.status_code == 503
    assert r.get_json()["erro"] == "token_servico_expirado"
    assert "autorizado" not in r.get_json()


def test_token_de_servico_valido_passa(aluno_matriculado):
    cliente = create_app(criar_config(gerar_token())).test_client()

    r = cliente.post(URL, json=corpo())

    assert r.status_code == 200
    assert r.get_json() == {"autorizado": True}


def test_token_valido_e_enviado_ao_suap(monkeypatch):
    token = gerar_token()
    recebido = {}

    def buscar_aluno_falso(matricula, tk, config):
        recebido["token"] = tk
        return aluno()

    monkeypatch.setattr(suap, "buscar_aluno", buscar_aluno_falso)
    cliente = create_app(criar_config(token)).test_client()

    r = cliente.post(URL, json=corpo())

    assert r.status_code == 200
    assert recebido["token"] == token
    assert token not in r.get_data(as_text=True)


# SuapTokenManager

def test_gerenciador_devolve_token_valido():
    token = gerar_token()
    gerenciador = SuapTokenManager({"SUAP_TOKEN": token})
    assert gerenciador.obter_token_servico() == token


def test_gerenciador_aceita_espacos_nas_pontas():
    token = gerar_token()
    gerenciador = SuapTokenManager({"SUAP_TOKEN": f"  {token} "})
    assert gerenciador.obter_token_servico() == token


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_gerenciador_sem_token_configurado(valor):
    gerenciador = SuapTokenManager({"SUAP_TOKEN": valor})
    with pytest.raises(TokenServicoExpirado):
        gerenciador.obter_token_servico()


def test_gerenciador_token_invalido():
    gerenciador = SuapTokenManager({"SUAP_TOKEN": "isto-nao-e-um-jwt"})
    with pytest.raises(TokenServicoExpirado):
        gerenciador.obter_token_servico()


def test_gerenciador_token_expirado():
    gerenciador = SuapTokenManager({"SUAP_TOKEN": gerar_token(segundos=-60)})
    with pytest.raises(TokenServicoExpirado):
        gerenciador.obter_token_servico()


def test_gerenciador_token_quase_expirado_usa_margem():
    # Falta menos que a margem de 30 s: já é tratado como expirado.
    gerenciador = SuapTokenManager({"SUAP_TOKEN": gerar_token(segundos=10)})
    with pytest.raises(TokenServicoExpirado):
        gerenciador.obter_token_servico()


def test_medir_validade_de_token_futuro():
    gerenciador = SuapTokenManager({})
    restante = gerenciador.medir_validade(gerar_token(segundos=600))
    assert 590 <= restante <= 600


def test_medir_validade_rejeita_token_expirado_ou_invalido():
    gerenciador = SuapTokenManager({})
    with pytest.raises(TokenServicoExpirado):
        gerenciador.medir_validade(gerar_token(segundos=-5))
    with pytest.raises(TokenServicoExpirado):
        gerenciador.medir_validade("lixo")
    with pytest.raises(TokenServicoExpirado):
        gerenciador.medir_validade(gerar_token(com_exp=False))


def test_suap_obter_token_servico_converte_erro():
    config = {"SUAP_TOKEN": gerar_token(segundos=-60)}
    with pytest.raises(SuapErro) as erro:
        suap.obter_token_servico(config)
    assert erro.value.codigo == "token_servico_expirado"
    assert erro.value.status_suap == 503


def test_suap_obter_token_servico_devolve_token():
    token = gerar_token()
    assert suap.obter_token_servico({"SUAP_TOKEN": token}) == token


# HISTÓRICO

@pytest.mark.parametrize("matricula", [ALUNO, SERVIDOR])
def test_historico_permitido(cliente, suap_falso, matricula):
    suap_falso["aluno"] = aluno()
    suap_falso["servidor"] = servidor("ATIVO PERMANENTE")
    cliente.post(URL, json=corpo(matricula))
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["matricula"] == matricula
    assert linhas[0]["catraca_id"] == CATRACA
    assert linhas[0]["resultado"] == "Permitido"
    assert linhas[0]["detalhes_erro"] is None


@pytest.mark.parametrize("matricula", [ALUNO, SERVIDOR])
def test_historico_negado(cliente, suap_falso, matricula):
    suap_falso["aluno"] = aluno(situacao="Cancelado")
    suap_falso["servidor"] = servidor("APOSENTADO")
    cliente.post(URL, json=corpo(matricula))
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["matricula"] == matricula
    assert linhas[0]["resultado"] == "Negado"


@pytest.mark.parametrize("matricula", [ALUNO, SERVIDOR])
def test_historico_erro(cliente, monkeypatch, matricula):
    def falha(*args, **kwargs):
        raise SuapErro("suap_indisponivel", "fora do ar", status_suap=503)

    monkeypatch.setattr(suap, "obter_token_servico", lambda config: "token-falso")
    monkeypatch.setattr(suap, "buscar_aluno", falha)
    monkeypatch.setattr(suap, "buscar_servidor", falha)
    cliente.post(URL, json=corpo(matricula))
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["matricula"] == matricula
    assert linhas[0]["resultado"] == "Erro"
    assert linhas[0]["detalhes_erro"] == "suap_indisponivel"


def test_historico_erro_de_token_de_servico():
    cliente = create_app(criar_config("")).test_client()
    cliente.post(URL, json=corpo(SERVIDOR))
    linhas = ler_historico()
    assert len(linhas) == 1
    assert linhas[0]["resultado"] == "Erro"
    assert linhas[0]["detalhes_erro"] == "token_servico_expirado"
