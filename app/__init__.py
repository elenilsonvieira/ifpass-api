from flask import Flask, jsonify

from app.config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.v1.routes import bp as v1_bp

    app.register_blueprint(v1_bp, url_prefix="/v1")

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
