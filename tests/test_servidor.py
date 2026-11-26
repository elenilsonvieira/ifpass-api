import pytest
import requests

from unittest.mock import Mock

from app.services import suap
from app.services.suap import SuapErro, buscar_servidor


CONFIG = {
    "SUAP_BASE_URL": "https://suap.exemplo.invalido/api",
    "SUAP_TIMEOUT_SEGUNDOS": 7,
}

MATRICULA = "1000001"
TOKEN = "token-falso-de-teste"

SITUACAO_PERMANENTE = {"codigo": "01", "nome": "ATIVO PERMANENTE"}
SITUACAO_SUBSTITUTO = {"codigo": "52", "nome": "CONT.PROF.SUBSTITUTO"}


def resposta_suap(status, dados=None):
    resposta = Mock()
    resposta.status_code = status
    resposta.json.return_value = dados
    return resposta


def servidor_suap(matricula=MATRICULA, nome="Servidor Teste Permanente",
                  situacao=SITUACAO_PERMANENTE):
    """Item no formato do SUAP real, com os campos extras que devem ser ignorados."""
    return {
        "url": f"https://suap.exemplo.invalido/api/recursos-humanos/servidores/v1/{matricula}/",
        "uuid": "00000000-0000-0000-0000-000000000000",
        "matricula": matricula,
        "nome": nome,
        "cargo_emprego": {"codigo": "000", "nome": "CARGO FICTICIO"},
        "lotacao_siape": {"codigo": "0", "nome": "LOTACAO FICTICIA"},
        "lotacao_suap": {"codigo": "0", "nome": "LOTACAO SUAP FICTICIA"},
        "setor_exercicio": {"codigo": "0", "nome": "SETOR FICTICIO"},
        "jornada_trabalho": "40 HORAS SEMANAIS",
        "funcao_codigo": None,
        "disciplina_ingresso": None,
        "situacao": situacao,
    }


def pagina(*itens):
    """Resposta paginada, como a do SUAP real."""
    return {
        "count": len(itens),
        "next": None,
        "previous": None,
        "results": list(itens),
    }


def instalar_get(monkeypatch, resposta):
    """Faz requests.get devolver a resposta dada e guarda os argumentos da chamada."""
    chamadas = []

    def simular_get(url, **kwargs):
        chamadas.append({"url": url, **kwargs})
        return resposta

    monkeypatch.setattr("app.services.suap.requests.get", simular_get)
    return chamadas


def buscar(monkeypatch, dados, matricula=MATRICULA, status=200):
    instalar_get(monkeypatch, resposta_suap(status, dados))
    return buscar_servidor(matricula, TOKEN, CONFIG)


# SERVIDORES ENCONTRADOS

def test_servidor_ativo_permanente(monkeypatch):
    resultado = buscar(monkeypatch, pagina(servidor_suap()))

    assert resultado == {
        "matricula": "1000001",
        "nome": "Servidor Teste Permanente",
        "situacao_codigo": "01",
        "situacao_nome": "ATIVO PERMANENTE",
    }
    # O código mantém o zero à esquerda: nunca vira número.
    assert isinstance(resultado["situacao_codigo"], str)
    assert resultado["situacao_codigo"] == "01"


def test_servidor_substituto(monkeypatch):
    resultado = buscar(
        monkeypatch,
        pagina(servidor_suap(
            matricula="1000002",
            nome="Servidor Teste Substituto",
            situacao=SITUACAO_SUBSTITUTO,
        )),
        matricula="1000002",
    )

    assert resultado == {
        "matricula": "1000002",
        "nome": "Servidor Teste Substituto",
        "situacao_codigo": "52",
        "situacao_nome": "CONT.PROF.SUBSTITUTO",
    }


def test_devolve_somente_as_chaves_esperadas(monkeypatch):
    resultado = buscar(monkeypatch, pagina(servidor_suap()))

    assert set(resultado) == {
        "matricula", "nome", "situacao_codigo", "situacao_nome"
    }


def test_lista_direta_como_reserva(monkeypatch):
    resultado = buscar(monkeypatch, [servidor_suap()])

    assert resultado["matricula"] == "1000001"
    assert resultado["situacao_codigo"] == "01"


