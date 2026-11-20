# Tarefa 03 — Eleitores

Implemente o módulo `eleitores`: cadastro, listagem, consulta, alteração e exclusão de eleitores pelo Chefe da Seção, e a consulta dos próprios dados pelo eleitor.

**Branch:** `feat/eleitores`

## Leia antes de começar

- `docs/PLANO.md`: seções 6 (tabela `eleitores` e "Política de exclusão"), 8 (RN-20 a RN-25, e RN-07, RN-08), 9.3, 10 (rotas `/eleitores` e o contrato "Cadastrar eleitor"), 12 (TI-18 a TI-26) e 13 (Fase 3).
- O código de `app/compartilhado/` e `app/identidade/` (você vai usar `identidade.servico`).

## O que fazer

1. `modelos.py` com a tabela `eleitores` (seção 6) + migração `0002_eleitores`. Registre em `registro_modelos.py`.
2. `dominio.py`: `EleitorResumo` (`id`, `usuario_id`, `criado_em`), `EleitorDetalhado` (com `nome`, `cpf`, `titulo_eleitor`, `data_nascimento`, `criado_em`), `validar_idade_eleitor` (RN-22).
3. `repositorio.py` e `servico.py` com `cadastrar_eleitor`, `listar_eleitores`, `obter_eleitor`, `atualizar_eleitor`, `excluir_eleitor`, `obter_eleitor_do_usuario` e `contar_aptos`, seguindo os passos da seção 9.3. Nome e CPF vêm de `identidade.servico` (este módulo não lê a tabela `usuarios`). Timestamps com o relógio injetável.
4. `esquemas.py` (`NovoEleitor`, `AlteracaoEleitor`, `EleitorResposta`, todos de entrada com `extra="forbid"`; CPF aceito com ou sem pontuação; título com 12 dígitos) e `rotas.py` com as 6 rotas da seção 10. Declare `/eleitores/eu` **antes** de `/eleitores/{eleitor_id}`.
5. Inclua o router no `main.py`.
6. `tests/auxiliares.py`: fábrica `novo_eleitor(cliente, cabecalho, **sobrescritas)` e fixture `cabecalho_eleitor`.

## Testes obrigatórios

- Integração: **TI-18 a TI-23, TI-25 e TI-26** (`tests/integracao/test_eleitores_api.py`).
- O **TI-24** (excluir eleitor que já votou) fica para a tarefa 08, quando existir voto. O código de exclusão já deve tratar o `IntegrityError` da FK de `registros_votacao`, mesmo que a tabela ainda não exista.
- Inclua testes unitários para `validar_idade_eleitor` (16 anos completos hoje, um dia a menos, nascimento no futuro).

## Não faça nesta tarefa

- Nada de candidatos, eleições ou votação.

## Pronto quando

- Testes verdes, junto com os anteriores.
- No Swagger, o Chefe cadastra, lista, edita e exclui um eleitor; o eleitor faz login e vê `/eleitores/eu`.

## Commits

1. `feat(eleitores): cria tabela de eleitores`
2. `feat(eleitores): cadastra eleitor com credencial`
3. `feat(eleitores): lista, consulta, altera e exclui eleitores`
4. `test(eleitores): cobre cadastro, validações e exclusão` (inclui marcar a tarefa no PROGRESSO e anotar que o TI-24 ficou para a tarefa 08)
