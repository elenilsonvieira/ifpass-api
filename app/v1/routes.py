from flask import Blueprint, current_app, jsonify, request

from app.services import suap

bp = Blueprint("v1", __name__)


@bp.get("/status")
def status():
    return jsonify({"status": "ok"}), 200


def _ler_token():
    """Extrai o token do cabeçalho Authorization."""
    prefixo = "Bearer "
    cabecalho = request.headers.get("Authorization", "")
    if not cabecalho.startswith(prefixo):
        return None
    return cabecalho[len(prefixo) :].strip() or None


def _ler_matricula():
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
    """Decide o resultado final e devolve (corpo, status)"""
    token = _ler_token()
    if token is None:
        return {"erro": "token ausente"}, 401

    matricula = _ler_matricula()
    if matricula is None:
        return {"erro": "matricula invalida"}, 400

    try:
        aluno = suap.buscar_aluno(matricula, token, current_app.config)
    except suap.SuapTokenRecusado:
        return {"erro": "token recusado pelo SUAP"}, 401
    except suap.SuapIndisponivel:
        return {"erro": "SUAP indisponivel"}, 503
    except NotImplementedError:
        return {"erro": "modo real nao implementado"}, 501

    return {"autorizado": suap.autorizado(aluno)}, 200


@bp.post("/acessos/validar")
def validar_acesso():
    corpo, codigo = _decidir_acesso()
    return jsonify(corpo), codigo
