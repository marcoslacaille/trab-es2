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

- Local (com a API no ar): http://localhost:8000/docs (Swagger UI) e http://localhost:8000/redoc.
- Público (GitHub Pages, somente leitura): _preencher com o link depois de ativar o Pages_ (`https://<usuario>.github.io/<repositorio>/`).
- A especificação publicada fica em `docs/openapi.json`. Depois de mudar rotas ou esquemas, regenere com `python -m app.scripts.exportar_openapi`; o teste TA-03 falha se ela ficar desatualizada.

### Testes e qualidade

```bash
pytest                       # todos os testes (os de integração usam o banco de teste, porta 5433)
ruff check .                 # lint
ruff format --check .        # formatação
```

No Windows, use `.venv\Scripts\python.exe -m <comando>` no lugar de `<comando>` (ex.: `.venv\Scripts\python.exe -m pytest`).
