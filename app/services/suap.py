import requests

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
    req = requests.get(
        f'{config["SUAP_BASE_URL"]}/ensino/alunos/v1/',
        params = {"search": matricula},
        headers = {"Authorization": f"Bearer {token}"},
        timeout=10
    )

    req.raise_for_status()

    res = req.json()

    dados = res.get("results", [])

    for dado in dados:

        # 1. Comparação exata da matrícula
        if str(dado.get("matricula", "")).strip() != str(matricula).strip():
            continue

        # 2. Verificação da situação
        situacao = dado.get("situacao", "")

        if situacao.strip().casefold() != "matriculado":
            continue

        # 3. Verificação do campus
        curso = dado.get("curso") or {}
        nome_curso = curso.get("nome", "")

        if "CAMPUS GUARABIRA" not in nome_curso.upper():
            continue

        return {
            "matricula": dado.get("matricula"),
            "situacao": situacao,
            "curso_nome": nome_curso
        }

    return None


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
