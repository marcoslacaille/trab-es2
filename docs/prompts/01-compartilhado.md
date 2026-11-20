# Tarefa 01 — Módulo compartilhado

Implemente as peças comuns que todos os módulos vão usar. A tarefa 00 já criou `config.py`, `banco.py`, o `/health` e a infraestrutura de testes.

**Branch:** `feat/compartilhado`

## Leia antes de começar

- `docs/PLANO.md`: seções 3, 5 ("Transações" e "Tratamento de erros"), 6 ("Tradução de restrições em erros"), 7 (só o item "Erros sem vazamento" das proteções), 9.1 (inteira), 10 ("Formato de erro" e "Catálogo de códigos de erro"), 11 (o arquivo `app/compartilhado/openapi.py`) e 12 (TU-01 a TU-06 e "Convenções").
- O código existente em `app/`.

## O que fazer

1. `app/compartilhado/erros.py`:
   - Hierarquia `ErroDeNegocio`, `NaoAutenticado` (401), `AcessoNegado` (403), `NaoEncontrado` (404), `ConflitoDeEstado` (409), `DadosInvalidos` (422), com `mensagem`, `codigo` e `detalhes` (seção 5).
   - Esquema Pydantic `ErroResposta` no formato `{"erro": {"codigo", "mensagem", "detalhes"}}` (seção 10).
   - `nome_da_restricao(erro: IntegrityError) -> str | None` (lê `erro.orig.diag.constraint_name`).
   - Dicionário `ERROS_POR_RESTRICAO` com a tabela da seção 6 (nome da restrição → código e status).
   - `registrar_tratadores(app)` com os 4 tratadores da seção 5: `ErroDeNegocio` (com `WWW-Authenticate: Bearer` no 401), `RequestValidationError` → 422 `DADOS_INVALIDOS` com `detalhes.campos` = lista de `{campo, mensagem}`, `IntegrityError` → 409 pelo nome da restrição (ou `CONFLITO_DE_DADOS`), `Exception` → 500 `ERRO_INTERNO` com mensagem genérica e detalhe só no log.
2. `app/compartilhado/relogio.py`: `agora()` e `obter_agora()` (seção 9.1).
3. `app/compartilhado/validadores.py`: `FORMATO_CPF`, `normalizar_cpf`, `cpf_valido`, `calcular_idade` (seção 9.1).
4. `app/compartilhado/dominio.py`: `Cargo` (na ordem da urna), `DIGITOS_POR_CARGO`, `CARGOS_DO_SEGUNDO_TURNO`, `numero_valido_para_cargo` (seção 9.1).
5. `app/compartilhado/paginacao.py`: parâmetros `pagina` (≥ 1, padrão 1) e `tamanho` (1 a 100, padrão 20) como dependência FastAPI, e esquema genérico `Pagina[T]` com `itens`, `pagina`, `tamanho`, `total` (seção 10).
6. `app/compartilhado/openapi.py`: `DESCRICAO_API`, `TAGS` e `respostas_de_erro(...)` (seção 11).
7. `app/main.py`: passe a usar `registrar_tratadores(app)`, `description=DESCRICAO_API`, `openapi_tags=TAGS` e `generate_unique_id_function=lambda rota: rota.name`.

## Testes obrigatórios

- Unitários em `tests/unitarios/test_validadores.py`: **TU-01 a TU-06** (seção 12).
- Integração em `tests/integracao/test_erros.py`: crie rotas de teste **só dentro do teste** (um `APIRouter` incluído num app de teste com `registrar_tratadores`) e verifique o formato de resposta de cada tratador: `ErroDeNegocio` 409, `NaoAutenticado` com o cabeçalho `WWW-Authenticate`, validação 422 com `detalhes.campos`, e exceção genérica → 500 sem vazar a mensagem original.

## Não faça nesta tarefa

- Nenhuma tabela, migração ou módulo de domínio.
- Não adicione rotas de teste ao app real.

## Pronto quando

- Todos os testes acima passam, junto com o `test_health`.
- `ruff check` e `ruff format --check` sem avisos.

## Commits

1. `feat(compartilhado): padroniza respostas de erro`
2. `feat(compartilhado): adiciona relógio injetável`
3. `feat(compartilhado): valida CPF e calcula idade`
4. `feat(compartilhado): define cargos e dígitos por cargo`
5. `feat(compartilhado): adiciona paginação e utilitários do OpenAPI`
6. `test(compartilhado): cobre validadores, cargos e tratadores de erro` (inclui marcar a tarefa no PROGRESSO)
