
from flask import Blueprint, current_app, jsonify, request

from app.services import catraca, suap
from app.services.historico import registrar_tentativa_acesso

bp = Blueprint("v1", __name__)


@bp.get("/status")
def status():
    return jsonify({"status": "ok"}), 200

def _ler_catraca_id():
    """Extrai e normaliza o identificador da catraca do corpo da requisição."""
    corpo = request.get_json(silent=True)

    if not isinstance(corpo, dict):
        return None

    catraca_id = corpo.get("catraca_id")

    if not isinstance(catraca_id, str) or not catraca_id.strip():
        return None

    return catraca_id.strip().upper()


def _ler_senha():
    """Extrai a senha do corpo da requisição."""
    corpo = request.get_json(silent=True)

    if not isinstance(corpo, dict):
        return None

    senha = corpo.get("senha")

    if not isinstance(senha, str) or not senha:
        return None

    return senha


def _ler_matricula():
    """Extrai e valida a matrícula do corpo da requisição."""
    corpo = request.get_json(silent=True)

    if not isinstance(corpo, dict):
        return None

    matricula = corpo.get("matricula")

    if (
        isinstance(matricula, str)
        and len(matricula) == 12
        and matricula.isascii()
        and matricula.isdigit()
    ):
        return matricula

    return None


def _decidir_acesso():
    """Decide o resultado final e devolve (corpo, status)."""

    matricula = _ler_matricula()
    if matricula is None:
        return {
            "erro": "matricula_invalida",
            "mensagem": "A matrícula deve conter exatamente 12 dígitos."
        }, 400

    senha = _ler_senha()
    if senha is None:
        return {
            "erro": "senha_ausente",
            "mensagem": "A senha deve ser informada."
        }, 400




    catraca_id = _ler_catraca_id()
    if catraca_id is None:
        return {
            "erro": "catraca_ausente",
            "mensagem": "O identificador da catraca deve ser informado."
        }, 400

    if not catraca.catraca_cadastrada(catraca_id, current_app.config):
        return {
            "erro": "catraca_nao_cadastrada",
            "mensagem": "A catraca informada não está cadastrada."
        }, 403


    try:
        # 1. Autenticar no SUAP
        tokens = suap.autenticar(
            matricula,
            senha,
            current_app.config
        )

        # 2. Obter access e refresh
        token = tokens["access"]

        # 3. Confirmar dono do token e consultar aluno
        aluno = suap.confirmar_dono_token(
            matricula,
            token,
            current_app.config
        )

    except suap.SuapErro as erro:
        corpo = erro.para_json()

        if erro.status_suap in (400, 401):
            return corpo, 401

        if erro.status_suap == 403:
            return corpo, 403

        if erro.status_suap == 429:
            return corpo, 503

        if erro.status_suap is not None and erro.status_suap >= 500:
            return corpo, 503

        if erro.codigo in ("timeout", "erro_conexao"):
            return corpo, 503

        return corpo, 502

    # 4. Verificar autorização
    return {
        "autorizado": suap.autorizado(aluno)
    }, 200


@bp.post("/acessos/validar")
def validar_acesso():

   

    corpo, codigo = _decidir_acesso()
    matricula = _ler_matricula()
    catraca_id = _ler_catraca_id()

    resultado = "Erro"
    detalhes_erro = corpo.get("erro")

    if codigo == 200:
        if corpo.get("autorizado") == True:
            resultado = "Permitido"
        else:
            resultado = "Negado"

    registrar_tentativa_acesso(
        matricula,
        resultado,
        detalhes_erro,
        catraca_id
    )

    return jsonify(corpo), codigo
