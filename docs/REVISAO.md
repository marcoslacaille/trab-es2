# Revisão final

Auditoria do projeto contra o enunciado e o checklist da seção 18 do PLANO, feita sobre a `main` no commit `814fe24` (tag `v1.0.0`). As correções estão na coluna **Situação** da seção 7. Os achados abaixo descrevem o estado antes das correções.

## 1. Resumo

- **Nenhum item "bloqueia a entrega" foi encontrado.** Há 1 item "deveria corrigir" (integrantes no README, já registrado em D-120), 4 de baixo risco ("deveria corrigir" ou "cosmético") e itens que dependem do grupo (autoria, revisão cruzada, ensaios, GitHub Pages).
- As 33 rotas existem, as 58 RNs estão implementadas e testadas, os 109 testes com ID do PLANO (TU-01 a 31, TI-01 a 74, TA-01 a 04) existem e passam.
- `ruff`, `pytest` (507 testes), `alembic downgrade base` + `upgrade head` e o roteiro da demonstração passaram do zero.

## 2. Resultados das verificações

| Verificação | Resultado |
| --- | --- |
| `ruff check .` | Sem avisos ("All checks passed!") |
| `ruff format --check .` | 104 arquivos já formatados |
| `pytest --cov=app --cov-report=term-missing` | **507 passed**, 2 warnings (ver P-05) |
| Cobertura total | **97%** (2.081 instruções, 63 não cobertas; meta: 85%) |
| Cobertura dos `dominio.py` | **100%** em todos (`apuracao`, `candidatos`, `eleicoes`, `eleitores`, `identidade`, `votacao`, `compartilhado`; meta: 90%) |
| Linhas sem cobertura | Só `scripts/seed_demo.py` (0%, 60 linhas) e `scripts/exportar_openapi.py` (67%, 4 linhas); o `exportar_openapi` é exercido pelo TA-03 e o `seed_demo` não tinha teste automático (só a verificação manual desta revisão), ver P-06 |
| `alembic upgrade head` / `downgrade base` / `upgrade head` num banco novo (`revisao`, já removido) | Os três funcionaram. Depois do `downgrade base` só restou a tabela `alembic_version`, sem tabelas, tipos ou funções soltas |
| `\d votos`, `\d eleicoes`, `\d registros_votacao` no psql | FK composta `fk_votos_candidatura_id_candidaturas (candidatura_id, eleicao_id, cargo)`, índice parcial `uq_eleicoes_uma_aberta`, `uq_eleicoes_data_turno`, `CHECK`s de janela e de status coerente, seção `Triggers` presente nas duas tabelas de votação |
| `seed_demo` do zero | Rodou sem erro e imprimiu a tabela de logins; a segunda execução não altera nada ("já existem") |
| Roteiro do `docs/DEMO.md` do zero (migrações, seed, uvicorn, requisições reais) | Abertura 200, 3 votos registrados e confirmados (201), Chefe votando 403, parcial 200, resultado com eleição aberta 409, encerramento 200, resultado final 200 (comparecimento 6 aptos, 2 votantes, 4 abstenções). Sem erros no log do servidor. O roteiro completo, passo a passo, também é o TI-74 |
| Segredos | `.env` fora do Git (no `.gitignore`; nunca esteve no histórico), só `.env.example` versionado. Únicas senhas no código: as de demonstração do `seed_demo` (documentadas, intencionais) |
| CI na `main` | Verde nos dois últimos pushes (#17 e #18) |
| Tag `v1.0.0` | Existe (anotada) e aponta para a `main` atual |

## 3. Matriz de rastreabilidade (seção 18)

Rotas: o OpenAPI gerado tem **34 operações** (33 de negócio + `/health`); todas com `summary` e descrição e com respostas de erro (401/403/404/409/422 conforme a rota). Todos os 109 IDs de teste do PLANO existem nos docstrings de `tests/`.

| Exigência | Rotas existem | RNs implementadas e citadas | Testes existem e passam |
| --- | --- | --- | --- |
| 1. Login dos 3 perfis | OK | OK (RN-01, 02, 05, 06) | OK (TU-07 a 12, TI-01 a 07) |
| 1. Funcionalidades por perfil | OK | OK (RN-03) | OK (TI-08, TA-02) |
| 2. Cadastrar eleição | OK | OK (RN-10 a 12, 14) | OK (TU-13, 15, TI-09 a 11) |
| 2. Abrir e encerrar | OK | OK (RN-10, 13, 15 a 18) | OK (TU-14, 16, TI-12 a 16) |
| 2. Consultar situação | OK | OK (RN-19) | OK (TU-18, TI-09, 17) |
| 3. CRUD de eleitores | OK | OK (RN-20 a 25) | OK (TU-05, TI-18 a 26) |
| 4. CRUD de candidatos e partidos | OK | OK (RN-30 a 33) | OK (TI-27 a 29) |
| 4. Candidaturas | OK | OK (RN-40 a 47) | OK (TU-06, 17, TI-30 a 37) |
| 5. Consultar candidatos por cargo | OK (`/cedula`) | OK (RN-55) | OK (TI-38) |
| 5. Registrar e confirmar o voto | OK | OK (RN-56 a 58) | OK (TU-21 a 24, TI-39 a 41, 54) |
| 5. Eleição não aberta | OK | OK (RN-51, 52) | OK (TU-19, TI-45, 52) |
| 5. Quem não é eleitor | OK | OK (RN-50, 53) | OK (TU-20, TI-46, 50) |
| 5. Um voto por cargo | OK | OK (RN-54) | OK (TI-42, 43, 65, 73) |
| 5. Voto confirmado imutável | OK (não existe rota; trigger) | OK (RN-59) | OK (TI-42, 63, 64) |
| Sigilo | — | OK (RN-60, 61) | OK (TI-53, 69 a 72) |
| 6. Eleitor vê todos os cargos | OK | OK (RN-71) | OK (TI-58) |
| 6. Candidato vê só o próprio cargo | OK | OK (RN-72) | OK (TI-57) |
| 6. Contagem atualizada | OK | OK (RN-74, 75) | OK (TU-26, TI-55) |
| 7. Resultado final | OK | OK (RN-70, 73 a 79) | OK (TU-25 a 31, TI-59 a 62) |
| Banco: tabelas, chaves, restrições | — | — | OK (TI-63 a 69) |
| Estrutura modular | — | — | OK (TA-01) |
| Testes unitários e de integração | — | — | OK (507) |
| Versionamento coerente | — | — | CI verde |
| Documentação Swagger | OK (`/docs`, `docs/openapi.json`) | — | OK (TA-03, TA-04); Pages: ver P-03 |
| Demonstração no Postman | OK (`docs/colecao-postman.json`) | — | OK (TI-74) |

## 4. Catálogo de RNs: onde está cada uma

As 58 RNs (RN-01 a 08, 10 a 19, 20 a 25, 30 a 33, 40 a 47, 50 a 61, 70 a 79) têm código citado em docstring de função em `app/` e em pelo menos um teste. Única exceção de forma: a **RN-04** é citada só no docstring do módulo `scripts/criar_chefe.py` (não no da função `criar_chefe`) e o PLANO não lhe atribui teste com ID (P-04). A tabela foi gerada por varredura com `ast` dos docstrings; a RN-71 aparece nas faixas "RN-70 a RN-72".

| RN | Implementação (arquivo: função com a RN na docstring) | Testes (IDs) | Nº de testes com a RN |
| --- | --- | --- | --- |
| RN-01 | identidade/senhas.py:hash_ficticio; identidade/senhas.py:senha_confere; identidade/servico.py:autenticar | TI-01, TI-02, TI-03, TU-08 | 7 |
| RN-02 | identidade/dependencias.py:obter_usuario_atual; identidade/servico.py:remover_credencial; identidade/tokens.py:criar_token_acesso (+1) | TI-05, TI-06, TI-07, TU-09, TU-10, TU-11, TU-12 | 7 |
| RN-03 | identidade/dependencias.py:exige_perfil; identidade/servico.py:atualizar_credencial | TA-01, TA-04, TI-08, TI-28 | 4 |
| RN-04 | docstring do módulo: compartilhado/log_requisicoes.py, scripts/criar_chefe.py (a função `criar_chefe` não cita) | docstring de `test_criar_chefe.py` (sem ID de TI no PLANO) | 2 |
| RN-05 | candidatos/servico.py:atualizar_candidato; candidatos/servico.py:cadastrar_candidato; eleitores/servico.py:atualizar_eleitor (+7) | TI-28, TU-07, TU-08 | 9 |
| RN-06 | identidade/dependencias.py:obter_usuario_atual | TA-02, TI-04, TI-08 | 7 |
| RN-07 | candidatos/servico.py:cadastrar_candidato; compartilhado/validadores.py:cpf_valido; compartilhado/validadores.py:normalizar_cpf (+3) | TI-01, TI-03, TI-18, TI-19, TI-28, TU-01, TU-02, TU-03, TU-04 | 15 |
| RN-08 | candidatos/servico.py:atualizar_candidato; candidatos/servico.py:cadastrar_candidato; eleitores/servico.py:atualizar_eleitor (+4) | sem ID no docstring (testa por nome) | 3 |
| RN-10 | eleicoes/servico.py:criar_eleicao | TI-09 | 4 |
| RN-11 | eleicoes/dominio.py:validar_agendamento; eleicoes/servico.py:criar_eleicao; eleicoes/servico.py:editar_eleicao | TU-13 | 8 |
| RN-12 | eleicoes/servico.py:_conferir_data_e_turno_livres; eleicoes/servico.py:criar_eleicao; eleicoes/servico.py:editar_eleicao | TI-10 | 2 |
| RN-13 | eleicoes/dominio.py:validar_abertura; eleicoes/dominio.py:validar_encerramento; eleicoes/servico.py:abrir_eleicao | TI-16, TU-14 | 5 |
| RN-14 | eleicoes/dominio.py:validar_edicao; eleicoes/servico.py:editar_eleicao | TI-11, TU-15 | 3 |
| RN-15 | eleicoes/dominio.py:validar_abertura; eleicoes/servico.py:abrir_eleicao | TI-12, TI-13, TI-14, TU-16 | 12 |
| RN-16 | eleicoes/dominio.py:validar_abertura | TI-15, TI-66, TU-16 | 5 |
| RN-17 | eleicoes/dominio.py:_validar_segundo_turno_completo; eleicoes/dominio.py:validar_abertura; eleicoes/servico.py:abrir_eleicao | TI-36, TU-16 | 4 |
| RN-18 | eleicoes/dominio.py:validar_encerramento; eleicoes/servico.py:encerrar_eleicao | TI-16, TU-14 | 5 |
| RN-19 | eleicoes/dominio.py:links_da_eleicao; eleicoes/esquemas.py:de_eleicao; eleicoes/servico.py:listar_eleicoes (+1) | TI-09, TI-17, TU-18 | 6 |
| RN-20 | eleitores/servico.py:cadastrar_eleitor; eleitores/servico.py:listar_eleitores; eleitores/servico.py:obter_eleitor | TI-18, TI-25 | 6 |
| RN-21 | eleitores/dominio.py:validar_titulo_eleitor; eleitores/servico.py:cadastrar_eleitor | TI-19 | 4 |
| RN-22 | compartilhado/validadores.py:calcular_idade; eleitores/dominio.py:validar_idade_eleitor; eleitores/servico.py:atualizar_eleitor (+1) | TI-20, TI-22, TU-05 | 8 |
| RN-23 | eleitores/servico.py:atualizar_eleitor | TI-21, TI-22 | 4 |
| RN-24 | eleitores/servico.py:excluir_eleitor | TI-23, TI-24 | 3 |
| RN-25 | eleitores/servico.py:obter_eleitor_logado | TI-26 | 3 |
| RN-30 | candidatos/servico.py:listar_candidatos; candidatos/servico.py:listar_partidos; candidatos/servico.py:obter_candidato (+1) | TI-27, TI-28, TI-29 | 11 |
| RN-31 | candidatos/dominio.py:validar_nascimento_do_candidato; candidatos/dominio.py:validar_nome_de_urna; candidatos/servico.py:atualizar_candidato (+1) | TI-28 | 12 |
| RN-32 | candidatos/dominio.py:validar_partido; candidatos/servico.py:criar_partido | TI-27 | 10 |
| RN-33 | candidatos/servico.py:atualizar_candidato; candidatos/servico.py:excluir_candidato | TI-28, TI-29 | 4 |
| RN-40 | eleicoes/dominio.py:validar_edicao; eleicoes/servico.py:_eleicao_editavel; eleicoes/servico.py:criar_candidatura (+3) | TI-30, TI-35 | 7 |
| RN-41 | eleicoes/servico.py:criar_candidatura | sem ID no docstring (testa por nome) | 1 |
| RN-42 | compartilhado/dominio.py:numero_valido_para_cargo; eleicoes/dominio.py:validar_candidatura; eleicoes/servico.py:_conferir_regras_da_candidatura (+1) | TI-31, TI-68, TU-06 | 7 |
| RN-43 | eleicoes/repositorio.py:existe_numero_no_cargo; eleicoes/servico.py:_conferir_numero_livre; eleicoes/servico.py:_conferir_regras_da_candidatura (+1) | TI-32 | 4 |
| RN-44 | eleicoes/repositorio.py:existe_candidatura_do_candidato; eleicoes/servico.py:criar_candidatura | TI-33 | 1 |
| RN-45 | eleicoes/dominio.py:validar_candidatura; eleicoes/servico.py:_conferir_regras_da_candidatura; eleicoes/servico.py:criar_candidatura | TI-36, TU-17 | 7 |
| RN-46 | candidatos/servico.py:obter_partido; eleicoes/servico.py:_conferir_candidato; eleicoes/servico.py:_conferir_partido (+1) | TI-34 | 2 |
| RN-47 | eleicoes/servico.py:candidaturas_do_usuario | TI-37 | 4 |
| RN-50 | votacao/servico.py:obter_cedula; votacao/servico.py:registrar_voto | TI-38, TI-46 | 3 |
| RN-51 | votacao/dominio.py:validar_pode_votar; votacao/servico.py:_eleitor_apto_a_votar; votacao/servico.py:registrar_voto | TI-45, TU-19 | 3 |
| RN-52 | votacao/dominio.py:validar_pode_votar; votacao/servico.py:_eleitor_apto_a_votar; votacao/servico.py:registrar_voto | TI-52, TU-19 | 4 |
| RN-53 | votacao/dominio.py:validar_eleitor_apto; votacao/servico.py:_eleitor_apto_a_votar; votacao/servico.py:obter_cedula (+1) | TI-50, TU-20 | 4 |
| RN-54 | votacao/repositorio.py:inserir_registro; votacao/servico.py:confirmar_voto; votacao/servico.py:registrar_voto | TI-42, TI-43, TI-44, TI-65, TI-73 | 7 |
| RN-55 | votacao/servico.py:obter_cedula; votacao/servico.py:registrar_voto | TI-38, TI-51 | 2 |
| RN-56 | votacao/cedulas.py:emitir_cedula; votacao/servico.py:confirmar_voto; votacao/servico.py:registrar_voto | TI-39, TI-41, TI-54 | 3 |
| RN-57 | votacao/cedulas.py:emitir_cedula; votacao/cedulas.py:ler_cedula; votacao/servico.py:confirmar_voto (+1) | TI-47, TI-48, TI-49, TU-12, TU-22, TU-23, TU-24 | 12 |
| RN-58 | votacao/dominio.py:resolver_escolha; votacao/servico.py:registrar_voto | TI-39, TI-40, TI-41, TU-21 | 8 |
| RN-59 | votacao/servico.py:confirmar_voto | TI-42, TI-63, TI-64 | 4 |
| RN-60 | votacao/cedulas.py:emitir_cedula; votacao/repositorio.py:inserir_voto; votacao/servico.py:confirmar_voto | TI-41, TI-67, TI-69, TI-70, TI-71, TI-72 | 8 |
| RN-61 | votacao/repositorio.py:cargos_votados; votacao/servico.py:obter_cedula; votacao/servico.py:obter_participacao | TI-38, TI-53 | 4 |
| RN-70 | apuracao/servico.py:_exigir_status; apuracao/servico.py:apuracao_parcial; apuracao/servico.py:resultado_final | TI-56, TI-59 | 2 |
| RN-71 | apuracao/servico.py:apuracao_parcial (citada como "RN-70 a RN-72") | TI-58 | 1 |
| RN-72 | apuracao/servico.py:_cargo_do_candidato; apuracao/servico.py:apuracao_parcial | TI-57 | 1 |
| RN-73 | apuracao/servico.py:resultado_final | TI-60 | 1 |
| RN-74 | apuracao/servico.py:apuracao_parcial; votacao/repositorio.py:contar_votos; votacao/servico.py:contar_votos | TI-55, TI-60 | 4 |
| RN-75 | apuracao/dominio.py:apurar_cargo | TI-60, TU-26 | 2 |
| RN-76 | apuracao/dominio.py:apurar_cargo; apuracao/dominio.py:percentual | TI-60, TU-25, TU-27 | 3 |
| RN-77 | apuracao/dominio.py:apurar_cargo; apuracao/dominio.py:definir_mais_votado | TI-61, TU-28, TU-29, TU-30 | 4 |
| RN-78 | apuracao/dominio.py:apurar_cargo; apuracao/dominio.py:definir_mais_votado | TU-31 | 1 |
| RN-79 | apuracao/servico.py:apuracao_parcial; apuracao/servico.py:resultado_final; eleitores/servico.py:contar_aptos (+1) | TI-62 | 1 |

## 5. Checklist da seção 18

| Item | Situação |
| --- | --- |
| 33 rotas com `summary`, descrição, exemplos e erros | **OK**. Verificado no OpenAPI: 33 + `/health`, todas com `summary`, descrição e erros. Exemplos de corpo nos POST/PATCH; as respostas de leitura usam o exemplo dos esquemas. Ver P-07 (esquemas sem exemplo) |
| 58 RNs na docstring e em pelo menos um teste | **OK** (RN-04: ver P-04) |
| `ruff check` e `ruff format --check` | **OK** |
| `pytest` verde; 85% total e 90% nos `dominio.py` | **OK** (97% total, 100% nos `dominio.py`) |
| Testes de arquitetura verdes | **OK** (TA-01 a TA-04) |
| Nenhum segredo, `.env` fora do Git | **OK** |
| `alembic upgrade head` e `downgrade base` | **OK** |
| Trigger, índice parcial, FK composta | **OK** (conferido no psql) |
| `seed_demo` do zero | **OK** |
| `docs/openapi.json` atualizado (TA-03) e GitHub Pages no ar | **Parcial**: openapi atualizado (TA-03 verde); **Pages não está no ar** (repositório privado, D-114). Ver P-03 |
| README com como rodar, testar, arquitetura, modularização, modelagem | **OK** (ver P-02 e P-01) |
| `ARQUITETURA.md`, `MODELAGEM.md`, `DEMO.md` | **OK** |
| Coleção Postman em `docs/` | **OK** (`colecao-postman.json` e `ambiente-postman.json`) |
| Commits pequenos, no padrão, com autoria de todos | **Depende do grupo**: os 97 commits têm um único autor (Marcos Lacaille). Ver P-08 |
| PRs revisados por outro membro | **Depende do grupo**: os 18 PRs mergeados têm 0 revisões |
| Tag `v1.0.0` e CI verde na `main` | **OK** |
| Ensaios, condução individual, 37 perguntas | **Depende do grupo** |
| Link do repositório / da documentação / README com arquitetura | **OK** (a documentação da API depende de P-03) |

## 6. Outros achados da busca por problemas

Sem ocorrência: `print` esquecido fora dos scripts de linha de comando (que imprimem por desenho), `TODO`/`FIXME` (as buscas só casam "metodo"), `breakpoint`, imports não usados ou variáveis não usadas, `.env` no histórico, nomes de classes de padrão (`Service`, `Factory`, `Manager`), código desativado de verdade.

Fronteiras entre módulos: nenhum módulo importa modelo ou repositório de outro. Alguns serviços importam `dataclass`es de `dominio.py` de outro módulo (por exemplo `apuracao/servico.py` importa de `eleicoes.dominio` e `votacao.dominio`), o que a regra de fronteira da seção 5 não previa literalmente; o TA-01 e o PLANO (código da seção 9) aceitam, e a questão já está registrada na D-035 (ABERTA). Não é pendência nova.

## 7. Tabela de pendências

| ID | Gravidade | Pendência | Correção proposta | Situação |
| --- | --- | --- | --- | --- |
| P-01 | Deveria corrigir | README, linha "Integrantes: Marcos Lacaille e demais membros do grupo (completar antes da entrega)" (D-120). O PLANO não traz os nomes. | Faltam os nomes do grupo. Substituir a linha pelos nomes completos. Commit: `docs(readme): completa a lista de integrantes` | **Aberta**: faltam os nomes do grupo |
| P-02 | Cosmético | A numeração das seções do README começa em "2. Links" (não existe a "1"). | Renumerar para 1 a 11 (ou chamar o parágrafo de abertura de "1. Visão geral"). Commit: `docs(readme): corrige a numeração das seções` | Corrigida (b3c5cd4) |
| P-03 | Deveria corrigir | O checklist pede "GitHub Pages no ar", mas o repositório é privado (D-114). O README já explica e aponta para `docs/index.html` e `docs/openapi.json`. | Decisão do grupo: (a) tornar o repositório público e ativar Pages, ou (b) manter como está e a entrega usar o link do repositório mais `docs/openapi.json`. Sem alteração de código | **Aberta**: decisão do grupo |
| P-04 | Cosmético | RN-04 citada só no docstring do módulo `criar_chefe.py`, não no da função; o PLANO não lhe dá ID de teste. | Citar `RN-04` no docstring de `criar_chefe()`. Commit: `docs(identidade): cita a RN-04 na função criar_chefe` | Corrigida (2085258) |
| P-05 | Cosmético | 2 warnings no pytest: `StarletteDeprecationWarning` (httpx no `TestClient`, vem das bibliotecas) e `RuntimeWarning` de `runpy` em `test_executado_como_script_sai_com_o_codigo_da_funcao`. | O primeiro não é corrigível aqui (biblioteca). O segundo: não importar `app.scripts.criar_chefe` antes de executar via `runpy`/subprocesso no teste, ou aceitar o aviso. Alternativa: só documentar | Mantida: o aviso vem do próprio teste que cobre o `__main__`; documentada na D-125 |
| P-06 | Cosmético | `seed_demo.py` aparece com 0% e `exportar_openapi.py` com 67% de cobertura, embora sejam testados (subprocesso/TA-03). Um professor que olhe o relatório pode estranhar. | Documentar no README que os scripts rodam em subprocesso, ou excluí-los do medidor (`[tool.coverage] omit`). Preferência: só documentar | Corrigida de outro modo (d66a85b): o `seed_demo` não tinha teste; ganhou um e passou a 92% (total 99%) |
| P-07 | Cosmético | No Swagger, 8 esquemas sem exemplo (`CorpoDoErro`, páginas de eleitor e candidato, `LinkResposta`...) e dois `LinkResposta` com nomes técnicos (`app__eleicoes__esquemas__LinkResposta`). | Dar `json_schema_extra` de exemplo a `CorpoDoErro` e às páginas; unificar o `LinkResposta`. Exige regenerar o `openapi.json`. Opcional | Corrigida em parte (0cbe7b4): `CorpoDoErro` ganhou exemplo e o `LinkResposta` da votação virou `LinkDaVotacao`; as páginas de listagem ficam sem exemplo próprio (os itens têm) |
| P-08 | Depende do grupo | Histórico com um único autor e PRs sem revisão por outro membro. | Nada a corrigir no código. O grupo deve decidir como justificar (ou fazer commits e revisões dos demais antes da entrega) | **Aberta**: depende do grupo |
| P-09 | Cosmético | Ruff com regras extras (ERA001) acusa 4 comentários de separação (`# (sigla, nome, número)`, `# ---- partidos (TI-27)`) como "código comentado". Não são código. | Nenhuma ação (regra não faz parte da configuração do projeto) | Sem ação |

**Gravidade "bloqueia a entrega": nenhuma.**

## 8. Decisões a registrar em `docs/DECISOES.md` (a partir de D-124)

D-124 a D-127, registradas no commit final.
