# Progresso das tarefas

Marque `[x]` quando a tarefa estiver integrada na `main` (o agente marca no último commit da tarefa; o grupo confere no merge).

- [x] 00 — Fundação do repositório
- [x] 01 — Módulo compartilhado
- [x] 02 — Identidade (login, JWT, perfis)
- [x] 02b — Consolidação das decisões 00 a 02
- [x] 03 — Eleitores
- [x] 04 — Candidatos e partidos
- [x] 05 — Eleições
- [x] 06 — Candidaturas
- [x] 07 — Votação: base (tabelas, trigger, domínio, cédula)
- [x] 08 — Votação: API
- [x] 09 — Sigilo e concorrência
- [x] 10 — Apuração
- [x] 11 — Qualidade transversal
- [x] 12 — Swagger e GitHub Pages
- [x] 13 — Seed e documentação de entrega
- [x] 14 — Revisão final

## Pendências e decisões registradas

Tudo o que foi feito e não estava prescrito no PLANO (lacunas, desvios, extras, conflitos e riscos) fica em [`docs/DECISOES.md`](../DECISOES.md), numerado e com status. As decisões das tarefas 00 a 02 que estavam aqui foram migradas para lá (D-001 a D-027).

Aqui ficam só os avisos de curto prazo entre tarefas, como testes adiados para uma tarefa seguinte.

### Avisos em aberto

- [ ] **Rodar a migração `0006` em todo banco já existente (21/11/2026, D-140).** A migração `0006_retrato_candidaturas` acrescenta `nome_urna` e `data_nascimento` à tabela `candidaturas`. Quem já tinha o banco local (porta 5432) criado antes dela precisa aplicá-la, senão a API dá erro ao ler as candidaturas. Cada integrante roda uma vez, depois do `git pull`, com o `docker compose up -d` no ar:
  - Windows: `.venv\Scripts\python.exe -m alembic upgrade head`
  - Linux/macOS: `.venv/bin/python -m alembic upgrade head`

  Para conferir: `alembic current` deve mostrar `0006 (head)`. O banco de teste (porta 5433) não precisa disso: a suíte refaz as migrações a cada execução. Marque este item quando todo o grupo tiver rodado.
- [ ] **Acrescentar `POSTGRES_USER` e `POSTGRES_PASSWORD` no `.env` de cada integrante (21/11/2026, D-141).** O `docker-compose.yml` não tem mais a senha escrita: lê essas duas variáveis do `.env`. Quem tem um `.env` antigo vai ver `required variable POSTGRES_USER is missing a value` no `docker compose up -d`. Copie as duas linhas do `.env.example` para o seu `.env` (com os valores de lá, `eleicao`/`eleicao`, o banco que já existe continua funcionando). Marque este item quando todo o grupo tiver feito.
