# Tarefa 02b — Consolidar as decisões das tarefas 00 a 02

As tarefas 00 a 02 registraram 27 entradas em `docs/DECISOES.md`. O grupo revisou e decidiu cada uma (tabela abaixo). Esta tarefa **aplica as decisões**: atualiza o `docs/PLANO.md` para que as próximas sessões leiam a especificação correta, faz duas correções pequenas de código e ajusta o `CLAUDE.md`.

**Branch:** `docs/consolidar-decisoes-00-02`

**Pré-requisito:** a branch `feat/identidade` já está integrada na `main`, e a suíte passou no Windows (D-024).

## Leia antes de começar

- `docs/DECISOES.md` inteiro.
- `docs/PLANO.md`: seções 3, 4, 5, 6, 7, 8, 9.1, 9.2, 10 e 12.
- O código de `app/compartilhado/`, `app/identidade/`, `tests/` e o `pyproject.toml`.

## Decisões do grupo

| ID | Decisão | O que fazer | Status final |
| --- | --- | --- | --- |
| D-001 | Aceita | Seção 12: trocar a lista fixa `TABELAS` pela fixture dinâmica real | `NO PLANO` |
| D-003 | Aceita | Seção 4: `pyproject.toml` com `[tool.ruff.format] exclude = ["*.md"]` e as versões fixadas de verdade nos `requirements` | `NO PLANO` |
| D-004 | Aceita | Seções 7, 9 e 11: **todos** os exemplos no estilo `Annotated[Tipo, Depends(...)]`; nenhum `= Depends(` pode sobrar | `NO PLANO` |
| D-005 | Aceita | Seção 6 ("Migrações"): comando com `--rev-id` | `NO PLANO` |
| D-006 | Aceita | Seção 5: árvore com os `__init__.py` de `tests/` | `NO PLANO` |
| D-007 | Aceita | Seção 9.1: descrever `Paginacao` e `obter_paginacao` | `NO PLANO` |
| D-008 | Aceita; mensagens nativas do Pydantic continuam em inglês | Seção 10: descrever `campo` e `mensagem` do 422 | `NO PLANO` |
| D-009 | Aceita | Seção 6: coluna "mensagem" na tabela de tradução de restrições | `NO PLANO` |
| D-010 | **Corrigir agora** | Ver "Correção 1" abaixo; atualizar a seção 9.1 | `RESOLVIDA` |
| D-011 | **Corrigir agora** | Ver "Correção 2" abaixo; atualizar as seções 5 e 10 | `RESOLVIDA` |
| D-012 | Aceita | Seções 9.2 e 10: contratos `UsuarioResposta`, `UsuarioLogadoResposta`, `LoginResposta`, `ResultadoDoLogin` | `NO PLANO` |
| D-013 | Aceita (a assinatura é a do PLANO; uma `dataclass` só para isso seria classite) | Seção 3: registrar `criar_credencial` como exceção aceita à regra dos 5 parâmetros | `NO PLANO` |
| D-014 | Aceita (`LookupError` = inconsistência interna, não erro do usuário) | Seção 9.2: dizer isso na descrição das duas funções | `NO PLANO` |
| D-015 | Aceita | Seção 8: RN-08 também em `identidade.servico` | `NO PLANO` |
| D-016 | Aceita | Seção 7: código de referência de `senhas.py` igual ao real | `NO PLANO` |
| D-017 | Aceita | Seção 7: `tokens.py` igual ao real | `NO PLANO` |
| D-018 | Aceita | Seção 7: fluxo do login igual ao real | `NO PLANO` |
| D-019 | Aceita | Nada no PLANO | `ACEITA` |
| D-020 | Aceita | Nada no PLANO | `ACEITA` |
| D-021 | Aceita | Seção 12: descrever os helpers e o registro da fixture | `NO PLANO` |
| D-022 | Aceita | Nada | `ACEITA` |
| D-023 | Aceita por enquanto | Reavaliar na tarefa 07 | continua `ABERTA` |
| D-024 | Resolvida pelo grupo (suíte rodada no Windows e no CI) | Nada | `RESOLVIDA` |
| D-025 | Aceita: os commits são do próprio Marcos, que conduziu a tarefa; manter o trailer `Co-Authored-By` | Nada | `ACEITA` |
| D-027 | Aceita: cosmético, o git normaliza no commit | Nada | `ACEITA` |