def test_remove_espacos_nas_pontas(monkeypatch):
    resultado = buscar(
        monkeypatch,
        pagina(servidor_suap(matricula=" 1000001 ", nome="  Servidor Teste  ")),
        matricula="1000001 ",
    )

    assert resultado["matricula"] == "1000001"
    assert resultado["nome"] == "Servidor Teste"


# CONFERÊNCIA EXATA DA MATRÍCULA

def test_varias_matriculas_devolve_somente_a_exata(monkeypatch):
    resultado = buscar(
        monkeypatch,
        pagina(
            servidor_suap(matricula="100000", nome="Servidor Teste Outro"),
            servidor_suap(matricula="10000011", nome="Servidor Teste Outro"),
            servidor_suap(matricula="1000001"),
            servidor_suap(matricula="1000002", nome="Servidor Teste Substituto"),
        ),
    )

    assert resultado["matricula"] == "1000001"
    assert resultado["nome"] == "Servidor Teste Permanente"


def test_matricula_parcial_nao_casa(monkeypatch):
    resultado = buscar(
        monkeypatch,
        pagina(servidor_suap(matricula="1000001")),
        matricula="100000",
    )

    assert resultado is None


# MATRÍCULA NÃO ENCONTRADA

@pytest.mark.parametrize(
    "dados",
    [
        pagina(),
        [],
        pagina(servidor_suap(matricula="1000009")),
    ],
)
def test_matricula_nao_encontrada(monkeypatch, dados):
    assert buscar(monkeypatch, dados) is None


# SITUAÇÃO AUSENTE OU INCOMPLETA

@pytest.mark.parametrize(
    "situacao, codigo, nome",
    [
        (None, "", ""),
        ("ATIVO PERMANENTE", "", ""),
        (["01", "ATIVO"], "", ""),
        (1, "", ""),
        ({}, "", ""),
        ({"codigo": "01"}, "01", ""),
        ({"nome": "ATIVO PERMANENTE"}, "", "ATIVO PERMANENTE"),
        ({"codigo": None, "nome": None}, "", ""),
        ({"codigo": None, "nome": "ATIVO PERMANENTE"}, "", "ATIVO PERMANENTE"),
    ],
)
def test_situacao_incompleta_devolve_vazio(monkeypatch, situacao, codigo, nome):
    resultado = buscar(monkeypatch, pagina(servidor_suap(situacao=situacao)))

    assert resultado["situacao_codigo"] == codigo
    assert resultado["situacao_nome"] == nome
    assert "None" not in resultado.values()


def test_situacao_ausente_no_item(monkeypatch):
    item = servidor_suap()
    del item["situacao"]

    resultado = buscar(monkeypatch, pagina(item))

    assert resultado["situacao_codigo"] == ""
    assert resultado["situacao_nome"] == ""


@pytest.mark.parametrize("nome", [None, ""])
def test_nome_ausente_ou_nulo_vira_vazio(monkeypatch, nome):
    resultado = buscar(monkeypatch, pagina(servidor_suap(nome=nome)))

    assert resultado["nome"] == ""


def test_nome_ausente_no_item(monkeypatch):
    item = servidor_suap()
    del item["nome"]

    assert buscar(monkeypatch, pagina(item))["nome"] == ""


# CHAMADA AO SUAP

def test_chamada_correta(monkeypatch):
    chamadas = instalar_get(monkeypatch, resposta_suap(200, pagina()))

    buscar_servidor(MATRICULA, TOKEN, CONFIG)

    assert len(chamadas) == 1
    chamada = chamadas[0]
    assert chamada["url"].endswith("/recursos-humanos/servidores/v1/")
    assert chamada["url"] == (
        "https://suap.exemplo.invalido/api/recursos-humanos/servidores/v1/"
    )
    assert chamada["params"] == {"search": MATRICULA}
    assert chamada["headers"] == {"Authorization": f"Bearer {TOKEN}"}
    assert chamada["timeout"] == CONFIG["SUAP_TIMEOUT_SEGUNDOS"]


def test_url_base_com_barra_final(monkeypatch):
    chamadas = instalar_get(monkeypatch, resposta_suap(200, pagina()))
    config = {**CONFIG, "SUAP_BASE_URL": "https://suap.exemplo.invalido/api/"}

    buscar_servidor(MATRICULA, TOKEN, config)

    assert chamadas[0]["url"] == (
        "https://suap.exemplo.invalido/api/recursos-humanos/servidores/v1/"
    )


