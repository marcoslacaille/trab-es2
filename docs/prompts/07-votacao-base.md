# Tarefa 07 — Votação, parte 1: tabelas, trigger, regras puras e cédula

Construa a base do módulo `votacao`, sem rotas ainda: as duas tabelas **sem ligação entre si** (é isso que garante o sigilo), o trigger que impede alterar votos, as regras puras do domínio e a cédula assinada. Esta é a parte mais importante do sistema: leia o PLANO com calma.

**Branch:** `feat/votacao-base`

## Leia antes de começar

- `docs/PLANO.md`: seções 1 (decisões D05 e D06), 6 (tabelas `registros_votacao` e `votos`, a FK composta, o trigger, "Carimbos de tempo" e "Limitação conhecida do sigilo"), 7 (tabela de ameaças), 8 (RN-50 a RN-61), 9.6 (funções puras e `cedulas.py`), 12 (TU-19 a TU-24 e TI-63 a TI-68) e 13 (Fase 6).
- `app/eleicoes/dominio.py` (para usar `EleicaoResumo`) e `app/compartilhado/dominio.py`.

## O que fazer

1. `app/votacao/modelos.py`:
   - `registros_votacao` com chave primária composta (`eleitor_id`, `eleicao_id`, `cargo`), **sem** coluna de horário e **sem** coluna de candidatura.
   - `votos` com `id` UUID gerado por `uuid.uuid4()` na aplicação, `eleicao_id`, `cargo`, `tipo`, `candidatura_id` (nulo), o CHECK `ck_votos_nominal_tem_candidatura`, a FK composta (`candidatura_id`, `eleicao_id`, `cargo`) → `candidaturas` (`id`, `eleicao_id`, `cargo`) e o índice `ix_votos_apuracao`. **Sem** `eleitor_id`, **sem** horário.
   - Registre em `registro_modelos.py`.
2. Migração `0005_votacao`: as tabelas + a função `impedir_alteracao_de_voto()` e os dois triggers (seção 6) via `op.execute`. O `downgrade` remove triggers e função. Teste `upgrade head`, `downgrade -1` e `upgrade head` de novo.
3. `app/votacao/dominio.py`: `TipoVoto` (`NOMINAL`, `BRANCO`, `NULO`), `ModoEscolha` (`NUMERO`, `BRANCO`), `Escolha` (`tipo`, `candidatura_id`, e os dados de exibição do candidato quando nominal), `validar_pode_votar`, `validar_eleitor_apto`, `resolver_escolha` (seção 9.6).
4. `app/votacao/cedulas.py`: exatamente como na seção 9.6 (`Cedula`, `emitir_cedula`, `ler_cedula`, audiência `eleicao-api:cedula`, expiração conferida com o relógio injetado no campo `expira_em`).
5. `app/votacao/repositorio.py`: `inserir_registro`, `inserir_voto`, `ja_votou`, `cargos_votados`, `contar_votos` (`GROUP BY`) e `contar_comparecimento`.

## Testes obrigatórios

- Unitários: **TU-19 a TU-24** (`tests/unitarios/test_votacao_dominio.py` e `tests/unitarios/test_cedulas.py`).
- Integração direto no banco: **TI-63 a TI-68** (`tests/integracao/test_banco_restricoes.py`). Use uma sessão SQLAlchemy e SQL com parâmetros para inserir e provocar cada violação; confira o nome da restrição ou a mensagem do trigger.

## Não faça nesta tarefa

- `servico.py` e `rotas.py` da votação (tarefa 08).
- Testes de sigilo e de concorrência (tarefa 09).

## Pronto quando

- Testes verdes, junto com os anteriores.
- No psql, `\d votos` mostra a FK composta, o CHECK e o trigger; `\d registros_votacao` mostra a chave primária composta e o trigger.

## Commits

1. `feat(votacao): cria tabelas de registro e voto sem ligação entre si`
2. `feat(votacao): impede alteração de votos com trigger`
3. `feat(votacao): adiciona regras de votação e resolução da escolha`
4. `feat(votacao): emite e valida a cédula assinada`
5. `test(votacao): cobre regras puras, cédula e restrições do banco` (inclui marcar a tarefa no PROGRESSO)
