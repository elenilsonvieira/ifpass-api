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
| POST   | `/v1/acessos/validar` | Valida o acesso de uma matrícula (`{"autorizado": true/false}`) |

### POST /v1/acessos/validar

Corpo JSON com a matrícula (12 dígitos) e o token do SUAP no cabeçalho
`Authorization: Token <token>`.

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/v1/acessos/validar `
  -Headers @{ Authorization = "Token <token>" } `
  -ContentType "application/json" `
  -Body '{"matricula": "202312345601"}'
```

curl (Linux):

```bash
curl -X POST http://127.0.0.1:5000/v1/acessos/validar \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"matricula": "202312345601"}'
```

| Código | Resposta | Quando |
|--------|----------|--------|
| 200 | `{"autorizado": true/false}` | Consulta concluída |
| 400 | `{"erro": "matricula invalida"}` | Corpo inválido ou matrícula fora do formato |
| 401 | `{"erro": "token ausente"}` / `{"erro": "token recusado pelo SUAP"}` | Sem token ou token recusado (o app deve pedir novo login) |
| 501 | `{"erro": "modo real nao implementado"}` | `SUAP_MODO=real` (ainda não implementado) |
| 503 | `{"erro": "SUAP indisponivel"}` | Falha ao consultar o SUAP (nunca devolve `autorizado: false` nesse caso) |

Com `SUAP_MODO=simulado`, a API usa matrículas fictícias:

| Matrícula | Resultado |
|-----------|-----------|
| `202312345601` | autorizado (Matriculado, Guarabira) |
| `202312345602` | negado (Evadido) |
| `202312345603` | negado (Formado) |
| `202312345604` | negado (curso do campus Sousa) |
| outra qualquer | negado (não encontrada) |
| `000000000000` | 503 (simula SUAP fora do ar) |
| token `invalido` | 401 (simula token recusado) |
