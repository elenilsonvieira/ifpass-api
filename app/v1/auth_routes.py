"""Rotas de autenticação do aplicativo."""

from flask import Blueprint, current_app, jsonify, request

from app.services import auth, suap

bp = Blueprint("auth", __name__)


@bp.post("/login")
def login():
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        return jsonify({"erro": "corpo_invalido", "mensagem": "Envie um objeto JSON."}), 400

    matricula = corpo.get("matricula")
    senha = corpo.get("senha")

    if not auth.validar_credenciais(matricula, senha):
        return jsonify({
            "erro": "credenciais_invalidas",
            "mensagem": "Informe uma matrícula de 12 dígitos (aluno) ou 7 dígitos (servidor) e uma senha."
        }), 400

    try:
        resultado = auth.realizar_login(matricula, senha, current_app.config)
    except suap.SuapErro as erro:
        # Não devolve detalhes da resposta do SUAP, que podem conter dados
        # enviados pelo usuário. Também não registra matrícula, senha ou token.
        if erro.codigo == "autenticacao_recusada" or erro.status_suap in (400, 401):
            return jsonify({
                "erro": "credenciais_invalidas",
                "mensagem": "Matrícula ou senha inválida."
            }), 401

        if erro.status_suap == 403:
            return jsonify({
                "erro": "acesso_negado",
                "mensagem": "O SUAP não permitiu consultar os dados deste usuário."
            }), 403

        if erro.codigo in ("timeout", "erro_conexao", "suap_indisponivel", "limite_requisicoes") or (
            erro.status_suap is not None and erro.status_suap >= 500
        ):
            return jsonify({
                "erro": "suap_indisponivel",
                "mensagem": "Não foi possível comunicar com o SUAP. Tente novamente mais tarde."
            }), 503

        return jsonify({
            "erro": "falha_suap",
            "mensagem": "Não foi possível concluir a autenticação no SUAP."
        }), 502

    if resultado is None:
        return jsonify({
            "erro": "usuario_nao_encontrado",
            "mensagem": "As credenciais foram autenticadas, mas o usuário não foi encontrado."
        }), 404

    return jsonify(resultado), 200
