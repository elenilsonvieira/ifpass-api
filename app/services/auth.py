"""
Casos de uso de autenticação de alunos e servidores no SUAP.

Nenhuma informação recebida ou retornada é persistida neste serviço.
"""

from app.services import suap


TAMANHOS_MATRICULA = {7, 12}


def validar_credenciais(matricula, senha):
    """Valida o formato dos dados sem registrar ou armazenar as credenciais."""
    if (
        not isinstance(matricula, str)
        or len(matricula) not in TAMANHOS_MATRICULA
        or not matricula.isascii()
        or not matricula.isdigit()
    ):
        return False

    return isinstance(senha, str) and bool(senha.strip())


def realizar_login(matricula, senha, config):
    """Autentica no SUAP e retorna somente os dados públicos necessários."""
    tokens = suap.autenticar(matricula, senha, config)
    access_token = tokens["access"]

    if len(matricula) == 12:
        dados = suap.buscar_aluno(matricula, access_token, config)
        tipo = "aluno"
    else:
        dados = suap.buscar_servidor(matricula, access_token, config)
        tipo = "servidor"

    if dados is None:
        return None

    # Lista explícita de campos: evita expor dados adicionais do SUAP.
    return {
        "token": access_token,
        "usuario": {
            "matricula": str(dados.get("matricula", matricula)).strip(),
            "nome": str(dados.get("nome") or "").strip(),
            "tipo": tipo,
        },
    }
