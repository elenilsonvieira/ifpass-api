from app import create_app


def test_status():
    cliente = create_app().test_client()
    resposta = cliente.get("/v1/status")
    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok"}
