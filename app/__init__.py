from flask import Flask, jsonify

from app.config import Config
from app.db import init_db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializa o banco de dados, criando as tabelas se necessário
    init_db()

    from app.v1.routes import bp as v1_bp
    from app.v1.auth_routes import bp as auth_bp

    app.register_blueprint(v1_bp, url_prefix="/v1")
    app.register_blueprint(auth_bp, url_prefix="/v1/auth")

    # A API responde JSON
    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return jsonify({"erro": "rota nao encontrada"}), 404

    @app.errorhandler(405)
    def metodo_nao_permitido(_erro):
        return jsonify({"erro": "metodo nao permitido"}), 405

    @app.errorhandler(500)
    def erro_interno(_erro):
        return jsonify({"erro": "erro interno"}), 500

    return app
