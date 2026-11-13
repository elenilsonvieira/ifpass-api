from flask import Flask

from app.config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.v1.routes import bp as v1_bp

    app.register_blueprint(v1_bp, url_prefix="/v1")
    return app
