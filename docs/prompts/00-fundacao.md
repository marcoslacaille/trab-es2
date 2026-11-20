# Tarefa 00 — Fundação do repositório

Você vai criar a base do projeto descrito em `docs/PLANO.md`, seguindo as regras do `CLAUDE.md`. Esta é a primeira tarefa: a pasta só tem `CLAUDE.md` e `docs/`.

## Leia antes de começar

- `docs/PLANO.md`: seções 0, 3, 4 (inteira), 5 (estrutura de pastas e `main.py`), 6 (só "Convenção de nomes das restrições"), 12 (só "Infraestrutura de teste") e 13 (Fase 0 e o arquivo do CI).

## Passo especial desta tarefa: Git

1. Se a pasta ainda não for um repositório: `git init -b main`.
2. Primeiro commit na `main`, só com o que já existe: `docs: adiciona plano do projeto e prompts das tarefas`.
3. Depois crie a branch `chore/fundacao` e siga o fluxo normal do `CLAUDE.md`.

## O que fazer

1. **Ambiente Python:** `py -3.12 -m venv .venv`. Crie `requirements.txt` e `requirements-dev.txt` (seção 4), instale com `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` e **fixe as versões exatas instaladas** (`pacote==x.y.z`) nos dois arquivos.
2. **Arquivos de projeto:** `pyproject.toml`, `.gitignore`, `.env.example` e `docker-compose.yml` exatamente como na seção 4. Copie `.env.example` para `.env` (o `.env` não vai para o Git).
3. **Banco:** `docker compose up -d` e confirme que os dois containers (`eleicao-banco` e `eleicao-banco-teste`) estão saudáveis.
4. **Pacote `app`:**
   - `app/__init__.py`, `app/compartilhado/__init__.py`.
   - `app/compartilhado/config.py`: a classe `Configuracao` da seção 4 (com os campos `chefe_*`) e `obter_configuracao()`.
   - `app/compartilhado/banco.py`: `Base` com a convenção de nomes da seção 6; `engine = create_engine(database_url, pool_pre_ping=True)`; `SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)`; dependência `obter_sessao()` que abre a sessão, entrega com `yield` e fecha no `finally` (fechar sem commit desfaz tudo).
   - `app/registro_modelos.py`: por enquanto só um docstring explicando que importará os modelos de todos os módulos (usado pelo Alembic).
   - `app/main.py`: o app FastAPI da seção 5 **só com** a rota `GET /health` (sem prefixo, tag "Sistema"), que executa `SELECT 1` usando `obter_sessao` e devolve `{"status": "ok"}`. Ainda não inclua routers de módulos (não existem).
5. **Alembic:** `alembic init migrations`. No `migrations/env.py`: a URL vem de `obter_configuracao().database_url` (não do `alembic.ini`); `import app.registro_modelos`; `target_metadata = Base.metadata`. Configure o `alembic.ini` para nomear arquivos de migração com prefixo numérico legível (ex.: `0001_...`), conforme a tabela de migrações da seção 6.
6. **Testes (infraestrutura da seção 12):**
   - `tests/conftest.py` igual ao da seção 12 (define `DATABASE_URL`, `BCRYPT_CUSTO` e `JWT_SEGREDO` de teste antes de importar o app).
   - `tests/integracao/conftest.py` com as fixtures `banco_migrado`, `banco_limpo`, `relogio` (`RelogioDeTeste`) e `cliente`. **Diferença em relação ao PLANO:** a fixture `banco_limpo` deve descobrir as tabelas dinamicamente (todas do schema `public`, exceto `alembic_version`) e dar `TRUNCATE ... RESTART IDENTITY CASCADE` só se houver alguma. Assim ela funciona desde já, quando ainda não existem tabelas. Registre essa decisão em `docs/prompts/PROGRESSO.md`.
   - Pastas `tests/unitarios/` e `tests/arquitetura/` (com `__init__.py` se necessário para o pytest).
   - `tests/integracao/test_health.py`: `GET /health` responde 200 com `{"status": "ok"}`.
7. **CI:** `.github/workflows/ci.yml` exatamente como na seção 13.
8. **README.md** inicial: nome do projeto, uma frase sobre ele e a seção "Como rodar" com os comandos da seção 4 (Windows e Linux/macOS). O README completo vem na tarefa 13.

## Não faça nesta tarefa

- Nenhum módulo de domínio (identidade, eleitores etc.), nenhuma tabela, nenhuma migração.
- Erros padronizados, relógio, validadores (tarefa 01).

## Pronto quando

- `docker compose up -d` sobe os dois bancos.
- `.venv\Scripts\python.exe -m uvicorn app.main:app` sobe e `GET http://localhost:8000/health` responde 200.
- `.venv\Scripts\python.exe -m alembic upgrade head` roda sem erro.
- `ruff check`, `ruff format --check` e `pytest` passam (1 teste).
- `git status` limpo e o `.env` **não** aparece no histórico.

## Commits (na branch `chore/fundacao`)

1. `chore: cria estrutura inicial e dependências do projeto`
2. `chore: adiciona docker compose com banco e banco de teste`
3. `chore: adiciona configuração e sessão do banco`
4. `chore: configura alembic`
5. `test: adiciona infraestrutura de testes e teste do health`
6. `ci: adiciona pipeline de lint e testes`
7. `docs: adiciona instruções iniciais de execução` (inclui marcar a tarefa 00 no PROGRESSO)

## Ao terminar

Faça o resumo do `CLAUDE.md` e me lembre de: criar o repositório público no GitHub, adicionar o `origin` e fazer o primeiro push.
