# Tarefa 11 — Qualidade transversal

Todas as funcionalidades existem. Agora verifique o sistema como um todo: permissões de todas as rotas, fronteiras entre módulos, o fluxo completo da demonstração, logs sem dados sensíveis e uma rodada de refatoração (a "programação estratégica" da aula 02).

**Branch:** `test/qualidade`

## Leia antes de começar

- `docs/PLANO.md`: seções 3 (inteira), 5 ("Regras de fronteira" e o grafo de módulos), 7 ("Proteções aplicadas"), 10 (tabela de rotas, com os perfis), 12 (TI-08, TI-74, TA-01, TA-02, TA-04 e "Convenções"), 13 (Fase 8) e 16 (roteiro, usado pelo TI-74).
- O código inteiro de `app/` e `tests/`.

## O que fazer

1. **TI-08** (`tests/integracao/test_permissoes.py`): uma tabela no próprio teste com todas as rotas protegidas da seção 10 (método, caminho com ids de exemplo, perfis permitidos). Parametrize: sem token → 401; cada perfil **não** permitido → 403 `PERFIL_NAO_AUTORIZADO`.
2. **TA-01** (`tests/arquitetura/test_dependencias.py`): com `ast`, leia cada `.py` de `app/<modulo>/` e verifique as regras de fronteira da seção 5 (arestas permitidas = exatamente o grafo; só `app.<outro>.servico`, `app.identidade.dependencias` e `app.compartilhado.*`; `dominio.py` sem `fastapi` e sem `sqlalchemy`). Exceções: `app/main.py`, `app/registro_modelos.py`, `app/scripts/`.
3. **TA-02** (`tests/arquitetura/test_rotas_protegidas.py`): para cada `APIRoute` fora da lista branca (`/health`, `/api/v1/auth/login`, documentação), a árvore de dependências contém `obter_usuario_atual`.
4. **TA-04** (`tests/arquitetura/test_openapi.py`): toda rota protegida documenta 401 em `responses`, e toda rota com perfil restrito documenta 403. Corrija as rotas que faltarem.
5. **TI-74** (`tests/integracao/test_fluxo_completo.py`): o roteiro da seção 16, partes 1 a 4, de ponta a ponta pela API (com o relógio de teste e dados próprios, sem depender do seed).
6. **Log de requisições:** middleware em `main.py` (ou em `compartilhado`) que registra método, caminho, status e duração em ms. Nunca corpo, cabeçalhos, token ou senha. Confira que o TI-72 continua verde.
7. **Refatoração:** revise todos os módulos contra as seções 3 e 7: nomes, funções com mais de ~40 linhas ou 5 parâmetros, duplicação, docstrings faltando (com RN), flags booleanas, ORM vazando para fora do módulo. Liste o que encontrou **antes** de mudar e espere meu OK.
8. **Cobertura:** `.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing`. Metas: 85% no total e 90% nos `dominio.py`. Adicione testes onde faltar.

## Não faça nesta tarefa

- Novas funcionalidades ou mudanças de regra de negócio.

## Pronto quando

- Todos os testes verdes; metas de cobertura atingidas; CI verde.

## Commits

1. `test: verifica permissões de todas as rotas por perfil`
2. `test: verifica fronteiras entre módulos e rotas protegidas`
3. `test: cobre o fluxo completo da eleição`
4. `feat: registra log das requisições sem dados sensíveis`
5. `refactor(<modulo>): ...` (um commit por refatoração relevante)
6. `test: amplia cobertura` (inclui marcar a tarefa no PROGRESSO)
