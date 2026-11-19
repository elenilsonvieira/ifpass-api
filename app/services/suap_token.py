
import time
import threading
import logging

import requests
import jwt


logger = logging.getLogger(__name__)


class SuapTokenManager:

    def __init__(self, config):
        self._config = config

        self._access_token = None
        self._refresh_token = None

        self._access_timeout = None

        self._margem_expiracao = 30
        self._lock = threading.Lock()

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

    def _calcular_expiracao(self, access_token):
        payload = jwt.decode(
            access_token,
            options={
                'verify_signature': False,
                'verify_exp': False,
                'verify_aud': False
            }
        )

        expiracao = payload.get('exp')

        if expiracao is None:
            raise ValueError(
                'O access token não possui campo exp.'
            )

        tempo_restante = expiracao - time.time()

        if tempo_restante <= 0:
            raise ValueError(
                'O SUAP retornou um access token expirado.'
            )

        return time.monotonic() + tempo_restante

    def _armazenar_tokens(self, access_token, refresh_token=None):
        expiracao = self._calcular_expiracao(access_token)

        self._access_token = access_token
        self._access_timeout = expiracao

        if refresh_token:
            self._refresh_token = refresh_token

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
