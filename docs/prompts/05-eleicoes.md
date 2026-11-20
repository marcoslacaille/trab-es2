# Tarefa 05 — Eleições: cadastro, edição, abertura, encerramento e HATEOAS

Implemente a primeira metade do módulo `eleicoes`: a eleição como raiz do agregado, com seu ciclo de vida AGENDADA → ABERTA → ENCERRADA e os `links` HATEOAS. As candidaturas vêm na tarefa 06, mas a **tabela** `candidaturas` já é criada aqui, porque está na mesma migração e a abertura precisa contar candidaturas.

**Branch:** `feat/eleicoes`

## Leia antes de começar

- `docs/PLANO.md`: seções 2, 3 (agregados e HATEOAS), 6 (tabelas `eleicoes` e `candidaturas`, índice parcial), 8 (RN-10 a RN-19), 9.5 (até `links_da_eleicao`, inclusive a tabela de links), 10 (rotas `/eleicoes` e o contrato "Criar eleição"), 11 (o exemplo de rota de abertura), 12 (TU-13 a TU-16, TU-18 e TI-09 a TI-17) e 13 (Fase 5).
- O código de `app/compartilhado/` e um módulo pronto como referência (`app/eleitores/`).

## O que fazer

1. `modelos.py` com `eleicoes` e `candidaturas` e **todas** as restrições da seção 6 (índice parcial `uq_eleicoes_uma_aberta`, `ck_eleicoes_status_coerente`, `uq_candidaturas_id_eleicao_id_cargo`, `ck_candidaturas_numero_por_cargo` etc.) + migração `0004_eleicoes_candidaturas`. Confira o índice parcial na migração gerada (o autogenerate pode errar). Registre em `registro_modelos.py`.
2. `dominio.py`: `StatusEleicao`, `EleicaoResumo`, `Link`, `validar_agendamento`, `validar_edicao`, `validar_abertura`, `validar_encerramento`, `links_da_eleicao` (seção 9.5).
3. `repositorio.py`: inclua `obter_com_trava_exclusiva` (`with_for_update()`), `existe_eleicao_aberta`, `contar_candidaturas_por_cargo` e `obter_com_trava_compartilhada` (`with_for_update(read=True)`).
4. `servico.py`: `criar_eleicao`, `editar_eleicao`, `abrir_eleicao`, `encerrar_eleicao`, `obter_eleicao`, `listar_eleicoes` e `obter_eleicao_para_votacao` (esta última sem commit, para a votação).
5. `esquemas.py` (`NovaEleicao`, `AlteracaoEleicao`, `EleicaoResposta` com `links`) e `rotas.py` com as 6 rotas de eleição da seção 10 (tag "Eleições"). As rotas recebem `agora` por `Depends(obter_agora)`.
6. Inclua o router no `main.py`.
7. `tests/auxiliares.py`: fábrica `nova_eleicao(cliente, cabecalho, **sobrescritas)` com data 2026-11-25, 08:00 às 17:00 (bate com o relógio de teste).

## Testes obrigatórios

- Unitários: **TU-13 a TU-16 e TU-18** (`tests/unitarios/test_eleicoes_dominio.py`).
- Integração: **TI-09, TI-10, TI-11 (só a parte "editar AGENDADA funciona"), TI-13, TI-14 e TI-17** (`tests/integracao/test_eleicoes_api.py`).
- **TI-12, TI-15, TI-16 e a parte "editar ABERTA → 409" do TI-11** precisam de uma eleição com candidatura para abrir; ficam para a tarefa 06. Anote isso no PROGRESSO.

## Não faça nesta tarefa

- Rotas, serviço ou regras de candidatura (tarefa 06).

## Pronto quando

- Testes verdes, junto com os anteriores.
- No Swagger, o Chefe cria e edita eleições, vê os `links` mudarem conforme o status, e a tentativa de abrir sem candidaturas responde 409 `SEM_CANDIDATURAS`.

## Commits

1. `feat(eleicoes): cria tabelas de eleições e candidaturas`
2. `feat(eleicoes): cadastra e edita eleições`
3. `feat(eleicoes): abre e encerra a votação`
4. `feat(eleicoes): adiciona links HATEOAS`
5. `test(eleicoes): cobre ciclo de vida da eleição` (inclui marcar a tarefa no PROGRESSO com os testes adiados)
