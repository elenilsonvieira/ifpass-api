# ifpass-api

API do projeto **Catraca IFPB** (IFPB Guarabira), feita em Python com Flask.
Recebe uma matrícula e um token do SUAP vindos do app mobile, consulta o SUAP
e responde `{"autorizado": true/false}`.

## Como rodar (Windows)

Requer Python 3.10+.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

## Como rodar (Linux)

Requer Python 3.10+ (em Debian/Ubuntu, instale também o `python3-venv`).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

O servidor sobe em http://127.0.0.1:5000. Edite o `.env` para ajustar a
configuração (nunca coloque matrícula, senha ou token em arquivos versionados).

## Testes

Com o ambiente virtual ativado (Windows ou Linux):

```bash
pytest
```

## Rotas

| Método | Rota         | Descrição                          |
|--------|--------------|------------------------------------|
| GET    | `/v1/status` | Verifica se a API está no ar (`{"status": "ok"}`) |
