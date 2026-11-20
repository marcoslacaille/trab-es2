# Progresso das tarefas

Marque `[x]` quando a tarefa estiver integrada na `main` (o agente marca no último commit da tarefa; o grupo confere no merge).

- [x] 00 — Fundação do repositório
- [x] 01 — Módulo compartilhado
- [x] 02 — Identidade (login, JWT, perfis)
- [x] 02b — Consolidação das decisões 00 a 02
- [x] 03 — Eleitores
- [x] 04 — Candidatos e partidos
- [x] 05 — Eleições
- [ ] 06 — Candidaturas
- [ ] 07 — Votação: base (tabelas, trigger, domínio, cédula)
- [ ] 08 — Votação: API
- [ ] 09 — Sigilo e concorrência
- [ ] 10 — Apuração
- [ ] 11 — Qualidade transversal
- [ ] 12 — Swagger e GitHub Pages
- [ ] 13 — Seed e documentação de entrega
- [ ] 14 — Revisão final

## Pendências e decisões registradas

Tudo o que foi feito e não estava prescrito no PLANO (lacunas, desvios, extras, conflitos e riscos) fica em [`docs/DECISOES.md`](../DECISOES.md), numerado e com status. As decisões das tarefas 00 a 02 que estavam aqui foram migradas para lá (D-001 a D-027).

Aqui ficam só os avisos de curto prazo entre tarefas, como testes adiados para uma tarefa seguinte.

- **TI-24 ficou para a tarefa 08** (excluir eleitor que já votou → 409 `EXCLUSAO_BLOQUEADA`): precisa da tabela `registros_votacao`, que só existe a partir da tarefa 07. O código de `excluir_eleitor` já trata o `IntegrityError` dessa FK (ver D-041).
- **TI-29, parte "candidato com candidatura → 409 `EXCLUSAO_BLOQUEADA`", ficou para a tarefa 06**: precisa da tabela `candidaturas`, que nasce na tarefa 05. O código de `excluir_candidato` já trata o `IntegrityError` dessa FK (ver D-053).
- **Tarefa 05: testes adiados para a tarefa 06** (precisam de uma eleição com candidatura para abrir): TI-12 (abrir na data e janela → ABERTA), TI-15 (outra aberta → 409 `OUTRA_ELEICAO_ABERTA`), TI-16 (encerrar ABERTA e reabrir ENCERRADA → 409) e a parte "editar ABERTA → 409" do TI-11. Também o TU-17 (`validar_candidatura`), que é da candidatura.
