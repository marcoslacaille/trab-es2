# Instruções permanentes para o agente

Projeto: backend do **Sistema de Simulação de Eleição Eletrônica** (trabalho de Engenharia de Software II).
Stack: Python 3.12, FastAPI, SQLAlchemy 2 (síncrono), Alembic, PostgreSQL 16 (Docker), pytest, ruff.

- **Especificação única:** `docs/PLANO.md`. Não invente nada que não esteja nele.
- **Tarefas:** `docs/prompts/NN-*.md`. Cada sessão executa **uma** tarefa, e só ela.
- **Progresso:** `docs/prompts/PROGRESSO.md`.

## Regras de trabalho

1. Leia as seções do `docs/PLANO.md` que a tarefa indicar, **sempre** junto com as seções 0, 3 e 5. Leia também o código que já existe nos módulos que a tarefa toca.
2. Se algo estiver ambíguo, contraditório ou faltando no PLANO, **pare e pergunte** antes de decidir.
3. Antes de escrever código, mostre a lista de arquivos que vai criar ou alterar e **espere o meu OK**.
4. Faça apenas o que a tarefa pede. Nada da próxima tarefa, nada dos "extras opcionais".
5. Nunca enfraqueça uma regra de negócio nem um teste para fazê-lo passar. Se um teste parecer errado, explique e pergunte.
6. Código, nomes, docstrings, mensagens de erro e commits em **português** (glossário da seção 2). Exceções: nomes de bibliotecas e palavras reservadas.
7. Simplicidade: um aluno precisa explicar qualquer função em 1 minuto. Sem metaprogramação, herança profunda ou padrões desnecessários (Factory, Strategy, Interface + Implementação).
8. Toda regra de negócio tem um código RN-xx (seção 8): cite-o na docstring da função que a implementa e no teste que a verifica (junto com o ID do teste, ex.: `"""TI-45 / RN-51: ..."""`).
9. Fronteiras entre módulos (seção 5): um módulo só importa `app.<outro>.servico` (e `app.identidade.dependencias` nas rotas); nunca acessa tabelas, modelos ou repositórios de outro módulo. Serviços devolvem `dataclass`es, nunca objetos ORM.
10. Nunca coloque segredos no código nem versione o `.env`.
11. **Registro de decisões:** tudo o que você fizer e não estiver prescrito no PLANO nem na tarefa (lacuna que você preencheu, desvio do PLANO, extra, conflito entre trechos do PLANO, risco percebido, mudança de ambiente ou de processo) vira uma linha nova no fim da tabela de `docs/DECISOES.md`, com o próximo ID, o tipo, o impacto e o status `ABERTA`. Faça isso no commit da mudança ou no último da tarefa. Nunca apague nem reescreva linhas antigas.

## Fluxo de cada tarefa

1. Confirme que está na `main` atualizada e sem alterações pendentes (`git status`). Crie a branch indicada na tarefa: `git switch -c <branch>`.
2. Leia o que a tarefa manda ler. Mostre a lista de arquivos e espere o OK.
3. Implemente em passos pequenos, rodando os testes a cada passo.
4. Verificação final (todas devem passar):
   - `.venv\Scripts\python.exe -m ruff check .`
   - `.venv\Scripts\python.exe -m ruff format --check .`
   - `.venv\Scripts\python.exe -m pytest`
5. Faça os commits indicados na tarefa (Conventional Commits em português, um assunto por commit). Não faça merge na `main` e não faça push: isso é com o grupo.
6. Marque a tarefa em `docs/prompts/PROGRESSO.md` (no último commit).
7. Termine com um resumo curto: arquivos criados, RNs implementadas, IDs dos testes adicionados, como rodar, e qualquer pendência ou decisão que precise de revisão humana (os IDs novos de `docs/DECISOES.md`).

## Ambiente (Windows)

- Use sempre o Python da venv: `.venv\Scripts\python.exe -m <comando>` (evita problemas de ativação no PowerShell).
- Banco: `docker compose up -d` (precisa do Docker Desktop aberto). Banco da aplicação na porta 5432; banco de teste na 5433.
- Migrações: `.venv\Scripts\python.exe -m alembic upgrade head`.
- API: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` (Swagger em http://localhost:8000/docs).
- Se o Docker não estiver rodando ou uma porta estiver ocupada, pare e me avise; não tente contornar.
