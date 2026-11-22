import requests

from unittest.mock import Mock


URL = "/v1/acessos/validar"

DADOS = {
    "matricula": "202310000000",
    "senha": "senha_teste",
    "catraca_id": "CATRACA-01",
}

CURSO_GUARABIRA = (
    "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)"
)


def resposta_suap(status, dados=None):
    resposta = Mock()
    resposta.status_code = status
    resposta.json.return_value = dados
    return resposta


def aluno_suap(situacao):
    return {
        "matricula": DADOS["matricula"],
        "situacao": situacao,
        "curso": {
            "nome": CURSO_GUARABIRA
        }
    }


def instalar_mock_suap(monkeypatch, alunos):
    """Simula autenticação e consulta de alunos no SUAP."""

    def simular_post(url, json=None, timeout=None, **kwargs):
        assert "obtain_token" in url

        return resposta_suap(
            200,
            {
                "access": "token-falso",
                "refresh": "refresh-falso"
            }
        )

    def simular_get(url, params=None, headers=None,
                    timeout=None, **kwargs):

        assert "ensino/alunos/v1/" in url

        return resposta_suap(
            200,
            {
                "results": alunos
            }
        )

    monkeypatch.setattr(
        "app.services.suap.requests.post",
        simular_post
    )

    monkeypatch.setattr(
        "app.services.suap.requests.get",
        simular_get
    )

# TESTE 1: MATRÍCULA ATIVA

def test_matricula_ativa(client, monkeypatch):

    instalar_mock_suap(
        monkeypatch,
        [aluno_suap("Matriculado")]
    )

    resposta = client.post(URL, json=DADOS)

    assert resposta.status_code == 200
    assert resposta.json["autorizado"] is True

# TESTE 2: MATRÍCULA INEXISTENTE

def test_matricula_inexistente(client, monkeypatch):

    instalar_mock_suap(
        monkeypatch,
        []
    )

    resposta = client.post(URL, json=DADOS)

    assert resposta.status_code == 200
    assert resposta.json["autorizado"] is False

# TESTE 3: MATRÍCULA INATIVA

def test_matricula_inativa(client, monkeypatch):

    instalar_mock_suap(
        monkeypatch,
        [aluno_suap("Cancelado")]
    )

    resposta = client.post(URL, json=DADOS)

    assert resposta.status_code == 200
    assert resposta.json["autorizado"] is False

# TESTE 4: TIMEOUT DO SUAP

def test_timeout_suap(client, monkeypatch):

    def simular_timeout(url, **kwargs):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(
        "app.services.suap.requests.post",
        simular_timeout
    )

    resposta = client.post(URL, json=DADOS)

    assert resposta.status_code == 503
    assert resposta.json["erro"] == "timeout"

# TESTE 5: FALHA DE CONEXÃO COM O SUAP

def test_falha_conexao_suap(client, monkeypatch):

    def simular_falha(url, **kwargs):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(
        "app.services.suap.requests.post",
        simular_falha
    )

    resposta = client.post(URL, json=DADOS)

    assert resposta.status_code == 503
    assert resposta.json["erro"] == "erro_conexao"

# TESTE 6: TOKEN RECUSADO

def test_token_recusado(client, monkeypatch):

    def simular_token_recusado(url, **kwargs):
        return resposta_suap(
            401,
            {"detail": "Credenciais inválidas"}
        )

    monkeypatch.setattr(
        "app.services.suap.requests.post",
        simular_token_recusado
    )

    resposta = client.post(URL, json=DADOS)

    assert resposta.status_code == 401
    assert resposta.json["erro"] == "autenticacao_recusada"
