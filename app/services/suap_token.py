
import time
import threading
import logging

import requests
import jwt


logger = logging.getLogger(__name__)


class TokenServicoExpirado(Exception):
    """Token de serviço ausente, inválido ou expirado."""


class SuapTokenManager:

    def __init__(self, config):
        self._config = config

        self._access_token = None
        self._refresh_token = None

        self._access_timeout = None

        self._margem_expiracao = 30
        self._lock = threading.Lock()

        token_env = (config.get("SUAP_TOKEN") or "").strip()
        if token_env:
            try:
                self._armazenar_tokens(token_env)
            except Exception:
                self._access_token = token_env
                self._access_timeout = 0

    def buscar_token(self, matricula, senha):

        response = requests.post(
            f'{self._config["SUAP_BASE_URL"]}/jwt/obtain_token/',
            data={
                'username': matricula,
                'password': senha
            },
            timeout=self._config['SUAP_TIMEOUT_SEGUNDOS']
        )

        response.raise_for_status()

        data = response.json()

        access_token = data.get('access')
        refresh_token = data.get('refresh')

        if not access_token:
            raise ValueError(
                'A resposta do SUAP não contém access token.'
            )

        return access_token, refresh_token

    def verificar_token(self):
        if not self._access_token:
            return False

        if not self._access_timeout:
            return False

        return (
            time.monotonic()
            < self._access_timeout - self._margem_expiracao
        )

    def _calcular_expiracao(self, token):
        try:
            payload = jwt.decode(
                token,
                options={
                    'verify_signature': False,
                    'verify_exp': False,
                    'verify_aud': False
                }
            )
        except jwt.PyJWTError as erro:
            raise TokenServicoExpirado('O token JWT informado é inválido.') from erro

        expiracao = payload.get('exp')

        if expiracao is None:
            raise TokenServicoExpirado('O token não possui campo exp.')

        tempo_restante = expiracao - time.time()

        if tempo_restante <= 0:
            raise TokenServicoExpirado('O token de serviço do SUAP está expirado.')

        return time.monotonic() + tempo_restante

    def medir_validade(self, token):
        """Retorna os segundos restantes de validade (campo exp) de um token JWT."""
        exp_monotonic = self._calcular_expiracao(token)
        return max(0.0, exp_monotonic - time.monotonic())

    def _armazenar_tokens(self, access_token, refresh_token=None):
        expiracao = self._calcular_expiracao(access_token)

        self._access_token = access_token
        self._access_timeout = expiracao

        if refresh_token:
            self._calcular_expiracao(refresh_token)
            self._refresh_token = refresh_token

    def obter_token_servico(self):
        """Retorna o token de serviço válido ou lança TokenServicoExpirado (HTTP 503)."""
        token_config = (self._config.get("SUAP_TOKEN") or "").strip()

        if not token_config:
            raise TokenServicoExpirado(
                "O token de serviço do SUAP (SUAP_TOKEN) não está configurado."
            )

        with self._lock:
            if self._access_token != token_config:
                self._armazenar_tokens(token_config)

            if not self.verificar_token():
                raise TokenServicoExpirado(
                    "O token de serviço do SUAP está expirado."
                )

            return self._access_token

    def renovar_token(self):
        if not self._refresh_token:
            raise ValueError( 'Não existe refresh token disponível.' )

        url = (
            self._config.get( 'SUAP_REFRESH_URL', f'{self._config["SUAP_BASE_URL"]}/jwt/refresh_token/' )
        )

        response = requests.post(
            url,
            json={
                'refresh': self._refresh_token
            },
            timeout=self._config['SUAP_TIMEOUT_SEGUNDOS']
        )

        response.raise_for_status()

        data = response.json()

        access_token = data.get('access')

        if not access_token:
            raise ValueError(
                'A resposta de renovação não contém access token.'
            )

        refresh_token = data.get(
            'refresh',
            self._refresh_token
        )

        self._armazenar_tokens(
            access_token,
            refresh_token
        )

        return self._access_token

    def obter_token(self, matricula=None, senha=None):
        if self.verificar_token():
            return self._access_token

        with self._lock:
            if self.verificar_token():
                return self._access_token

            if self._refresh_token:

                try:
                    return self.renovar_token()

                except requests.exceptions.HTTPError as error:

                    status_code = (
                        error.response.status_code
                        if error.response is not None
                        else None
                    )

                    if status_code != 401:
                        raise

                    self.invalidar_token()

                except requests.exceptions.RequestException:
                    raise

            if matricula is None or senha is None:
                raise ValueError(
                    'Matrícula e senha são necessárias '
                    'para realizar uma nova autenticação.'
                )

            access_token, refresh_token = self.buscar_token(
                matricula,
                senha
            )

            self._armazenar_tokens(
                access_token,
                refresh_token
            )

            return self._access_token

    # DESCARTAR TOKEN
    def invalidar_token(self):

        self._access_token = None
        self._refresh_token = None
        self._access_timeout = None
