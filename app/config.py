import os

from dotenv import load_dotenv

# Carrega o arquivo .env (se existir) para as variáveis de ambiente.
load_dotenv()


class Config:
    SUAP_BASE_URL = os.getenv("SUAP_BASE_URL", "https://suap.ifpb.edu.br/api")
    SUAP_TIMEOUT_SEGUNDOS = float(os.getenv("SUAP_TIMEOUT_SEGUNDOS", "5"))
    SUAP_MODO = os.getenv("SUAP_MODO", "simulado")  # simulado | real
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
