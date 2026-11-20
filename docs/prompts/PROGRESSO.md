# Progresso das tarefas

Marque `[x]` quando a tarefa estiver integrada na `main` (o agente marca no último commit da tarefa; o grupo confere no merge).

- [x] 00 — Fundação do repositório
- [x] 01 — Módulo compartilhado
- [ ] 02 — Identidade (login, JWT, perfis)
- [ ] 03 — Eleitores
- [ ] 04 — Candidatos e partidos
- [ ] 05 — Eleições
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

Anote aqui qualquer decisão tomada durante as tarefas que não estava no PLANO (e atualize o PLANO também).

- **Tarefa 00, `banco_limpo`:** diferente do PLANO (seção 12), a fixture descobre as tabelas dinamicamente (todas do schema `public`, exceto `alembic_version`) e só faz `TRUNCATE ... RESTART IDENTITY CASCADE` se houver alguma. Assim ela funciona desde já, quando ainda não existe nenhuma tabela. O PLANO ainda mostra a lista fixa `TABELAS`.
- **Tarefa 00, fixture `relogio`:** criava o `RelogioDeTeste` sem ligá-lo à aplicação. **Resolvido na tarefa 01:** a fixture agora faz `app.dependency_overrides[obter_agora]` (como na seção 12) e o aviso da docstring saiu.
- **Tarefa 00, `pyproject.toml`:** acrescentado `[tool.ruff.format] exclude = ["*.md"]`. O ruff 0.17.6 também formata blocos de código dentro de arquivos `.md`, e o `ruff format --check .` falhava por causa do `docs/PLANO.md`. O PLANO (seção 4) ainda mostra o `pyproject.toml` sem essa linha.
- **Tarefa 00, rotas com `Depends`:** o ruff acusa B008 em `sessao: Session = Depends(obter_sessao)`. Use `sessao: Annotated[Session, Depends(obter_sessao)]` nas próximas rotas (o PLANO, seções 7 e 9, ainda mostra o estilo antigo).
- **Tarefa 00, nomes das migrações:** o Alembic só gera `0001_...` se o número for passado: `python -m alembic revision --autogenerate --rev-id 0001 -m "identidade"` (o `file_template` do `alembic.ini` já é `<número>_<descrição>`).
- **Tarefa 00, pacotes de teste:** `tests/` e suas subpastas têm `__init__.py`, para o `tests/auxiliares.py` (tarefa 02) poder ser importado e para não haver conflito entre arquivos de mesmo nome em pastas diferentes.
- **Tarefa 01, `Paginacao`:** o PLANO só cita o nome. Foi implementada como `dataclass` (`pagina`, `tamanho`) com a propriedade `deslocamento` (`(pagina - 1) * tamanho`), mais a dependência `obter_paginacao`. A propriedade `deslocamento` não está no PLANO; acrescentar lá.
- **Tarefa 01, 422 (`detalhes.campos`):** `campo` é o `loc` do Pydantic sem o prefixo `body`/`query`/`path`, unido por ponto; `mensagem` é o `msg` do Pydantic sem o prefixo `"Value error, "`. As mensagens nativas do Pydantic continuam em inglês (ex.: "Field required"). O PLANO não define isso; acrescentar lá.
- **Tarefa 01, `ERROS_POR_RESTRICAO`:** cada entrada é uma `TraducaoDeRestricao` (código, status e mensagem em português), porque o corpo do erro precisa de mensagem além do código.
- **Tarefa 01, pendência de revisão (CPF):** `FORMATO_CPF` usa `\d`, que em Python também casa dígitos de outros alfabetos (ex.: árabe-índicos), e `normalizar_cpf` os aceitaria. O código segue o PLANO à risca; decidir se vale usar `re.ASCII` (ou `[0-9]`) na seção 9.1.
- **Tarefa 01, pendência de revisão (404/405):** erros do próprio FastAPI (rota inexistente, método não permitido) ainda respondem `{"detail": ...}`, fora do formato padrão. O PLANO manda só 4 tratadores, então ficou assim.
