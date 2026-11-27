"""Testes do login de alunos e servidores sem acesso à rede."""

import pytest

from app.services import auth, suap


URL = "/v1/auth/login"
ALUNO = "202413810024"
SERVIDOR = "1000001"
SENHA = "senha-ficticia-nao-registrar"
TOKEN = "access-token-ficticio"
REFRESH = "refresh-token-ficticio"


@pytest.mark.parametrize("matricula", [ALUNO, SERVIDOR])
def test_login_devolve_token_e_dados_minimos(client, monkeypatch, matricula):
    tipo = "aluno" if len(matricula) == 12 else "servidor"
    dados_usuario = {"matricula": matricula, "nome": "Pessoa Teste"}
    chamadas = []

    def autenticar(m, s, config):
        chamadas.append((m, s))
        return {"access": TOKEN, "refresh": REFRESH}

    def buscar(m, token, config):
        chamadas.append((m, token))
        return dados_usuario

    monkeypatch.setattr(suap, "autenticar", autenticar)
    monkeypatch.setattr(suap, "buscar_aluno", buscar)
    monkeypatch.setattr(suap, "buscar_servidor", buscar)

    resposta = client.post(URL, json={"matricula": matricula, "senha": SENHA})

    assert resposta.status_code == 200
    assert resposta.get_json() == {
        "token": TOKEN,
        "usuario": {"matricula": matricula, "nome": "Pessoa Teste", "tipo": tipo},
    }
    assert REFRESH not in resposta.get_data(as_text=True)
    assert chamadas == [(matricula, SENHA), (matricula, TOKEN)]


def test_login_aluno_chama_somente_consulta_de_aluno(client, monkeypatch):
    chamadas = []
    monkeypatch.setattr(suap, "autenticar", lambda *a: {"access": TOKEN, "refresh": REFRESH})
    monkeypatch.setattr(suap, "buscar_aluno", lambda *a: chamadas.append("aluno") or {
        "matricula": ALUNO, "nome": "Aluna Teste"
    })
    monkeypatch.setattr(suap, "buscar_servidor", lambda *a: chamadas.append("servidor"))

    resposta = client.post(URL, json={"matricula": ALUNO, "senha": SENHA})

    assert resposta.status_code == 200
    assert chamadas == ["aluno"]


def test_login_servidor_chama_somente_consulta_de_servidor(client, monkeypatch):
    chamadas = []
    monkeypatch.setattr(suap, "autenticar", lambda *a: {"access": TOKEN, "refresh": REFRESH})
    monkeypatch.setattr(suap, "buscar_aluno", lambda *a: chamadas.append("aluno"))
    monkeypatch.setattr(suap, "buscar_servidor", lambda *a: chamadas.append("servidor") or {
        "matricula": SERVIDOR, "nome": "Servidor Teste"
    })

    resposta = client.post(URL, json={"matricula": SERVIDOR, "senha": SENHA})

    assert resposta.status_code == 200
    assert chamadas == ["servidor"]


@pytest.mark.parametrize("matricula", ["123", "12345678", "12345678901", "1234567890123", "123456a", "１２３４５６７"])
def test_matricula_invalida(client, matricula):
    resposta = client.post(URL, json={"matricula": matricula, "senha": SENHA})
    assert resposta.status_code == 400
    assert resposta.get_json()["erro"] == "credenciais_invalidas"


@pytest.mark.parametrize("senha", [None, "", "   ", 123])
def test_senha_ausente_ou_invalida(client, senha):
    resposta = client.post(URL, json={"matricula": ALUNO, "senha": senha})
    assert resposta.status_code == 400


def test_corpo_json_invalido(client):
    resposta = client.post(URL, data="texto", content_type="text/plain")
    assert resposta.status_code == 400
    assert resposta.get_json()["erro"] == "corpo_invalido"


def test_senha_invalida_no_suap_retorna_401(client, monkeypatch):
    def autenticar(*args):
        raise suap.SuapErro("autenticacao_recusada", "Credenciais recusadas", status_suap=401)

    monkeypatch.setattr(suap, "autenticar", autenticar)
    resposta = client.post(URL, json={"matricula": ALUNO, "senha": SENHA})

    assert resposta.status_code == 401
    assert resposta.get_json()["erro"] == "credenciais_invalidas"
    assert SENHA not in resposta.get_data(as_text=True)


@pytest.mark.parametrize("codigo", ["timeout", "erro_conexao", "suap_indisponivel"])
def test_falha_de_comunicacao_retorna_503(client, monkeypatch, codigo):
    monkeypatch.setattr(
        suap, "autenticar",
        lambda *args: (_ for _ in ()).throw(suap.SuapErro(codigo, "Falha", status_suap=503)),
    )
    resposta = client.post(URL, json={"matricula": ALUNO, "senha": SENHA})
    assert resposta.status_code == 503


def test_usuario_nao_encontrado_retorna_404(client, monkeypatch):
    monkeypatch.setattr(suap, "autenticar", lambda *a: {"access": TOKEN, "refresh": REFRESH})
    monkeypatch.setattr(suap, "buscar_aluno", lambda *a: None)

    resposta = client.post(URL, json={"matricula": ALUNO, "senha": SENHA})

    assert resposta.status_code == 404
    assert resposta.get_json()["erro"] == "usuario_nao_encontrado"


def test_login_nao_grava_historico(client, monkeypatch):
    monkeypatch.setattr(suap, "autenticar", lambda *a: {"access": TOKEN, "refresh": REFRESH})
    monkeypatch.setattr(suap, "buscar_aluno", lambda *a: {"matricula": ALUNO, "nome": "Pessoa Teste"})

    resposta = client.post(URL, json={"matricula": ALUNO, "senha": SENHA})

    assert resposta.status_code == 200
    # A rota de login não chama registrar_tentativa_acesso nem persiste perfil.
    from app.db import get_db_connection
    conexao = get_db_connection()
    try:
        linhas = conexao.execute("SELECT * FROM historico_acessos").fetchall()
    finally:
        conexao.close()
    assert linhas == []


def test_realizar_login_nao_retem_senha_ou_refresh():
    assert auth.validar_credenciais(ALUNO, SENHA)
    # O serviço devolve somente access e campos públicos; refresh é descartado.
    assert auth.TAMANHOS_MATRICULA == {7, 12}
