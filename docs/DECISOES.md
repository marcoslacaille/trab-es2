# Registro de decisões fora do PLANO

Este arquivo guarda tudo o que foi feito e **não estava prescrito** no `docs/PLANO.md` nem no arquivo da tarefa: lacunas que o agente preencheu, desvios do PLANO, extras, conflitos e riscos percebidos. Serve para o grupo fazer, depois, uma análise minuciosa: o que foi criado, o que falta e o que o PLANO precisa passar a dizer.

**Regra de uso:** o agente acrescenta uma linha aqui sempre que, durante uma tarefa, fizer algo desse tipo (a regra está no `CLAUDE.md`). Linhas antigas nunca são apagadas nem reescritas: quando o grupo decide, só muda a coluna **Status · ação**. O próximo ID é o seguinte ao último da tabela.

## Como ler

| Tipo | Significa |
| --- | --- |
| LACUNA | O PLANO não diz nada sobre isso e o agente escolheu um caminho. |
| DESVIO | O código faz diferente do que o PLANO mostra (e a linha diz por quê). |
| EXTRA | Algo criado que o PLANO e a tarefa não prescrevem. |
| CONFLITO | Duas partes do PLANO se contradizem. |
| RISCO | Fragilidade ou defeito percebido, que não é escolha de design. |
| AMBIENTE | Sobre ferramentas, ambiente ou processo; não é código do produto. |

**Impacto:** Baixo (detalhe interno), Médio (muda contrato da API, regra ou tarefas futuras), Alto (pode bloquear a entrega ou invalidar uma regra de negócio).

**Status:** `ABERTA` (o grupo ainda não revisou), `ACEITA` (revisada, vale como está), `NO PLANO` (o PLANO já foi atualizado; nada a fazer), `RESOLVIDA` (já corrigido, nada pendente).

## Registro

