# ifpass-api

API do projeto **Catraca IFPB** (IFPB Guarabira), feita em Python com Flask.
Recebe a matrícula, a senha e a catraca de origem vindas do app mobile,
autentica no SUAP e responde `{"autorizado": true/false}`.

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

Corpo JSON com `matricula` (12 dígitos), `senha` (do SUAP) e `catraca_id`
(precisa estar em `CATRACAS_CADASTRADAS`). A API autentica no SUAP e confirma
se o aluno está matriculado no campus Guarabira.

```bash
curl -X POST http://127.0.0.1:5000/v1/acessos/validar \
  -H "Content-Type: application/json" \
  -d '{"matricula": "<matricula>", "senha": "<senha>", "catraca_id": "CATRACA-01"}'
```

| Código | Resposta | Quando |
|--------|----------|--------|
| 200 | `{"autorizado": true/false}` | Consulta concluída |
| 400 | `matricula_invalida`, `senha_ausente` ou `catraca_ausente` | Corpo inválido (verificado nesta ordem) |
| 401 | `autenticacao_recusada` | O SUAP recusou a matrícula/senha |
| 403 | `catraca_nao_cadastrada` / `acesso_negado` | Catraca fora da lista, ou o SUAP negou a operação |
| 502 | `resposta_invalida`, `recurso_nao_encontrado` etc. | Resposta inesperada do SUAP |
| 503 | `timeout`, `erro_conexao`, `suap_indisponivel`, `limite_requisicoes` | SUAP fora do ar ou lento (nunca devolve `autorizado: false` nesse caso) |

Os erros têm o formato `{"erro": "<codigo>", "mensagem": "..."}`.

## Histórico de acessos

Cada chamada a `/v1/acessos/validar` é registrada em `ifpass.db` (SQLite,
criado automaticamente e não versionado), na tabela `historico_acessos`, com
`matricula`, `catraca_id`, `data_hora`, `resultado` (`Permitido`, `Negado` ou
`Erro`) e `detalhes_erro`. A senha e o token não são gravados.

Para consultar sem alterar nada:

```bash
python -c "import sqlite3; [print(l) for l in sqlite3.connect('ifpass.db').execute('SELECT * FROM historico_acessos')]"
```

## Publicação (demonstração)

A API está preparada para o [Render](https://render.com) (plano gratuito) pelo
arquivo `render.yaml`. A API recebe a **senha do aluno**: use sempre HTTPS (o
Render já fornece).

### Passo a passo (manual)

1. Crie uma conta no Render (pode entrar com o GitHub).
2. Clique em **New → Blueprint** e informe o repositório
   `https://github.com/elenilsonvieira/ifpass-api` (é público; se preferir,
   conecte sua conta do GitHub) e a branch `main`.
3. Confirme os dados lidos do `render.yaml` e clique em **Apply**.
4. Aguarde o primeiro deploy. Quando aparecer **Live**, copie a URL do serviço
   (algo como `https://ifpass-api.onrender.com`).

Sem Blueprint, vale **New → Web Service** com: build `pip install -r requirements.txt`,
start `gunicorn "app:create_app()" --bind 0.0.0.0:$PORT --workers 1 --timeout 30`
e *Health Check Path* `/v1/status`.

### Variáveis de ambiente

Já vêm do `render.yaml`; para alterar, abra o serviço → aba **Environment**.

| Variável | Valor sugerido | Para que serve |
|----------|----------------|----------------|
| `FLASK_DEBUG` | `0` | Desliga o modo debug em produção |
| `SUAP_BASE_URL` | `https://suap.ifpb.edu.br/api` | Endereço da API do SUAP |
| `SUAP_TIMEOUT_SEGUNDOS` | `10` | Tempo máximo de espera pelo SUAP |
| `CATRACAS_CADASTRADAS` | `CATRACA-01` | Catracas aceitas (separe por vírgula) |

### Testando a API publicada

Troque `<URL>` pela URL do serviço:

```bash
curl <URL>/v1/status

curl -X POST <URL>/v1/acessos/validar \
  -H "Content-Type: application/json" \
  -d '{"matricula": "<matricula>", "senha": "<senha>", "catraca_id": "CATRACA-01"}'
```

Não cole credenciais reais em comandos que ficam no histórico do terminal nem
na tela durante a gravação do vídeo.

O app mobile deve apontar para a URL publicada e enviar `matricula`, `senha` e
`catraca_id` no corpo de `POST /v1/acessos/validar`.

### Limitações do plano gratuito

- O serviço **dorme após 15 minutos sem tráfego**; a primeira chamada depois
  disso pode levar cerca de 1 minuto. Antes da demonstração, acorde-o com
  `GET <URL>/v1/status`.
- O `ifpass.db` é **efêmero**: o histórico de acessos se perde a cada reinício
  ou novo deploy.
- A API só deve ser usada por HTTPS, pois recebe a senha do aluno.
