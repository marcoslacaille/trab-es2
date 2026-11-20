# Tarefa 14 — Revisão final antes da entrega

Faça uma auditoria completa do projeto contra o enunciado e o checklist do PLANO, como se você fosse o professor corrigindo. **Primeiro relate, depois corrija**: não altere nada antes de eu aprovar a lista.

**Branch:** `chore/revisao-final`

## Leia antes de começar

- `docs/PLANO.md`: seção 18 (matriz de rastreabilidade e checklist) e seção 8 (todas as RNs).
- O repositório inteiro: `app/`, `tests/`, `migrations/`, `docs/`, `README.md`, histórico do Git (`git log --oneline --graph --decorate`).

## O que fazer

1. Para **cada linha** da matriz de rastreabilidade da seção 18: confirme que as rotas existem, que as RNs estão implementadas (procure o código RN nas docstrings) e que os testes listados existem e passam.
2. Para **cada RN** de RN-01 a RN-79: aponte o arquivo e a função que a implementa e o teste que a verifica. Liste as que estiverem sem teste ou sem citação.
3. Para **cada item** do checklist da seção 18: marque OK ou o que falta.
4. Rode e registre os resultados:
   - `ruff check .` e `ruff format --check .`
   - `pytest --cov=app --cov-report=term-missing` (com a cobertura total e a dos `dominio.py`)
   - `alembic downgrade base` e `alembic upgrade head` num banco limpo
   - o roteiro do `docs/DEMO.md` do zero, com o seed
5. Procure problemas que um professor de Engenharia de Software notaria: código morto, `print` esquecido, `TODO`, segredo no repositório, `.env` versionado, módulo importando o que não devia, nomes em inglês misturados, comentário que contradiz o código, README desatualizado.
6. Escreva tudo em `docs/REVISAO.md`: uma tabela de pendências com gravidade (bloqueia a entrega / deveria corrigir / cosmético) e a correção proposta para cada uma.
7. **Pare e me mostre o `docs/REVISAO.md`.** Depois que eu aprovar, corrija os itens aprovados, um commit por correção.

## Pronto quando

- `docs/REVISAO.md` sem nenhum item "bloqueia a entrega" em aberto.
- Checklist da seção 18 todo OK (exceto os itens que dependem do grupo, como o ensaio da apresentação).

## Commits

1. `docs: adiciona relatório de revisão final`
2. `fix(...)` / `docs(...)` / `test(...)`: um por correção aprovada
3. Último commit marca a tarefa no PROGRESSO.
