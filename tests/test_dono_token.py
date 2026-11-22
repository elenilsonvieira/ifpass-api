from app.services import suap


def test_confirmar_dono_token_retorna_aluno_quando_matricula_bate(monkeypatch):
    monkeypatch.setattr(
        suap,
        "buscar_aluno",
        lambda matricula, token, config: {
            "matricula": "202413810024",
            "situacao": "Matriculado",
            "curso_nome": "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)",
        },
    )

    resultado = suap.confirmar_dono_token("202413810024", "token-valido", {})

    assert resultado is not None
    assert resultado["matricula"] == "202413810024"


def test_confirmar_dono_token_retorna_none_quando_matricula_diverge(monkeypatch):
    monkeypatch.setattr(
        suap,
        "buscar_aluno",
        lambda matricula, token, config: {
            "matricula": "202499999999",
            "situacao": "Matriculado",
            "curso_nome": "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)",
        },
    )

    resultado = suap.confirmar_dono_token("202413810024", "token-valido", {})

    assert resultado is None