| ID | Tarefa | Tipo | Impacto | O que foi feito e por quê | Onde | Status · ação |
| --- | --- | --- | --- | --- | --- | --- |
| D-001 | 00 | DESVIO | Baixo | A fixture `banco_limpo` descobre as tabelas do schema `public` (todas, menos `alembic_version`) e só faz `TRUNCATE` se houver alguma. O PLANO (seção 12) mostra uma lista fixa `TABELAS`. Assim a fixture funciona desde a tarefa 00, quando ainda não existe tabela. | `tests/integracao/conftest.py` | ABERTA · atualizar o exemplo da seção 12 |
| D-002 | 00 | DESVIO | Baixo | A fixture `relogio` nascia sem ligar o `RelogioDeTeste` à aplicação. Corrigido na tarefa 01 com `app.dependency_overrides[obter_agora]`, como na seção 12. | `tests/integracao/conftest.py` | RESOLVIDA |
| D-003 | 00 | DESVIO | Baixo | Acrescentado `[tool.ruff.format] exclude = ["*.md"]`: o ruff 0.17.6 também formata blocos de código dentro de `.md`, e o `ruff format --check .` falhava por causa do `docs/PLANO.md`. | `pyproject.toml` | ABERTA · atualizar o `pyproject.toml` da seção 4 |
| D-004 | 00 | DESVIO | Baixo | As rotas e dependências usam `Annotated[Session, Depends(obter_sessao)]`, porque o ruff acusa B008 no estilo `= Depends(...)`, que ainda aparece nas seções 7 e 9 do PLANO. | rotas e dependências de todos os módulos | ABERTA · atualizar os exemplos das seções 7 e 9 |
| D-005 | 00 | LACUNA | Baixo | O Alembic só gera `0001_...` se o número for passado: `python -m alembic revision --autogenerate --rev-id 0001 -m "identidade"` (o `file_template` do `alembic.ini` já é `<número>_<descrição>`). | `alembic.ini` | ABERTA · acrescentar o comando na seção 6 ("Migrações") |
| D-006 | 00 | EXTRA | Baixo | `tests/` e suas subpastas têm `__init__.py`, para `tests/auxiliares.py` poder ser importado e para não haver conflito entre arquivos de mesmo nome em pastas diferentes. | `tests/**/__init__.py` | ABERTA · acrescentar à árvore da seção 5 |
| D-007 | 01 | LACUNA | Baixo | `Paginacao` (o PLANO só cita o nome) é uma `dataclass` com `pagina`, `tamanho` e a propriedade `deslocamento` (`(pagina - 1) * tamanho`), mais a dependência `obter_paginacao`. | `compartilhado/paginacao.py` | ABERTA · descrever na seção 9.1 |
| D-008 | 01 | LACUNA | Médio | Erro 422, `detalhes.campos`: `campo` é o `loc` do Pydantic sem o prefixo `body`/`query`/`path`, unido por ponto; `mensagem` é o `msg` sem o prefixo "Value error, ". As mensagens nativas do Pydantic continuam em inglês (ex.: "Field required"). Faz parte do contrato da API. | `compartilhado/erros.py` | ABERTA · descrever na seção 10; decidir se traduz as mensagens nativas |
| D-009 | 01 | DESVIO | Baixo | `ERROS_POR_RESTRICAO` guarda uma `TraducaoDeRestricao` (código, status e mensagem em português) por restrição. A tabela da seção 6 só tem código e HTTP, e o corpo do erro precisa de mensagem. | `compartilhado/erros.py` | ABERTA · acrescentar a mensagem à tabela da seção 6 |
| D-010 | 01 | RISCO | Médio | `FORMATO_CPF` usa `\d`, que em Python casa dígitos de outros alfabetos. Verificado na tarefa 02: o CPF `٢٩١٤١٧٧٧٦٣٨` passa por `normalizar_cpf` e `cpf_valido`, e só o `ck_usuarios_cpf_digitos` do banco o recusa (`IntegrityError`). A API devolveria o 409 genérico `CONFLITO_DE_DADOS` em vez de 422 `CPF_INVALIDO`. Os dados ficam protegidos, mas o erro devolvido é o errado. | `compartilhado/validadores.py` | ABERTA · decidir usar `re.ASCII` ou `[0-9]` na seção 9.1 e cobrir com teste |
| D-011 | 01 | RISCO | Médio | Erros do próprio FastAPI (rota inexistente 404, método não permitido 405) respondem `{"detail": ...}`, fora do formato padrão de erro. O PLANO manda só 4 tratadores. | `app/main.py`, `compartilhado/erros.py` | ABERTA · decidir se acrescenta um tratador para `HTTPException` |
| D-012 | 02 | LACUNA | Médio | Contratos que o PLANO não define: `UsuarioResposta` (`id`, `nome`, `perfil`; vai dentro do login), `UsuarioLogadoResposta` (acrescenta `cpf`; resposta do `GET /auth/me`) e `LoginResposta`. `autenticar` devolve a `dataclass` `ResultadoDoLogin` (`access_token`, `expira_em`, `usuario`). Incluir o `cpf` no `/auth/me` foi proposto pelo agente e aprovado em conversa. | `identidade/esquemas.py`, `identidade/dominio.py` | ABERTA · descrever nas seções 9.2 e 10 |
| D-013 | 02 | CONFLITO | Médio | `criar_credencial(sessao, cpf, nome, senha, perfil, agora)` tem 6 parâmetros, e a seção 3 manda no máximo 5 (acima disso, agrupar em `dataclass`). Foi mantida a assinatura da seção 9.2, que as tarefas 03 e 04 vão chamar. | `identidade/servico.py` | ABERTA · decidir antes da tarefa 03 |
| D-014 | 02 | LACUNA | Médio | O PLANO não diz o que `atualizar_credencial` e `remover_credencial` fazem com um id inexistente. Levantam `LookupError` (vira 500 `ERRO_INTERNO`), porque quem chama já conhece o usuário e a ausência seria inconsistência. Nenhum código novo entrou no catálogo de erros. | `identidade/servico.py` | ABERTA · decidir se vira `NaoEncontrado` ou fica |
| D-015 | 02 | DESVIO | Baixo | A RN-08 (nome de 3 a 120 caracteres) também é conferida no serviço (`criar_credencial`, `atualizar_credencial`), e o nome é gravado sem os espaços das pontas. O PLANO põe a RN-08 só nos esquemas. Motivo: o script `criar_chefe` não passa por esquema, e sem isso um nome inválido viraria `IntegrityError` do banco. | `identidade/servico.py` | ABERTA · aceitar ou mover a regra |
| D-016 | 02 | DESVIO | Médio | No código de referência de `senhas.py` (seção 7), o bcrypt 5 levanta `ValueError` para senha com mais de 72 bytes (verificado em `hashpw` e `checkpw`). No login isso viraria 500 e mudaria o tempo de resposta. `senha_confere` agora devolve `False` nesse caso, gastando o tempo de uma comparação. | `identidade/senhas.py` | ABERTA · corrigir o código de referência da seção 7 |
| D-017 | 02 | DESVIO | Baixo | `ler_token_acesso` também converte `ValueError` (do `int(sub)`) em `TOKEN_INVALIDO`; no PLANO só `InvalidTokenError`. | `identidade/tokens.py` | ABERTA · aceitar ou atualizar a seção 7 |
| D-018 | 02 | DESVIO | Baixo | `autenticar` confere a senha contra o hash fictício também quando o CPF vem mal formatado (o PLANO só cita o CPF inexistente), para as duas falhas levarem tempo parecido. | `identidade/servico.py` | ABERTA · aceitar ou atualizar a seção 7 |
| D-019 | 02 | EXTRA | Baixo | `listar_usuarios`: `%`, `_` e `\` digitados no filtro de nome valem como texto (escapados no `ILIKE`), e a ordenação desempata por `id` (o PLANO diz só "por nome"). | `identidade/repositorio.py` | ABERTA |
| D-020 | 02 | LACUNA | Baixo | `criar_chefe`: a idempotência vem de tratar `CPF_JA_CADASTRADO` (o serviço não tem consulta pública por CPF). Se o CPF já existir com outro perfil, nada é alterado e a mensagem não distingue os casos. A mensagem de sucesso imprime nome e CPF (nunca a senha). Sai com código 1 se faltar `CHEFE_CPF` ou `CHEFE_SENHA`, ou se os dados forem inválidos. | `app/scripts/criar_chefe.py` | ABERTA |
| D-021 | 02 | EXTRA | Baixo | Helpers de teste: `criar_chefe(cpf, senha, agora_)` aceita parâmetros opcionais; `gerar_cpf` evita CPF de dígitos repetidos; a fixture `cabecalho_chefe` fica em `tests/auxiliares.py` (como no PLANO) e é registrada por um import em `tests/integracao/conftest.py`, porque o pytest só descobre fixtures de `conftest.py` ou importadas. | `tests/auxiliares.py`, `tests/integracao/conftest.py` | ABERTA · acrescentar à seção 12 |
| D-022 | 02 | EXTRA | Baixo | Testes além dos obrigatórios: senha acima de 72 bytes (TU-08), CPF com pontuação (TI-01) e CPF mal formatado (TI-03). | `tests/unitarios/test_identidade.py`, `tests/integracao/test_auth_api.py` | ABERTA |
| D-023 | 02 | LACUNA | Baixo | TU-12: o módulo de votação ainda não existe, então o token de cédula é montado à mão com `jwt.encode` e `aud="eleicao-api:cedula"`. | `tests/unitarios/test_identidade.py` | ABERTA · na tarefa 07, avaliar trocar pelo emissor real de cédula |
| D-024 | 02 | AMBIENTE | Médio | A verificação da tarefa 02 rodou numa VM Linux (Python 3.12.15, PostgreSQL 16.2 sem Docker), e não no Windows com Docker (`postgres:16-alpine`). Tudo fora do repositório: o script `~/rodar.sh` sobe o Postgres, roda o comando e o desliga. A suíte inteira passou lá, mas o grupo ainda não a rodou no ambiente oficial. | fora do repositório | ABERTA · rodar `ruff` e `pytest` no Windows, ou deixar o CI rodar, antes do merge |
| D-025 | 02 | AMBIENTE | Médio | Os commits da tarefa 02 foram feitos com a identidade de Marcos Lacaille (copiada do histórico), por variáveis de ambiente e sem alterar a configuração do git. Todos têm o trailer `Co-Authored-By: Claude`. O PLANO manda cada membro commitar com o próprio usuário. | histórico da branch `feat/identidade` | ABERTA · se quiserem outra autoria, reescrever antes do merge |
| D-026 | 02 | AMBIENTE | Baixo | Foi liberada a exclusão de arquivos na pasta do projeto durante a sessão. Usada só para apagar travas e temporários que o git deixou em `.git`; nenhum arquivo do projeto foi apagado. | `.git` | RESOLVIDA |
| D-027 | 02 | AMBIENTE | Baixo | Os arquivos novos foram criados com fim de linha LF, e os que já existiam estão em CRLF (git com `autocrlf` no Windows). O git normaliza no commit, então o histórico não é afetado, mas o editor pode mostrar mistura. | `app/identidade/*`, `app/scripts/*`, `tests/*` | ABERTA · decidir se adota um `.gitattributes` |

## O que existe mas ainda não tem teste

Cobertura medida em 20/11/2026, ao fim da tarefa 02: `app/identidade` 78% (o `dominio.py` tem 100%; a meta do PLANO é 90% nos `dominio.py` e 85% no total do projeto).

| Item | Onde | Quando será coberto |
| --- | --- | --- |
| `exige_perfil` e o 403 `PERFIL_NAO_AUTORIZADO` | `identidade/dependencias.py` | Nas rotas protegidas por perfil a partir da tarefa 03, e no TI-08 (tarefa 11) |
| Script `criar_chefe` (0%) | `app/scripts/criar_chefe.py` | Nenhum teste está prescrito. Foi verificado à mão (criar, repetir, senha curta, CPF inválido, variável ausente). Decidir se vale um teste |
| `atualizar_credencial`, `listar_usuarios`, `obter_usuarios`, nome inválido, `LookupError` | `identidade/servico.py`, `identidade/repositorio.py` | Tarefas 03 e 04 (eleitores e candidatos usam essas funções) |

## Adiado de propósito

| Item | Motivo |
| --- | --- |
| Limite de tentativas de login | A tarefa 02 o proíbe (extra opcional, seção 13 do PLANO) |
| Rotas de eleitores e candidatos | Tarefas 03 e 04; o TI-07 apaga o usuário pelo serviço de identidade |

## Roteiro para a análise do grupo

1. Filtrar o Status `ABERTA` e ordenar por Impacto (Médio e Alto primeiro).
2. Para cada linha: aceitar (`ACEITA`), pedir mudança no código, ou atualizar o PLANO (`NO PLANO`).
3. Conferir as duas seções de cima: o que existe sem teste e o que foi adiado de propósito.
4. Sugestão: antes da entrega, nenhuma linha `ABERTA` de impacto Médio ou Alto.
