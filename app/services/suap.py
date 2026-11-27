
import requests
from app.services.suap_token import SuapTokenManager, TokenServicoExpirado

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


# Nome do parâmetro de busca da consulta de servidores no SUAP.
_PARAM_BUSCA_SERVIDOR = "search"


# Nomes de situação (em maiúsculas) que liberam o servidor. Fácil de ampliar.
_NOMES_SERVIDOR_ATIVO = {"ATIVO PERMANENTE", "CONT.PROF.SUBSTITUTO"}

_gerenciadores_token = {}


def obter_token_servico(config) -> str:
    """Obtém o token de serviço configurado e valida sua expiração."""
    chave = id(config)
    gerenciador = _gerenciadores_token.get(chave)

    if gerenciador is None:
        gerenciador = SuapTokenManager(config)
        _gerenciadores_token[chave] = gerenciador

    try:
        return gerenciador.obter_token_servico()
    except TokenServicoExpirado as erro:
        raise SuapErro(
            "token_servico_expirado",
            str(erro),
            status_suap=503
        ) from erro

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

        if not isinstance(access, str) or not access:
            raise SuapErro(
                "tokens_ausentes",
                "O SUAP não retornou um access token válido.",
                status_suap=req.status_code
            )

        if not isinstance(refresh, str) or not refresh:
            refresh = None

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

def confirmar_dono_token(matricula: str, token: str, config) -> dict | None:
    """Confirma que a matrícula consultada com o token bate com a informada.

    Nota: a API do SUAP IFPB não expõe endpoint de perfil (/meus-dados/)
    e o JWT retornado por /jwt/obtain_token/ contém apenas user_id (sem matrícula).
    A titularidade é garantida pela autenticação prévia (matrícula + senha)
    combinada com a verificação exata da matrícula retornada na consulta.
    """
    aluno = buscar_aluno(matricula, token, config)

    if aluno is None:
        return None

    if str(aluno.get("matricula", "")).strip() != matricula:
        return None

    return aluno






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
                "nome": _texto(dado.get("nome")),
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


def _texto(valor) -> str:
    """Converte para texto sem espaços nas pontas; None vira ''."""
    if valor is None:
        return ""

    return str(valor).strip()


def buscar_servidor(matricula: str, token: str, config) -> dict | None:
    """Consulta o servidor no SUAP pela matrícula.

    Só devolve os dados do servidor; a regra de vínculo ativo (ou de campus)
    fica a cargo de quem chamar esta função.
    """

    try:
        req = requests.get(
            f'{config["SUAP_BASE_URL"].rstrip("/")}/recursos-humanos/servidores/v1/',
            params={_PARAM_BUSCA_SERVIDOR: matricula},
            headers={"Authorization": f"Bearer {token}"},
            timeout=config["SUAP_TIMEOUT_SEGUNDOS"]
        )

        res = verificar_resposta(req)

        # O SUAP devolve um objeto paginado; a lista direta é só reserva.
        # Não seguimos "next": a busca por matrícula exata traz um servidor.
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
                "A lista de servidores retornada pelo SUAP é inválida.",
                status_suap=req.status_code
            )

        # Valida todos os itens antes de procurar, para o resultado não
        # depender da posição do servidor na lista.
        if any(not isinstance(dado, dict) for dado in dados):
            raise SuapErro(
                "resposta_invalida",
                "O SUAP retornou dados de servidor inválidos.",
                status_suap=req.status_code
            )

        for dado in dados:
            # 1. Comparação exata da matrícula
            if _texto(dado.get("matricula")) != _texto(matricula):
                continue

            # 2. Situação: objeto com "codigo" e "nome" (ex.: "01" não vira número)
            situacao = dado.get("situacao")

            if not isinstance(situacao, dict):
                situacao = {}

            return {
                "matricula": _texto(dado.get("matricula")),
                "nome": _texto(dado.get("nome")),
                "situacao_codigo": _texto(situacao.get("codigo")),
                "situacao_nome": _texto(situacao.get("nome"))
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
    """Verifica se o aluno está com situação "Matriculado" (qualquer campus)."""

    if aluno is None:
        return False

    return _texto(aluno.get("situacao")).casefold() == "matriculado"




def servidor_autorizado(servidor: dict | None) -> bool:
    """Verifica se o nome da situação do servidor está em _NOMES_SERVIDOR_ATIVO."""

    if servidor is None:
        return False

    return _texto(servidor.get("situacao_nome")).upper() in _NOMES_SERVIDOR_ATIVO
