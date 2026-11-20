# Como usar os prompts

O `docs/PLANO.md` é a especificação inteira, mas um agente não deve implementar tudo numa conversa só: o contexto fica enorme, ele começa a esquecer regras e o resultado piora. Por isso o trabalho foi dividido em **15 tarefas**, cada uma num arquivo deste diretório. Cada tarefa entrega uma parte funcionando, com testes verdes e commits próprios.

## Antes da primeira tarefa (uma vez só)

1. Instale: **Python 3.12**, **Git**, **Docker Desktop** e o **Claude Code**.
2. Abra o Docker Desktop e deixe rodando.
3. Abra o terminal (PowerShell) na pasta `trab-es2`.
4. Inicie o agente com o Sonnet: `claude --model sonnet` (ou, já dentro dele, `/model` e escolha Sonnet).

O `CLAUDE.md` da raiz é lido automaticamente pelo Claude Code em toda sessão. Ele tem as regras permanentes (idioma, fronteiras entre módulos, fluxo de cada tarefa). Se for usar outra ferramenta, cole o conteúdo do `CLAUDE.md` antes de cada tarefa.

## A cada tarefa

1. Comece uma sessão limpa: `/clear` no Claude Code (ou feche e abra de novo).
2. Abra o arquivo da tarefa, copie **tudo** e cole no agente.
3. O agente vai mostrar a lista de arquivos que pretende criar. Leia e responda "ok" (ou peça ajustes).
4. Acompanhe. Quando ele terminar, leia o resumo e **rode os testes você mesmo**: `.venv\Scripts\python.exe -m pytest`.
5. Leia o código gerado. Se não entender algo, use o prompt `EXTRA-explicar-codigo.md`. Lembre: a arguição é individual.
6. Integre a branch na `main`:
   - Com GitHub: `git push -u origin <branch>`, abra o Pull Request, outro membro revisa e aprova, faça o merge.
   - Sem GitHub ainda: `git switch main` e depois `git merge --no-ff <branch>`.
7. Só então passe para a próxima tarefa.

Se algo quebrar e o agente não resolver, use `EXTRA-corrigir-erro.md`.

## Depois da tarefa 00

Crie um repositório **vazio e público** no GitHub (público por causa do GitHub Pages da tarefa 12) e conecte:

```bash
git remote add origin https://github.com/<usuario>/<repositorio>.git
git push -u origin main
```

Cada membro deve commitar com o próprio usuário Git (`git config user.name` e `git config user.email`), para o histórico mostrar a contribuição de todos.

## Ordem das tarefas

| # | Arquivo | O que entrega | Fase do PLANO | Branch |
| --- | --- | --- | --- | --- |
| 00 | `00-fundacao.md` | Estrutura, dependências, Docker, Alembic, `/health`, CI | 0 | `chore/fundacao` |
| 01 | `01-compartilhado.md` | Erros padronizados, relógio, validadores, `Cargo`, paginação | 1 | `feat/compartilhado` |
| 02 | `02-identidade.md` | Usuários, login, JWT, perfis, script do Chefe | 2 | `feat/identidade` |
| 02b | `02b-consolidar-decisoes.md` | Consolida as decisões das tarefas 00 a 02: atualiza o PLANO e faz duas correções (dígitos ASCII, erros 404 e 405) | — | `docs/consolidar-decisoes-00-02` |
| 03 | `03-eleitores.md` | CRUD de eleitores | 3 | `feat/eleitores` |
| 04 | `04-candidatos-partidos.md` | CRUD de candidatos e cadastro de partidos | 4 | `feat/candidatos` |
| 05 | `05-eleicoes.md` | Eleições: cadastro, edição, abertura, encerramento, HATEOAS | 5 (parte 1) | `feat/eleicoes` |
| 06 | `06-candidaturas.md` | Candidaturas dentro da eleição; regras do 2º turno | 5 (parte 2) | `feat/candidaturas` |
| 07 | `07-votacao-base.md` | Tabelas de voto, trigger, regras puras, cédula assinada | 6 (parte 1) | `feat/votacao-base` |
| 08 | `08-votacao-api.md` | Cédula, registro e confirmação do voto pela API | 6 (parte 2) | `feat/votacao-api` |
| 09 | `09-sigilo-concorrencia.md` | Testes de sigilo, logs e voto simultâneo | 6 (parte 3) | `test/sigilo-concorrencia` |
| 10 | `10-apuracao.md` | Apuração parcial e resultado final | 7 | `feat/apuracao` |
| 11 | `11-qualidade.md` | Matriz de permissões, testes de arquitetura, fluxo completo, logs, refatoração | 8 | `test/qualidade` |
| 12 | `12-swagger-pages.md` | Swagger caprichado, `openapi.json`, GitHub Pages | 9 (parte 1) | `docs/swagger` |
| 13 | `13-seed-documentacao.md` | Dados de demo, README, ARQUITETURA, MODELAGEM, DEMO, coleção Postman | 9 (parte 2) | `docs/entrega` |
| 14 | `14-revisao-final.md` | Auditoria contra o checklist da seção 18 | Revisão | `chore/revisao-final` |

Prompts de apoio (use quando precisar):

- `EXTRA-explicar-codigo.md`: pede ao agente para explicar um módulo como numa arguição.
- `EXTRA-corrigir-erro.md`: para quando um teste ou comando falhar.
- `EXTRA-consolidar-decisoes.md`: rodada de consolidação das decisões (veja a seção abaixo).

## Rodada de consolidação

A cada 2 ou 3 tarefas (ou sempre que uma tarefa registrar uma decisão de impacto Médio ou Alto em `docs/DECISOES.md`), roda-se o `EXTRA-consolidar-decisoes.md` numa sessão nova. O agente lista as linhas `ABERTA` por impacto, o grupo decide cada uma, e só então o agente atualiza o PLANO, faz as correções aprovadas e muda o status das linhas. Cada rodada vira uma tarefa `NNb` (como a `02b`) e é integrada na `main` antes da tarefa seguinte.

## Divisão no grupo (seção 13 do PLANO)

| Membro | Tarefas |
| --- | --- |
| 1 | 00, 01, 02 |
| 2 | 03, 04 |
| 3 | 05, 06 |
| 4 | 07, 08, 09 |
| 5 | 10, 12, 13 |
| Todos | 11 e 14 (revisão cruzada) |

As tarefas são sequenciais: cada uma depende das anteriores estarem na `main`. Quem não está implementando no momento revisa o Pull Request de quem está.
