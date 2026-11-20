# Progresso das tarefas

Marque `[x]` quando a tarefa estiver integrada na `main` (o agente marca no último commit da tarefa; o grupo confere no merge).

- [x] 00 — Fundação do repositório
- [x] 01 — Módulo compartilhado
- [x] 02 — Identidade (login, JWT, perfis)
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
- **Tarefa 02, esquemas e retorno do login:** o PLANO só dá o contrato do login. Foram criados `UsuarioResposta` (`id`, `nome`, `perfil`, dentro do login) e `UsuarioLogadoResposta` (acrescenta `cpf`, usado no `GET /auth/me`), além de `LoginResposta`. `autenticar` devolve a `dataclass` `ResultadoDoLogin` (`access_token`, `expira_em`, `usuario`). Acrescentar nas seções 9.2 e 10 do PLANO.
- **Tarefa 02, pendência de revisão (6 parâmetros):** `criar_credencial(sessao, cpf, nome, senha, perfil, agora)` tem 6 parâmetros, e a seção 3 manda no máximo 5. Foi mantida a assinatura da seção 9.2 do PLANO. Decidir se agrupa em uma `dataclass` (isso afetaria as tarefas 03 e 04).
- **Tarefa 02, pendência de revisão (usuário inexistente):** o PLANO não diz o que fazem `atualizar_credencial` e `remover_credencial` com um id que não existe. Levantam `LookupError` (vira 500 `ERRO_INTERNO`), porque quem chama já conhece o usuário e a ausência seria inconsistência. Nenhum código novo entrou no catálogo de erros.
- **Tarefa 02, RN-08 no serviço:** além dos esquemas, `criar_credencial` e `atualizar_credencial` conferem o nome (3 a 120 caracteres, sem espaços nas pontas) e gravam o nome já sem os espaços das pontas. Motivo: o script `criar_chefe` não passa por esquema, e sem isso um nome inválido viraria `IntegrityError` do banco.
- **Tarefa 02, senha com mais de 72 bytes no login:** o bcrypt 5 levanta `ValueError` para senha maior que 72 bytes. `senha_confere` devolve `False` nesse caso (gastando o tempo de uma comparação), para o login responder o mesmo 401 em vez de 500. Ver o TU-08.
- **Tarefa 02, `ler_token_acesso`:** também converte `ValueError` (ao fazer `int(sub)`) em `TOKEN_INVALIDO`. O TU-12 monta o token de cédula com `jwt.encode` e `aud="eleicao-api:cedula"`, porque o módulo de votação ainda não existe.
- **Tarefa 02, `listar_usuarios`:** `%` e `_` digitados no filtro de nome valem como texto comum (escapados no `ILIKE`).
- **Tarefa 02, `criar_chefe`:** a idempotência vem de tratar o `CPF_JA_CADASTRADO` de `criar_credencial` (o serviço não tem função pública de consulta por CPF). Se o CPF já existir com outro perfil, o script também não altera nada.
- **Tarefa 02, fixture `cabecalho_chefe`:** fica em `tests/auxiliares.py` (como no PLANO) e é registrada por um import em `tests/integracao/conftest.py`, porque o pytest só descobre fixtures de `conftest.py` ou importadas.
