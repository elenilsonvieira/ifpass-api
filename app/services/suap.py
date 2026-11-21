
import requests


class SuapIndisponivel(Exception):
    """Timeout, erro de rede ou 5xx do SUAP"""


class SuapTokenRecusado(Exception):
    """O SUAP recusou as credenciais ou o token"""


class SuapRespostaInvalida(Exception):
    """O SUAP retornou dados inesperados"""


class SuapErro(Exception):
    """Armazena os detalhes de um erro do SUAP."""

    def __init__(self, codigo, mensagem, detalhes=None, status_suap=None):
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes
        self.status_suap = status_suap
        super().__init__(mensagem)

    def para_json(self):
        return {
            "erro": self.codigo,
            "mensagem": self.mensagem,
            "origem": "SUAP",
            "status_suap": self.status_suap,
            "detalhes": self.detalhes
        }


_CURSO_GUARABIRA = "TECNOLOGIA EM SISTEMAS PARA INTERNET (CAMPUS GUARABIRA)"


def verificar_resposta(req):
    """Verifica a resposta HTTP e identifica erros do SUAP."""

    status = req.status_code

    try:
        dados = req.json()
    except ValueError:
        dados = None

    if 200 <= status < 300:
        if dados is None:
            raise SuapErro(
                "resposta_invalida",
                "O SUAP retornou uma resposta que não é um JSON válido.",
                status_suap=status
            )

        return dados

    detalhes = None

    if isinstance(dados, dict):
        campos_permitidos = ("detail", "non_field_errors", "message")

        detalhes = {
            chave: valor
            for chave, valor in dados.items()
            if chave in campos_permitidos
            and isinstance(valor, str)
            and len(valor) <= 300
        }

        if not detalhes:
            detalhes = None

    if status in (400, 401, 403):
        raise SuapErro(
            "autenticacao_recusada" if status in (400, 401) else "acesso_negado",
            (
                "O SUAP recusou as credenciais ou o token."
                if status in (400, 401)
                else "O SUAP não permitiu a operação solicitada."
            ),
            detalhes,
            status
        )

    if status == 404:
        raise SuapErro(
            "recurso_nao_encontrado",
            "O endpoint solicitado não foi encontrado no SUAP.",
            detalhes,
            status
        )

    if status == 429:
        raise SuapErro(
            "limite_requisicoes",
            "O SUAP recebeu muitas requisições. Tente novamente mais tarde.",
            detalhes,
            status
        )

    if status >= 500:
        raise SuapErro(
            "suap_indisponivel",
            "O SUAP apresentou um erro interno ou está indisponível.",
            detalhes,
            status
        )

    raise SuapErro(
        "erro_suap",
        "O SUAP retornou um erro inesperado.",
        detalhes,
        status
    )


def autenticar(matricula: str, senha: str, config) -> dict:
    """Autentica no SUAP e retorna access e refresh."""

    try:
        req = requests.post(
            f'{config["SUAP_BASE_URL"].rstrip("/")}/jwt/obtain_token/',
            json={
                "username": matricula,
                "password": senha
            },
            timeout=config["SUAP_TIMEOUT_SEGUNDOS"]
        )

        res = verificar_resposta(req)

        if not isinstance(res, dict):
            raise SuapErro(
                "resposta_invalida",
                "O SUAP retornou um formato de autenticação inválido.",
                status_suap=req.status_code
            )

        access = res.get("access")
        refresh = res.get("refresh")

        if (
            not isinstance(access, str)
            or not access
            or not isinstance(refresh, str)
            or not refresh
        ):
            raise SuapErro(
                "tokens_ausentes",
                "O SUAP não retornou access e refresh válidos.",
                status_suap=req.status_code
            )

        return {
            "access": access,
            "refresh": refresh
        }

    except requests.exceptions.Timeout:
        raise SuapErro(
            "timeout",
            "O SUAP demorou demais para responder."
        )

    except requests.exceptions.ConnectionError:
        raise SuapErro(
            "erro_conexao",
            "Não foi possível estabelecer conexão com o SUAP."
        )

    except requests.exceptions.RequestException:
        raise SuapErro(
            "erro_conexao",
            "Ocorreu uma falha na comunicação com o SUAP."
        )


def buscar_aluno(matricula: str, token: str, config) -> dict | None:
    """Consulta o aluno no SUAP pela matrícula."""

    try:
        req = requests.get(
            f'{config["SUAP_BASE_URL"].rstrip("/")}/ensino/alunos/v1/',
            params={"search": matricula},
            headers={"Authorization": f"Bearer {token}"},
            timeout=config["SUAP_TIMEOUT_SEGUNDOS"]
        )

        res = verificar_resposta(req)

        if isinstance(res, list):
            dados = res

        elif isinstance(res, dict):
            dados = res.get("results")

        else:
            raise SuapErro(
                "resposta_invalida",
                "O SUAP retornou um formato de consulta inválido.",
                status_suap=req.status_code
            )

        if not isinstance(dados, list):
            raise SuapErro(
                "resposta_invalida",
                "A lista de alunos retornada pelo SUAP é inválida.",
                status_suap=req.status_code
            )

        for dado in dados:
            if not isinstance(dado, dict):
                raise SuapErro(
                    "resposta_invalida",
                    "O SUAP retornou dados de aluno inválidos.",
                    status_suap=req.status_code
                )

            # 1. Comparação exata da matrícula
            if str(dado.get("matricula", "")).strip() != matricula:
                continue

            # 2. Obter situação do aluno
            situacao = dado.get("situacao", "")

            # 3. Obter curso do aluno
            curso = dado.get("curso") or {}

            if isinstance(curso, dict):
                nome_curso = curso.get("nome", "")
            elif isinstance(curso, str):
                nome_curso = curso
            else:
                nome_curso = ""

            return {
                "matricula": dado.get("matricula"),
                "situacao": situacao,
                "curso_nome": nome_curso
            }

        return None

    except requests.exceptions.Timeout:
        raise SuapErro(
            "timeout",
            "O SUAP demorou demais para responder."
        )

    except requests.exceptions.ConnectionError:
        raise SuapErro(
            "erro_conexao",
            "Não foi possível estabelecer conexão com o SUAP."
        )

    except requests.exceptions.RequestException:
        raise SuapErro(
            "erro_conexao",
            "Ocorreu uma falha na comunicação com o SUAP."
        )


def autorizado(aluno: dict | None) -> bool:
    """Verifica se o aluno está matriculado no Campus Guarabira."""

    if aluno is None:
        return False

    return (
        str(aluno.get("situacao", "")).strip().casefold() == "matriculado"
        and "CAMPUS GUARABIRA"
        in str(aluno.get("curso_nome", "")).upper()
    )
