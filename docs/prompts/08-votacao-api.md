# Tarefa 08 — Votação, parte 2: cédula, registro e confirmação pela API

Exponha a votação pela API: o eleitor consulta a cédula, registra o voto (recebe uma prévia e o token da cédula, **sem gravar nada**) e confirma (grava de forma definitiva, em uma transação, nas duas tabelas sem ligação).

**Branch:** `feat/votacao-api`

## Leia antes de começar

- `docs/PLANO.md`: seções 7 (tabela de ameaças), 8 (RN-50 a RN-61), 9.6 (casos de uso e o código de `confirmar_voto`), 10 (rotas `/votacao` e os contratos "Cédula", "Registrar voto", "Confirmar voto" e "Participação"), 12 (TI-24 e TI-38 a TI-54) e 13 (Fase 6).
- O código de `app/votacao/` (tarefa 07), `app/eleicoes/servico.py` e `app/eleitores/servico.py`.

## O que fazer

1. `app/votacao/servico.py`: `obter_cedula`, `registrar_voto`, `confirmar_voto` (siga o código de referência da seção 9.6, inclusive a trava compartilhada via `eleicoes.servico.obter_eleicao_para_votacao` e o tratamento de `pk_registros_votacao`), `obter_participacao`, `contar_votos`, `contar_comparecimento`.
   - `registrar_voto` **não grava nada e não faz commit**.
   - A resposta da confirmação **não** contém a escolha.
2. `app/votacao/esquemas.py`: `CedulaResposta`, `PedidoRegistroVoto` (validador: `numero` obrigatório no modo NUMERO e proibido no modo BRANCO; `numero` só com dígitos, 1 a 5), `PreviaVotoResposta` (com `links` → confirmar), `PedidoConfirmacaoVoto`, `ComprovanteVotoResposta` (com `links`), `ParticipacaoResposta`.
3. `app/votacao/rotas.py`: as 4 rotas da seção 10, todas com `exige_perfil(Perfil.ELEITOR)` e `agora` injetado, tag "Votação".
4. Inclua o router no `main.py`.
5. `tests/auxiliares.py`: helper `votar(cliente, cabecalho, eleicao_id, cargo, numero=None, branco=False)` (registro + confirmação).

## Testes obrigatórios

- Integração: **TI-38 a TI-54** (`tests/integracao/test_votacao_api.py`). No TI-39, confirme no banco que `votos` e `registros_votacao` continuam vazios depois do registro.
- O adiado da tarefa 03: **TI-24** (excluir eleitor que já votou → 409 `EXCLUSAO_BLOQUEADA`).

## Não faça nesta tarefa

- Testes de sigilo, logs e concorrência (tarefa 09).
- Apuração (tarefa 10).

## Pronto quando

- Testes verdes, junto com os anteriores.
- Validação manual no Swagger: com uma eleição de hoje aberta, um eleitor consulta a cédula, registra Presidente com número existente (prévia NOMINAL), registra com número inexistente (NULO), registra BRANCO, confirma, e a segunda confirmação responde 409.

## Commits

1. `feat(votacao): monta a cédula do eleitor`
2. `feat(votacao): registra voto com cédula assinada`
3. `feat(votacao): confirma voto de forma atômica`
4. `feat(votacao): informa em quais cargos o eleitor já votou`
5. `test(votacao): cobre registro, confirmação e regras de votação` (inclui marcar a tarefa no PROGRESSO)
