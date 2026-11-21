# API de Simulação de Eleição Eletrônica

Backend (FastAPI + PostgreSQL) do Sistema de Simulação de Eleição Eletrônica, trabalho de Engenharia de Software II.

> README inicial. A versão completa (arquitetura, regras de negócio, demonstração) vem na tarefa 13.

## Como rodar

Pré-requisitos: Python 3.12, Git e Docker Desktop aberto.

### Windows (PowerShell)

```powershell
docker compose up -d                                  # sobe banco (5432) e banco de teste (5433)
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env
.venv\Scripts\python.exe -m alembic upgrade head      # aplica as migrações
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Linux / macOS

```bash
docker compose up -d                                  # sobe banco (5432) e banco de teste (5433)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head                                  # aplica as migrações
uvicorn app.main:app --reload
```

A API fica em http://localhost:8000, o Swagger em http://localhost:8000/docs e a verificação de saúde em http://localhost:8000/health.

### Documentação da API

A API é documentada pelo próprio código (OpenAPI 3.1). Com a API no ar, o Swagger UI interativo fica em http://localhost:8000/docs (ReDoc em http://localhost:8000/redoc). A especificação completa, com descrições, regras (RN-xx), exemplos e erros de cada rota, está em [`docs/openapi.json`](docs/openapi.json); dá para importá-la no Postman ou no Insomnia.

- **Autenticação:** `POST /api/v1/auth/login` (formulário com `username` = CPF e `password` = senha) devolve um token JWT. Envie-o em `Authorization: Bearer <token>`; no Swagger, use o botão *Authorize*.
- **Fluxo do voto (Eleitor):** consultar a cédula → registrar o voto (recebe `token_cedula`, válido por 5 minutos) → confirmar com o token. Cada cargo é votado separadamente.
- **Erros:** todas as rotas respondem `{"erro": {"codigo", "mensagem", "detalhes"}}`. 401 = não autenticado, 403 = perfil sem permissão, 404 = não encontrado, 409 = conflito com regra de negócio, 422 = dados inválidos.
- **GitHub Pages:** a publicação fica para depois (repositório privado); o `docs/index.html` já está pronto.
- Depois de mudar rotas ou esquemas, regenere a especificação com `python -m app.scripts.exportar_openapi` (o teste TA-03 falha se ela ficar desatualizada) e atualize as tabelas abaixo (copiadas dela).

#### Rotas

##### Sistema

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/health` | Público | Verifica se a API e o banco estão no ar | 200 | — |

##### Autenticação

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/auth/login` | Público | Entra no sistema com CPF e senha | 200 | 401, 422 |
| `GET` | `/api/v1/auth/me` | Qualquer logado | Consulta o usuário logado | 200 | 401 |

##### Eleições

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/eleicoes` | Chefe | Cria uma eleição | 201 | 401, 403, 409, 422 |
| `GET` | `/api/v1/eleicoes` | Qualquer logado | Lista as eleições | 200 | 401, 422 |
| `GET` | `/api/v1/eleicoes/{eleicao_id}` | Qualquer logado | Consulta uma eleição | 200 | 401, 404, 422 |
| `PATCH` | `/api/v1/eleicoes/{eleicao_id}` | Chefe | Altera uma eleição | 200 | 401, 403, 404, 409, 422 |
| `POST` | `/api/v1/eleicoes/{eleicao_id}/abertura` | Chefe | Abre a votação | 200 | 401, 403, 404, 409, 422 |
| `POST` | `/api/v1/eleicoes/{eleicao_id}/encerramento` | Chefe | Encerra a votação | 200 | 401, 403, 404, 409, 422 |

