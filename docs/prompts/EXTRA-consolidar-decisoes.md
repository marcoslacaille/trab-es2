# Prompt de apoio — Rodada de consolidação de decisões

Use a cada 2 ou 3 tarefas, ou sempre que uma tarefa registrar uma decisão de impacto **Médio** ou **Alto** em `docs/DECISOES.md`. Rode numa sessão nova, com a `main` atualizada e sem alterações pendentes. Troque `<NN>` pelo número da última tarefa concluída.

---

Vamos fazer uma rodada de consolidação de decisões. Siga as regras do `CLAUDE.md`. **Branch:** `docs/consolidar-decisoes-<NN>`.

**Etapa 1 — Relatório (não altere nada ainda).**

1. Leia `docs/DECISOES.md` e liste todas as linhas `ABERTA`, ordenadas por impacto (Alto, Médio, Baixo).
2. Para cada uma, mostre: o ID, o resumo em uma frase, a sua recomendação (**aceitar**, **corrigir o código** ou **atualizar o PLANO**), o motivo em uma frase e o esforço (pequeno, médio, grande).
3. Aponte quais delas afetam as próximas tarefas (`docs/prompts/`) e por quê.
4. **Pare e espere o meu veredito** para cada linha.

**Etapa 2 — Aplicação (só depois do meu veredito).**

1. Atualize o `docs/PLANO.md` em tudo o que foi aceito: o PLANO passa a descrever o código real. Não mexa em seções que não foram citadas.
2. Faça as correções de código aprovadas, uma por commit, cada uma com teste.
3. Em `docs/DECISOES.md`, mude só a coluna "Status · ação" de cada linha (`ACEITA`, `NO PLANO (seção X)` ou `RESOLVIDA`). Linhas novas desta rodada entram no fim da tabela.
4. Se alguma decisão mudar o que uma tarefa futura deve fazer, atualize o arquivo dessa tarefa em `docs/prompts/`.
5. Verificação completa (`ruff check`, `ruff format --check`, `pytest`) e commits:
   - `fix(<modulo>): ... (D-xxx)` para cada correção
   - `docs(plano): incorpora as decisões D-xxx a D-yyy`
   - `docs: atualiza status das decisões`
