# Tarefa 06 — Candidaturas dentro da eleição

Implemente a segunda metade do módulo `eleicoes`: as candidaturas (candidato + eleição + cargo + partido + número), sempre alteradas **pela raiz do agregado** (a eleição), e as regras do 2º turno. Com isso, a abertura da eleição passa a funcionar de ponta a ponta.

**Branch:** `feat/candidaturas`

## Leia antes de começar

- `docs/PLANO.md`: seções 3 (agregados), 8 (RN-17 e RN-40 a RN-47), 9.5 (a partir de `criar_candidatura`), 10 (rotas de candidaturas e `/candidaturas/minhas`, contrato "Criar candidatura"), 12 (TU-17, TI-11, TI-12, TI-15, TI-16, TI-29 completo, TI-30 a TI-37) e 13 (Fase 5).
- O código de `app/eleicoes/` (tarefa 05) e `app/candidatos/servico.py`.

## O que fazer

1. `dominio.py`: `CandidaturaDetalhada` (campos da seção 9.5) e `validar_candidatura` (RN-42 e RN-45). Confira que `validar_abertura` já cobre a RN-17 (2º turno com exatamente 2 por cargo).
2. `servico.py`: `criar_candidatura`, `editar_candidatura`, `remover_candidatura`, `listar_candidaturas`, `candidaturas_do_usuario` e `buscar_candidatura_por_numero`. Toda alteração começa com a trava exclusiva na eleição (`obter_com_trava_exclusiva`). Candidato e partido são conferidos via `candidatos.servico` (RN-46: inexistente → 422 `REFERENCIA_INEXISTENTE` com `detalhes.campo`). Dados de exibição (nome de urna, sigla) vêm de `candidatos.servico` e são juntados em memória.
3. `esquemas.py` e `rotas.py`: as 4 rotas sob `/eleicoes/{eleicao_id}/candidaturas` e `GET /candidaturas/minhas` (tag "Candidaturas"). Editar permite só cargo, número e partido.
4. `tests/auxiliares.py`: fábrica `nova_candidatura(...)` e `eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)` (seção 12: Presidente 10 e 20, Senador 101 e 202, já aberta).

## Testes obrigatórios

- Unitários: **TU-17**.
- Integração: **TI-30 a TI-37** (`tests/integracao/test_candidaturas_api.py`).
- Os adiados da tarefa 05: **TI-11** (parte "editar ABERTA"), **TI-12, TI-15 e TI-16**.
- O adiado da tarefa 04: **TI-29** completo (excluir candidato com candidatura → 409 `EXCLUSAO_BLOQUEADA`).

## Não faça nesta tarefa

- Nada de votação ou apuração.

## Pronto quando

- Testes verdes, junto com os anteriores.
- Validação manual no Swagger (fora dos testes vale o relógio real): crie uma eleição para **hoje** com janela 00:00 às 23:59, adicione candidaturas, abra, confirme que uma nova candidatura é recusada (409 `ELEICAO_NAO_EDITAVEL`) e encerre.

## Commits

1. `feat(eleicoes): gerencia candidaturas pela eleição`
2. `feat(eleicoes): aplica regras de número por cargo e de segundo turno`
3. `feat(eleicoes): lista as candidaturas do candidato logado`
4. `test(eleicoes): cobre candidaturas e abertura com candidatos` (inclui marcar a tarefa no PROGRESSO e remover a anotação dos testes adiados)

Depois do merge na `main`, crie a tag `v0.2.0`.