def test_nao_imprime_nem_registra_token_ou_dados(monkeypatch, capsys, caplog):
    buscar(monkeypatch, pagina(servidor_suap()))

    saida = capsys.readouterr()
    tudo = saida.out + saida.err + caplog.text
    assert TOKEN not in tudo
    assert "Servidor Teste Permanente" not in tudo


# ERROS HTTP DO SUAP

@pytest.mark.parametrize(
    "status, codigo",
    [
        (401, "autenticacao_recusada"),
        (403, "acesso_negado"),
        (404, "recurso_nao_encontrado"),
        (429, "limite_requisicoes"),
        (500, "suap_indisponivel"),
        (503, "suap_indisponivel"),
    ],
)
def test_erros_http_do_suap(monkeypatch, status, codigo):
    instalar_get(monkeypatch, resposta_suap(status, {"detail": "Erro de teste"}))

    with pytest.raises(SuapErro) as erro:
        buscar_servidor(MATRICULA, TOKEN, CONFIG)

    assert erro.value.codigo == codigo
    assert erro.value.status_suap == status
    assert erro.value.para_json()["origem"] == "SUAP"
    assert TOKEN not in str(erro.value.para_json())


# FALHAS DE REDE

@pytest.mark.parametrize(
    "excecao, codigo",
    [
        (requests.exceptions.Timeout(), "timeout"),
        (requests.exceptions.ConnectionError(), "erro_conexao"),
        (requests.exceptions.RequestException(), "erro_conexao"),
    ],
)
def test_falhas_de_rede(monkeypatch, excecao, codigo):
    def simular_falha(url, **kwargs):
        raise excecao

    monkeypatch.setattr("app.services.suap.requests.get", simular_falha)

    with pytest.raises(SuapErro) as erro:
        buscar_servidor(MATRICULA, TOKEN, CONFIG)

    assert erro.value.codigo == codigo
    assert erro.value.status_suap is None


# RESPOSTAS INVÁLIDAS

def test_resposta_que_nao_e_json(monkeypatch):
    resposta = Mock()
    resposta.status_code = 200
    resposta.json.side_effect = ValueError("não é JSON")
    instalar_get(monkeypatch, resposta)

    with pytest.raises(SuapErro) as erro:
        buscar_servidor(MATRICULA, TOKEN, CONFIG)

    assert erro.value.codigo == "resposta_invalida"


@pytest.mark.parametrize(
    "dados",
    [
        None,
        "texto solto",
        123,
        {},
        {"count": 0},
        {"results": None},
        {"results": "nao-e-lista"},
        {"results": {"matricula": MATRICULA}},
    ],
)
def test_formato_invalido(monkeypatch, dados):
    instalar_get(monkeypatch, resposta_suap(200, dados))

    with pytest.raises(SuapErro) as erro:
        buscar_servidor(MATRICULA, TOKEN, CONFIG)

    assert erro.value.codigo == "resposta_invalida"


@pytest.mark.parametrize("item", ["texto", None, 5, [MATRICULA]])
def test_item_que_nao_e_dict(monkeypatch, item):
    instalar_get(monkeypatch, resposta_suap(200, pagina(item)))

    with pytest.raises(SuapErro) as erro:
        buscar_servidor(MATRICULA, TOKEN, CONFIG)

    assert erro.value.codigo == "resposta_invalida"


@pytest.mark.parametrize(
    "itens",
    [
        # item inválido depois de um item que não casa
        [servidor_suap(matricula="1000009"), "lixo"],
        # item inválido depois do servidor procurado: também é erro
        [servidor_suap(), "lixo"],
        # item inválido antes do servidor procurado
        ["lixo", servidor_suap()],
    ],
)
def test_item_invalido_em_qualquer_posicao(monkeypatch, itens):
    instalar_get(monkeypatch, resposta_suap(200, pagina(*itens)))

    with pytest.raises(SuapErro) as erro:
        buscar_servidor(MATRICULA, TOKEN, CONFIG)

    assert erro.value.codigo == "resposta_invalida"


def test_funcao_existe_no_modulo():
    assert suap.buscar_servidor is buscar_servidor