## O que fazer

1. **Atualizar o `docs/PLANO.md`** conforme a tabela. Regra: em item aceito, **o PLANO passa a descrever o código real**, nunca o contrário. Mantenha o estilo do documento e não mexa em seções que a tabela não cita. No topo do PLANO, logo abaixo do título, acrescente: "Fonte da verdade: este arquivo no repositório. Quando ele e uma linha `ACEITA` de `docs/DECISOES.md` divergirem, vale a decisão até a próxima consolidação."
2. **Correção 1 (D-010): só dígitos ASCII.**
   - Em `app/compartilhado/validadores.py`, crie `so_digitos(texto: str) -> bool` (`texto.isascii() and texto.isdigit()`).
   - `FORMATO_CPF` com `[0-9]` no lugar de `\d`; `cpf_valido` e `numero_valido_para_cargo` usando `so_digitos`.
   - Procure outros `\d` e `isdigit()` no projeto (esquemas, padrões de título) e troque pelo equivalente ASCII.
   - Testes: CPF com dígitos arábico-índicos (`٢٩١٤١٧٧٧٦٣٨`) recusado em `cpf_valido` (unitário) e no login (integração, mesmo 401 genérico); `numero_valido_para_cargo("١٠", Cargo.PRESIDENTE)` falso.
3. **Correção 2 (D-011): erros do framework no formato padrão.**
   - Em `registrar_tratadores`, acrescente um tratador para `starlette.exceptions.HTTPException`: 404 → `ROTA_NAO_ENCONTRADA` ("Rota não encontrada."), 405 → `METODO_NAO_PERMITIDO` ("Método não permitido para esta rota."), qualquer outro status → `ERRO_HTTP`, sempre no formato `{"erro": {"codigo", "mensagem", "detalhes"}}`.
   - Acrescente os dois códigos ao catálogo da seção 10 do PLANO.
   - Testes: `GET /rota-que-nao-existe` → 404 `ROTA_NAO_ENCONTRADA`; `DELETE /health` → 405 `METODO_NAO_PERMITIDO`.
4. **`docs/DECISOES.md`:** mude **só a coluna "Status · ação"** de cada linha, conforme a tabela acima, acrescentando entre parênteses a seção atualizada (ex.: `NO PLANO (seção 7)`). Se esta tarefa gerar algo novo, acrescente linhas a partir de D-028.
5. **`CLAUDE.md`:**
   - Na lista de regras, acrescente: "12. Antes de começar uma tarefa, leia em `docs/DECISOES.md` todas as linhas com status `ABERTA` ou `ACEITA` que tocam os módulos da tarefa. Se o PLANO e uma dessas linhas divergirem, siga a linha e avise no resumo."
   - No passo 7 do fluxo, peça para listar as decisões novas **ordenadas por impacto** (Alto, Médio, Baixo).
6. **`docs/prompts/README.md`:** na tabela "Ordem das tarefas", acrescente a linha `02b` entre 02 e 03, e uma seção curta "Rodada de consolidação" explicando que, a cada 2 ou 3 tarefas (ou sempre que surgir decisão de impacto Médio ou Alto), roda-se o `EXTRA-consolidar-decisoes.md`.
7. **`docs/prompts/PROGRESSO.md`:** acrescente e marque a linha "02b — Consolidação das decisões 00 a 02".

## Não faça nesta tarefa

- Nada das tarefas 03 em diante.
- Nenhuma mudança de comportamento além das correções 1 e 2.

## Pronto quando

- `ruff check`, `ruff format --check` e `pytest` verdes.
- No `docs/PLANO.md`, a busca por `= Depends(` não encontra nada.
- Em `docs/DECISOES.md`, a única linha `ABERTA` de D-001 a D-027 é a D-023.

## Commits

1. `fix(compartilhado): aceita apenas dígitos ASCII em CPF e números (D-010)`
2. `feat(compartilhado): padroniza erros 404 e 405 do framework (D-011)`
3. `docs(plano): incorpora as decisões D-001 a D-027`
4. `docs: atualiza status das decisões, CLAUDE.md e prompts` (inclui o PROGRESSO)
