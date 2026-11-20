# Tarefa 04 — Candidatos e partidos

Implemente o módulo `candidatos`: CRUD de candidatos (as pessoas) e cadastro e listagem de partidos. As candidaturas (candidato + eleição + cargo + número) **não** são desta tarefa: elas ficam no módulo `eleicoes` (tarefa 06).

**Branch:** `feat/candidatos`

## Leia antes de começar

- `docs/PLANO.md`: seções 2 (diferença entre candidato e candidatura), 6 (tabelas `candidatos` e `partidos`, "Política de exclusão"), 8 (RN-30 a RN-33), 9.4, 10 (rotas `/candidatos` e `/partidos`, contratos de partido e candidato), 12 (TI-27 a TI-29) e 13 (Fase 4).
- O código de `app/eleitores/` (siga o mesmo padrão) e `app/identidade/servico.py`.

## O que fazer

1. `modelos.py` com `candidatos` e `partidos` (seção 6) + migração `0003_candidatos_partidos`. Registre em `registro_modelos.py`.
2. `dominio.py`: `CandidatoResumo` (`id`, `usuario_id`, `nome_urna`, `data_nascimento`), `CandidatoDetalhado`, `PartidoResumo` (`id`, `sigla`, `nome`, `numero`) e as validações (nascimento no passado, nome de urna de 3 a 30 caracteres).
3. `repositorio.py` e `servico.py`: `cadastrar_candidato`, `listar_candidatos`, `obter_candidato`, `atualizar_candidato`, `excluir_candidato`, `obter_candidato_do_usuario`, `obter_resumos_de_candidatos(ids)`, `criar_partido`, `listar_partidos`, `obter_partido` (seção 9.4). A exclusão já trata o `IntegrityError` da FK de `candidaturas` (a tabela ainda não existe).
4. `esquemas.py` e `rotas.py`: as 6 rotas de candidatos (com `/candidatos/eu` antes de `/{candidato_id}`) e as 2 de partidos (seção 10), tags "Candidatos" e "Partidos". Sigla convertida para maiúsculas.
5. Inclua o router no `main.py`.
6. `tests/auxiliares.py`: fábricas `novo_partido`, `novo_candidato` e fixture `cabecalho_candidato`.

## Testes obrigatórios

- Integração: **TI-27, TI-28** e a parte "excluir candidato sem candidaturas → 204" do **TI-29** (`tests/integracao/test_candidatos_api.py`). A parte "com candidatura → 409" fica para a tarefa 06.
- Unitários para as validações do `dominio.py`.

## Não faça nesta tarefa

- Nada de candidaturas, eleições ou números de candidatura.

## Pronto quando

- Testes verdes, junto com os anteriores.
- No Swagger, o Chefe cria partidos e candidatos; um candidato faz login e vê `/candidatos/eu`; qualquer usuário logado lista partidos.

## Commits

1. `feat(candidatos): cria tabelas de candidatos e partidos`
2. `feat(candidatos): cadastra partidos`
3. `feat(candidatos): gerencia candidatos`
4. `test(candidatos): cobre partidos e candidatos` (inclui marcar a tarefa no PROGRESSO)
