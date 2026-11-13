from flask import Blueprint, jsonify

bp = Blueprint("v1", __name__)


@bp.get("/status")
def status():
    return jsonify({"status": "ok"}), 200
