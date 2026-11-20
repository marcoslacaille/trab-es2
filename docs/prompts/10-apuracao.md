# Tarefa 10 — Apuração parcial e resultado final

Implemente o módulo `apuracao`, que **não tem tabelas**: ele combina as contagens de `votacao`, as candidaturas de `eleicoes` e os eleitores aptos de `eleitores`, e aplica as regras de apuração (percentual sobre votos válidos, mais votado, desempate pelo mais idoso, visibilidade por perfil).

**Branch:** `feat/apuracao`

## Leia antes de começar

- `docs/PLANO.md`: seções 5 (por que `apuracao` não tem tabelas), 8 (RN-70 a RN-79), 9.7 (inteira, com o código de referência), 10 (rotas `/apuracao` e o contrato "Apuração parcial e resultado final"), 12 (TU-25 a TU-31 e TI-55 a TI-62) e 13 (Fase 7).
- `app/votacao/servico.py` (`contar_votos`, `contar_comparecimento`), `app/eleicoes/servico.py` (`listar_candidaturas`, `candidaturas_do_usuario`, `obter_eleicao`) e `app/eleitores/servico.py` (`contar_aptos`).

## O que fazer

1. `app/apuracao/dominio.py`: `SituacaoCargo`, `LinhaApuracao` (inclui `data_nascimento`, usada só no desempate), `ResultadoCargo`, `percentual`, `definir_mais_votado`, `apurar_cargo` (seção 9.7).
2. `app/apuracao/servico.py`: `apuracao_parcial` e `resultado_final` com as regras de visibilidade (RN-70 a RN-73) e o comparecimento (RN-79).
3. `app/apuracao/esquemas.py`: `ApuracaoResposta` no formato da seção 10. A **data de nascimento não aparece** na resposta. Percentuais como texto com 2 casas.
4. `app/apuracao/rotas.py`: `GET /apuracao/eleicoes/{eleicao_id}/parcial?cargo=` (Chefe, Eleitor, Candidato) e `GET /apuracao/eleicoes/{eleicao_id}/resultado?cargo=` (todos), tag "Apuração".
5. Inclua o router no `main.py`.

## Testes obrigatórios

- Unitários: **TU-25 a TU-31** (`tests/unitarios/test_apuracao_dominio.py`). Monte as listas de candidaturas e contagens à mão, sem banco.
- Integração: **TI-55 a TI-62** (`tests/integracao/test_apuracao_api.py`). Para o empate do TI-61, crie dois candidatos com datas de nascimento diferentes e dê o mesmo número de votos a cada um.

## Não faça nesta tarefa

- Server-Sent Events ou qualquer outra forma de "tempo real" além de consultar de novo (é extra opcional).

## Pronto quando

- Testes verdes, junto com os anteriores.
- Validação manual no Swagger: com votos registrados, o eleitor vê a parcial de todos os cargos; um candidato vê só o seu cargo e recebe 403 ao pedir outro; depois do encerramento, o resultado mostra o mais votado de cada cargo e o comparecimento.

## Commits

1. `feat(apuracao): calcula percentuais e mais votado`
2. `feat(apuracao): disponibiliza acompanhamento parcial por perfil`
3. `feat(apuracao): disponibiliza resultado final`
4. `test(apuracao): cobre apuração, desempate e visibilidade` (inclui marcar a tarefa no PROGRESSO)

Depois do merge na `main`, crie a tag `v0.4.0`.
