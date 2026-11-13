class SuapIndisponivel(Exception):
    """Mostra um erro possível: Timeout, erro de rede ou 5xx do SUAP"""


class SuapTokenRecusado(Exception):
    """O SUAP respondeu 401/403 ao token"""


_CURSO_GUARABIRA = "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)"

# Dados fictícios usados no modo simulado.
_ALUNOS_SIMULADOS = {
    "202312345601": {"situacao": "Matriculado", "curso_nome": _CURSO_GUARABIRA},
    "202312345602": {"situacao": "Evadido", "curso_nome": _CURSO_GUARABIRA},
    "202312345603": {"situacao": "Formado", "curso_nome": _CURSO_GUARABIRA},
    "202312345604": {
        "situacao": "Matriculado",
        "curso_nome": "TECNOLOGIA EM ALIMENTOS (CAMPUS SOUSA)",
    },
}


def buscar_aluno(matricula: str, token: str, config) -> dict | None:
    """Retorna {matricula, situacao, curso_nome} ou None se não existir"""
    if config["SUAP_MODO"] == "simulado":
        return _buscar_simulado(matricula, token)
    raise NotImplementedError(
        "Consulta real ao SUAP será implementada na tarefa 'Consultar aluno no SUAP'"
    )


def _buscar_simulado(matricula: str, token: str) -> dict | None:
    # Gatilhos de erro, usados nos testes.
    if token == "invalido":
        raise SuapTokenRecusado()
    if matricula == "000000000000":
        raise SuapIndisponivel()

    dados = _ALUNOS_SIMULADOS.get(matricula)
    if dados is None:
        return None
    return {
        "matricula": matricula,
        "situacao": dados["situacao"],
        "curso_nome": dados["curso_nome"],
    }


def autorizado(aluno: dict | None) -> bool:
    if aluno is None:
        return False
    return (
        aluno.get("situacao") == "Matriculado"
        and "CAMPUS GUARABIRA" in str(aluno.get("curso_nome", "")).upper()
    )