##### Candidaturas

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/eleicoes/{eleicao_id}/candidaturas` | Chefe | Lista as candidaturas da eleição | 200 | 401, 403, 404, 422 |
| `POST` | `/api/v1/eleicoes/{eleicao_id}/candidaturas` | Chefe | Cria uma candidatura | 201 | 401, 403, 404, 409, 422 |
| `PATCH` | `/api/v1/eleicoes/{eleicao_id}/candidaturas/{candidatura_id}` | Chefe | Altera uma candidatura | 200 | 401, 403, 404, 409, 422 |
| `DELETE` | `/api/v1/eleicoes/{eleicao_id}/candidaturas/{candidatura_id}` | Chefe | Remove uma candidatura | 204 | 401, 403, 404, 409, 422 |
| `GET` | `/api/v1/candidaturas/minhas` | Candidato | Lista as candidaturas do candidato logado | 200 | 401, 403 |

##### Eleitores

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/eleitores` | Chefe | Cadastra um eleitor | 201 | 401, 403, 409, 422 |
| `GET` | `/api/v1/eleitores` | Chefe | Lista os eleitores | 200 | 401, 403, 422 |
| `GET` | `/api/v1/eleitores/eu` | Eleitor | Consulta os próprios dados de eleitor | 200 | 401, 403, 404 |
| `GET` | `/api/v1/eleitores/{eleitor_id}` | Chefe | Consulta um eleitor | 200 | 401, 403, 404, 422 |
| `PATCH` | `/api/v1/eleitores/{eleitor_id}` | Chefe | Altera um eleitor | 200 | 401, 403, 404, 422 |
| `DELETE` | `/api/v1/eleitores/{eleitor_id}` | Chefe | Exclui um eleitor | 204 | 401, 403, 404, 409, 422 |

##### Candidatos

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/candidatos` | Chefe | Cadastra um candidato | 201 | 401, 403, 409, 422 |
| `GET` | `/api/v1/candidatos` | Chefe | Lista os candidatos | 200 | 401, 403, 422 |
| `GET` | `/api/v1/candidatos/eu` | Candidato | Consulta os próprios dados de candidato | 200 | 401, 403, 404 |
| `GET` | `/api/v1/candidatos/{candidato_id}` | Chefe | Consulta um candidato | 200 | 401, 403, 404, 422 |
| `PATCH` | `/api/v1/candidatos/{candidato_id}` | Chefe | Altera um candidato | 200 | 401, 403, 404, 422 |
| `DELETE` | `/api/v1/candidatos/{candidato_id}` | Chefe | Exclui um candidato | 204 | 401, 403, 404, 409, 422 |

##### Partidos

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/partidos` | Qualquer logado | Lista os partidos | 200 | 401 |
| `POST` | `/api/v1/partidos` | Chefe | Cadastra um partido | 201 | 401, 403, 409, 422 |

##### Votação

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/votacao/eleicoes/{eleicao_id}/cedula` | Eleitor | Consulta a cédula | 200 | 401, 403, 404, 409, 422 |
| `POST` | `/api/v1/votacao/eleicoes/{eleicao_id}/votos/registro` | Eleitor | Registra o voto (etapa 1) | 200 | 401, 403, 404, 409, 422 |
| `POST` | `/api/v1/votacao/eleicoes/{eleicao_id}/votos/confirmacao` | Eleitor | Confirma o voto (etapa 2) | 201 | 401, 403, 404, 409, 422 |
| `GET` | `/api/v1/votacao/eleicoes/{eleicao_id}/participacao` | Eleitor | Consulta em quais cargos já votou | 200 | 401, 403, 404, 422 |

##### Apuração

| Método | Caminho | Quem acessa | O que faz | Sucesso | Erros |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/apuracao/eleicoes/{eleicao_id}/parcial` | Qualquer logado | Acompanha a apuração parcial | 200 | 401, 403, 404, 409, 422 |
| `GET` | `/api/v1/apuracao/eleicoes/{eleicao_id}/resultado` | Qualquer logado | Consulta o resultado final | 200 | 401, 404, 409, 422 |

### Testes e qualidade

```bash
pytest                       # todos os testes (os de integração usam o banco de teste, porta 5433)
ruff check .                 # lint
ruff format --check .        # formatação
```

No Windows, use `.venv\Scripts\python.exe -m <comando>` no lugar de `<comando>` (ex.: `.venv\Scripts\python.exe -m pytest`).
