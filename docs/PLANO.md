# Plano do projeto — Sistema de Eleição Eletrônica (FastAPI + PostgreSQL)

Fonte da verdade: este arquivo no repositório. Quando ele e uma linha `ACEITA` de `docs/DECISOES.md` divergirem, vale a decisão até a próxima consolidação.

Versão de 19/11/2026

## 0. Como usar este documento

Este documento é a especificação completa do projeto. A **Parte A** (seções 1 a 15) é a especificação para implementar. A **Parte B** (seções 16 a 18) é para o grupo: roteiro da demo, arguição e checklist. O que foi feito diferente do que está aqui, ou que este documento não previa, fica registrado em `docs/DECISOES.md`.

### Regras de trabalho

1. Este documento é a especificação única. Não invente rotas, tabelas, campos ou regras que não estejam nele; se algo estiver ambíguo ou contraditório, decida com o grupo e registre em `docs/DECISOES.md`.
2. Implemente na ordem das fases da seção 13. Só comece uma fase quando a anterior estiver verde (`ruff check`, `ruff format --check` e `pytest` passando).
3. Ao fim de cada fase: rode os comandos de verificação, faça os commits listados na fase (Conventional Commits, em português) e resuma no PR os arquivos criados, as RNs implementadas e os testes adicionados.
4. Nunca enfraqueça uma regra de negócio nem um teste para fazê-lo passar.
5. Código, nomes, docstrings, mensagens de erro e commits em português (linguagem ubíqua da seção 2). Exceções: nomes de bibliotecas e palavras reservadas do Python.
6. Simplicidade acima de tudo: qualquer integrante precisa conseguir explicar qualquer função em 1 minuto. Sem metaprogramação, sem herança profunda, sem padrões desnecessários (Factory, Strategy, Interface + Implementação).
7. Toda regra de negócio tem um código RN-xx (seção 8). Cite o RN na docstring da função que a implementa e no nome ou na docstring do teste que a verifica.
8. Respeite as fronteiras entre módulos da seção 5.

### Como o grupo usa este documento

- Uma fase por vez. Leia o diff de cada fase antes de integrar e rode os testes.
- Cada membro será arguido sozinho: todos precisam ler o código de todos os módulos, não só o seu (seção 17).
- Quando quiser mudar uma decisão, mude primeiro aqui e depois no código. O documento e o código não podem divergir.

## 1. Contexto, escopo e decisões de projeto

Vamos construir uma API REST que simula uma eleição eletrônica com três perfis (Chefe da Seção, Eleitor e Candidato), organizada como **monólito modular** em Python + FastAPI + PostgreSQL, com testes unitários e de integração, histórico Git coerente e documentação Swagger. Trabalho da disciplina de Engenharia de Software II (Prof. Marcelo Soares Loutfi), em grupo de até 5 pessoas. Cada membro será arguido individualmente.

### Escopo: o que o sistema faz

1. Login de Chefe da Seção, Eleitor e Candidato, com funcionalidades separadas por perfil.
2. Chefe da Seção: cadastra, edita, abre, encerra e consulta eleições (data, turno, horários).
3. Chefe da Seção: CRUD de eleitores, CRUD de candidatos, cadastro de partidos e associação de candidato a eleição + cargo (candidatura).
4. Eleitor: consulta a cédula (candidatos por cargo), registra o voto e confirma o voto.
5. Eleitor acompanha a votação de todos os cargos; Candidato acompanha só o cargo que disputa.
6. Resultado final após o encerramento: votos por candidato e mais votado por cargo.
7. Tudo persistido em PostgreSQL: usuários, eleitores, candidatos, partidos, eleições, candidaturas, registros de votação e votos.

### Decisões de projeto

| # | Decisão | Escolha | Motivo | Alternativa descartada (e por quê) |
| --- | --- | --- | --- | --- |
| D01 | Arquitetura | Monólito modular organizado por domínio | O enunciado não exige distribuição; a aula 06 aponta menor complexidade operacional; fronteiras iguais às de bounded contexts | Microsserviços (rede, vários bancos, deploy) e camadas técnicas globais (toda mudança atravessa todas as camadas) |
| D02 | Banco | PostgreSQL 16 | Restrições, transações, índice parcial e trigger garantem as regras críticas | SQLite (concorrência fraca), MongoDB (o problema é relacional) |
| D03 | Acesso a dados | SQLAlchemy 2.0 **síncrono** + Alembic; rotas `def` | Mais fácil de ler, testar e explicar; desempenho não é gargalo nessa escala | Async (event loop, `await` e sessões assíncronas sem ganho real aqui) |
| D04 | Perfis | Exatamente um perfil por usuário | O enunciado define três tipos de usuário | Vários papéis por usuário (RBAC mais complexo) |
| D05 | Fluxo do voto | Duas etapas: registro devolve uma **cédula assinada** (token); confirmação grava | O banco nunca guarda eleitor e escolha juntos, nem por um segundo | Rascunho de voto numa tabela (liga eleitor à escolha até a confirmação) |
| D06 | Sigilo | Duas tabelas sem ligação: `registros_votacao` (quem votou em qual cargo) e `votos` (o quê, sem quem); voto com UUID aleatório e sem horário | Nenhuma tabela, rota ou resposta liga eleitor e voto (os limites para quem lê o banco direto estão na seção 6) | Tabela única com `eleitor_id`; coluna "anônimo" |
| D07 | Apuração | Calculada a cada consulta (`GROUP BY`) | Sempre atualizada, sem estado duplicado | Contadores incrementais ou cache (risco de divergência) |
| D08 | Abertura e encerramento | Manuais, pelo Chefe; os horários definem a janela permitida | O enunciado diz que só o Chefe abre e encerra | Agendador automático (mais peças, difícil de demonstrar) |
| D09 | Candidaturas | Parte do agregado **Eleição** (a eleição é a raiz) | Toda mudança passa pela raiz (aula 07); a regra "só com eleição AGENDADA" fica num lugar só | Candidatura dentro do módulo de candidatos (cria dependência circular entre módulos) |
| D10 | Relógio | Função `agora()` injetável | Testes de data e horário determinísticos | `datetime.now()` espalhado pelo código |
| D11 | Idioma do código | Português | Linguagem ubíqua: o código usa as palavras do enunciado | Inglês (tradução mental o tempo todo) |
| D12 | Versionamento da API | Prefixo `/api/v1` | Boa prática citada no material de Swagger | Sem versão |

### Regras complementares de realismo

Não estão no enunciado, mas deixam a simulação coerente com a eleição brasileira. Na apresentação, chame-as de **regras complementares definidas pelo grupo**.

- Quantidade de dígitos do número por cargo: Presidente 2, Governador 2, Senador 3, Deputado Federal 4, Deputado Estadual 5.
- Eleitor com pelo menos 16 anos.
- Voto em branco e voto nulo (número inexistente vira nulo, como na urna).
- Empate no mais votado: vence o candidato mais idoso.
- Segundo turno: só Governador e Presidente, com exatamente 2 candidatos por cargo.
- Só vota quem foi cadastrado antes da abertura da eleição ("previamente cadastrado").

### Fora do escopo (dizer isso com segurança se perguntarem)

- Frontend: a demonstração é feita no Postman ou Insomnia, como pede o enunciado.
- Várias seções, zonas ou UFs: o sistema simula **uma** seção.
- Regras de "eleito" (maioria absoluta, quociente eleitoral): o enunciado pede o **mais votado**.
- Geração automática do 2º turno a partir do 1º.
- Recuperação de senha, e-mail, HTTPS (responsabilidade do ambiente de deploy) e limite de tentativas de login (extra opcional, seção 13).

## 2. Linguagem ubíqua (glossário)

Estes termos são usados de forma idêntica no código, no banco, na API, nos testes e na apresentação. Nenhum sinônimo: se o glossário diz "candidatura", o código não diz "inscrição".

| Termo | No código | Significado |
| --- | --- | --- |
| Chefe da Seção | `Perfil.CHEFE_SECAO` | Administra o processo eleitoral: cadastra eleitores, candidatos, partidos e eleições; abre e encerra a votação. |
| Eleitor | `Eleitor`, `Perfil.ELEITOR` | Pessoa cadastrada que pode votar, uma vez por cargo em cada eleição. |
| Candidato | `Candidato`, `Perfil.CANDIDATO` | Pessoa que disputa um cargo; faz login para acompanhar a votação do seu cargo. |
| Usuário | `Usuario` | Credencial de acesso (CPF + senha + perfil). Todo eleitor, candidato e chefe tem um. |
| Partido | `Partido` | Agremiação com sigla, nome e número de 2 dígitos (10 a 99). |
| Eleição | `Eleicao` | Um pleito em uma data e um turno, com horário de abertura e de encerramento. Raiz do agregado que contém as candidaturas. |
| Turno | `turno` (1 ou 2) | Cada turno é uma eleição separada no sistema. |
| Situação da eleição | `StatusEleicao`: `AGENDADA`, `ABERTA`, `ENCERRADA` | Ciclo de vida, sempre nessa ordem, sem volta. |
| Janela de votação | `horario_abertura`, `horario_encerramento` | Intervalo do dia da eleição em que abrir e votar são permitidos. |
| Cargo | `Cargo` | `DEPUTADO_ESTADUAL`, `DEPUTADO_FEDERAL`, `SENADOR`, `GOVERNADOR`, `PRESIDENTE`. |
| Candidatura | `Candidatura` | Associação de um candidato a uma eleição, com cargo, partido e número. É nela que se vota. |
| Número | `numero` | Identificação eleitoral da candidatura, digitada pelo eleitor (texto só com dígitos). |
| Cédula | `Cedula` | Lista de cargos disputados e candidaturas de uma eleição, vista pelo eleitor. |
| Registro do voto | `registrar_voto` | 1ª etapa: o eleitor informa a escolha e recebe a prévia + o **token da cédula**. Nada é gravado. |
| Token da cédula | `token_cedula` | Token assinado e de curta duração que carrega a escolha até a confirmação. |
| Confirmação do voto | `confirmar_voto` | 2ª etapa: grava o voto de forma definitiva e irreversível. |
| Registro de votação | `RegistroVotacao` | Fato "este eleitor já votou para este cargo nesta eleição". Não diz em quem. |
| Voto | `Voto` | Escolha anônima: eleição, cargo, tipo e candidatura. Não diz quem votou. |
| Tipo de voto | `TipoVoto`: `NOMINAL`, `BRANCO`, `NULO` | Nominal = em uma candidatura; Nulo = número inexistente para o cargo. |
| Modo de escolha | `ModoEscolha`: `NUMERO`, `BRANCO` | O que o eleitor envia no registro: um número digitado ou a tecla BRANCO. |
| Votos válidos | `votos_validos` | Somente votos nominais. Brancos e nulos não são válidos. |
| Apuração parcial | `parcial` | Contagem durante a eleição ABERTA. |
| Resultado final | `resultado` | Contagem após o encerramento, com o mais votado de cada cargo. |
| Mais votado | `mais_votado` | Candidatura com mais votos nominais no cargo (desempate: mais idoso). Não significa "eleito". |
| Comparecimento | `comparecimento` | Eleitores aptos, eleitores que votaram em pelo menos um cargo e abstenção. |
| Eleitor apto | `aptos` | Eleitor cadastrado antes da abertura da eleição. |

## 3. Princípios de design obrigatórios

O código será avaliado com a régua da disciplina (Ousterhout nas aulas 02 a 05, Newman e DDD nas aulas 06 e 07). Cada princípio abaixo vira uma regra concreta no código, que o grupo deve saber apontar.

| Princípio (aula) | Regra no código | Onde aparece |
| --- | --- | --- |
| Tolerância zero à complexidade (02) | Nomes que dizem o que a coisa é. Proibido: `temp`, `aux`, `data2`, `x`, `processa()`. | Todo o projeto |
| Programação estratégica (02) | Ao fim de cada fase, uma rodada de refatoração antes do commit final (investimento contínuo de 10 a 20%). | Plano de fases |
| Módulos profundos (03) | Cada módulo expõe poucas funções públicas em `servico.py` e esconde muita lógica atrás delas. | `servico.py` de cada módulo |
| Evitar classite (03) | Funções e `dataclass` simples. Nada de uma classe por operação, nem Interface + Implementação para tudo. | Todo o projeto |
| Interface formal e informal (03) | Assinaturas tipadas (formal) + docstring com regras de uso e RN (informal). | Funções públicas |
| Ocultação de informação (04) | Só `identidade` conhece bcrypt e JWT de acesso. Só `votacao` conhece as tabelas de voto. Os outros módulos chamam funções, não tabelas. | Fronteiras de módulo |
| `private` não é ocultação (04) | Nunca devolver o modelo ORM na API; sempre um esquema de resposta explícito. Nada de getter e setter que só expõem campos. | `esquemas.py` |
| Sem flags de controle (04, 05) | Nenhuma função pública recebe booleano que muda o comportamento. `abrir_eleicao()` e `encerrar_eleicao()`, nunca `alterar_status(id, abrir=True)`. Escolhas viram enum (`ModoEscolha`). | Serviços e rotas |
| Sem decomposição temporal (04) | Organizar por responsabilidade (rotas, serviço, domínio, repositório), nunca por etapa ("passo1", "passo2"). | Estrutura de pastas |
| Baixo acoplamento (04, 06) | Nenhum módulo lê ou escreve tabela de outro (evita acoplamento de recurso comum e de conteúdo). Sem acoplamento de passagem: não repassar objetos que o módulo não usa. | Teste de arquitetura |
| Propósito geral (05) | Interfaces genéricas, implementações específicas. Um único `registrar_voto(cargo, modo, numero)` para todos os cargos; nunca `votar_presidente()`. | `votacao` |
| Especialização nas bordas (05) | Rotas e esquemas são específicos do HTTP; o domínio no meio é genérico. | Camadas |
| Lei de Conway (06) | A divisão de módulos espelha a divisão de trabalho do grupo. | Seção 13 |
| Bounded contexts (07) | Cada módulo é um contexto com vocabulário próprio. `Cargo` vive no núcleo compartilhado (shared kernel). | `app/compartilhado/dominio.py` |
| Agregados (07) | `Eleicao` é raiz; candidaturas só mudam pela eleição (`/eleicoes/{id}/candidaturas`). Entre agregados, referência por ID. | `eleicoes` |
| Regra de dependência (07) | Dependências apontam para dentro: rotas → serviço → domínio. `dominio.py` não importa FastAPI nem SQLAlchemy. | Teste de arquitetura |
| HATEOAS (07) | Respostas de eleição e de votação trazem `links` com as próximas ações possíveis. | `eleicoes`, `votacao` |
| Documentação como contrato (Swagger) | Code-first: a spec OpenAPI sai do código; toda rota documenta respostas de erro e tem exemplos reais. | Seção 11 |

### Regras de estilo

- Funções com no máximo \~40 linhas e no máximo 5 parâmetros; acima disso, agrupe em uma `dataclass`.
  - Exceção aceita (D-013): `identidade.servico.criar_credencial(sessao, cpf, nome, senha, perfil, agora)` tem 6 parâmetros. A assinatura é a da seção 9.2, chamada pelos módulos `eleitores` e `candidatos`, e uma `dataclass` só para isso seria classite.
- Tipagem em todas as assinaturas públicas.
- Docstring em toda função pública: o que faz, regras (RN-xx) e erros que pode levantar.
- Comentários explicam o **porquê**, não o quê.
- `ruff` como linter e formatador; zero avisos.

## 4. Stack, dependências e ambiente

Python 3.12 + FastAPI + SQLAlchemy 2 (síncrono) + PostgreSQL 16 em Docker, testado com pytest. Tudo roda com três comandos: subir o banco, aplicar as migrações e iniciar a API.

| Componente | Escolha | Para quê |
| --- | --- | --- |
| Linguagem | Python 3.12 | Base do projeto |
| Framework web | FastAPI + Uvicorn | Rotas, validação, injeção de dependências, Swagger automático |
| Validação e esquemas | Pydantic v2 + pydantic-settings | Corpo das requisições e respostas; leitura do `.env` |
| Banco | PostgreSQL 16 (imagem `postgres:16-alpine`) | Persistência e integridade |
| Acesso a dados | SQLAlchemy 2.x (ORM, modo síncrono) + driver psycopg 3 | Consultas e transações |
| Migrações | Alembic | Esquema do banco versionado no Git |
| Senhas | `bcrypt` (biblioteca direta, sem passlib) | Hash de senha |
| Tokens | PyJWT (HS256) | Token de acesso e token da cédula |
| Fuso horário | `zoneinfo` + pacote `tzdata` | Horários da eleição em America/Sao_Paulo (no Windows o `tzdata` é obrigatório) |
| Testes | pytest + pytest-cov + httpx (TestClient) | Testes unitários, de integração e cobertura |
| Qualidade | ruff | Lint e formatação |
| Cliente de API | Insomnia ou Postman | Demonstração (importam o `openapi.json`) |
| CI | GitHub Actions | Roda lint e testes a cada push |

### Arquivos de dependências

`requirements.txt` (execução):

```text
fastapi==0.165.0
uvicorn[standard]==0.54.0
pydantic==2.14.4
pydantic-settings==2.16.3
sqlalchemy==2.1.9
psycopg[binary]==3.3.9
alembic==1.20.1
bcrypt==5.0.0
pyjwt==2.15.1
tzdata==2026.6
python-multipart==0.0.34
```

`requirements-dev.txt` (desenvolvimento e testes):

```text
-r requirements.txt
pytest==9.2.0
pytest-cov==7.1.0
httpx==0.28.1
ruff==0.17.6
```

As versões acima são as **fixadas** (`pacote==x.y.z`) na tarefa 00, depois de instaladas e testadas; trocar uma versão é decisão do grupo. `python-multipart` é necessário porque o login usa formulário OAuth2.

### `docker-compose.yml`

```yaml
services:
  banco:
    image: postgres:16-alpine
    container_name: eleicao-banco
    environment:
      POSTGRES_USER: eleicao
      POSTGRES_PASSWORD: eleicao
      POSTGRES_DB: eleicao
    ports:
      - "5432:5432"
    volumes:
      - dados_banco:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U eleicao -d eleicao"]
      interval: 5s
      timeout: 3s
      retries: 10

  banco_teste:
    image: postgres:16-alpine
    container_name: eleicao-banco-teste
    environment:
      POSTGRES_USER: eleicao
      POSTGRES_PASSWORD: eleicao
      POSTGRES_DB: eleicao_teste
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data

volumes:
  dados_banco:
```

O banco de teste é separado (porta 5433) e vive só na memória (`tmpfs`), então os testes nunca apagam os dados da demonstração. Se alguém do grupo já tiver PostgreSQL instalado na porta 5432, troque a porta externa para 5434 e ajuste o `.env`.

### `.env.example` (versionado; o `.env` real não vai para o Git)

```text
AMBIENTE=dev
DATABASE_URL=postgresql+psycopg://eleicao:eleicao@localhost:5432/eleicao
TEST_DATABASE_URL=postgresql+psycopg://eleicao:eleicao@localhost:5433/eleicao_teste
JWT_SEGREDO=troque-por-um-segredo-com-pelo-menos-32-caracteres
JWT_EXPIRACAO_MINUTOS=60
CEDULA_EXPIRACAO_MINUTOS=5
BCRYPT_CUSTO=12
FUSO_HORARIO=America/Sao_Paulo
CHEFE_CPF=29141777638
CHEFE_NOME=Chefe da Seção
CHEFE_SENHA=Chefe@2026
```

### Configuração (`app/compartilhado/config.py`)

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    """Configurações lidas de variáveis de ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ambiente: str = "dev"
    database_url: str
    jwt_segredo: str = Field(min_length=32)
    jwt_expiracao_minutos: int = 60
    cedula_expiracao_minutos: int = 5
    bcrypt_custo: int = 12
    fuso_horario: str = "America/Sao_Paulo"
    # usados só pelo script criar_chefe
    chefe_cpf: str | None = None
    chefe_nome: str = "Chefe da Seção"
    chefe_senha: str | None = None


@lru_cache
def obter_configuracao() -> Configuracao:
    return Configuracao()
```

Se `JWT_SEGREDO` faltar ou tiver menos de 32 caracteres, a API **não sobe**. Isso é proposital (falhar cedo é mais seguro).

### `pyproject.toml` (ferramentas)

```toml
[project]
name = "eleicao-api"
version = "1.0.0"
requires-python = ">=3.12"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.format]
# Os .md (como o docs/PLANO.md) têm trechos de código só para leitura; não são código do projeto.
exclude = ["*.md"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

### `.gitignore`

```text
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
```

### Comandos do dia a dia

```bash
docker compose up -d                       # sobe banco e banco de teste
python -m venv .venv
.venv\Scripts\Activate.ps1                  # Windows PowerShell
source .venv/bin/activate                  # Linux/macOS
pip install -r requirements-dev.txt
copy .env.example .env                     # Windows (Linux/macOS: cp .env.example .env)
alembic upgrade head                       # cria as tabelas
python -m app.scripts.criar_chefe          # cria o Chefe da Seção inicial
python -m app.scripts.seed_demo            # opcional: dados de demonstração
uvicorn app.main:app --reload              # API em http://localhost:8000 e Swagger em /docs

pytest                                     # todos os testes
pytest tests/unitarios                     # só unitários (sem banco)
pytest tests/integracao                    # só integração (precisa do banco_teste)
pytest --cov=app --cov-report=term-missing # cobertura
ruff check . && ruff format .              # qualidade
```

## 5. Arquitetura

Um único processo FastAPI e um único banco, divididos em **6 módulos de domínio** mais um módulo compartilhado. Cada módulo é dono das suas tabelas e só conversa com os outros pelas funções do `servico.py` deles. As dependências formam um grafo sem ciclos, verificado por um teste automático.

### Módulos e dependências

```mermaid
graph TD
    eleitores --> identidade
    candidatos --> identidade
    eleicoes --> candidatos
    votacao --> eleicoes
    votacao --> eleitores
    apuracao --> votacao
    apuracao --> eleicoes
    apuracao --> eleitores
```

Todo módulo também pode usar `compartilhado` e `identidade.dependencias` (autenticação nas rotas). Nenhuma outra dependência é permitida.

| Módulo | Responsabilidade (contexto) | Tabelas que possui | Interface pública (`servico.py`) |
| --- | --- | --- | --- |
| `compartilhado` | Infraestrutura e núcleo compartilhado: configuração, sessão do banco, erros, relógio, paginação, validadores, `Cargo` | nenhuma | (utilitários) |
| `identidade` | Credenciais, login, token de acesso, perfis | `usuarios` | `autenticar`, `criar_credencial`, `atualizar_credencial`, `remover_credencial`, `obter_usuario`, obter_usuarios, listar_usuarios + `dependencias.py`: `obter_usuario_atual`, `exige_perfil` |
| `eleitores` | Cadastro de eleitores | `eleitores` | `cadastrar_eleitor`, `listar_eleitores`, `obter_eleitor`, `atualizar_eleitor`, `excluir_eleitor`, `obter_eleitor_do_usuario`, `contar_aptos` |
| `candidatos` | Cadastro de candidatos (pessoas) e partidos | `candidatos`, `partidos` | `cadastrar_candidato`, `listar_candidatos`, `obter_candidato`, `atualizar_candidato`, `excluir_candidato`, `obter_candidato_do_usuario`, `obter_resumos_de_candidatos`, `criar_partido`, `listar_partidos`, `obter_partido` |
| `eleicoes` | Eleição (raiz do agregado) e suas candidaturas | `eleicoes`, `candidaturas` | `criar_eleicao`, `editar_eleicao`, `abrir_eleicao`, `encerrar_eleicao`, `obter_eleicao`, `listar_eleicoes`, `criar_candidatura`, `editar_candidatura`, `remover_candidatura`, `listar_candidaturas`, `candidaturas_do_usuario`, `obter_eleicao_para_votacao`, `buscar_candidatura_por_numero` |
| `votacao` | Cédula, registro e confirmação do voto, sigilo | `registros_votacao`, `votos` | `obter_cedula`, `registrar_voto`, `confirmar_voto`, `obter_participacao`, `contar_votos`, `contar_comparecimento` |
| `apuracao` | Acompanhamento parcial e resultado final (somente leitura) | nenhuma | `apuracao_parcial`, `resultado_final` |

Por que `apuracao` não tem tabelas: ela só combina dados que outros módulos já possuem (contagens de `votacao`, candidaturas de `eleicoes`, eleitores aptos de `eleitores`) e aplica as regras de apuração. Assim, nenhum módulo lê a tabela de outro (sem acoplamento de recurso comum).

### Camadas dentro de cada módulo

Todo módulo tem a mesma forma. Quem entende um entende todos.

| Arquivo | Responsabilidade | Pode importar | Não pode importar |
| --- | --- | --- | --- |
| `rotas.py` | HTTP: recebe a requisição, chama o serviço, devolve o esquema de resposta. Sem regra de negócio. | `esquemas`, `servico` do próprio módulo, `identidade.dependencias`, `compartilhado` | `repositorio`, `modelos` |
| `esquemas.py` | Contratos Pydantic de entrada e saída, com exemplos para o Swagger | `dominio` do próprio módulo, `compartilhado` | SQLAlchemy |
| `servico.py` | Casos de uso. Única porta de entrada do módulo para os outros. Controla a transação. | `dominio`, `repositorio` do próprio módulo, `servico` de outros módulos permitidos | `rotas`, FastAPI |
| `dominio.py` | Regras puras: enums, `dataclass`es de retorno, funções de validação. Testável sem banco. | `compartilhado.dominio`, `compartilhado.validadores`, `compartilhado.erros` | FastAPI, SQLAlchemy, `repositorio` |
| `repositorio.py` | Consultas SQLAlchemy somente nas tabelas do módulo | `modelos` do próprio módulo | outros módulos |
| `modelos.py` | Tabelas ORM do módulo | `compartilhado.banco` | modelos de outros módulos (chave estrangeira por nome da tabela em texto: `ForeignKey("eleicoes.id")`) |

Arquivos extras por módulo: `identidade/senhas.py`, `identidade/tokens.py`, `identidade/dependencias.py`, `votacao/cedulas.py`.

### Regras de fronteira (o teste de arquitetura verifica)

1. Um módulo importa de outro **apenas** `app.<outro>.servico` (e `app.identidade.dependencias` nas rotas).
2. Funções públicas do serviço devolvem `dataclass`es do `dominio.py`, **nunca** objetos ORM. O modelo do banco não vaza para fora do módulo.
3. Nenhum `import` forma ciclo entre módulos; as arestas permitidas são exatamente as do diagrama acima.
4. `dominio.py` não importa `fastapi` nem `sqlalchemy`.
5. Exceções à regra 1, só na "raiz de composição": `app/main.py`, `app/registro_modelos.py`, `app/scripts/*` e `migrations/env.py`.

### Transações

- Cada requisição recebe uma sessão pela dependência `obter_sessao` (abre, entrega e fecha; fechar sem commit desfaz tudo).
- **Casos de uso chamados pelas rotas fazem `sessao.commit()` no final.** Funções públicas pensadas para outros módulos (`criar_credencial`, `remover_credencial` etc.) **não fazem commit**: quem chama controla a transação. A docstring diz isso.
- Exemplo: `cadastrar_eleitor` chama `identidade.criar_credencial` (sem commit), grava o eleitor e só então faz commit. Se algo falhar, nada fica gravado pela metade.
- Erro de integridade (`IntegrityError`) dentro de um caso de uso: `sessao.rollback()` e conversão para um erro de negócio com código (seção 10).

### Tratamento de erros

`app/compartilhado/erros.py` define uma hierarquia curta. O código do erro vai como argumento, para não criar uma classe por erro (evita classite):

```python
class ErroDeNegocio(Exception):
    status_http = 409

    def __init__(self, mensagem: str, codigo: str, detalhes: dict | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo
        self.detalhes = detalhes or {}


class NaoAutenticado(ErroDeNegocio):
    status_http = 401


class AcessoNegado(ErroDeNegocio):
    status_http = 403


class NaoEncontrado(ErroDeNegocio):
    status_http = 404


class ConflitoDeEstado(ErroDeNegocio):
    status_http = 409


class DadosInvalidos(ErroDeNegocio):
    status_http = 422


# uso: raise ConflitoDeEstado("A eleição não está aberta.", codigo="ELEICAO_NAO_ABERTA")
```

Tratadores registrados no `main.py`:

1. `ErroDeNegocio` → `status_http` da classe + corpo `{"erro": {"codigo", "mensagem", "detalhes"}}`; em 401, cabeçalho `WWW-Authenticate: Bearer`.
2. `RequestValidationError` (Pydantic) → 422, código `DADOS_INVALIDOS`, `detalhes.campos` = lista de `{campo, mensagem}`.
3. `IntegrityError` não tratado → 409, código mapeado pelo nome da restrição (tabela na seção 6) ou `CONFLITO_DE_DADOS`.
4. `HTTPException` do Starlette (os erros do próprio framework; a `HTTPException` do FastAPI é subclasse dela) → 404 `ROTA_NAO_ENCONTRADA` ("Rota não encontrada."), 405 `METODO_NAO_PERMITIDO` ("Método não permitido para esta rota.") e qualquer outro status `ERRO_HTTP` ("Erro na requisição."), sempre no mesmo corpo `{"erro": {...}}`. Os cabeçalhos que o framework mandou (como o `Allow` do 405) são mantidos.
5. `Exception` → 500, código `ERRO_INTERNO`, mensagem genérica; detalhes só no log, nunca na resposta.

### Estrutura de pastas

```text
eleicao-api/
├── app/
│   ├── main.py                  # raiz de composição: cria o app, inclui routers, tratadores de erro
│   ├── registro_modelos.py      # importa os modelos de todos os módulos (para o Alembic)
│   ├── compartilhado/
│   │   ├── config.py            # Configuracao (pydantic-settings)
│   │   ├── banco.py             # engine, SessionLocal, Base com convenção de nomes, obter_sessao
│   │   ├── erros.py             # ErroDeNegocio e subclasses, ErroResposta, tratadores
│   │   ├── relogio.py           # agora(), obter_agora (dependência injetável)
│   │   ├── dominio.py           # Cargo, DIGITOS_POR_CARGO (núcleo compartilhado)
│   │   ├── validadores.py       # CPF, só dígitos, idade
│   │   ├── paginacao.py         # Paginacao, obter_paginacao, Pagina[T]
│   │   └── openapi.py           # respostas_de_erro(...), descrição das tags
│   ├── identidade/   modelos, repositorio, dominio, senhas, tokens, servico, dependencias, esquemas, rotas
│   ├── eleitores/    modelos, repositorio, dominio, servico, esquemas, rotas
│   ├── candidatos/   modelos, repositorio, dominio, servico, esquemas, rotas
│   ├── eleicoes/     modelos, repositorio, dominio, servico, esquemas, rotas
│   ├── votacao/      modelos, repositorio, dominio, cedulas, servico, esquemas, rotas
│   ├── apuracao/     dominio, servico, esquemas, rotas
│   └── scripts/
│       ├── criar_chefe.py
│       ├── seed_demo.py
│       └── exportar_openapi.py
├── migrations/                  # Alembic: env.py e versions/
├── tests/
│   ├── __init__.py              # tests/ e cada subpasta têm __init__.py: assim `tests.auxiliares`
│   │                            # pode ser importado e arquivos de mesmo nome em pastas diferentes não conflitam
│   ├── conftest.py
│   ├── auxiliares.py            # fábricas de dados e helpers de login
│   ├── unitarios/               # sem banco e sem HTTP (com __init__.py)
│   ├── integracao/              # API + PostgreSQL de teste (com __init__.py)
│   └── arquitetura/             # fronteiras, rotas protegidas, OpenAPI atualizado (com __init__.py)
├── docs/
│   ├── PLANO.md                 # este documento
│   ├── ARQUITETURA.md
│   ├── MODELAGEM.md
│   ├── DEMO.md                  # roteiro da apresentação
│   ├── openapi.json             # spec exportada
│   └── index.html               # Swagger UI estático (GitHub Pages)
├── .github/workflows/ci.yml
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
└── README.md
```

### `app/main.py` (esqueleto)

```python
from fastapi import FastAPI

from app.apuracao.rotas import roteador as rotas_apuracao
from app.candidatos.rotas import roteador as rotas_candidatos
from app.compartilhado.erros import registrar_tratadores
from app.compartilhado.openapi import DESCRICAO_API, TAGS
from app.eleicoes.rotas import roteador as rotas_eleicoes
from app.eleitores.rotas import roteador as rotas_eleitores
from app.identidade.rotas import roteador as rotas_identidade
from app.votacao.rotas import roteador as rotas_votacao

app = FastAPI(
    title="API de Simulação de Eleição Eletrônica",
    version="1.0.0",
    description=DESCRICAO_API,
    openapi_tags=TAGS,
)
registrar_tratadores(app)

PREFIXO = "/api/v1"
for roteador in (rotas_identidade, rotas_eleicoes, rotas_eleitores, rotas_candidatos,
                 rotas_votacao, rotas_apuracao):
    app.include_router(roteador, prefix=PREFIXO)


@app.get("/health", tags=["Sistema"], summary="Verifica se a API e o banco estão no ar")
def health() -> dict:
    ...  # executa SELECT 1 e devolve {"status": "ok"}
```

## 6. Modelagem do banco de dados

São 8 tabelas. As regras mais críticas são garantidas pelo próprio PostgreSQL, mesmo que a aplicação tenha um bug: um voto por eleitor e cargo (chave primária), uma eleição aberta por vez (índice parcial), voto coerente com a candidatura (chave estrangeira composta) e voto imutável (trigger). O ponto central do modelo é que **`registros_votacao` e `votos` não têm nenhuma ligação entre si**: é isso que impede que uma tabela, rota ou resposta ligue quem votou ao que foi votado. O sigilo tem dois limites: quem acessa o banco diretamente ainda consegue ligar as duas tabelas pelo `xmin` e pela ordem física das linhas (D-134), e quem compara a apuração parcial antes e depois de um voto, sabendo quem votou nesse intervalo, deduz a escolha. Detalhes nas limitações conhecidas do sigilo, no fim desta seção.

### Diagrama entidade-relacionamento

```mermaid
erDiagram
    USUARIOS ||--o| ELEITORES : "é um"
    USUARIOS ||--o| CANDIDATOS : "é um"
    CANDIDATOS ||--o{ CANDIDATURAS : "concorre em"
    PARTIDOS ||--o{ CANDIDATURAS : "representa"
    ELEICOES ||--o{ CANDIDATURAS : "contém"
    ELEITORES ||--o{ REGISTROS_VOTACAO : "compareceu"
    ELEICOES ||--o{ REGISTROS_VOTACAO : "registra"
    ELEICOES ||--o{ VOTOS : "recebe"
    CANDIDATURAS |o--o{ VOTOS : "recebe se nominal"

    USUARIOS {
        bigint id PK
        char cpf UK
        varchar nome
        varchar senha_hash
        varchar perfil
        timestamptz criado_em
        timestamptz atualizado_em
    }
    ELEITORES {
        bigint id PK
        bigint usuario_id FK
        char titulo_eleitor UK
        date data_nascimento
        timestamptz criado_em
    }
    CANDIDATOS {
        bigint id PK
        bigint usuario_id FK
        varchar nome_urna
        date data_nascimento
        timestamptz criado_em
    }
    PARTIDOS {
        bigint id PK
        varchar sigla UK
        varchar nome UK
        smallint numero UK
        timestamptz criado_em
    }
    ELEICOES {
        bigint id PK
        varchar descricao
        date data
        smallint turno
        time horario_abertura
        time horario_encerramento
        varchar status
        timestamptz aberta_em
        timestamptz encerrada_em
        timestamptz criado_em
    }
    CANDIDATURAS {
        bigint id PK
        bigint eleicao_id FK
        bigint candidato_id FK
        bigint partido_id FK
        varchar cargo
        varchar numero
        timestamptz criado_em
    }
    REGISTROS_VOTACAO {
        bigint eleitor_id PK
        bigint eleicao_id PK
        varchar cargo PK
    }
    VOTOS {
        uuid id PK
        bigint eleicao_id FK
        varchar cargo
        varchar tipo
        bigint candidatura_id FK
    }
```

Repare: não existe linha entre `REGISTROS_VOTACAO` e `VOTOS`. Isso é proposital.

### Convenção de nomes das restrições (`app/compartilhado/banco.py`)

Toda restrição tem nome previsível. Assim a aplicação traduz uma violação do banco em um código de erro amigável.

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

CONVENCAO_DE_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO_DE_NOMES)
```

### Tabelas

**`usuarios`** (módulo `identidade`): credencial de qualquer pessoa que faz login.

| Coluna | Tipo | Restrições |
| --- | --- | --- |
| id | BIGINT IDENTITY | PK |
| cpf | CHAR(11) | NOT NULL, `uq_usuarios_cpf`, `ck_usuarios_cpf_digitos`: `cpf ~ '^[0-9]{11}$'` |
| nome | VARCHAR(120) | NOT NULL, `ck_usuarios_nome_minimo`: `char_length(trim(nome)) >= 3` |
| senha_hash | VARCHAR(60) | NOT NULL (hash bcrypt; a senha nunca é gravada) |
| perfil | VARCHAR(20) | NOT NULL, `ck_usuarios_perfil_valido`: `perfil IN ('CHEFE_SECAO','ELEITOR','CANDIDATO')` |
| criado_em | TIMESTAMPTZ | NOT NULL |
| atualizado_em | TIMESTAMPTZ | NOT NULL |

**`eleitores`** (módulo `eleitores`)

| Coluna | Tipo | Restrições |
| --- | --- | --- |
| id | BIGINT IDENTITY | PK |
| usuario_id | BIGINT | NOT NULL, `uq_eleitores_usuario_id`, FK → `usuarios.id` ON DELETE RESTRICT |
| titulo_eleitor | CHAR(12) | NOT NULL, `uq_eleitores_titulo_eleitor`, `ck_eleitores_titulo_digitos`: `titulo_eleitor ~ '^[0-9]{12}$'` |
| data_nascimento | DATE | NOT NULL |
| criado_em | TIMESTAMPTZ | NOT NULL (usado para saber se o eleitor estava cadastrado antes da abertura) |

**`candidatos`** (módulo `candidatos`)

| Coluna | Tipo | Restrições |
| --- | --- | --- |
| id | BIGINT IDENTITY | PK |
| usuario_id | BIGINT | NOT NULL, `uq_candidatos_usuario_id`, FK → `usuarios.id` ON DELETE RESTRICT |
| nome_urna | VARCHAR(30) | NOT NULL |
| data_nascimento | DATE | NOT NULL (usada no desempate por idade) |
| criado_em | TIMESTAMPTZ | NOT NULL |

**`partidos`** (módulo `candidatos`)

| Coluna | Tipo | Restrições |
| --- | --- | --- |
| id | BIGINT IDENTITY | PK |
| sigla | VARCHAR(10) | NOT NULL, `uq_partidos_sigla`, `ck_partidos_sigla_formato`: `sigla ~ '^[A-Z0-9]{2,10}$'` |
| nome | VARCHAR(100) | NOT NULL, `uq_partidos_nome` |
| numero | SMALLINT | NOT NULL, `uq_partidos_numero`, `ck_partidos_numero_faixa`: `numero BETWEEN 10 AND 99` |
| criado_em | TIMESTAMPTZ | NOT NULL |

**`eleicoes`** (módulo `eleicoes`, raiz do agregado)

| Coluna | Tipo | Restrições |
| --- | --- | --- |
| id | BIGINT IDENTITY | PK |
| descricao | VARCHAR(120) | NOT NULL |
| data | DATE | NOT NULL |
| turno | SMALLINT | NOT NULL, `ck_eleicoes_turno_valido`: `turno IN (1, 2)` |
| horario_abertura | TIME | NOT NULL |
| horario_encerramento | TIME | NOT NULL, `ck_eleicoes_janela_valida`: `horario_abertura < horario_encerramento` |
| status | VARCHAR(10) | NOT NULL DEFAULT `'AGENDADA'`, `ck_eleicoes_status_valido`: `status IN ('AGENDADA','ABERTA','ENCERRADA')` |
| aberta_em | TIMESTAMPTZ | NULL até a abertura |
| encerrada_em | TIMESTAMPTZ | NULL até o encerramento |
| criado_em | TIMESTAMPTZ | NOT NULL |

Restrições da tabela:

- `uq_eleicoes_data_turno`: UNIQUE (`data`, `turno`). A seção não tem duas eleições no mesmo dia e turno.
- `ck_eleicoes_status_coerente`: o status combina com os carimbos de tempo.

```sql
(status = 'AGENDADA'  AND aberta_em IS NULL     AND encerrada_em IS NULL) OR
(status = 'ABERTA'    AND aberta_em IS NOT NULL AND encerrada_em IS NULL) OR
(status = 'ENCERRADA' AND aberta_em IS NOT NULL AND encerrada_em IS NOT NULL)
```

- `uq_eleicoes_uma_aberta`: índice único **parcial**, só uma eleição ABERTA por vez.

```python
Index("uq_eleicoes_uma_aberta", "status", unique=True, postgresql_where=text("status = 'ABERTA'"))
```

**`candidaturas`** (módulo `eleicoes`, entidade interna do agregado)

| Coluna | Tipo | Restrições |
| --- | --- | --- |
| id | BIGINT IDENTITY | PK |
| eleicao_id | BIGINT | NOT NULL, FK → `eleicoes.id` ON DELETE RESTRICT |
| candidato_id | BIGINT | NOT NULL, FK → `candidatos.id` ON DELETE RESTRICT |
| partido_id | BIGINT | NOT NULL, FK → `partidos.id` ON DELETE RESTRICT |
| cargo | VARCHAR(20) | NOT NULL, `ck_candidaturas_cargo_valido`: os 5 cargos |
| numero | VARCHAR(5) | NOT NULL, `ck_candidaturas_numero_por_cargo` (abaixo) |
| criado_em | TIMESTAMPTZ | NOT NULL |

- `uq_candidaturas_eleicao_id_cargo_numero`: número único por cargo na eleição (Presidente 13 e Governador 13 podem coexistir).
- `uq_candidaturas_eleicao_id_candidato_id`: um candidato tem no máximo uma candidatura por eleição.
- `uq_candidaturas_id_eleicao_id_cargo`: UNIQUE (`id`, `eleicao_id`, `cargo`), alvo da chave estrangeira composta de `votos`.
- `ck_candidaturas_numero_por_cargo`:

```sql
(cargo IN ('PRESIDENTE', 'GOVERNADOR') AND numero ~ '^[1-9][0-9]$') OR
(cargo = 'SENADOR'           AND numero ~ '^[1-9][0-9]{2}$') OR
(cargo = 'DEPUTADO_FEDERAL'  AND numero ~ '^[1-9][0-9]{3}$') OR
(cargo = 'DEPUTADO_ESTADUAL' AND numero ~ '^[1-9][0-9]{4}$')
```

**`registros_votacao`** (módulo `votacao`): quem já votou em qual cargo. Não diz em quem.

| Coluna | Tipo | Restrições |
| --- | --- | --- |
| eleitor_id | BIGINT | FK → `eleitores.id` ON DELETE RESTRICT |
| eleicao_id | BIGINT | FK → `eleicoes.id` ON DELETE RESTRICT; índice `ix_registros_votacao_eleicao_id` |
| cargo | VARCHAR(20) | `ck_registros_votacao_cargo_valido` |

- `pk_registros_votacao`: PRIMARY KEY (`eleitor_id`, `eleicao_id`, `cargo`). É **esta chave** que impede o voto duplo, inclusive com duas requisições chegando ao mesmo tempo.
- Sem coluna de horário e sem coluna de candidatura, de propósito.

**`votos`** (módulo `votacao`): o quê foi votado. Não diz quem votou.

| Coluna | Tipo | Restrições |
| --- | --- | --- |
| id | UUID | PK, gerado com `uuid.uuid4()` (aleatório, não revela a ordem) |
| eleicao_id | BIGINT | NOT NULL, FK → `eleicoes.id` ON DELETE RESTRICT |
| cargo | VARCHAR(20) | NOT NULL, `ck_votos_cargo_valido` |
| tipo | VARCHAR(10) | NOT NULL, `ck_votos_tipo_valido`: `tipo IN ('NOMINAL','BRANCO','NULO')` |
| candidatura_id | BIGINT | NULL (só preenchida no voto nominal) |

- `ck_votos_nominal_tem_candidatura`: `(tipo = 'NOMINAL') = (candidatura_id IS NOT NULL)`.
- `fk_votos_candidatura_id_candidaturas`: chave estrangeira **composta** (`candidatura_id`, `eleicao_id`, `cargo`) → `candidaturas` (`id`, `eleicao_id`, `cargo`). O banco garante que um voto para Senador nunca aponta para uma candidatura a Presidente, nem de outra eleição. Com `candidatura_id` nulo (branco ou nulo), a FK não é verificada (MATCH SIMPLE).
- `ix_votos_apuracao`: índice em (`eleicao_id`, `cargo`, `candidatura_id`) para a contagem.
- Sem `eleitor_id`, sem `criado_em`, sem id sequencial.

### Trigger: voto e registro são imutáveis

Criado na migração da votação com `op.execute(...)`. Mesmo um bug na aplicação (ou um `UPDATE` manual) não consegue alterar ou apagar um voto confirmado. Nos testes, a limpeza usa `TRUNCATE`, que não dispara triggers de linha.

```sql
CREATE FUNCTION impedir_alteracao_de_voto() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Votos e registros de votação confirmados são imutáveis';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_votos_imutaveis
    BEFORE UPDATE OR DELETE ON votos
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_de_voto();

CREATE TRIGGER trg_registros_votacao_imutaveis
    BEFORE UPDATE OR DELETE ON registros_votacao
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_de_voto();
```

O `downgrade` da migração remove os dois triggers e a função.

### Carimbos de tempo

Todos os `criado_em`, `atualizado_em`, `aberta_em` e `encerrada_em` são preenchidos **pelo serviço com o relógio injetável** (`agora`), não por `DEFAULT now()` do banco. Motivo: nos testes o relógio é congelado; se o banco usasse o horário real, a regra "eleitor cadastrado antes da abertura" daria resultados errados.

### Tradução de restrições em erros

O serviço verifica antes (mensagem clara) e o banco garante depois (corrida e bugs). Se a restrição disparar, `compartilhado/erros.py` traduz pelo nome dela (`exc.orig.diag.constraint_name`):

| Restrição | Código de erro | HTTP | Mensagem |
| --- | --- | --- | --- |
| `uq_usuarios_cpf` | `CPF_JA_CADASTRADO` | 409 | "Já existe um usuário com este CPF." |
| `uq_eleitores_titulo_eleitor` | `TITULO_JA_CADASTRADO` | 409 | "Já existe um eleitor com este título de eleitor." |
| `uq_partidos_sigla`, `uq_partidos_numero`, `uq_partidos_nome` | `PARTIDO_DUPLICADO` | 409 | "Já existe um partido com esta sigla, nome ou número." |
| `uq_eleicoes_data_turno` | `ELEICAO_DUPLICADA` | 409 | "Já existe uma eleição nesta data e turno." |
| `uq_eleicoes_uma_aberta` | `OUTRA_ELEICAO_ABERTA` | 409 | "Já existe outra eleição aberta." |
| `uq_candidaturas_eleicao_id_cargo_numero` | `NUMERO_JA_UTILIZADO` | 409 | "Este número já é usado por outra candidatura neste cargo." |
| `uq_candidaturas_eleicao_id_candidato_id` | `CANDIDATURA_DUPLICADA` | 409 | "Este candidato já tem candidatura nesta eleição." |
| `pk_registros_votacao` | `VOTO_JA_REGISTRADO` | 409 | "O eleitor já votou neste cargo nesta eleição." |
| `fk_registros_votacao_eleitor_id_eleitores` (ao excluir eleitor) | `EXCLUSAO_BLOQUEADA` | 409 | "Não é possível excluir: há registros que dependem deste." |
| `fk_candidaturas_candidato_id_candidatos` (ao excluir candidato) | `EXCLUSAO_BLOQUEADA` | 409 | "Não é possível excluir: há registros que dependem deste." |

Restrição que não está na tabela, ou que o driver não nomeia, vira `CONFLITO_DE_DADOS` (409, "Os dados enviados conflitam com os já gravados."). No código, cada linha é uma `TraducaoDeRestricao` (código, status e mensagem em português) em `ERROS_POR_RESTRICAO`.

### Política de exclusão

| Entidade | Pode excluir? | Como funciona |
| --- | --- | --- |
| Eleitor | Sim, se nunca votou | O serviço apaga o eleitor e depois a credencial. Se ele já votou, a FK de `registros_votacao` bloqueia → 409 `EXCLUSAO_BLOQUEADA`. |
| Candidato | Sim, se não tiver candidaturas | A FK de `candidaturas` bloqueia → 409. Remova as candidaturas antes (só com eleição AGENDADA). |
| Candidatura | Só com eleição AGENDADA | Regra no serviço de `eleicoes`. |
| Eleição e partido | Não há rota de exclusão | Eleições são histórico; partidos fora do escopo. |
| Voto e registro | Nunca | Trigger. |

### Migrações (Alembic), uma por fase

| Arquivo | Fase | Conteúdo |
| --- | --- | --- |
| `0001_identidade` | 2 | `usuarios` |
| `0002_eleitores` | 3 | `eleitores` |
| `0003_candidatos_partidos` | 4 | `candidatos`, `partidos` |
| `0004_eleicoes_candidaturas` | 5 | `eleicoes` (com índice parcial), `candidaturas` |
| `0005_votacao` | 6 | `registros_votacao`, `votos`, função e triggers |

Gere com `python -m alembic revision --autogenerate --rev-id 0001 -m "identidade"` (use `0002`, `0003`... nas próximas). O `--rev-id` é necessário para o arquivo se chamar `0001_identidade`: o `file_template` do `alembic.ini` já é `<número>_<descrição>`, mas o Alembic só gera o número se ele for informado. **Revise o arquivo gerado** (o autogenerate não cria trigger e pode errar o índice parcial) e teste `alembic upgrade head` e `alembic downgrade -1`.

### Limitações conhecidas do sigilo (para o README)

Na API e no modelo lógico, nada liga eleitor e voto. Os limites:

- **O `xmin`:** o registro de quem votou e o voto são gravados na mesma transação (para nunca existir registro sem voto nem voto sem registro), então as duas linhas têm o mesmo identificador de transação, e quem pode ler as duas tabelas liga cada voto ao eleitor com `JOIN ... ON v.xmin = r.xmin` (D-134).
- **A ordem física** em que as linhas foram gravadas nas duas tabelas, também para quem tem acesso direto ao banco.
- **A parcial exata:** quem consulta a apuração antes e depois de um único voto, e sabe quem votou nesse intervalo, deduz a escolha (o mesmo acontece em qualquer seção real com um único eleitor). Mostrar a parcial é exigência do enunciado.

A urna real resolve os dois primeiros embaralhando o registro digital do voto. Aqui o acesso direto ao banco precisa ficar restrito, e mudar o desenho é decisão em aberto (D-134).

## 7. Autenticação, perfis e segurança

Login com CPF e senha devolve um token JWT de 60 minutos. A cada requisição o sistema valida o token **e recarrega o usuário do banco**: o token prova quem você é, mas o que você pode fazer vem do banco. Toda rota exige login, exceto `/auth/login`, `/health` e a documentação.

### Perfis

| Perfil | Valor | Como nasce |
| --- | --- | --- |
| Chefe da Seção | `CHEFE_SECAO` | Script `python -m app.scripts.criar_chefe`, com `CHEFE_CPF`, `CHEFE_NOME` e `CHEFE_SENHA` do `.env`. Idempotente: se o CPF já existe, não faz nada. Não existe rota para criar chefe. |
| Eleitor | `ELEITOR` | Cadastrado pelo Chefe (`POST /eleitores`). |
| Candidato | `CANDIDATO` | Cadastrado pelo Chefe (`POST /candidatos`). |

Não há autocadastro. Cada pessoa tem exatamente um perfil (decisão D04).

### Fluxo do login (`POST /api/v1/auth/login`)

1. Recebe um formulário OAuth2 (`application/x-www-form-urlencoded`): `username` = CPF (com ou sem pontuação), `password` = senha. Esse formato faz o botão **Authorize** do Swagger funcionar.
2. Normaliza o CPF (só dígitos, de 0 a 9). Se o formato for inválido, **não consulta o banco** e segue como se o usuário não existisse (não ajuda quem tenta adivinhar CPFs).
3. Se o formato for válido, busca o usuário pelo CPF.
4. Se não houver usuário (CPF mal formatado ou inexistente), **ainda assim** confere a senha contra um hash fictício, para a resposta levar o mesmo tempo, e responde 401 `CREDENCIAIS_INVALIDAS` ("CPF ou senha inválidos.").
5. Se a senha não conferir, o mesmo 401 com a mesma mensagem. Senha com mais de 72 bytes nunca confere (a comparação é feita mesmo assim, só para gastar o mesmo tempo).
6. Se conferir, gera o token e responde 200 com `access_token`, `token_type: "bearer"`, `expira_em` e `usuario` (`id`, `nome`, `perfil`).

### Token de acesso

| Campo (claim) | Valor |
| --- | --- |
| `sub` | ID do usuário, **como texto** (o PyJWT exige texto) |
| `perfil` | Perfil no momento do login (só informativo; a autorização usa o perfil do banco) |
| `aud` | `"eleicao-api:acesso"`. Impede que o token da cédula seja usado como token de acesso, e vice-versa. |
| `iat` / `exp` | Emissão e expiração (60 minutos), com o relógio real |
| Algoritmo | HS256 com `JWT_SEGREDO` (mínimo 32 caracteres). Na leitura, `algorithms=["HS256"]` é sempre explícito (bloqueia o truque do `alg: none`). |

`ler_token_acesso` devolve o ID do usuário. Qualquer falha vira 401 `TOKEN_INVALIDO`: assinatura, audiência ou expiração inválidas, claim obrigatório ausente e também um `sub` que não é número inteiro (`ValueError`).

### Código de referência

Os três arquivos abaixo são o código real do repositório (tarefa 02).

`app/identidade/senhas.py`:

```python
"""Hash de senhas com bcrypt. Só este módulo conhece o bcrypt (ocultação de informação)."""

from functools import lru_cache

import bcrypt

from app.compartilhado.config import obter_configuracao
from app.identidade.dominio import BYTES_MAXIMOS_SENHA


def gerar_hash(senha: str) -> str:
    """Gera o hash bcrypt da senha. A senha em si nunca é gravada (RN-05)."""
    custo = obter_configuracao().bcrypt_custo
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=custo)).decode("utf-8")


def senha_confere(senha: str, senha_hash: str) -> bool:
    """Diz se a senha corresponde ao hash (RN-01).

    Senha com mais de 72 bytes nunca confere (nenhuma senha assim é aceita no cadastro, RN-05).
    O bcrypt recusa esse tamanho com erro, então a comparação é feita mesmo assim, só para
    gastar o mesmo tempo, e o resultado é sempre falso.
    """
    dados = senha.encode("utf-8")
    if len(dados) > BYTES_MAXIMOS_SENHA:
        bcrypt.checkpw(dados[:BYTES_MAXIMOS_SENHA], senha_hash.encode("utf-8"))
        return False
    return bcrypt.checkpw(dados, senha_hash.encode("utf-8"))


@lru_cache
def hash_ficticio() -> str:
    """Hash usado quando o CPF não existe, para o login demorar o mesmo tempo (RN-01)."""
    return gerar_hash("senha-que-nao-pertence-a-ninguem")
```

`app/identidade/tokens.py`:

```python
"""Token JWT de acesso. Só este módulo conhece o JWT de acesso (ocultação de informação)."""

from datetime import UTC, datetime, timedelta

import jwt

from app.compartilhado.config import obter_configuracao
from app.compartilhado.erros import NaoAutenticado
from app.identidade.dominio import Perfil

ALGORITMO = "HS256"
# A audiência impede que o token da cédula seja usado como token de acesso, e vice-versa.
AUDIENCIA_ACESSO = "eleicao-api:acesso"


def criar_token_acesso(usuario_id: int, perfil: Perfil) -> tuple[str, datetime]:
    """Emite o token de acesso (RN-02). Devolve o token e o instante em que ele expira.

    O `perfil` vai no token só como informação: a autorização usa o perfil do banco.
    """
    configuracao = obter_configuracao()
    # Relógio real (e não o injetável): o JWT é validado pela biblioteca com o relógio real.
    emitido_em = datetime.now(UTC)
    expira_em = emitido_em + timedelta(minutes=configuracao.jwt_expiracao_minutos)
    dados = {
        "sub": str(usuario_id),  # o PyJWT exige texto
        "perfil": perfil.value,
        "aud": AUDIENCIA_ACESSO,
        "iat": emitido_em,
        "exp": expira_em,
    }
    token = jwt.encode(dados, configuracao.jwt_segredo, algorithm=ALGORITMO)
    return token, expira_em


def ler_token_acesso(token: str) -> int:
    """Valida assinatura, audiência e expiração (RN-02). Devolve o ID do usuário.

    Levanta `NaoAutenticado` (`TOKEN_INVALIDO`, 401) se o token não servir.
    """
    configuracao = obter_configuracao()
    try:
        dados = jwt.decode(
            token,
            configuracao.jwt_segredo,
            algorithms=[ALGORITMO],  # explícito: bloqueia o truque do `alg: none`
            audience=AUDIENCIA_ACESSO,
            options={"require": ["sub", "exp", "aud"]},
        )
        return int(dados["sub"])
    except (jwt.InvalidTokenError, ValueError) as erro:
        raise NaoAutenticado("Token inválido ou expirado.", codigo="TOKEN_INVALIDO") from erro
```

`app/identidade/dependencias.py`:

```python
"""Dependências FastAPI de autenticação, usadas pelas rotas de todos os módulos."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.compartilhado.banco import obter_sessao
from app.compartilhado.erros import AcessoNegado, NaoAutenticado
from app.identidade import servico, tokens
from app.identidade.dominio import Perfil, UsuarioAutenticado

# auto_error=False: nós mesmos respondemos 401 no formato padrão de erro da API.
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def obter_usuario_atual(
    token: Annotated[str | None, Depends(esquema_oauth2)],
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> UsuarioAutenticado:
    """Toda rota protegida depende desta função (RN-06).

    RN-02: o token prova quem você é, mas o usuário é recarregado do banco a cada requisição;
    quem foi excluído depois do login perde o acesso na hora.
    """
    if not token:
        raise NaoAutenticado("Autenticação necessária.", codigo="NAO_AUTENTICADO")
    usuario = servico.obter_usuario(sessao, tokens.ler_token_acesso(token))
    if usuario is None:
        raise NaoAutenticado("Token inválido ou expirado.", codigo="TOKEN_INVALIDO")
    return usuario


def exige_perfil(*perfis_permitidos: Perfil):
    """Cria uma dependência que só deixa passar os perfis informados (RN-03).

    Uso numa rota: `Depends(exige_perfil(Perfil.CHEFE_SECAO))`. Quem tem outro perfil recebe
    403 `PERFIL_NAO_AUTORIZADO`; sem login, 401 (a mesma de `obter_usuario_atual`).
    """

    def verificar(
        usuario: Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)],
    ) -> UsuarioAutenticado:
        if usuario.perfil not in perfis_permitidos:
            raise AcessoNegado(
                "Seu perfil não tem permissão para esta operação.",
                codigo="PERFIL_NAO_AUTORIZADO",
                detalhes={"perfis_permitidos": [perfil.value for perfil in perfis_permitidos]},
            )
        return usuario

    return verificar


# uso numa rota:
# def abrir(..., usuario: Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.CHEFE_SECAO))]):
```

### Senhas

- Mínimo de 8 caracteres e máximo de **72 bytes** em UTF-8 (limite do bcrypt; versões recentes recusam senhas maiores). Não pode ser só espaços. No login, `senha_confere` devolve falso para senha acima de 72 bytes (o bcrypt 5 levantaria `ValueError`, que viraria 500 e mudaria o tempo de resposta).
- Custo do bcrypt configurável: 12 em uso normal, 4 nos testes (senão os testes ficam lentos).
- Nenhuma resposta, log ou mensagem de erro contém senha ou hash.

### Proteções aplicadas em todo o projeto

- **Negar por padrão:** toda rota tem `obter_usuario_atual` ou `exige_perfil` (teste automático verifica; lista branca: `/auth/login`, `/health`, `/docs`, `/redoc`, `/openapi.json`).
- **Sem atribuição em massa:** todo esquema de entrada usa `model_config = ConfigDict(extra="forbid")`. Mandar `"perfil": "CHEFE_SECAO"` no cadastro de eleitor dá 422.
- **Respostas explícitas:** sempre `response_model`; nunca o modelo ORM; nunca `senha_hash`.
- **SQL injection:** só consultas SQLAlchemy com parâmetros; proibido montar SQL com f-string. O único SQL cru é o das migrações.
- **Limites de tamanho:** todo campo texto tem `max_length`; paginação com `tamanho` máximo 100.
- **Erros sem vazamento:** o erro 500 devolve mensagem genérica; o detalhe vai só para o log.
- **Logs:** registram método, caminho, status e duração. Nunca registram corpo da requisição, token, senha ou conteúdo de voto.
- **CORS desligado:** não há frontend; nada de `allow_origins=["*"]`.
- **Segredos:** só em `.env` (fora do Git). O `.env.example` tem valores de exemplo, e o README avisa para trocá-los.

### Ameaças e como o sistema se defende

| Ameaça | Defesa | Onde |
| --- | --- | --- |
| Descobrir quais CPFs têm conta | Mesma mensagem e mesmo tempo de resposta para CPF inexistente e senha errada | Login |
| Usar token roubado indefinidamente | Expiração de 60 min; usuário excluído perde o acesso na hora (recarregado do banco) | `obter_usuario_atual` |
| Virar Chefe mandando `perfil` no corpo | `extra="forbid"` + perfil lido do banco | Esquemas e dependências |
| Votar duas vezes (inclusive em paralelo) | Chave primária de `registros_votacao` | Banco |
| Votar no instante em que o Chefe encerra | Trava compartilhada na linha da eleição durante a confirmação | `confirmar_voto` (seção 9) |
| Alterar ou apagar um voto | Não existe rota; trigger bloqueia no banco | API e banco |
| Descobrir em quem alguém votou | Tabelas sem ligação, UUID aleatório, sem horário, nenhuma rota expõe, logs sem voto, confirmação não devolve a escolha | Modelo, API, logs |
| Confirmar a cédula de outro eleitor | `sub` da cédula precisa ser o usuário logado | `votacao.servico.confirmar_voto` |
| Usar a cédula como token de acesso | Audiências diferentes (`acesso` × `cedula`) | `tokens`, `cedulas` |
| Forjar uma cédula | Assinatura HMAC com segredo do servidor | `cedulas` |
| SQL injection | ORM com parâmetros | Repositórios |
| Força bruta no login | Fora do escopo; extra opcional: limite de tentativas (seção 13) | — |

### Limitações assumidas (para o README)

- O token não pode ser revogado antes de expirar; isso é mitigado porque o usuário é recarregado do banco a cada requisição.
- HTTPS é responsabilidade do ambiente onde a API for publicada.
- As limitações de sigilo descritas na seção 6.

## 8. Catálogo de regras de negócio

São 58 regras, cada uma com código, lugar no código, erro e origem. **Origem** diz se a regra vem do enunciado (E), de uma decisão de projeto (D) ou é uma regra complementar de realismo (C). O código RN é citado na docstring da função e no teste.

### Identidade e acesso

| RN | Regra | Onde | Erro (HTTP) | Origem |
| --- | --- | --- | --- | --- |
| RN-01 | Login por CPF e senha. Qualquer falha responde o mesmo 401, com a mesma mensagem e tempo parecido. | `identidade.servico.autenticar` | `CREDENCIAIS_INVALIDAS` (401) | E |
| RN-02 | Token de acesso expira em 60 min; a cada requisição o usuário é recarregado do banco. | `identidade.dependencias` | `TOKEN_INVALIDO` (401) | D |
| RN-03 | Cada usuário tem um único perfil, e cada rota declara quais perfis aceita. | `exige_perfil` | `PERFIL_NAO_AUTORIZADO` (403) | E |
| RN-04 | Não há autocadastro. O Chefe inicial nasce por script; eleitores e candidatos só pelo Chefe. | `scripts/criar_chefe.py`, rotas | — | D |
| RN-05 | Senha entre 8 caracteres e 72 bytes, não pode ser só espaços; guardada apenas como hash bcrypt. | `identidade.dominio.validar_senha` | `SENHA_INVALIDA` (422) | D |
| RN-06 | Toda rota exige autenticação, exceto login, health e documentação. | `identidade.dependencias` | `NAO_AUTENTICADO` (401) | E |
| RN-07 | CPF válido (11 dígitos, dígitos verificadores corretos, não todos iguais) e único entre todos os usuários. Aceita com ou sem pontuação e grava só dígitos. | `compartilhado.validadores`, `identidade.servico` | `CPF_INVALIDO` (422), `CPF_JA_CADASTRADO` (409) | D |
| RN-08 | Nome com 3 a 120 caracteres (ignorando espaços nas pontas). | Esquemas e `identidade.servico` | `DADOS_INVALIDOS` (422) | D |

A RN-08 também é conferida em `identidade.servico` (`criar_credencial` e `atualizar_credencial`), porque o script `criar_chefe` não passa por esquema; lá o nome é gravado sem os espaços das pontas.

### Eleições

| RN | Regra | Onde | Erro (HTTP) | Origem |
| --- | --- | --- | --- | --- |
| RN-10 | Só o Chefe cria, edita, abre e encerra eleições. | Rotas de `eleicoes` | `PERFIL_NAO_AUTORIZADO` (403) | E |
| RN-11 | Ao criar ou editar: turno 1 ou 2; horário de abertura antes do de encerramento; data não anterior a hoje. | `eleicoes.dominio.validar_agendamento` | `DADOS_INVALIDOS`, `JANELA_INVALIDA`, `DATA_NO_PASSADO` (422) | E |
| RN-12 | Não existem duas eleições com a mesma data e o mesmo turno. | Serviço + `uq_eleicoes_data_turno` | `ELEICAO_DUPLICADA` (409) | D |
| RN-13 | Ciclo de vida AGENDADA → ABERTA → ENCERRADA, sem pular etapa e sem voltar. | `eleicoes.dominio` | `TRANSICAO_INVALIDA` (409) | E |
| RN-14 | Descrição, data, turno e horários só podem ser editados enquanto AGENDADA. | `eleicoes.dominio.validar_edicao` | `ELEICAO_NAO_EDITAVEL` (409) | D |
| RN-15 | Para abrir: status AGENDADA; hoje é a data da eleição; o horário atual está entre abertura (inclusive) e encerramento (exclusive); existe pelo menos 1 candidatura. | `eleicoes.dominio.validar_abertura` | `TRANSICAO_INVALIDA`, `FORA_DA_DATA`, `FORA_DA_JANELA`, `SEM_CANDIDATURAS` (409) | E + D |
| RN-16 | Só uma eleição ABERTA por vez. | Serviço + `uq_eleicoes_uma_aberta` | `OUTRA_ELEICAO_ABERTA` (409) | D |
| RN-17 | Em eleição de 2º turno, para abrir, cada cargo disputado precisa ter exatamente 2 candidaturas. | `eleicoes.dominio.validar_abertura` | `SEGUNDO_TURNO_INCOMPLETO` (409) | C |
| RN-18 | Para encerrar: status ABERTA. Pode encerrar a qualquer hora (antes ou depois do horário previsto). Ao encerrar, nenhum voto novo entra. | `eleicoes.dominio.validar_encerramento` | `TRANSICAO_INVALIDA` (409) | E |
| RN-19 | Qualquer usuário autenticado consulta uma eleição (situação, horários, carimbos) e recebe `links` com as ações possíveis para o seu perfil naquele status. | `eleicoes.dominio.links_da_eleicao` | `ELEICAO_NAO_ENCONTRADA` (404) | E + D |

### Eleitores

| RN | Regra | Onde | Erro (HTTP) | Origem |
| --- | --- | --- | --- | --- |
| RN-20 | Só o Chefe cadastra, altera, consulta e exclui eleitores. | Rotas de `eleitores` | `PERFIL_NAO_AUTORIZADO` (403) | E |
| RN-21 | Título de eleitor com 12 dígitos, único. | Esquema + serviço + `uq_eleitores_titulo_eleitor` | `DADOS_INVALIDOS` (422), `TITULO_JA_CADASTRADO` (409) | D |
| RN-22 | Eleitor com pelo menos 16 anos na data do cadastro; data de nascimento no passado. | `eleitores.dominio.validar_idade_eleitor` | `IDADE_MINIMA` (422) | C |
| RN-23 | CPF e título não mudam depois do cadastro; só nome, data de nascimento e senha podem ser alterados. | Esquema de atualização (`extra="forbid"`) | `DADOS_INVALIDOS` (422) | D |
| RN-24 | Só exclui eleitor que nunca votou; a credencial é removida junto. | `eleitores.servico.excluir_eleitor` + FK | `EXCLUSAO_BLOQUEADA` (409) | D |
| RN-25 | O eleitor consulta os próprios dados (`/eleitores/eu`). | Rotas de `eleitores` | — | D |

### Candidatos e partidos

| RN | Regra | Onde | Erro (HTTP) | Origem |
| --- | --- | --- | --- | --- |
| RN-30 | Só o Chefe gerencia candidatos e cadastra partidos; qualquer autenticado lista partidos. | Rotas de `candidatos` | `PERFIL_NAO_AUTORIZADO` (403) | E |
| RN-31 | Candidato tem nome, nome de urna (3 a 30 caracteres), CPF (RN-07), data de nascimento no passado e senha (RN-05). | Esquemas, `candidatos.dominio` | `DADOS_INVALIDOS` (422) | E |
| RN-32 | Partido: sigla de 2 a 10 letras maiúsculas ou dígitos, nome e número (10 a 99), os três únicos. | Esquema + serviço + restrições | `DADOS_INVALIDOS` (422), `PARTIDO_DUPLICADO` (409) | E |
| RN-33 | Só exclui candidato sem candidaturas; a credencial é removida junto. CPF não muda. | `candidatos.servico.excluir_candidato` + FK | `EXCLUSAO_BLOQUEADA` (409) | D |

### Candidaturas (dentro do agregado Eleição)

| RN | Regra | Onde | Erro (HTTP) | Origem |
| --- | --- | --- | --- | --- |
| RN-40 | Candidatura liga candidato + eleição + cargo + partido + número. Só o Chefe cria, altera ou remove, e só com a eleição AGENDADA. | `eleicoes.servico` | `ELEICAO_NAO_EDITAVEL` (409) | E |
| RN-41 | Cargo é um dos 5 valores do enum `Cargo`. | Esquema | `DADOS_INVALIDOS` (422) | E |
| RN-42 | Número com a quantidade de dígitos do cargo (Presidente 2, Governador 2, Senador 3, Dep. Federal 4, Dep. Estadual 5), sem zero à esquerda. | `compartilhado.dominio.numero_valido_para_cargo` + `ck_candidaturas_numero_por_cargo` | `NUMERO_INVALIDO_PARA_CARGO` (422) | C |
| RN-43 | Número único por cargo na eleição. | Serviço + restrição | `NUMERO_JA_UTILIZADO` (409) | E |
| RN-44 | Um candidato tem no máximo uma candidatura por eleição. | Serviço + restrição | `CANDIDATURA_DUPLICADA` (409) | D |
| RN-45 | 2º turno: só cargos GOVERNADOR e PRESIDENTE, no máximo 2 candidaturas por cargo. | `eleicoes.dominio.validar_candidatura` | `CARGO_NAO_PERMITIDO_NO_TURNO`, `LIMITE_SEGUNDO_TURNO` (409) | C |
| RN-46 | Candidato e partido informados precisam existir. | `eleicoes.servico` (via `candidatos.servico`) | `REFERENCIA_INEXISTENTE` (422) | D |
| RN-47 | O candidato consulta as próprias candidaturas (`/candidaturas/minhas`). | Rotas de `eleicoes` | — | D |

### Votação

| RN | Regra | Onde | Erro (HTTP) | Origem |
| --- | --- | --- | --- | --- |
| RN-50 | Só usuário com perfil ELEITOR vota (Chefe e Candidato não). | `exige_perfil(Perfil.ELEITOR)` | `PERFIL_NAO_AUTORIZADO` (403) | E |
| RN-51 | Só se vota em eleição ABERTA. | `votacao.dominio.validar_pode_votar` | `ELEICAO_NAO_ABERTA` (409) | E |
| RN-52 | Só se vota dentro da janela: se o horário de encerramento passou e o Chefe ainda não encerrou, o voto é recusado. | `votacao.dominio.validar_pode_votar` | `JANELA_ENCERRADA` (409) | C |
| RN-53 | Só vota o eleitor cadastrado antes da abertura da eleição ("previamente cadastrado"). | `votacao.dominio.validar_eleitor_apto` | `ELEITOR_NAO_APTO` (403) | E + C |
| RN-54 | Um voto por eleitor, por cargo, por eleição. | Serviço + `pk_registros_votacao` | `VOTO_JA_REGISTRADO` (409) | E |
| RN-55 | Só se vota em cargo disputado (com pelo menos 1 candidatura na eleição). | `votacao.servico` | `CARGO_NAO_DISPUTADO` (422) | D |
| RN-56 | O voto tem duas etapas: registrar (nada é gravado; pode repetir para mudar de ideia) e confirmar (definitivo). | `votacao.servico` | — | E |
| RN-57 | A cédula expira em 5 minutos e só vale para o eleitor e a eleição em que foi emitida. | `votacao.cedulas` | `CEDULA_INVALIDA`, `CEDULA_EXPIRADA` (422) | D |
| RN-58 | Modo NUMERO exige a quantidade de dígitos do cargo; número com candidatura vira voto NOMINAL, número sem candidatura vira NULO. Modo BRANCO vira BRANCO. A prévia informa o tipo resultante. | `votacao.dominio.resolver_escolha` | `NUMERO_INVALIDO_PARA_CARGO` (422) | C |
| RN-59 | Voto confirmado não pode ser alterado nem excluído. | Sem rota + trigger | `VOTO_JA_REGISTRADO` (409) ao tentar de novo | E |
| RN-60 | Sigilo: o banco nunca guarda eleitor e escolha juntos; voto sem horário e com UUID aleatório; a confirmação não devolve a escolha; nenhuma rota diz em quem um eleitor votou; logs sem a escolha. | Modelo, `votacao`, logs | — | E |
| RN-61 | O eleitor consulta em quais cargos já votou na eleição (sem a escolha). | `votacao.servico.obter_participacao` | — | D |

### Apuração

| RN | Regra | Onde | Erro (HTTP) | Origem |
| --- | --- | --- | --- | --- |
| RN-70 | Parcial só com eleição ABERTA; resultado final só com ENCERRADA. | `apuracao.servico` | `APURACAO_INDISPONIVEL` (409) | E |
| RN-71 | Eleitor e Chefe veem a parcial de todos os cargos. | `apuracao.servico` | — | E |
| RN-72 | Candidato vê a parcial só do cargo da sua candidatura nessa eleição. Sem candidatura nela, ou pedindo outro cargo: 403. | `apuracao.servico` | `SEM_CANDIDATURA_NA_ELEICAO`, `CARGO_NAO_PERMITIDO` (403) | E |
| RN-73 | O resultado final é visível para todos os perfis autenticados. | `apuracao.servico` | — | D |
| RN-74 | A contagem é calculada no momento da consulta (sempre atualizada). | `votacao.servico.contar_votos` | — | E |
| RN-75 | Lista todas as candidaturas do cargo, inclusive com 0 votos, ordenadas por votos (decrescente) e depois por número. | `apuracao.dominio.apurar_cargo` | — | E |
| RN-76 | Percentual sobre votos válidos (nominais), com 2 casas e arredondamento "meio para cima". Brancos e nulos aparecem à parte. | `apuracao.dominio.percentual` | — | C |
| RN-77 | Mais votado = mais votos nominais. Empate: vence o mais idoso. Empate persistente (mesma data de nascimento): situação EMPATE, sem mais votado. | `apuracao.dominio.definir_mais_votado` | — | E + C |
| RN-78 | Cargo sem votos válidos: `mais_votado` nulo e situação SEM_VOTOS_VALIDOS. | `apuracao.dominio.definir_mais_votado` | — | D |
| RN-79 | Comparecimento: eleitores aptos (cadastrados antes da abertura), votantes (votaram em pelo menos 1 cargo) e abstenção (aptos − votantes); por cargo, total de votos. | `apuracao.servico` | — | C |

## 9. Lógica dos casos de uso

Cada caso de uso abaixo vira uma função pública do `servico.py`, na ordem de passos descrita. As validações puras ficam no `dominio.py` (testadas sem banco); o serviço só busca dados, chama o domínio, grava e faz commit. As três peças mais delicadas têm código de referência: relógio, confirmação do voto e apuração.

### 9.1 Peças compartilhadas

**Relógio injetável** (`app/compartilhado/relogio.py`). Toda rota que depende de data ou hora recebe `agora: Annotated[datetime, Depends(obter_agora)]` e repassa ao serviço. Nos testes, `app.dependency_overrides[obter_agora]` congela o tempo.

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.compartilhado.config import obter_configuracao


def agora() -> datetime:
    """Data e hora atuais no fuso da eleição (America/Sao_Paulo), com fuso (aware)."""
    return datetime.now(ZoneInfo(obter_configuracao().fuso_horario))


def obter_agora() -> datetime:
    """Dependência FastAPI. Os testes substituem esta função para congelar o tempo."""
    return agora()
```

**Validadores** (`app/compartilhado/validadores.py`). Só valem os dígitos ASCII de 0 a 9: `\d` e `isdigit()` sozinhos aceitam dígitos de outros alfabetos (como os arábico-índicos), que o banco trata de outro jeito; por isso o formato usa `[0-9]` e existe `so_digitos` (D-010).

```python
"""Validadores puros (sem banco e sem HTTP) usados por vários módulos."""

import re
from datetime import date

FORMATO_CPF = re.compile(r"^[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}$")


def so_digitos(texto: str) -> bool:
    """Diz se o texto tem só dígitos de 0 a 9 (ASCII).

    `str.isdigit()` sozinho aceita dígitos de outros alfabetos (como os arábico-índicos),
    que o banco e o `int()` tratam de outro jeito. Por isso exigimos também `isascii()`.
    """
    return texto.isascii() and texto.isdigit()


def normalizar_cpf(valor: str) -> str:
    """Aceita '529.982.247-25' ou '52998224725' e devolve só os dígitos (RN-07).

    Devolve texto vazio se o formato não for de um CPF (letras, tamanho errado etc.).
    """
    if not FORMATO_CPF.match(valor.strip()):
        return ""
    return re.sub(r"[^0-9]", "", valor)


def cpf_valido(cpf: str) -> bool:
    """Confere os dois dígitos verificadores (RN-07).

    Espera o CPF já normalizado (só dígitos). Recusa tamanho errado e dígitos todos iguais.
    """
    if len(cpf) != 11 or not so_digitos(cpf) or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def calcular_idade(nascimento: date, referencia: date) -> int:
    """Idade completa, em anos, na data de referência (base da RN-22).

    Quem nasceu em 29/02 só faz aniversário em 01/03 nos anos não bissextos.
    """
    ja_fez_aniversario = (referencia.month, referencia.day) >= (nascimento.month, nascimento.day)
    return referencia.year - nascimento.year - (0 if ja_fez_aniversario else 1)
```

**Núcleo compartilhado** (`app/compartilhado/dominio.py`). A ordem do enum é a ordem da urna real e é usada para ordenar cédula e apuração.

```python
from enum import StrEnum

from app.compartilhado.validadores import so_digitos


class Cargo(StrEnum):
    DEPUTADO_FEDERAL = "DEPUTADO_FEDERAL"
    DEPUTADO_ESTADUAL = "DEPUTADO_ESTADUAL"
    SENADOR = "SENADOR"
    GOVERNADOR = "GOVERNADOR"
    PRESIDENTE = "PRESIDENTE"


DIGITOS_POR_CARGO = {
    Cargo.DEPUTADO_FEDERAL: 4,
    Cargo.DEPUTADO_ESTADUAL: 5,
    Cargo.SENADOR: 3,
    Cargo.GOVERNADOR: 2,
    Cargo.PRESIDENTE: 2,
}

CARGOS_DO_SEGUNDO_TURNO = {Cargo.GOVERNADOR, Cargo.PRESIDENTE}


def numero_valido_para_cargo(numero: str, cargo: Cargo) -> bool:
    """Só dígitos (0 a 9, ASCII), sem zero à esquerda, na quantidade do cargo (RN-42)."""
    return so_digitos(numero) and numero[0] != "0" and len(numero) == DIGITOS_POR_CARGO[cargo]
```

**Paginação** (`app/compartilhado/paginacao.py`). `Paginacao` é uma `dataclass` imutável com `pagina` e `tamanho` e a propriedade `deslocamento` (`(pagina - 1) * tamanho`: quantos itens pular na consulta). `obter_paginacao` é a dependência FastAPI que lê `pagina` (≥ 1, padrão 1) e `tamanho` (1 a 100, padrão 20) da query e devolve uma `Paginacao`; as rotas de listagem a recebem com `Annotated[Paginacao, Depends(obter_paginacao)]` e a repassam ao serviço. `Pagina[T]` é a resposta genérica de toda listagem: `itens`, `pagina`, `tamanho` e `total` (total do filtro, somando todas as páginas).

### 9.2 Identidade

- **`autenticar(sessao, cpf, senha) -> ResultadoDoLogin`**: fluxo da seção 7 (RN-01). Devolve a `dataclass` `ResultadoDoLogin` (token, expiração e `UsuarioAutenticado`). Não grava nada, então não faz commit.
- **`criar_credencial(sessao, cpf, nome, senha, perfil, agora) -> int`** (sem commit; os 6 parâmetros são uma exceção aceita à regra dos 5, seção 3): normaliza e valida o CPF (RN-07, 422); valida o nome (RN-08, 422 `DADOS_INVALIDOS`) e o grava sem os espaços das pontas; valida a senha (RN-05); se o CPF já existe, 409 `CPF_JA_CADASTRADO`; insere com hash; `sessao.flush()` para obter o id; devolve o id.
- **`atualizar_credencial(sessao, usuario_id, agora, nome=None, senha=None)`** (sem commit): altera só o que veio; o nome passa por RN-08, a nova senha por RN-05 e vira hash; atualiza `atualizado_em`. CPF e perfil nunca mudam (RN-03). Se o `usuario_id` não existe, levanta `LookupError`: quem chama já conhece o usuário, então a ausência é uma inconsistência interna (vira 500 `ERRO_INTERNO`), e não um erro do usuário da API.
- **`remover_credencial(sessao, usuario_id)`** (sem commit): apaga o usuário; os tokens dele deixam de valer na hora (RN-02). Com `usuario_id` inexistente levanta `LookupError`, pelo mesmo motivo.
- **`obter_usuario(sessao, usuario_id) -> UsuarioAutenticado | None`** e **`obter_usuarios(sessao, ids) -> dict[int, UsuarioAutenticado]`**.
- **`listar_usuarios(sessao, perfil, nome, paginacao) -> Pagina[UsuarioAutenticado]`**: filtra por perfil e por nome (`ILIKE '%nome%'`), ordena por nome. Usado pelas listagens de eleitores e candidatos.

**Contratos** (`identidade/esquemas.py` e `identidade/dominio.py`):

- `UsuarioResposta`: `id`, `nome` e `perfil`. Vai dentro da resposta do login.
- `UsuarioLogadoResposta`: `id`, `nome`, `cpf` (só dígitos) e `perfil`. Resposta de `GET /auth/me`.
- `LoginResposta`: `access_token`, `token_type` (sempre `"bearer"`), `expira_em` (UTC) e `usuario` (`UsuarioResposta`).
- `ResultadoDoLogin` (`dataclass` de `dominio.py`): `access_token`, `expira_em` e `usuario` (`UsuarioAutenticado`). É o que `autenticar` devolve e a rota converte em `LoginResposta`.

### 9.3 Eleitores

- **`cadastrar_eleitor(sessao, dados, agora)`**: (1) valida idade mínima com `calcular_idade(data_nascimento, agora.date()) >= 16` e nascimento no passado (RN-22); (2) título já existe → 409 (RN-21); (3) `identidade.criar_credencial(..., perfil=ELEITOR)`; (4) insere o eleitor com `criado_em=agora`; (5) commit; (6) devolve `EleitorDetalhado` (dados do eleitor + nome e CPF da credencial).
- **`listar_eleitores(sessao, nome, paginacao)`**: (1) `identidade.listar_usuarios(perfil=ELEITOR, nome, paginacao)`; (2) busca os eleitores desses `usuario_id` numa única consulta; (3) junta mantendo a ordem. Assim o módulo não lê a tabela `usuarios`.
- **`obter_eleitor(sessao, eleitor_id)`**: 404 `ELEITOR_NAO_ENCONTRADO` se não existir.
- **`atualizar_eleitor(sessao, eleitor_id, alteracoes, agora)`**: só nome, data de nascimento e senha (RN-23); nova data passa por RN-22; nome e senha vão para `identidade.atualizar_credencial`; commit.
- **`excluir_eleitor(sessao, eleitor_id)`**: (1) obtém (404); (2) apaga a linha de `eleitores` e dá `flush()`; (3) se der `IntegrityError` da FK de `registros_votacao`, faz rollback e levanta 409 `EXCLUSAO_BLOQUEADA` ("O eleitor já votou e não pode ser excluído."); (4) `identidade.remover_credencial`; (5) commit (RN-24).
- **`obter_eleitor_do_usuario(sessao, usuario_id) -> EleitorResumo | None`**: usado por `votacao` (traz `id` e `criado_em`).
- **`contar_aptos(sessao, ate: datetime) -> int`**: eleitores com `criado_em <= ate`. Usado por `apuracao` (RN-79).

### 9.4 Candidatos e partidos

- **`cadastrar_candidato`**, **`listar_candidatos`**, **`obter_candidato`**, **`atualizar_candidato`** (nome, nome de urna, data de nascimento, senha): mesmo padrão de eleitores, com perfil CANDIDATO (RN-31).
- **`excluir_candidato`**: apaga o candidato e dá `flush()`; `IntegrityError` da FK de `candidaturas` → 409 `EXCLUSAO_BLOQUEADA` ("Remova as candidaturas antes."); remove a credencial; commit (RN-33).
- **`obter_candidato_do_usuario(sessao, usuario_id)`** e **`obter_resumos_de_candidatos(sessao, ids) -> dict[int, CandidatoResumo]`** (id, nome de urna, data de nascimento): usados por `eleicoes`.
- **`criar_partido(sessao, dados, agora)`**: sigla em maiúsculas; se sigla, nome ou número já existem → 409 `PARTIDO_DUPLICADO` (RN-32); commit. **`listar_partidos`** ordena por número. **`obter_partido`** devolve `None` se não existir.

### 9.5 Eleições e candidaturas

Toda alteração no agregado começa travando a linha da eleição com `SELECT ... FOR UPDATE` (`repositorio.obter_com_trava_exclusiva`). A raiz controla o acesso: duas alterações no mesmo agregado nunca se cruzam.

- **`criar_eleicao(sessao, dados, agora)`**: (1) `dominio.validar_agendamento(dados, hoje=agora.date())`: data não anterior a hoje, abertura antes do encerramento (RN-11); (2) já existe eleição com mesma data e turno → 409 (RN-12); (3) insere com status AGENDADA e `criado_em=agora`; (4) commit.
- **`editar_eleicao(sessao, eleicao_id, alteracoes, agora)`**: trava; `validar_edicao(status)` (RN-14); aplica; revalida RN-11 e RN-12 (ignorando a própria); commit.
- **`abrir_eleicao(sessao, eleicao_id, agora)`**:
  1. Trava a eleição (404 se não existe).
  2. `existe_outra_aberta = repositorio.existe_eleicao_aberta()`.
  3. `candidaturas_por_cargo = repositorio.contar_candidaturas_por_cargo(eleicao_id)` (dict `Cargo -> int`).
  4. `dominio.validar_abertura(eleicao, agora, existe_outra_aberta, candidaturas_por_cargo)`, nesta ordem: status AGENDADA (RN-13); nenhuma outra aberta (RN-16); `agora.date() == eleicao.data` (RN-15, `FORA_DA_DATA`); `horario_abertura <= agora.time() < horario_encerramento` (RN-15, `FORA_DA_JANELA`); pelo menos 1 candidatura (RN-15); se turno 2, cada cargo com candidaturas tem exatamente 2 (RN-17).
  5. Status ABERTA e `aberta_em = agora`; commit. Se o índice parcial disparar (corrida), 409 `OUTRA_ELEICAO_ABERTA`.
- **`encerrar_eleicao(sessao, eleicao_id, agora)`**: trava exclusiva; `validar_encerramento(status)` (RN-18); status ENCERRADA e `encerrada_em = agora`; commit. A trava exclusiva espera as confirmações de voto em andamento (que seguram trava compartilhada) terminarem; depois disso, nenhum voto novo passa.
- **`obter_eleicao`**, **`listar_eleicoes(status=None)`**: leitura simples; a resposta inclui `links` (RN-19).
- **`dominio.links_da_eleicao(eleicao, perfil) -> list[Link]`** (HATEOAS). `Link` tem `rel`, `metodo` e `href`:

| Situação | Links |
| --- | --- |
| Sempre | `self` (GET `/api/v1/eleicoes/{id}`) |
| Chefe e AGENDADA | `editar` (PATCH), `candidaturas` (GET), `nova-candidatura` (POST), `abrir` (POST `/abertura`) |
| Chefe e ABERTA | `encerrar` (POST `/encerramento`), `apuracao-parcial` |
| Eleitor e ABERTA | `cedula` (GET `/votacao/eleicoes/{id}/cedula`), `apuracao-parcial` |
| Candidato e ABERTA | `apuracao-parcial` |
| Qualquer perfil e ENCERRADA | `resultado` |

- **`criar_candidatura(sessao, eleicao_id, dados, agora)`**:
  1. Trava a eleição; `validar_edicao(status)` → só AGENDADA (RN-40).
  2. `candidatos.servico.obter_candidato` e `obter_partido`; inexistente → 422 `REFERENCIA_INEXISTENTE` com `detalhes.campo` (RN-46).
  3. `dominio.validar_candidatura(eleicao, cargo, numero, quantidade_no_cargo)`: dígitos (RN-42); no turno 2, só Governador e Presidente e no máximo 2 por cargo (RN-45).
  4. Número já usado no cargo → 409 (RN-43); candidato já tem candidatura nesta eleição → 409 (RN-44).
  5. Insere; commit.
- **`editar_candidatura`** (cargo, número e partido; nunca candidato ou eleição) e **`remover_candidatura`**: mesma trava e mesmas regras, ignorando a própria candidatura nas checagens de duplicidade.
- **`listar_candidaturas(sessao, eleicao_id, cargo=None) -> list[CandidaturaDetalhada]`**: busca as candidaturas, depois `candidatos.obter_resumos_de_candidatos(ids)` e os partidos, e junta tudo em memória. Ordena pela ordem do enum `Cargo` e depois por número. `CandidaturaDetalhada` tem: `id`, `eleicao_id`, `cargo`, `numero`, `candidato_id`, `nome_urna`, `data_nascimento`, `partido_sigla`, `partido_numero`.
- **`candidaturas_do_usuario(sessao, usuario_id)`**: acha o candidato pelo usuário e lista as candidaturas dele (RN-47).
- **`obter_eleicao_para_votacao(sessao, eleicao_id) -> EleicaoResumo`**: `SELECT ... FOR SHARE` (trava compartilhada que dura até o fim da transação de quem chamou). **Não faz commit.**

### 9.6 Votação

Funções puras em `votacao/dominio.py`:

- **`validar_pode_votar(eleicao, agora)`**: status diferente de ABERTA → 409 `ELEICAO_NAO_ABERTA` (RN-51); `agora.date() != eleicao.data` ou `agora.time() >= horario_encerramento` → 409 `JANELA_ENCERRADA` (RN-52).
- **`validar_eleitor_apto(eleitor_criado_em, eleicao_aberta_em)`**: cadastrado depois da abertura → 403 `ELEITOR_NAO_APTO` (RN-53).
- **`resolver_escolha(cargo, modo, numero, candidaturas_do_cargo) -> Escolha`** (RN-58): modo BRANCO → `Escolha(BRANCO, None)`; modo NUMERO → se `numero_valido_para_cargo` for falso, 422; se existe candidatura com o número, `Escolha(NOMINAL, candidatura)`; senão `Escolha(NULO, None)`.

Casos de uso em `votacao/servico.py`:

- **`obter_cedula(sessao, usuario, eleicao_id, agora)`**: (1) eleitor do usuário; (2) eleição → `validar_pode_votar`; (3) `validar_eleitor_apto`; (4) `eleicoes.listar_candidaturas`; (5) cargos em que já votou; (6) monta a cédula só com cargos disputados, na ordem do enum: `{cargo, digitos, ja_votou, candidatos: [{numero, nome_urna, partido_sigla}]}`.
- **`registrar_voto(sessao, usuario, eleicao_id, pedido, agora) -> PreviaVoto`**: (1) a (3) como acima; (4) já votou no cargo → 409 (RN-54); (5) cargo sem candidaturas → 422 (RN-55); (6) `resolver_escolha`; (7) `cedulas.emitir_cedula` (RN-57). **Nada é gravado, nada de commit** (RN-56). Devolve cargo, tipo, candidato escolhido (ou nulo), mensagem ("Voto NULO: número sem candidato para este cargo." etc.), `token_cedula`, `expira_em` e link `confirmar`.
- **`confirmar_voto(...)`**: o coração do sistema, código abaixo.
- **`obter_participacao(sessao, usuario, eleicao_id)`**: lista os cargos disputados com `ja_votou` verdadeiro ou falso, sem nenhuma escolha (RN-61).
- **`contar_votos(sessao, eleicao_id) -> list[ContagemVoto]`** (`cargo`, `tipo`, `candidatura_id`, `total`): `SELECT cargo, tipo, candidatura_id, COUNT(*) FROM votos WHERE eleicao_id = :id GROUP BY cargo, tipo, candidatura_id` (RN-74).
- **`contar_comparecimento(sessao, eleicao_id) -> Comparecimento`**: `COUNT(DISTINCT eleitor_id)` e contagem por cargo em `registros_votacao`.

`app/votacao/cedulas.py`. A cédula é cifrada e autenticada com Fernet (pacote `cryptography`), com chave derivada do `JWT_SEGREDO` por HKDF e contexto próprio (D-144): quem vê o token, sem a chave, não lê o eleitor nem a escolha, e ela é diferente da chave do token de acesso. A expiração usa o relógio injetável, por isso fica no próprio conteúdo (`expira_em`, com a mesma precisão devolvida ao eleitor) e é conferida à mão. A resposta do registro vem com `Cache-Control: no-store`.

```python
import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.compartilhado.config import obter_configuracao
from app.compartilhado.dominio import Cargo
from app.compartilhado.erros import DadosInvalidos
from app.votacao.dominio import Escolha, TipoVoto

CONTEXTO_DA_CHAVE = b"eleicao-api:cedula"


@dataclass(frozen=True)
class Cedula:
    usuario_id: int
    eleicao_id: int
    cargo: Cargo
    tipo: TipoVoto
    candidatura_id: int | None


def _cifrador() -> Fernet:
    segredo = obter_configuracao().jwt_segredo.encode("utf-8")
    chave = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=CONTEXTO_DA_CHAVE).derive(segredo)
    return Fernet(base64.urlsafe_b64encode(chave))


def emitir_cedula(usuario_id: int, eleicao_id: int, cargo: Cargo, escolha: Escolha,
                  agora: datetime) -> tuple[str, datetime]:
    """Cifra a escolha e devolve ao eleitor. Nada vai para o banco (RN-56, RN-57, RN-60)."""
    expira_em = agora + timedelta(minutes=obter_configuracao().cedula_expiracao_minutos)
    dados = {
        "usuario_id": usuario_id, "eleicao_id": eleicao_id, "cargo": cargo.value,
        "tipo": escolha.tipo.value, "candidatura_id": escolha.candidatura_id,
        "expira_em": expira_em.isoformat(),
    }
    return _cifrador().encrypt(json.dumps(dados).encode("utf-8")).decode("ascii"), expira_em


def ler_cedula(token: str, agora: datetime) -> Cedula:
    try:
        dados = json.loads(_cifrador().decrypt(token.encode("utf-8")))
        cedula = Cedula(int(dados["usuario_id"]), int(dados["eleicao_id"]), Cargo(dados["cargo"]),
                        TipoVoto(dados["tipo"]), dados["candidatura_id"])
        expira_em = datetime.fromisoformat(dados["expira_em"])
    except (InvalidToken, KeyError, ValueError, TypeError) as erro:
        raise DadosInvalidos("Cédula inválida.", codigo="CEDULA_INVALIDA") from erro
    if agora > expira_em:
        raise DadosInvalidos("Cédula expirada. Registre o voto novamente.", codigo="CEDULA_EXPIRADA")
    return cedula
```

`confirmar_voto` em `app/votacao/servico.py`:

```python
def confirmar_voto(sessao: Session, usuario: UsuarioAutenticado, eleicao_id: int,
                   token_cedula: str, agora: datetime) -> ComprovanteVoto:
    """Grava o voto de forma definitiva (RN-54, RN-56, RN-59, RN-60)."""
    cedula = cedulas.ler_cedula(token_cedula, agora)
    if cedula.usuario_id != usuario.id or cedula.eleicao_id != eleicao_id:
        raise DadosInvalidos("Esta cédula não pertence a você ou a esta eleição.", codigo="CEDULA_INVALIDA")

    eleitor = eleitores_servico.obter_eleitor_do_usuario(sessao, usuario.id)
    # Trava compartilhada: o encerramento espera este voto terminar (e vice-versa)
    eleicao = eleicoes_servico.obter_eleicao_para_votacao(sessao, eleicao_id)
    dominio.validar_pode_votar(eleicao, agora)
    dominio.validar_eleitor_apto(eleitor.criado_em, eleicao.aberta_em)

    try:
        # Duas gravações na MESMA transação, em tabelas SEM ligação entre si
        repositorio.inserir_registro(sessao, eleitor.id, eleicao_id, cedula.cargo)
        repositorio.inserir_voto(sessao, eleicao_id, cedula.cargo, cedula.tipo, cedula.candidatura_id)
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        if nome_da_restricao(erro) == "pk_registros_votacao":
            raise ConflitoDeEstado("Você já votou para este cargo.", codigo="VOTO_JA_REGISTRADO") from erro
        if nome_da_restricao(erro) == "fk_registros_votacao_eleitor_id_eleitores":  # D-145
            raise NaoEncontrado("Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO") from erro
        raise

    # A resposta NÃO contém a escolha (RN-60)
    return ComprovanteVoto(eleicao_id=eleicao_id, cargo=cedula.cargo, mensagem="Voto confirmado.")
```

Por que a confirmação não checa "já votou" antes de inserir: a chave primária faz isso de forma atômica. Uma checagem antes seria inútil com duas requisições simultâneas (as duas veriam "ainda não votou"). O registro do voto (etapa 1) checa antes só para dar uma resposta rápida.

### 9.7 Apuração

- **`apuracao_parcial(sessao, usuario, eleicao_id, cargo_pedido, agora)`**:
  1. Eleição (404); status diferente de ABERTA → 409 `APURACAO_INDISPONIVEL`, com `detalhes.status` e o link do resultado se já encerrada (RN-70).
  2. Cargos visíveis: Candidato → só o cargo da sua candidatura nesta eleição; sem candidatura → 403 `SEM_CANDIDATURA_NA_ELEICAO`; `cargo_pedido` diferente → 403 `CARGO_NAO_PERMITIDO` (RN-72). Eleitor e Chefe → `cargo_pedido` se informado, senão todos os disputados (RN-71).
  3. `eleicoes.listar_candidaturas`, `votacao.contar_votos`, `votacao.contar_comparecimento`, `eleitores.contar_aptos(ate=eleicao.aberta_em)`.
  4. `dominio.apurar_cargo(...)` para cada cargo visível.
  5. Devolve `tipo: "PARCIAL"`, `gerado_em: agora`, comparecimento e cargos. Na parcial, `mais_votado` significa "quem lidera até agora".
- **`resultado_final(sessao, usuario, eleicao_id, cargo_pedido, agora)`**: status diferente de ENCERRADA → 409 (RN-70); qualquer perfil vê todos os cargos (RN-73); `tipo: "FINAL"`.

Código de referência de `app/apuracao/dominio.py`:

```python
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class SituacaoCargo(StrEnum):
    DEFINIDO = "DEFINIDO"
    EMPATE = "EMPATE"
    SEM_VOTOS_VALIDOS = "SEM_VOTOS_VALIDOS"


def percentual(votos: int, validos: int) -> Decimal:
    """Percentual sobre votos válidos, 2 casas, meio para cima (RN-76)."""
    if validos == 0:
        return Decimal("0.00")
    return (Decimal(votos) * 100 / Decimal(validos)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def definir_mais_votado(linhas: list[LinhaApuracao]) -> tuple[LinhaApuracao | None, SituacaoCargo, str | None]:
    """Linhas já ordenadas por votos. Empate: mais idoso; persistindo, EMPATE (RN-77, RN-78)."""
    if not linhas or linhas[0].votos == 0:
        return None, SituacaoCargo.SEM_VOTOS_VALIDOS, None
    lideres = [linha for linha in linhas if linha.votos == linhas[0].votos]
    if len(lideres) == 1:
        return lideres[0], SituacaoCargo.DEFINIDO, "MAIOR_VOTACAO"
    nascimento_mais_antigo = min(linha.data_nascimento for linha in lideres)
    mais_idosos = [linha for linha in lideres if linha.data_nascimento == nascimento_mais_antigo]
    if len(mais_idosos) == 1:
        return mais_idosos[0], SituacaoCargo.DEFINIDO, "DESEMPATE_POR_IDADE"
    return None, SituacaoCargo.EMPATE, None
```

`apurar_cargo(cargo, candidaturas_do_cargo, contagens_do_cargo) -> ResultadoCargo` faz: separa brancos e nulos; soma os nominais por candidatura; cria uma linha por candidatura **inclusive com 0 votos** (RN-75); calcula percentuais; ordena por `(-votos, numero)`; chama `definir_mais_votado`; devolve `total_votos`, `votos_validos`, `brancos`, `nulos`, `candidatos`, `mais_votado`, `situacao`, `criterio`. A data de nascimento é usada no desempate, mas **não aparece** na resposta.

## 10. API: rotas, contratos e erros

São 33 rotas sob `/api/v1`, mais o `/health`. Todas falam JSON, exceto o login (formulário OAuth2). Todo erro tem o mesmo formato, com um `codigo` estável que os testes e o Postman podem conferir.

### Rotas

Legenda de perfis: **C** = Chefe da Seção, **E** = Eleitor, **K** = Candidato, **Todos** = qualquer autenticado.

| Método | Caminho | Perfis | Sucesso | Erros principais | RN |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | Público | 200 | — | — |
| POST | `/auth/login` | Público | 200 | 401, 422 | RN-01 |
| GET | `/auth/me` | Todos | 200 | 401 | RN-02 |
| POST | `/eleicoes` | C | 201 | 403, 409, 422 | RN-10 a 12 |
| GET | `/eleicoes?status=` | Todos | 200 | 401 | RN-19 |
| GET | `/eleicoes/{eleicao_id}` | Todos | 200 | 404 | RN-19 |
| PATCH | `/eleicoes/{eleicao_id}` | C | 200 | 404, 409, 422 | RN-11, 12, 14 |
| POST | `/eleicoes/{eleicao_id}/abertura` | C | 200 | 404, 409 | RN-13, 15 a 17 |
| POST | `/eleicoes/{eleicao_id}/encerramento` | C | 200 | 404, 409 | RN-13, 18 |
| GET | `/eleicoes/{eleicao_id}/candidaturas?cargo=` | C | 200 | 404 | RN-40 |
| POST | `/eleicoes/{eleicao_id}/candidaturas` | C | 201 | 404, 409, 422 | RN-40 a 46 |
| PATCH | `/eleicoes/{eleicao_id}/candidaturas/{candidatura_id}` | C | 200 | 404, 409, 422 | RN-40 a 45 |
| DELETE | `/eleicoes/{eleicao_id}/candidaturas/{candidatura_id}` | C | 204 | 404, 409 | RN-40 |
| GET | `/candidaturas/minhas` | K | 200 | 403 | RN-47 |
| POST | `/eleitores` | C | 201 | 409, 422 | RN-20 a 22 |
| GET | `/eleitores?nome=&pagina=&tamanho=` | C | 200 | 403 | RN-20 |
| GET | `/eleitores/eu` | E | 200 | 403 | RN-25 |
| GET | `/eleitores/{eleitor_id}` | C | 200 | 404 | RN-20 |
| PATCH | `/eleitores/{eleitor_id}` | C | 200 | 404, 422 | RN-22, 23 |
| DELETE | `/eleitores/{eleitor_id}` | C | 204 | 404, 409 | RN-24 |
| POST | `/candidatos` | C | 201 | 409, 422 | RN-30, 31 |
| GET | `/candidatos?nome=&pagina=&tamanho=` | C | 200 | 403 | RN-30 |
| GET | `/candidatos/eu` | K | 200 | 403 | RN-30 |
| GET | `/candidatos/{candidato_id}` | C | 200 | 404 | RN-30 |
| PATCH | `/candidatos/{candidato_id}` | C | 200 | 404, 422 | RN-31 |
| DELETE | `/candidatos/{candidato_id}` | C | 204 | 404, 409 | RN-33 |
| POST | `/partidos` | C | 201 | 409, 422 | RN-32 |
| GET | `/partidos` | Todos | 200 | 401 | RN-30 |
| GET | `/votacao/eleicoes/{eleicao_id}/cedula` | E | 200 | 403, 404, 409 | RN-50 a 53 |
| POST | `/votacao/eleicoes/{eleicao_id}/votos/registro` | E | 200 | 403, 409, 422 | RN-50 a 58 |
| POST | `/votacao/eleicoes/{eleicao_id}/votos/confirmacao` | E | 201 | 403, 409, 422 | RN-54, 56, 57, 59, 60 |
| GET | `/votacao/eleicoes/{eleicao_id}/participacao` | E | 200 | 403, 404 | RN-61 |
| GET | `/apuracao/eleicoes/{eleicao_id}/parcial?cargo=` | C, E, K | 200 | 403, 404, 409 | RN-70 a 72, 74 a 79 |
| GET | `/apuracao/eleicoes/{eleicao_id}/resultado?cargo=` | Todos | 200 | 404, 409 | RN-70, 73 a 79 |

Detalhes de implementação:

- Declare `/eleitores/eu` e `/candidatos/eu` **antes** de `/{id}` no arquivo de rotas (o FastAPI casa na ordem declarada).
- IDs de caminho são `int` (`Path(gt=0)`); `cargo` e `status` em query são enums (valor inválido dá 422).
- Abertura e encerramento devolvem a eleição atualizada (com os novos `links`). DELETE devolve 204 sem corpo.
- Paginação: `pagina` ≥ 1 (padrão 1), `tamanho` de 1 a 100 (padrão 20); resposta `{"itens": [...], "pagina": 1, "tamanho": 20, "total": 42}`.
- Nomes dos esquemas: `NovaEleicao`, `AlteracaoEleicao`, `EleicaoResposta`, `NovoEleitor`, `AlteracaoEleitor`, `EleitorResposta`, `PedidoRegistroVoto`, `PreviaVotoResposta`, `PedidoConfirmacaoVoto`, `ComprovanteVotoResposta`, `ApuracaoResposta` etc. Todo esquema de entrada tem `extra="forbid"`.

### Contratos (exemplos que também vão para o Swagger)

**Login**: `POST /api/v1/auth/login`, corpo `application/x-www-form-urlencoded`: `username=29141777638&password=Chefe@2026`.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expira_em": "2026-11-25T12:00:00Z",
  "usuario": {"id": 1, "nome": "Chefe da Seção", "perfil": "CHEFE_SECAO"}
}
```

`usuario` é um `UsuarioResposta` (`id`, `nome`, `perfil`) e `token_type` é sempre `"bearer"`. O corpo todo é uma `LoginResposta`.

**Usuário logado**: `GET /api/v1/auth/me`, resposta `UsuarioLogadoResposta` (acrescenta o `cpf`, só dígitos; nunca traz senha nem hash).

```json
{"id": 1, "nome": "Chefe da Seção", "cpf": "29141777638", "perfil": "CHEFE_SECAO"}
```

**Criar eleição**: `POST /api/v1/eleicoes`

```json
{
  "descricao": "Eleições Gerais 2026 — 1º turno",
  "data": "2026-11-25",
  "turno": 1,
  "horario_abertura": "08:00",
  "horario_encerramento": "17:00"
}
```

Resposta 201:

```json
{
  "id": 1,
  "descricao": "Eleições Gerais 2026 — 1º turno",
  "data": "2026-11-25",
  "turno": 1,
  "horario_abertura": "08:00:00",
  "horario_encerramento": "17:00:00",
  "status": "AGENDADA",
  "aberta_em": null,
  "encerrada_em": null,
  "links": [
    {"rel": "self", "metodo": "GET", "href": "/api/v1/eleicoes/1"},
    {"rel": "editar", "metodo": "PATCH", "href": "/api/v1/eleicoes/1"},
    {"rel": "candidaturas", "metodo": "GET", "href": "/api/v1/eleicoes/1/candidaturas"},
    {"rel": "nova-candidatura", "metodo": "POST", "href": "/api/v1/eleicoes/1/candidaturas"},
    {"rel": "abrir", "metodo": "POST", "href": "/api/v1/eleicoes/1/abertura"}
  ]
}
```

**Cadastrar eleitor**: `POST /api/v1/eleitores`

```json
{
  "nome": "Ana Beatriz Souza",
  "cpf": "011.524.493-03",
  "titulo_eleitor": "100000000001",
  "data_nascimento": "1990-04-12",
  "senha": "Eleitor@123"
}
```

Resposta 201 (sem senha): `{"id": 1, "nome": "Ana Beatriz Souza", "cpf": "01152449303", "titulo_eleitor": "100000000001", "data_nascimento": "1990-04-12", "criado_em": "2026-11-25T07:30:00-03:00"}`

**Cadastrar partido**: `POST /api/v1/partidos` com `{"sigla": "PINO", "nome": "Partido da Inovação", "numero": 10}`.

**Cadastrar candidato**: `POST /api/v1/candidatos` com `{"nome": "Carlos Henrique Lima", "nome_urna": "Carlos Lima", "cpf": "398.259.791-94", "data_nascimento": "1968-03-05", "senha": "Candidato@123"}`.

**Criar candidatura**: `POST /api/v1/eleicoes/1/candidaturas`

```json
{"candidato_id": 1, "partido_id": 1, "cargo": "PRESIDENTE", "numero": "10"}
```

Resposta 201: `{"id": 1, "eleicao_id": 1, "cargo": "PRESIDENTE", "numero": "10", "candidato": {"id": 1, "nome_urna": "Carlos Lima"}, "partido": {"id": 1, "sigla": "PINO", "numero": 10}}`

**Cédula**: `GET /api/v1/votacao/eleicoes/1/cedula`

```json
{
  "eleicao_id": 1,
  "cargos": [
    {
      "cargo": "PRESIDENTE",
      "digitos": 2,
      "ja_votou": false,
      "candidatos": [
        {"numero": "10", "nome_urna": "Carlos Lima", "partido_sigla": "PINO"},
        {"numero": "20", "nome_urna": "Marina Costa", "partido_sigla": "UC"}
      ]
    }
  ]
}
```

**Registrar voto** (etapa 1): `POST /api/v1/votacao/eleicoes/1/votos/registro` com `{"cargo": "PRESIDENTE", "modo": "NUMERO", "numero": "10"}` ou `{"cargo": "SENADOR", "modo": "BRANCO"}`. Um validador do esquema exige `numero` quando o modo é NUMERO e o proíbe quando é BRANCO.

```json
{
  "cargo": "PRESIDENTE",
  "tipo_voto": "NOMINAL",
  "candidato": {"numero": "10", "nome_urna": "Carlos Lima", "partido_sigla": "PINO"},
  "mensagem": "Confira os dados e confirme o voto.",
  "token_cedula": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expira_em": "2026-11-25T10:05:00-03:00",
  "links": [{"rel": "confirmar", "metodo": "POST", "href": "/api/v1/votacao/eleicoes/1/votos/confirmacao"}]
}
```

**Confirmar voto** (etapa 2): `POST /api/v1/votacao/eleicoes/1/votos/confirmacao` com `{"token_cedula": "eyJ..."}`. Resposta 201, **sem a escolha**:

```json
{
  "eleicao_id": 1,
  "cargo": "PRESIDENTE",
  "mensagem": "Voto confirmado.",
  "links": [
    {"rel": "cedula", "metodo": "GET", "href": "/api/v1/votacao/eleicoes/1/cedula"},
    {"rel": "participacao", "metodo": "GET", "href": "/api/v1/votacao/eleicoes/1/participacao"}
  ]
}
```

**Participação**: `{"eleicao_id": 1, "cargos": [{"cargo": "PRESIDENTE", "ja_votou": true}, {"cargo": "SENADOR", "ja_votou": false}]}`

**Apuração parcial e resultado final** (mesmo formato; `tipo` muda para `FINAL` no resultado):

```json
{
  "eleicao_id": 1,
  "tipo": "PARCIAL",
  "status_eleicao": "ABERTA",
  "gerado_em": "2026-11-25T10:30:00-03:00",
  "comparecimento": {"eleitores_aptos": 6, "votantes": 3, "abstencao": 3},
  "cargos": [
    {
      "cargo": "PRESIDENTE",
      "total_votos": 3,
      "votos_validos": 2,
      "brancos": 1,
      "nulos": 0,
      "situacao": "DEFINIDO",
      "criterio": "MAIOR_VOTACAO",
      "mais_votado": {"numero": "10", "nome_urna": "Carlos Lima", "partido_sigla": "PINO", "votos": 2, "percentual_validos": "100.00"},
      "candidatos": [
        {"numero": "10", "nome_urna": "Carlos Lima", "partido_sigla": "PINO", "votos": 2, "percentual_validos": "100.00"},
        {"numero": "20", "nome_urna": "Marina Costa", "partido_sigla": "UC", "votos": 0, "percentual_validos": "0.00"}
      ]
    }
  ]
}
```

### Formato de erro (todas as rotas)

```json
{"erro": {"codigo": "ELEICAO_NAO_ABERTA", "mensagem": "A eleição não está aberta.", "detalhes": {"status": "AGENDADA"}}}
```

Erro de validação do Pydantic, reformatado pelo tratador:

```json
{"erro": {"codigo": "DADOS_INVALIDOS", "mensagem": "Dados inválidos na requisição.", "detalhes": {"campos": [{"campo": "cpf", "mensagem": "CPF inválido."}]}}}
```

`detalhes.campos` traz um item por problema. `campo` é o caminho do campo: o `loc` do Pydantic sem o prefixo `body`, `query` ou `path`, unido por ponto (ex.: `cpf`, `pagina`). `mensagem` é o `msg` do Pydantic sem o prefixo "Value error, ". As mensagens dos nossos validadores são em português; as nativas do Pydantic continuam em inglês (ex.: "Field required").

Os erros do próprio framework seguem o mesmo formato: rota inexistente dá 404 `ROTA_NAO_ENCONTRADA` e método não permitido dá 405 `METODO_NAO_PERMITIDO` (com o cabeçalho `Allow`).

### Catálogo de códigos de erro

| HTTP | Códigos |
| --- | --- |
| 401 | `NAO_AUTENTICADO`, `TOKEN_INVALIDO`, `CREDENCIAIS_INVALIDAS` |
| 403 | `PERFIL_NAO_AUTORIZADO`, `ELEITOR_NAO_APTO`, `SEM_CANDIDATURA_NA_ELEICAO`, `CARGO_NAO_PERMITIDO` |
| 404 | `ELEICAO_NAO_ENCONTRADA`, `ELEITOR_NAO_ENCONTRADO`, `CANDIDATO_NAO_ENCONTRADO`, `CANDIDATURA_NAO_ENCONTRADA`, `ROTA_NAO_ENCONTRADA` |
| 405 | `METODO_NAO_PERMITIDO` |
| 409 | `CPF_JA_CADASTRADO`, `TITULO_JA_CADASTRADO`, `PARTIDO_DUPLICADO`, `ELEICAO_DUPLICADA`, `TRANSICAO_INVALIDA`, `ELEICAO_NAO_EDITAVEL`, `FORA_DA_DATA`, `FORA_DA_JANELA`, `SEM_CANDIDATURAS`, `OUTRA_ELEICAO_ABERTA`, `SEGUNDO_TURNO_INCOMPLETO`, `NUMERO_JA_UTILIZADO`, `CANDIDATURA_DUPLICADA`, `CARGO_NAO_PERMITIDO_NO_TURNO`, `LIMITE_SEGUNDO_TURNO`, `EXCLUSAO_BLOQUEADA`, `ELEICAO_NAO_ABERTA`, `JANELA_ENCERRADA`, `VOTO_JA_REGISTRADO`, `APURACAO_INDISPONIVEL`, `CONFLITO_DE_DADOS` |
| 422 | `DADOS_INVALIDOS`, `CPF_INVALIDO`, `SENHA_INVALIDA`, `IDADE_MINIMA`, `DATA_NO_PASSADO`, `JANELA_INVALIDA`, `NUMERO_INVALIDO_PARA_CARGO`, `REFERENCIA_INEXISTENTE`, `CARGO_NAO_DISPUTADO`, `CEDULA_INVALIDA`, `CEDULA_EXPIRADA` |
| 500 | `ERRO_INTERNO` |
| Outros status do framework | `ERRO_HTTP` |

Critério: **401** = não sei quem você é; **403** = sei quem você é e você não pode; **404** = o recurso do caminho não existe; **409** = o pedido é válido mas conflita com o estado atual; **422** = o pedido em si está errado.

## 11. Documentação Swagger/OpenAPI

A documentação é **code-first**: o FastAPI lê as rotas, os tipos e os esquemas Pydantic e gera a especificação OpenAPI 3.1 sozinho, servida em `/docs` (Swagger UI), `/redoc` e `/openapi.json`. Como a spec sai do código, ela não fica desatualizada. Para o link público que o enunciado pede, a spec é exportada para `docs/openapi.json` e publicada no GitHub Pages com o Swagger UI.

### O que cada rota precisa ter

- `summary` curto em português (aparece na lista do Swagger) e `description` com as regras (citando RN-xx).
- `response_model` e `status_code` corretos.
- `responses=respostas_de_erro(...)` com cada código de erro possível daquela rota (boa prática do material: documentar os erros, não só o caminho feliz).
- `tags=[...]` de um destes grupos: Sistema, Autenticação, Eleições, Candidaturas, Eleitores, Candidatos, Partidos, Votação, Apuração.
- Esquemas com `Field(description=..., examples=[...])` usando valores realistas (os da seção 14), nunca `"string"` ou `0`.

### `app/compartilhado/openapi.py`

```python
from app.compartilhado.erros import ErroResposta

DESCRICAO_API = """
API de simulação de eleição eletrônica (trabalho de Engenharia de Software II).

**Como autenticar:** clique em *Authorize*, informe o CPF em `username` e a senha em `password`.

**Fluxo do voto:** consulte a cédula → registre o voto (recebe `token_cedula`) → confirme com o token.

**Erros:** todas as rotas respondem `{"erro": {"codigo", "mensagem", "detalhes"}}`.
"""

TAGS = [
    {"name": "Sistema", "description": "Saúde da aplicação."},
    {"name": "Autenticação", "description": "Login e dados do usuário logado."},
    {"name": "Eleições", "description": "Cadastro, abertura, encerramento e situação (Chefe da Seção)."},
    {"name": "Candidaturas", "description": "Associação de candidato a eleição, cargo, partido e número."},
    {"name": "Eleitores", "description": "Cadastro de eleitores (Chefe da Seção)."},
    {"name": "Candidatos", "description": "Cadastro de candidatos (Chefe da Seção)."},
    {"name": "Partidos", "description": "Cadastro e consulta de partidos."},
    {"name": "Votação", "description": "Cédula, registro e confirmação do voto (Eleitor)."},
    {"name": "Apuração", "description": "Acompanhamento parcial e resultado final."},
]

_DESCRICOES = {
    401: "Não autenticado ou token inválido",
    403: "Perfil sem permissão para esta operação",
    404: "Recurso não encontrado",
    409: "Conflito com o estado atual (regra de negócio)",
    422: "Dados inválidos",
}


def respostas_de_erro(*codigos_http: int) -> dict:
    """Monta o 'responses' de uma rota com o formato padrão de erro."""
    return {codigo: {"model": ErroResposta, "description": _DESCRICOES[codigo]} for codigo in codigos_http}
```

Exemplo de rota bem documentada:

```python
@roteador.post(
    "/eleicoes/{eleicao_id}/abertura",
    tags=["Eleições"],
    summary="Abre a votação",
    description="Muda a eleição de AGENDADA para ABERTA. Só no dia e dentro da janela, "
                "com pelo menos uma candidatura e nenhuma outra eleição aberta (RN-13, RN-15 a RN-17).",
    response_model=EleicaoResposta,
    responses=respostas_de_erro(401, 403, 404, 409),
)
def abrir(
    eleicao_id: Annotated[int, Path(gt=0)],
    usuario: Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.CHEFE_SECAO))],
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    eleicao = servico.abrir_eleicao(sessao, eleicao_id, agora)
    return EleicaoResposta.de_eleicao(eleicao, usuario.perfil)
```

Em todo o projeto as dependências e os parâmetros de rota usam o estilo `Annotated[Tipo, Depends(...)]` (o ruff acusa B008 quando o `Depends` entra como valor padrão do parâmetro; D-004).

No `FastAPI(...)` do `main.py`, use também `generate_unique_id_function=lambda rota: rota.name`, para os `operationId` ficarem legíveis (`abrir`, `registrar_voto`). Os nomes das funções de rota precisam ser únicos no projeto.

### Botão Authorize

O `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` da seção 7 faz o Swagger mostrar o cadeado. Na demo: Authorize → `username` = CPF, `password` = senha → todas as rotas passam a mandar o token.

### Link público (entregável "link da documentação da API")

1. Script `app/scripts/exportar_openapi.py`: grava `json.dumps(app.openapi(), ensure_ascii=False, indent=2)` em `docs/openapi.json`.
2. Arquivo `docs/index.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>API de Simulação de Eleição Eletrônica — Documentação</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({ url: "openapi.json", dom_id: "#swagger-ui" });
  </script>
</body>
</html>
```

3. No GitHub: Settings → Pages → Deploy from a branch → `main` e pasta `/docs`. No plano gratuito o repositório precisa ser público. O link fica `https://<usuario>.github.io/<repositorio>/`.
4. Esse link é só leitura (não há servidor por trás, então o "Try it out" não executa). Para testar ao vivo, use `http://localhost:8000/docs` ou o Postman/Insomnia.
5. Teste `tests/arquitetura/test_openapi.py`: compara `app.openapi()` com `docs/openapi.json` e falha com a mensagem "Rode python -m app.scripts.exportar_openapi". Assim o link público nunca fica desatualizado.

### Postman e Insomnia

Os dois importam `docs/openapi.json` e criam uma coleção com todas as rotas. Crie um ambiente com as variáveis `base_url` (`http://localhost:8000/api/v1`), `token_chefe`, `token_eleitor`, `token_candidato`, `eleicao_id` e `token_cedula`. Salve a coleção final em `docs/colecao-postman.json` (ou Insomnia) no repositório.

### Frase pronta para a arguição

"A documentação é code-first. O FastAPI gera a especificação OpenAPI 3.1 a partir das rotas, dos type hints e dos esquemas Pydantic. Nós complementamos com descrições, exemplos e as respostas de erro de cada rota. Um script exporta a spec para o GitHub Pages, e um teste garante que a versão publicada é igual à do código."

## 12. Testes

São cerca de 110 testes em três pastas. **Unitários** testam as regras puras do `dominio.py`, sem banco e sem HTTP, e rodam em menos de 2 segundos. **Integração** chama a API de verdade (TestClient) contra um PostgreSQL de teste com as migrações aplicadas, então testam também restrições, trigger e transações. **Arquitetura** verifica as fronteiras entre módulos, as rotas protegidas e a spec publicada. Meta de cobertura: 90% ou mais nos `dominio.py` e 85% ou mais no total.

### Diferença entre unitário e integração (o professor vai perguntar)

|  | Unitário | Integração |
| --- | --- | --- |
| O que testa | Uma função de regra, isolada | O caminho inteiro: HTTP → rota → serviço → banco → resposta |
| Dependências | Nenhuma (só Python) | API + PostgreSQL de teste (porta 5433) |
| Velocidade | Milissegundos | Décimos de segundo |
| Exemplo | `validar_abertura` recusa abrir fora da data | `POST /eleicoes/1/abertura` fora da data responde 409 `FORA_DA_DATA` |
| Quando falha, aponta para | A regra errada | Algum ponto da integração (rota, transação, restrição) |
| Pasta | `tests/unitarios/` | `tests/integracao/` |

### Infraestrutura de teste

`tests/conftest.py` (configuração antes de importar o app):

```python
import os

URL_TESTE = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://eleicao:eleicao@localhost:5433/eleicao_teste"
)
# Nos testes, a própria aplicação aponta para o banco de teste (nunca para o da demo)
os.environ["DATABASE_URL"] = URL_TESTE
os.environ["BCRYPT_CUSTO"] = "4"  # bcrypt rápido nos testes
os.environ.setdefault("JWT_SEGREDO", "segredo-de-teste-com-pelo-menos-32-caracteres")
```

`tests/integracao/conftest.py`:

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.compartilhado.banco import engine
from app.compartilhado.relogio import obter_agora
from app.main import app
from tests.auxiliares import cabecalho_chefe  # noqa: F401  (registra a fixture)

TABELAS_DO_PUBLIC = """
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename <> 'alembic_version'
"""


@pytest.fixture(scope="session", autouse=True)
def banco_migrado():
    """Recria o esquema uma vez por execução, com as migrações reais (constraints e trigger)."""
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def banco_limpo():
    """Cada teste começa com o banco vazio. TRUNCATE não dispara o trigger de imutabilidade.

    As tabelas são descobertas no próprio banco (todas do schema public, menos a
    alembic_version), então a fixture funciona mesmo quando ainda não existe nenhuma tabela.
    """
    with engine.begin() as conexao:
        tabelas = conexao.execute(text(TABELAS_DO_PUBLIC)).scalars().all()
        if tabelas:
            lista = ", ".join(f'"{tabela}"' for tabela in tabelas)
            conexao.execute(text(f"TRUNCATE {lista} RESTART IDENTITY CASCADE"))


class RelogioDeTeste:
    def __init__(self, inicio: datetime):
        self.atual = inicio

    def __call__(self) -> datetime:
        return self.atual

    def avancar(self, **intervalo) -> None:
        self.atual += timedelta(**intervalo)


@pytest.fixture
def relogio():
    """Congela o tempo em 25/11/2026 às 10:00 (horário de Brasília)."""
    relogio = RelogioDeTeste(datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo")))
    app.dependency_overrides[obter_agora] = relogio
    yield relogio
    app.dependency_overrides.pop(obter_agora, None)


@pytest.fixture
def cliente(relogio):
    return TestClient(app)
```

A fixture `banco_limpo` **descobre as tabelas no próprio banco** (todas do schema `public`, menos `alembic_version`) e só faz `TRUNCATE` se houver alguma. Assim não há lista fixa de tabelas para manter e a fixture já funciona na tarefa 00, quando ainda não existe tabela.

O `migrations/env.py` lê a URL de `obter_configuracao().database_url`, então nos testes ele já usa o banco de teste.

`tests/auxiliares.py` (fábricas que deixam cada teste com 5 a 10 linhas):

- `gerar_cpf(semente: int) -> str`: CPF válido e determinístico (mesmo algoritmo da seção 9); pula o CPF de dígitos todos iguais (RN-07).
- `criar_chefe(cpf=CPF_CHEFE, senha=SENHA_CHEFE, agora_=None) -> int`: cria o Chefe direto pelo serviço de identidade, faz commit e devolve o id. `CPF_CHEFE` (`29141777638`) e `SENHA_CHEFE` (`Chefe@2026`) são constantes do mesmo arquivo.
- `login(cliente, cpf, senha) -> dict`: devolve o cabeçalho `{"Authorization": "Bearer ..."}`.
- Fixtures `cabecalho_chefe`, `cabecalho_eleitor`, `cabecalho_candidato`. Elas ficam em `tests/auxiliares.py` e são registradas por um `import` em `tests/integracao/conftest.py` (o pytest só descobre fixtures de `conftest.py` ou importadas; por isso o `# noqa: F401`). Toda fixture nova de `auxiliares.py` precisa ser importada ali também.
- `novo_eleitor`, `novo_partido`, `novo_candidato`, `nova_eleicao`, `nova_candidatura`: chamam a API com dados válidos padrão e aceitam sobrescritas (`novo_eleitor(cliente, cab, data_nascimento="2015-01-01")`).
- `eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)`: eleição em 25/11/2026 das 08:00 às 17:00, Presidente 10 e 20, Senador 101 e 202, já aberta. Devolve os ids.
- `votar(cliente, cabecalho, eleicao_id, cargo, numero=None, branco=False)`: registro + confirmação (helper de teste; a API continua sem flags).

### Testes unitários (`tests/unitarios/`)

| ID | Arquivo | Caso | RN |
| --- | --- | --- | --- |
| TU-01 | `test_validadores.py` | CPF válido conhecido (529.982.247-25) é aceito | RN-07 |
| TU-02 | `test_validadores.py` | CPF com dígito verificador errado é recusado | RN-07 |
| TU-03 | `test_validadores.py` | CPF com todos os dígitos iguais é recusado | RN-07 |
| TU-04 | `test_validadores.py` | Normalização aceita com e sem pontuação; recusa letras e tamanho errado | RN-07 |
| TU-05 | `test_validadores.py` | Idade antes e depois do aniversário, e nascido em 29/02 | RN-22 |
| TU-06 | `test_validadores.py` | `numero_valido_para_cargo` parametrizado: 5 cargos × (válido, curto, longo, zero à esquerda, letras) | RN-42 |
| TU-07 | `test_identidade.py` | Senha com 7 caracteres, só espaços ou mais de 72 bytes é recusada; com 8 é aceita | RN-05 |
| TU-08 | `test_identidade.py` | Hash diferente da senha; `senha_confere` verdadeiro e falso | RN-05 |
| TU-09 | `test_identidade.py` | Token de acesso: criar e ler devolve o id | RN-02 |
| TU-10 | `test_identidade.py` | Token adulterado é recusado | RN-02 |
| TU-11 | `test_identidade.py` | Token expirado é recusado (configuração com expiração negativa via `monkeypatch`) | RN-02 |
| TU-12 | `test_identidade.py` | Token de cédula usado como token de acesso é recusado | RN-02, RN-57 |
| TU-13 | `test_eleicoes_dominio.py` | Agendamento: data no passado, janela invertida e caso válido | RN-11 |
| TU-14 | `test_eleicoes_dominio.py` | Transições parametrizadas (3 status × abrir/encerrar): só AGENDADA→ABERTA e ABERTA→ENCERRADA passam | RN-13 |
| TU-15 | `test_eleicoes_dominio.py` | Edição só em AGENDADA | RN-14 |
| TU-16 | `test_eleicoes_dominio.py` | Abertura: fora da data; antes da abertura; exatamente no horário de abertura (passa); exatamente no de encerramento (falha); outra aberta; sem candidaturas; 2º turno com 1 e com 3 candidatos; caso válido | RN-15 a 17 |
| TU-17 | `test_eleicoes_dominio.py` | Candidatura no 2º turno: Senador recusado; terceiro candidato recusado | RN-45 |
| TU-18 | `test_eleicoes_dominio.py` | `links_da_eleicao` para cada perfil × status (tabela da seção 9.5) | RN-19 |
| TU-19 | `test_votacao_dominio.py` | Pode votar: AGENDADA e ENCERRADA recusam; ABERTA depois do encerramento e no dia seguinte recusam; dentro da janela passa | RN-51, RN-52 |
| TU-20 | `test_votacao_dominio.py` | Eleitor apto: cadastrado antes ou no mesmo instante passa; depois é recusado | RN-53 |
| TU-21 | `test_votacao_dominio.py` | `resolver_escolha`: número existente → NOMINAL; inexistente → NULO; BRANCO → BRANCO; dígitos errados → 422 | RN-58 |
| TU-22 | `test_cedulas.py` | Emitir e ler devolve os mesmos dados | RN-57 |
| TU-23 | `test_cedulas.py` | Ler 6 minutos depois → `CEDULA_EXPIRADA` | RN-57 |
| TU-24 | `test_cedulas.py` | Cédula adulterada e token de acesso no lugar da cédula → `CEDULA_INVALIDA` | RN-57 |
| TU-25 | `test_apuracao_dominio.py` | Percentual: 1/3 = 33.33; 2/3 = 66.67; 0 válidos = 0.00 | RN-76 |
| TU-26 | `test_apuracao_dominio.py` | Candidato com 0 votos aparece; ordenação por votos e depois número | RN-75 |
| TU-27 | `test_apuracao_dominio.py` | Brancos e nulos não entram nos válidos | RN-76 |
| TU-28 | `test_apuracao_dominio.py` | Mais votado único → DEFINIDO, critério MAIOR_VOTACAO | RN-77 |
| TU-29 | `test_apuracao_dominio.py` | Empate resolvido pelo mais idoso → DESEMPATE_POR_IDADE | RN-77 |
| TU-30 | `test_apuracao_dominio.py` | Empate com mesma data de nascimento → EMPATE, sem mais votado | RN-77 |
| TU-31 | `test_apuracao_dominio.py` | Só brancos e nulos → SEM_VOTOS_VALIDOS | RN-78 |

### Testes de integração (`tests/integracao/`)

| ID | Arquivo | Caso | RN |
| --- | --- | --- | --- |
| TI-01 | `test_auth_api.py` | Login correto devolve token e perfil | RN-01 |
| TI-02 | `test_auth_api.py` | Senha errada → 401 `CREDENCIAIS_INVALIDAS` | RN-01 |
| TI-03 | `test_auth_api.py` | CPF inexistente → 401 com a mesma mensagem | RN-01 |
| TI-04 | `test_auth_api.py` | Sem token → 401 `NAO_AUTENTICADO` e cabeçalho `WWW-Authenticate` | RN-06 |
| TI-05 | `test_auth_api.py` | Token inválido → 401 `TOKEN_INVALIDO` | RN-02 |
| TI-06 | `test_auth_api.py` | `/auth/me` devolve o usuário logado | RN-02 |
| TI-07 | `test_auth_api.py` | Usuário excluído com token ainda válido → 401 | RN-02 |
| TI-08 | `test_permissoes.py` | Matriz parametrizada: cada rota protegida × cada perfil não permitido → 403; sem token → 401 (tabela da seção 10) | RN-03, RN-06 |
| TI-09 | `test_eleicoes_api.py` | Criar → 201, AGENDADA, link `abrir` presente | RN-10, RN-19 |
| TI-10 | `test_eleicoes_api.py` | Mesma data e turno → 409 `ELEICAO_DUPLICADA` | RN-12 |
| TI-11 | `test_eleicoes_api.py` | Editar AGENDADA funciona; editar ABERTA → 409 | RN-14 |
| TI-12 | `test_eleicoes_api.py` | Abrir na data e janela → ABERTA, `aberta_em` preenchido, link `encerrar` | RN-15 |
| TI-13 | `test_eleicoes_api.py` | Abrir sem candidaturas → 409 `SEM_CANDIDATURAS` | RN-15 |
| TI-14 | `test_eleicoes_api.py` | Abrir fora da data ou fora da janela → 409 | RN-15 |
| TI-15 | `test_eleicoes_api.py` | Abrir com outra eleição aberta → 409 `OUTRA_ELEICAO_ABERTA` | RN-16 |
| TI-16 | `test_eleicoes_api.py` | Encerrar ABERTA funciona; encerrar AGENDADA e reabrir ENCERRADA → 409 | RN-13, RN-18 |
| TI-17 | `test_eleicoes_api.py` | Listar com filtro de status | RN-19 |
| TI-18 | `test_eleitores_api.py` | Cadastrar → 201, sem senha na resposta; o eleitor consegue fazer login | RN-20 |
| TI-19 | `test_eleitores_api.py` | CPF inválido → 422; CPF repetido (inclusive de um candidato) → 409; título repetido → 409 | RN-07, RN-21 |
| TI-20 | `test_eleitores_api.py` | Menor de 16 anos → 422 `IDADE_MINIMA` | RN-22 |
| TI-21 | `test_eleitores_api.py` | Campo extra `perfil` no corpo → 422 | RN-23 |
| TI-22 | `test_eleitores_api.py` | Alterar nome e senha (a nova senha funciona); tentar alterar CPF → 422 | RN-23 |
| TI-23 | `test_eleitores_api.py` | Excluir eleitor que não votou → 204, e o login dele falha | RN-24 |
| TI-24 | `test_eleitores_api.py` | Excluir eleitor que votou → 409 `EXCLUSAO_BLOQUEADA` | RN-24 |
| TI-25 | `test_eleitores_api.py` | Listar com filtro por nome e paginação (`total`, `pagina`, `tamanho`) | RN-20 |
| TI-26 | `test_eleitores_api.py` | `/eleitores/eu` devolve os dados do próprio eleitor | RN-25 |
| TI-27 | `test_candidatos_api.py` | Criar partido; sigla ou número repetido → 409 | RN-32 |
| TI-28 | `test_candidatos_api.py` | Cadastrar candidato; `/candidatos/eu` | RN-30, RN-31 |
| TI-29 | `test_candidatos_api.py` | Excluir candidato sem candidaturas → 204; com candidatura → 409 | RN-33 |
| TI-30 | `test_candidaturas_api.py` | Criar candidatura válida → 201 | RN-40 |
| TI-31 | `test_candidaturas_api.py` | Dígitos errados para o cargo → 422 | RN-42 |
| TI-32 | `test_candidaturas_api.py` | Número repetido no mesmo cargo → 409; Presidente 10 e Governador 10 na mesma eleição → 201 | RN-43 |
| TI-33 | `test_candidaturas_api.py` | Mesmo candidato duas vezes na eleição → 409 | RN-44 |
| TI-34 | `test_candidaturas_api.py` | Candidato ou partido inexistente → 422 `REFERENCIA_INEXISTENTE` | RN-46 |
| TI-35 | `test_candidaturas_api.py` | Criar, editar ou remover com eleição ABERTA → 409 | RN-40 |
| TI-36 | `test_candidaturas_api.py` | 2º turno: Senador → 409; 3º candidato a Presidente → 409; abrir com 1 candidato → 409 | RN-17, RN-45 |
| TI-37 | `test_candidaturas_api.py` | `/candidaturas/minhas` | RN-47 |
| TI-38 | `test_votacao_api.py` | Cédula lista só cargos disputados, na ordem da urna, com `ja_votou` | RN-55, RN-61 |
| TI-39 | `test_votacao_api.py` | Registrar voto nominal → 200 com candidato e token, e **nenhuma linha** em `votos` nem em `registros_votacao` | RN-56 |
| TI-40 | `test_votacao_api.py` | Registrar número inexistente → NULO; modo BRANCO → BRANCO | RN-58 |
| TI-41 | `test_votacao_api.py` | Confirmar → 201 sem a escolha na resposta; 1 linha em cada tabela | RN-56, RN-60 |
| TI-42 | `test_votacao_api.py` | Confirmar a mesma cédula de novo → 409 `VOTO_JA_REGISTRADO` | RN-54, RN-59 |
| TI-43 | `test_votacao_api.py` | Registrar de novo no mesmo cargo depois de confirmar → 409 | RN-54 |
| TI-44 | `test_votacao_api.py` | Votar em outro cargo depois do primeiro → 201 | RN-54 |
| TI-45 | `test_votacao_api.py` | Eleição AGENDADA ou ENCERRADA → 409 `ELEICAO_NAO_ABERTA` | RN-51 |
| TI-46 | `test_votacao_api.py` | Chefe e Candidato tentando votar → 403 | RN-50 |
| TI-47 | `test_votacao_api.py` | Cédula de outro eleitor → 422 `CEDULA_INVALIDA` | RN-57 |
| TI-48 | `test_votacao_api.py` | Cédula de outra eleição → 422 | RN-57 |
| TI-49 | `test_votacao_api.py` | `relogio.avancar(minutes=6)` e confirmar → 422 `CEDULA_EXPIRADA` | RN-57 |
| TI-50 | `test_votacao_api.py` | Eleitor cadastrado depois da abertura → 403 `ELEITOR_NAO_APTO` | RN-53 |
| TI-51 | `test_votacao_api.py` | Cargo sem candidaturas → 422 `CARGO_NAO_DISPUTADO` | RN-55 |
| TI-52 | `test_votacao_api.py` | Depois do horário de encerramento, sem o Chefe encerrar → 409 `JANELA_ENCERRADA` | RN-52 |
| TI-53 | `test_votacao_api.py` | `/participacao` mostra cargos votados, sem a escolha | RN-61 |
| TI-54 | `test_votacao_api.py` | Mudar de ideia: registrar 10, registrar 20, confirmar a segunda cédula → conta para o 20; a primeira cédula depois disso → 409 | RN-56 |
| TI-55 | `test_apuracao_api.py` | Parcial muda a cada voto confirmado (0 → 1 → 2) | RN-74 |
| TI-56 | `test_apuracao_api.py` | Parcial com eleição AGENDADA ou ENCERRADA → 409 | RN-70 |
| TI-57 | `test_apuracao_api.py` | Candidato vê só o seu cargo; pedir outro → 403; candidato sem candidatura na eleição → 403 | RN-72 |
| TI-58 | `test_apuracao_api.py` | Eleitor e Chefe veem todos os cargos | RN-71 |
| TI-59 | `test_apuracao_api.py` | Resultado com eleição ABERTA → 409 | RN-70 |
| TI-60 | `test_apuracao_api.py` | Resultado final: votos, percentuais, brancos, nulos e mais votado por cargo | RN-73 a 76 |
| TI-61 | `test_apuracao_api.py` | Empate no resultado decidido pelo mais idoso | RN-77 |
| TI-62 | `test_apuracao_api.py` | Comparecimento: aptos, votantes e abstenção | RN-79 |
| TI-63 | `test_banco_restricoes.py` | `UPDATE` direto em `votos` → erro do trigger | RN-59 |
| TI-64 | `test_banco_restricoes.py` | `DELETE` direto em `votos` e em `registros_votacao` → erro do trigger | RN-59 |
| TI-65 | `test_banco_restricoes.py` | Registro duplicado inserido direto → violação de `pk_registros_votacao` | RN-54 |
| TI-66 | `test_banco_restricoes.py` | Duas eleições ABERTA → violação de `uq_eleicoes_uma_aberta` | RN-16 |
| TI-67 | `test_banco_restricoes.py` | Voto NOMINAL sem candidatura → CHECK; voto para Senador apontando candidatura a Presidente → FK composta | RN-60 |
| TI-68 | `test_banco_restricoes.py` | Número com dígitos errados inserido direto → CHECK | RN-42 |
| TI-69 | `test_sigilo.py` | Inspeção do esquema (`sqlalchemy.inspect`): `votos` não tem coluna nem FK para eleitor ou usuário, nem coluna de data/hora; `registros_votacao` não tem candidatura nem tipo | RN-60 |
| TI-70 | `test_sigilo.py` | Depois de votar, nenhuma resposta (`/participacao`, `/eleitores/eu`, `/auth/me`, confirmação) contém o número ou o nome do candidato escolhido | RN-60 |
| TI-71 | `test_sigilo.py` | IDs de `votos` são UUID versão 4 | RN-60 |
| TI-72 | `test_sigilo.py` | Com `caplog`, a confirmação não registra token, número nem candidatura no log | RN-60 |
| TI-73 | `test_concorrencia.py` | Duas threads, cada uma com sua sessão, chamam `confirmar_voto` com a mesma cédula ao mesmo tempo (`threading.Barrier`): exatamente um sucesso, um `VOTO_JA_REGISTRADO`, 1 voto no banco | RN-54 |
| TI-74 | `test_fluxo_completo.py` | O roteiro da demonstração (seção 16) de ponta a ponta | Todas |

O TI-73 testa no nível do serviço (duas sessões reais em duas threads), porque o TestClient não garante requisições realmente simultâneas.

### Testes de arquitetura (`tests/arquitetura/`)

| ID | Arquivo | Caso |
| --- | --- | --- |
| TA-01 | `test_dependencias.py` | Com `ast`, lê cada `.py` de `app/<modulo>/` e verifica: só importa `app.<outro>.servico` dos módulos permitidos no grafo da seção 5 (mais `app.identidade.dependencias` e `app.compartilhado`); `dominio.py` não importa `fastapi` nem `sqlalchemy`. |
| TA-02 | `test_rotas_protegidas.py` | Para cada `APIRoute` do app, exceto a lista branca, a árvore de dependências contém `obter_usuario_atual`. |
| TA-03 | `test_openapi.py` | `app.openapi()` é igual a `docs/openapi.json`. |
| TA-04 | `test_openapi.py` | Toda rota protegida documenta a resposta 401, e toda rota com perfil restrito documenta a 403. |

### Convenções

- Nome do teste diz o comportamento: `test_nao_permite_votar_com_eleicao_agendada`.
- Docstring cita o RN e o ID: `"""TI-45 / RN-51: ..."""`.
- Padrão Arrange, Act, Assert, separados por uma linha em branco.
- Toda verificação de erro confere o **status** e o **`codigo`** do corpo.
- Nada de `sleep` para esperar tempo passar: use `relogio.avancar(...)`.

## 13. Plano de implementação, Git e divisão do grupo

São 10 fases, na ordem das dependências entre módulos (quem é usado vem antes de quem usa). Cada fase termina com o sistema funcionando, testes verdes e commits pequenos. Nenhuma fase começa antes da anterior estar verde.

### Como executar cada fase

1. `git switch -c feat/<nome-da-fase>` a partir da `main` atualizada.
2. Liste os arquivos que a fase vai criar ou alterar e implemente seguindo as seções que ela indica.
3. Leia o diff inteiro. Se não conseguir explicar um trecho, não commite.
4. Rode `ruff check .`, `ruff format --check .` e `pytest`.
5. Faça os commits da fase (abaixo), um assunto por commit.
6. Abra um Pull Request; **outro membro** revisa e aprova; merge na `main`.

### Fases

**Fase 0: fundação do repositório**

- Entrega: estrutura de pastas da seção 5; `requirements*.txt`, `pyproject.toml`, `docker-compose.yml`, `.env.example`, `.gitignore`; `alembic init migrations` com `env.py` lendo `obter_configuracao().database_url` e `target_metadata = Base.metadata` (importando `app.registro_modelos`); `main.py` com `/health`; `tests/conftest.py` e `tests/integracao/conftest.py`; `.github/workflows/ci.yml`; README com "como rodar".
- Pronto quando: `docker compose up -d`, `uvicorn app.main:app` sobe, `GET /health` responde 200, e `pytest` passa com um teste de integração do health.
- Commits: `chore: cria estrutura inicial do projeto` · `chore: adiciona docker compose com banco e banco de teste` · `chore: configura alembic` · `test: adiciona teste do endpoint de health` · `ci: adiciona pipeline de lint e testes`.

**Fase 1: módulo compartilhado**

- Entrega: `config.py`, `banco.py` (convenção de nomes, `obter_sessao`), `erros.py` (hierarquia, `ErroResposta`, tratadores, tradução de restrições), `relogio.py`, `validadores.py`, `dominio.py` (`Cargo`), `paginacao.py`, `openapi.py`.
- Testes: TU-01 a TU-06.
- Commits: `feat(compartilhado): adiciona configuração e sessão do banco` · `feat(compartilhado): padroniza respostas de erro` · `feat(compartilhado): adiciona relógio injetável` · `feat(compartilhado): valida CPF e calcula idade` · `feat(compartilhado): define cargos e dígitos por cargo` · `test(compartilhado): cobre validadores e números por cargo`.

**Fase 2: identidade**

- Entrega: modelo `usuarios` + migração `0001_identidade`; `dominio.py` (`Perfil`, `UsuarioAutenticado`, `validar_senha`); `senhas.py`; `tokens.py`; `servico.py`; `dependencias.py`; rotas `/auth/login` e `/auth/me`; script `criar_chefe`.
- Testes: TU-07 a TU-12, TI-01 a TI-07.
- Commits: `feat(identidade): cria tabela de usuários` · `feat(identidade): gera hash de senha com bcrypt` · `feat(identidade): emite e valida token de acesso` · `feat(identidade): adiciona login e consulta do usuário logado` · `feat(identidade): protege rotas por perfil` · `feat(scripts): cria chefe da seção inicial` · `test(identidade): ...`. Tag `v0.1.0`.

**Fase 3: eleitores**

- Entrega: modelo + `0002_eleitores`; domínio (idade mínima); serviço usando `identidade.servico`; rotas CRUD + `/eleitores/eu`.
- Testes: TI-18 a TI-23, TI-25, TI-26 (o TI-24 entra na Fase 6, quando existir voto).
- Commits: `feat(eleitores): cria tabela de eleitores` · `feat(eleitores): cadastra eleitor com credencial` · `feat(eleitores): lista, consulta, altera e exclui eleitores` · `test(eleitores): ...`.

**Fase 4: candidatos e partidos**

- Entrega: modelos + `0003_candidatos_partidos`; serviço; rotas de candidatos (CRUD + `/eu`) e de partidos.
- Testes: TI-27, TI-28 e a parte "sem candidaturas" do TI-29.
- Commits: `feat(candidatos): cria tabelas de candidatos e partidos` · `feat(candidatos): cadastra partidos` · `feat(candidatos): gerencia candidatos` · `test(candidatos): ...`.

**Fase 5: eleições e candidaturas**

- Entrega: modelos + `0004_eleicoes_candidaturas` (com índice parcial e FK composta-alvo); domínio (agendamento, transições, abertura, candidatura, links); serviço com travas; rotas de eleições e candidaturas + `/candidaturas/minhas`.
- Testes: TU-13 a TU-18, TI-09 a TI-17, TI-29 completo, TI-30 a TI-37.
- Commits: `feat(eleicoes): cria tabelas de eleições e candidaturas` · `feat(eleicoes): cadastra e edita eleições` · `feat(eleicoes): abre e encerra a votação` · `feat(eleicoes): adiciona links HATEOAS` · `feat(eleicoes): gerencia candidaturas pela eleição` · `test(eleicoes): ...`. Tag `v0.2.0`.

**Fase 6: votação**

- Entrega: modelos + `0005_votacao` (com trigger); `dominio.py`; `cedulas.py`; serviço (cédula, registro, confirmação, participação, contagens); rotas.
- Testes: TU-19 a TU-24, TI-24, TI-38 a TI-54, TI-63 a TI-73.
- Commits: `feat(votacao): cria tabelas de registro e voto sem ligação entre si` · `feat(votacao): impede alteração de votos com trigger` · `feat(votacao): monta a cédula do eleitor` · `feat(votacao): registra voto com cédula assinada` · `feat(votacao): confirma voto de forma atômica` · `test(votacao): ...` · `test(votacao): garante sigilo e voto único sob concorrência`. Tag `v0.3.0`.

**Fase 7: apuração**

- Entrega: `dominio.py` (percentual, apurar cargo, mais votado), serviço (parcial e resultado, com regras de visibilidade), rotas.
- Testes: TU-25 a TU-31, TI-55 a TI-62.
- Commits: `feat(apuracao): calcula percentuais e mais votado` · `feat(apuracao): disponibiliza acompanhamento parcial por perfil` · `feat(apuracao): disponibiliza resultado final` · `test(apuracao): ...`. Tag `v0.4.0`.

**Fase 8: qualidade transversal**

- Entrega: matriz de permissões (TI-08); testes de arquitetura TA-01, TA-02, TA-04; fluxo completo TI-74; middleware de log (método, caminho, status, duração); revisão de segurança com a tabela da seção 7; **rodada de refatoração** (nomes, funções longas, duplicação); cobertura nas metas.
- Commits: `test: verifica permissões de todas as rotas por perfil` · `test: verifica fronteiras entre módulos` · `test: cobre o fluxo completo da eleição` · `feat: registra log das requisições sem dados sensíveis` · `refactor: ...`.

**Fase 9: documentação e entrega**

- Entrega: descrições, exemplos e respostas de erro em todas as rotas; `exportar_openapi.py`, `docs/openapi.json`, `docs/index.html`, GitHub Pages ativo; TA-03; `seed_demo.py`; `README.md`, `docs/ARQUITETURA.md`, `docs/MODELAGEM.md`, `docs/DEMO.md` (seção 15); coleção Postman ou Insomnia em `docs/`.
- Commits: `docs: documenta rotas com exemplos e erros` · `docs: publica especificação OpenAPI no GitHub Pages` · `feat(scripts): adiciona dados de demonstração` · `docs: descreve arquitetura, modularização e modelagem` · `docs: adiciona roteiro e coleção da demonstração`. Tag `v1.0.0`.

### Regras de Git

- `main` sempre verde. Trabalho em branches (`feat/identidade`, `feat/votacao`, `docs/entrega`), integrado por Pull Request revisado por outro membro.
- Conventional Commits em português: `tipo(escopo): descrição no presente`. Tipos: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `ci`.
- Um assunto por commit; teste junto da funcionalidade ou logo depois.
- Proibido: "ajustes", "final", "agora vai", um commit gigante com o projeto inteiro, `.env` versionado.
- Cada membro commita com o próprio usuário Git (`git config user.name` e `user.email`), para o histórico mostrar a contribuição de cada um.
- Tags semânticas marcam marcos: `v0.1.0` (login), `v0.2.0` (eleições), `v0.3.0` (votação), `v0.4.0` (apuração), `v1.0.0` (entrega).

### `.github/workflows/ci.yml`

```yaml
name: CI

on: [push, pull_request]

jobs:
  testes:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: eleicao
          POSTGRES_PASSWORD: eleicao
          POSTGRES_DB: eleicao_teste
        ports:
          - 5433:5432
        options: >-
          --health-cmd "pg_isready -U eleicao"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    env:
      TEST_DATABASE_URL: postgresql+psycopg://eleicao:eleicao@localhost:5433/eleicao_teste
      DATABASE_URL: postgresql+psycopg://eleicao:eleicao@localhost:5433/eleicao_teste
      JWT_SEGREDO: segredo-de-ci-com-pelo-menos-32-caracteres
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest --cov=app --cov-report=term-missing
```

### Divisão do grupo (Lei de Conway na prática)

A divisão de trabalho espelha a divisão de módulos. Com menos de 5 pessoas, junte linhas.

| Membro | Módulos | Fases | Também cuida de |
| --- | --- | --- | --- |
| 1 | `compartilhado`, `identidade` | 0, 1, 2 | CI, revisão de segurança |
| 2 | `eleitores`, `candidatos` | 3, 4 | Dados de demonstração |
| 3 | `eleicoes` (com candidaturas) | 5 | HATEOAS, relógio e travas |
| 4 | `votacao` | 6 | Sigilo, trigger, concorrência |
| 5 | `apuracao`, documentação | 7, 9 | Swagger, README, GitHub Pages |
| Todos | Revisão cruzada | 8 | Cada um lê e explica o código dos outros (a arguição é individual) |

### Extras opcionais (só depois da v1.0.0, se sobrar tempo)

Nada daqui entra sem decisão do grupo.

- Limite de tentativas de login (por exemplo, 5 falhas em 15 minutos por CPF).
- Apuração parcial em tempo real via Server-Sent Events.
- `Dockerfile` da API e serviço `api` no compose.
- Deploy público da API (para o "Try it out" funcionar no link).

## 14. Dados de demonstração (seed)

`python -m app.scripts.seed_demo` cria um cenário completo e fictício: o Chefe, 3 partidos, 6 eleitores, 10 candidatos (2 por cargo) e uma eleição **para o dia em que o script roda**, das 00:00 às 23:59, ainda AGENDADA (assim a demo mostra a abertura). Todos os CPFs abaixo têm dígitos verificadores válidos. Nomes e partidos são inventados.

### Regras do script

- Usa os **serviços** dos módulos (não SQL direto), para que todas as regras sejam aplicadas também aqui.
- Usa `relogio.agora()` para a data da eleição.
- Se o CPF do Chefe já tiver dados de demo, para com a mensagem "Dados de demonstração já existem".
- Para recomeçar do zero: `docker compose down -v`, `docker compose up -d`, `alembic upgrade head`, `python -m app.scripts.seed_demo`.
- Imprime no fim a tabela de logins abaixo (nunca em produção: senhas fixas são só para a demo).

### Chefe da Seção

| Nome | CPF | Senha |
| --- | --- | --- |
| Chefe da Seção | 291.417.776-38 | `Chefe@2026` |

### Partidos

| Sigla | Nome | Número |
| --- | --- | --- |
| PINO | Partido da Inovação | 10 |
| UC | União Cidadã | 20 |
| MV | Movimento Verde | 30 |

### Eleitores (senha de todos: `Eleitor@123`)

| Nome | CPF | Título | Nascimento |
| --- | --- | --- | --- |
| Ana Beatriz Souza | 011.524.493-03 | 100000000001 | 1990-04-12 |
| Bruno Almeida | 341.672.110-17 | 100000000002 | 1985-09-30 |
| Camila Rocha | 945.807.302-24 | 100000000003 | 2001-01-15 |
| Diego Martins | 917.400.297-04 | 100000000004 | 1978-06-22 |
| Elisa Ferreira | 526.018.159-06 | 100000000005 | 2008-02-10 (17 anos, pode votar) |
| Fábio Nunes | 356.230.123-53 | 100000000006 | 1960-12-03 |

Reservado para a demo ao vivo (cadastrar **depois** da abertura e mostrar RN-53): Gustavo Pereira, CPF 217.533.772-34, título 100000000007, nascido em 1995-05-05.

### Candidatos e candidaturas (senha de todos: `Candidato@123`)

| Cargo | Número | Nome de urna | Nome completo | CPF | Nascimento | Partido |
| --- | --- | --- | --- | --- | --- | --- |
| Presidente | 10 | Carlos Lima | Carlos Henrique Lima | 398.259.791-94 | 1968-03-05 | PINO |
| Presidente | 20 | Marina Costa | Marina Costa Ribeiro | 795.422.058-30 | 1972-07-19 | UC |
| Governador | 10 | Ricardo Souza | Ricardo Souza Neto | 906.790.377-99 | 1965-11-11 | PINO |
| Governador | 30 | Helena Prado | Helena Prado Antunes | 787.789.328-07 | 1975-05-02 | MV |
| Senador | 202 | Paulo Mendes | Paulo Roberto Mendes | 748.526.057-00 | 1959-08-08 | UC |
| Senador | 303 | Lúcia Ramos | Lúcia Ramos Vieira | 442.323.221-91 | 1970-10-10 | MV |
| Deputado Federal | 1010 | Tiago Freitas | Tiago Freitas Moura | 198.344.417-03 | 1988-04-04 | PINO |
| Deputado Federal | 2020 | Sandra Oliveira | Sandra Oliveira Lins | 308.023.002-78 | 1980-12-12 | UC |
| Deputado Estadual | 10100 | Rafael Dias | Rafael Dias Correia | 577.463.706-91 | 1992-03-14 | PINO |
| Deputado Estadual | 30300 | Juliana Torres | Juliana Torres Bastos | 864.542.841-58 | 1983-07-07 | MV |

Repare que Presidente 10 e Governador 10 convivem na mesma eleição: o número é único **por cargo** (RN-43).

### Eleição

| Campo | Valor |
| --- | --- |
| Descrição | Eleições Gerais 2026 — 1º turno (simulação) |
| Data | Data de hoje (no fuso America/Sao_Paulo) |
| Turno | 1 |
| Janela | 00:00 às 23:59 |
| Status após o seed | AGENDADA, com as 10 candidaturas acima |

## 15. Entregáveis escritos

O enunciado pede três entregas: o link do repositório, o link da documentação da API e um arquivo (PDF ou README) com arquitetura, modularização e modelagem do banco. O README é o arquivo principal; os detalhes ficam em `docs/` e são linkados a partir dele. Se o professor preferir PDF, exporte o README (por exemplo, `pandoc README.md -o entrega.pdf` ou imprimindo a página do GitHub).

| Entregável | Onde | Conteúdo |
| --- | --- | --- |
| Link do repositório | GitHub (público) | Código, histórico de commits, tags, CI verde |
| Link da documentação da API | GitHub Pages (`https://<usuario>.github.io/<repositorio>/`) | Swagger UI com `docs/openapi.json` (seção 11) |
| Arquivo de arquitetura, modularização e modelagem | `README.md` + `docs/ARQUITETURA.md` + `docs/MODELAGEM.md` | Abaixo |

### Estrutura obrigatória do `README.md`

1. **Título e selo do CI.** Um parágrafo sobre o sistema, disciplina, professor e integrantes do grupo.
2. **Links:** repositório, documentação pública (GitHub Pages), Swagger local (`http://localhost:8000/docs`).
3. **Como rodar:** pré-requisitos (Python 3.12, Docker) e os comandos da seção 4, na ordem, para Windows e Linux/macOS. Deve funcionar numa máquina limpa.
4. **Como testar:** os comandos de teste; o que é unitário, integração e arquitetura; onde fica cada um; como ver a cobertura.
5. **Arquitetura:** monólito modular por domínio, em 4 a 6 frases; o diagrama mermaid de módulos; as camadas de cada módulo; as principais decisões (D01, D05, D06, D09) com o porquê. Link para `docs/ARQUITETURA.md`.
6. **Modularização:** a tabela de módulos (responsabilidade, tabelas que possui, interface pública); as regras de fronteira; como o teste TA-01 garante as regras; a ligação com os conceitos da disciplina (módulos profundos, ocultação de informação, acoplamento, bounded contexts, agregados).
7. **Modelagem do banco:** o diagrama ER em mermaid; uma linha por tabela dizendo o que guarda; as restrições mais importantes e o porquê de cada uma; a explicação do sigilo (duas tabelas sem ligação). Link para `docs/MODELAGEM.md`.
8. **Regras de negócio:** link para a tabela de RNs (pode ser `docs/PLANO.md`, seção 8) e destaque das regras complementares.
9. **Segurança e sigilo:** resumo da seção 7.
10. **Limitações conhecidas:** as das seções 6 e 7, ditas com franqueza.
11. **Estrutura de pastas:** a árvore da seção 5.
12. **Versionamento:** padrão de commits, branches e tags.

### `docs/ARQUITETURA.md`

Versão completa das seções 1 (decisões D01 a D12 com alternativas descartadas), 3 (princípios e onde aparecem no código), 5 (módulos, camadas, fronteiras, transações, erros) e 7 (segurança). Inclua o fluxo do voto como diagrama de sequência:

```mermaid
sequenceDiagram
    actor Eleitor
    participant API
    participant Votacao as módulo votacao
    participant Eleicoes as módulo eleicoes
    participant Banco as PostgreSQL
    Eleitor->>API: POST /votos/registro (cargo, número)
    API->>Votacao: registrar_voto
    Votacao->>Eleicoes: eleição está ABERTA? candidaturas do cargo
    Votacao-->>Eleitor: prévia + token_cedula (nada gravado)
    Eleitor->>API: POST /votos/confirmacao (token_cedula)
    API->>Votacao: confirmar_voto
    Votacao->>Eleicoes: trava compartilhada na eleição
    Votacao->>Banco: INSERT registros_votacao (quem)
    Votacao->>Banco: INSERT votos (o quê, sem quem)
    Votacao->>Banco: COMMIT
    Votacao-->>Eleitor: "Voto confirmado." (sem a escolha)
```

### `docs/MODELAGEM.md`

A seção 6 inteira: diagrama ER, dicionário de dados (todas as colunas), restrições com nome e motivo, índices, trigger, política de exclusão, migrações e limitações.

### `docs/DEMO.md`

O roteiro da seção 16, com as requisições exatas e as respostas esperadas, para qualquer membro conduzir a demonstração.

## 16. Roteiro da apresentação (Parte B)

Roteiro de cerca de 20 minutos que cobre, na ordem, os 11 itens que o enunciado manda demonstrar. Rode-o inteiro pelo menos duas vezes antes da aula. Qualquer membro do grupo deve conseguir conduzi-lo sozinho.

### Preparação (antes da aula)

1. `docker compose down -v` e `docker compose up -d` (banco limpo).
2. `alembic upgrade head`, `python -m app.scripts.seed_demo` e `uvicorn app.main:app`.
3. `pytest` uma vez (confirma que está tudo verde).
4. Postman ou Insomnia com a coleção importada e o ambiente configurado (seção 11).
5. Abertos: VS Code com o projeto, um terminal com `docker exec -it eleicao-banco psql -U eleicao -d eleicao`, o Swagger local e o link do GitHub Pages.

No Postman, a aba **Tests** (ou Scripts → Post-response) do login guarda o token automaticamente:

```javascript
pm.environment.set("token_chefe", pm.response.json().access_token);
```

E a do registro de voto guarda a cédula:

```javascript
pm.environment.set("token_cedula", pm.response.json().token_cedula);
```

### Parte 1: perfis e cadastros (Chefe da Seção)

| # | Requisição | O que mostrar | Esperado |
| --- | --- | --- | --- |
| 1 | `POST /auth/login` (Chefe 291.417.776-38) | Login e perfil no token | 200, `CHEFE_SECAO` |
| 2 | `GET /eleitores?pagina=1&tamanho=5` | Listagem paginada dos dados do seed | 200, `total: 6` |
| 3 | `POST /eleitores` (Igor Barbosa, CPF 081.836.584-66, título 100000000008, 1999-09-09) | Cadastro de eleitor; a resposta não tem senha | 201 |
| 4 | `POST /eleitores` com CPF 111.111.111-11, depois com nascimento em 2015 | Validações | 422 `CPF_INVALIDO`, 422 `IDADE_MINIMA` |
| 5 | `POST /candidatos` (Renata Campos, nome de urna "Renata Campos", CPF 241.592.066-54, 1977-01-20) | Cadastro de candidato | 201 |
| 6 | `POST /eleicoes` (2º turno, data de amanhã, 08:00 às 17:00) | Cadastro de eleição e `links` (HATEOAS) | 201, `AGENDADA` |
| 7 | `POST /eleicoes/2/candidaturas` com Renata para SENADOR | Regra do 2º turno | 409 `CARGO_NAO_PERMITIDO_NO_TURNO` |
| 8 | `GET /eleicoes/1` | Situação da eleição do seed; link `abrir` | 200, `AGENDADA` |
| 9 | `POST /eleicoes/1/abertura` | Abertura; os `links` mudam para `encerrar` | 200, `ABERTA` |
| 10 | `POST /eleicoes/1/candidaturas` (qualquer) | Candidaturas congeladas depois da abertura | 409 `ELEICAO_NAO_EDITAVEL` |

### Parte 2: votação (Eleitor) e regras de negócio

| # | Requisição | O que mostrar | Esperado |
| --- | --- | --- | --- |
| 11 | Login de Ana (011.524.493-03) | Perfil Eleitor | 200, `ELEITOR` |
| 12 | `GET /votacao/eleicoes/1/cedula` | Cargos na ordem da urna, dígitos e candidatos | 200 |
| 13 | `POST .../votos/registro` `{cargo: PRESIDENTE, modo: NUMERO, numero: "10"}` | Prévia com Carlos Lima e `token_cedula`. Dizer: **nada foi gravado ainda** | 200, `NOMINAL` |
| 14 | `POST .../votos/confirmacao` `{token_cedula}` | Voto confirmado; a resposta **não diz em quem** | 201 |
| 15 | Repetir a confirmação com o mesmo token | Voto único e imutável | 409 `VOTO_JA_REGISTRADO` |
| 16 | Registro `{cargo: SENADOR, modo: BRANCO}` + confirmação | Voto em branco | 200 `BRANCO`, depois 201 |
| 17 | Registro `{cargo: GOVERNADOR, modo: NUMERO, numero: "99"}` + confirmação | Número sem candidato vira nulo | 200 `NULO`, depois 201 |
| 18 | Bruno vota Presidente 20; Camila vota Presidente 10 | Mais votos para a apuração | 201 |
| 19 | Com o token do Chefe, `POST .../votos/registro` | Só eleitor vota | 403 `PERFIL_NAO_AUTORIZADO` |
| 20 | Chefe cadastra Gustavo Pereira (217.533.772-34); Gustavo faz login e tenta abrir a cédula | Eleitor cadastrado depois da abertura | 403 `ELEITOR_NAO_APTO` |

### Parte 3: acompanhamento da votação

| # | Requisição | O que mostrar | Esperado |
| --- | --- | --- | --- |
| 21 | Ana: `GET /apuracao/eleicoes/1/parcial` | Todos os cargos, percentuais, brancos e nulos, comparecimento | 200, Carlos 2 × Marina 1 |
| 22 | Login de Carlos Lima (398.259.791-94), `GET .../parcial` | Candidato vê só o próprio cargo | 200, só PRESIDENTE |
| 23 | Carlos: `GET .../parcial?cargo=SENADOR` | Restrição por cargo | 403 `CARGO_NAO_PERMITIDO` |
| 24 | `GET /apuracao/eleicoes/1/resultado` com a eleição aberta | Resultado só depois do encerramento | 409 `APURACAO_INDISPONIVEL` |

### Parte 4: encerramento e resultado final

| # | Requisição | O que mostrar | Esperado |
| --- | --- | --- | --- |
| 25 | Chefe: `POST /eleicoes/1/encerramento` | Encerramento | 200, `ENCERRADA` |
| 26 | Diego tenta registrar voto | Nenhum voto depois do encerramento | 409 `ELEICAO_NAO_ABERTA` |
| 27 | `GET /apuracao/eleicoes/1/resultado` | Votos por candidato, mais votado por cargo, comparecimento e abstenção | 200, `tipo: FINAL`, Presidente: Carlos Lima |

### Parte 5: bastidores (o que o professor também pede)

| # | O quê | Como mostrar |
| --- | --- | --- |
| 28 | Sigilo no banco | No psql: `SELECT * FROM registros_votacao;` e `SELECT * FROM votos;` → não existe coluna que ligue uma tabela à outra. Depois `UPDATE votos SET tipo = 'BRANCO';` → erro do trigger. |
| 29 | Testes | Árvore `tests/unitarios`, `tests/integracao`, `tests/arquitetura`; rodar `pytest tests/unitarios -v` (rápido, sem banco) e `pytest tests/integracao -q`; abrir um teste de cada tipo e explicar a diferença (tabela da seção 12); mostrar a cobertura. |
| 30 | Estrutura modular | No VS Code: as pastas dos módulos; abrir `votacao/` e seguir uma requisição: `rotas.py` → `servico.py` → `dominio.py` / `repositorio.py`; abrir `tests/arquitetura/test_dependencias.py` e explicar que as fronteiras são verificadas automaticamente. |
| 31 | Documentação | Swagger local (`/docs`): tags, Authorize, exemplos e respostas de erro; link do GitHub Pages; a frase da seção 11 sobre code-first. |
| 32 | Versionamento | `git log --oneline --graph --decorate` (commits pequenos, tags), Pull Requests e o CI verde no GitHub. |

Se algo der errado ao vivo: o teste TI-74 (`pytest tests/integracao/test_fluxo_completo.py -v`) executa esse mesmo roteiro e prova que o sistema funciona.

## 17. Preparação para a arguição individual

Cada membro será arguido sozinho, então todos precisam saber explicar o sistema inteiro, não só o próprio módulo. Abaixo estão as perguntas mais prováveis, com respostas curtas que usam o vocabulário da disciplina. Treine respondendo em voz alta e apontando o arquivo no código.

### Como estudar (cada membro)

- Conduza o roteiro da seção 16 sozinho, do início ao fim.
- Para **cada** módulo, siga uma requisição de ponta a ponta: rota → serviço → domínio → repositório → tabela.
- Leia a tabela de RNs (seção 8) e saiba apontar onde cada regra está no código e qual teste a verifica.
- Saiba rodar e explicar um teste unitário, um de integração e o de arquitetura.

### Arquitetura e conceitos da disciplina

**1. Por que monólito modular e não microsserviços?** O enunciado não pede distribuição, e microsserviços trariam rede, vários bancos e deploy separado sem benefício aqui. O monólito modular tem menor complexidade operacional (aula 06), mas mantém fronteiras de domínio claras. Se um dia precisar, cada módulo já tem as fronteiras de um serviço.

**2. Dê um exemplo de módulo profundo.** `votacao.confirmar_voto`: uma interface pequena (token da cédula) que esconde a decifração da cédula, a trava na eleição, a gravação em duas tabelas sem ligação, a transação e a tradução do erro de chave duplicada. Quem chama não precisa saber de nada disso.

**3. Onde há ocultação de informação?** Só `identidade` sabe que a senha usa bcrypt e o token usa JWT. Só `votacao` conhece as tabelas de voto. Os serviços devolvem `dataclass`es, nunca o modelo do banco, então o formato das tabelas não vaza para outros módulos.

**4. Que acoplamentos existem entre os módulos?** Só acoplamento de domínio (um serviço chama funções de outro), que é o normal. Evitamos acoplamento de recurso comum e de conteúdo: nenhum módulo lê ou escreve a tabela de outro, e o teste TA-01 garante isso.

**5. Mas as tabelas têm chave estrangeira entre módulos. Isso não é acoplamento de recurso comum?** No monólito há um banco só, e a FK serve para integridade. Cada tabela tem um único módulo dono que lê e escreve nela; os outros só guardam o id. Em microsserviços trocaríamos a FK por uma referência via API, no estilo HATEOAS (aula 07).

**6. Como aparece a Lei de Conway?** Os módulos foram desenhados para espelhar a divisão do trabalho do grupo (seção 13): cada integrante responde por um módulo. No histórico do Git, a implementação ficou concentrada em poucas pessoas; a divisão aparece na responsabilidade de cada um pelo seu módulo, nas revisões e na apresentação. Diga isso com franqueza se perguntarem.

**7. Qual é o agregado do sistema?** A Eleição é a raiz, e as candidaturas são entidades internas. Toda mudança em candidatura passa pela eleição (`/eleicoes/{id}/candidaturas`), que trava a própria linha e aplica a regra "só com eleição AGENDADA" num lugar só.

**8. Onde estão os bounded contexts e a linguagem ubíqua?** Cada módulo é um contexto: "candidato" (a pessoa) vive em `candidatos`, e "candidatura" (a disputa numa eleição) vive em `eleicoes`. `Cargo` é o núcleo compartilhado. O código usa as mesmas palavras do enunciado, em português (glossário da seção 2).

**9. Onde está a regra de dependência da Clean Architecture?** Rotas dependem do serviço, que depende do domínio. O `dominio.py` não importa FastAPI nem SQLAlchemy, por isso é testado sem banco. O teste de arquitetura verifica isso.

**10. Por que não usaram flags?** Uma flag como `alterar_status(id, abrir=True)` deixa a interface obscura (aulas 04 e 05). Usamos funções explícitas (`abrir_eleicao`, `encerrar_eleicao`) e enums (`ModoEscolha.NUMERO` ou `BRANCO`).

**11. Onde está o HATEOAS?** As respostas de eleição e de votação trazem `links` com as próximas ações possíveis para aquele perfil e status. Por exemplo, uma eleição AGENDADA mostra `abrir` ao Chefe; uma ABERTA mostra `cedula` ao Eleitor.

**12. Vocês caíram em classite?** Não. Usamos funções e `dataclass`es simples, sem uma classe por operação nem pares Interface + Implementação. Cada módulo tem poucas funções públicas que fazem bastante coisa.

**13. Um módulo que só faz CRUD é bem feito?** Um módulo só de CRUD tende a ser raso e a empurrar as regras para quem o usa. Os módulos de cadastro (`eleitores`, `candidatos`) são os mais simples por natureza, mas ainda escondem a criação da credencial e as validações. As regras de verdade ficam nos módulos profundos (`eleicoes`, `votacao`, `apuracao`).

### Regras de negócio

**14. Como garantem um voto por cargo?** A chave primária (eleitor, eleição, cargo) da tabela `registros_votacao`. O registro do voto também checa antes, só para responder rápido, mas quem garante é o banco.

**15. E se duas requisições de voto chegarem ao mesmo tempo?** As duas tentam inserir a mesma chave primária; o PostgreSQL deixa uma passar e recusa a outra, que vira 409. O teste TI-73 prova isso com duas threads.

**16. Como garantem o sigilo?** O banco nunca guarda eleitor e escolha juntos. `registros_votacao` diz quem votou em qual cargo; `votos` diz o quê foi votado, sem quem; as duas são gravadas na mesma transação e não têm coluna nem chave que as ligue. O voto tem UUID aleatório e nenhum horário, a confirmação não devolve a escolha e os logs não a registram. Os limites, ditos com franqueza: como as duas linhas nascem na mesma transação, quem lê o banco direto as liga pelo `xmin` (e também pela ordem física), por isso o acesso direto ao banco fica restrito (D-134); e a parcial exata, consultada antes e depois de um voto, permite deduzir a escolha.

**17. Por que duas etapas, e o que é a cédula?** O enunciado pede registrar e confirmar. No registro, o servidor devolve a escolha numa cédula cifrada de 5 minutos (que ninguém lê sem a chave do servidor, D-144) e não grava nada; na confirmação, decifra, confere e grava. Descartamos guardar um rascunho no banco porque ele ligaria eleitor e escolha até a confirmação.

**18. O que impede um voto no exato instante do encerramento?** A confirmação pega uma trava compartilhada na linha da eleição, e o encerramento precisa de uma trava exclusiva. Então o encerramento espera os votos em andamento terminarem, e os votos seguintes já veem a eleição ENCERRADA.

**19. O voto pode ser alterado?** Não existe rota para isso, e um trigger no banco recusa qualquer UPDATE ou DELETE em `votos` e `registros_votacao`. Antes de confirmar, o eleitor pode registrar de novo quantas vezes quiser.

**20. Por que um candidato não pode votar?** O enunciado define três tipos de usuário e pede para bloquear "voto de usuário que não seja eleitor". Decidimos um perfil por pessoa (decisão D04). Na vida real o candidato também é eleitor; aqui isso é uma simplificação assumida.

**21. Mais votado é o mesmo que eleito?** Não. O enunciado pede o mais votado. "Eleito" depende de maioria absoluta (Presidente e Governador) ou de quociente eleitoral (deputados), o que está fora do escopo. Em empate, vence o mais idoso; se as datas forem iguais, o resultado mostra EMPATE.

**22. E se o Chefe esquecer de encerrar?** Passado o horário de encerramento, novos votos são recusados (`JANELA_ENCERRADA`). O resultado final só aparece depois que o Chefe encerra.

**23. Como o candidato fica restrito ao próprio cargo?** A apuração parcial descobre a candidatura do usuário naquela eleição e só devolve aquele cargo. Pedir outro cargo dá 403.

### Segurança

**24. Como funcionam o login e o token?** A senha é conferida com bcrypt; o token JWT é assinado com HS256, expira em 60 minutos e tem audiência própria. A cada requisição o usuário é recarregado do banco, então o perfil vem do banco, não do token.

**25. E se alguém mandar `"perfil": "CHEFE_SECAO"` no cadastro?** Os esquemas de entrada recusam campos extras (`extra="forbid"`), então dá 422.

**26. Por que a mesma mensagem para CPF inexistente e senha errada?** Para não revelar quais CPFs têm conta. Por isso também conferimos um hash fictício quando o CPF não existe, para o tempo de resposta ser parecido.

### Banco de dados

**27. Explique o modelo.** São 8 tabelas: credenciais em `usuarios`; dados de pessoa em `eleitores` e `candidatos`; `partidos`; `eleicoes` e suas `candidaturas`; e as duas tabelas da votação, sem ligação entre si (seção 6).

**28. Para que serve o índice parcial?** `uq_eleicoes_uma_aberta` é único só nas linhas com status ABERTA. Isso garante, no banco, que nunca há duas eleições abertas.

**29. Para que serve a chave estrangeira composta em `votos`?** Ela aponta para (id, eleição, cargo) da candidatura. Assim o banco garante que um voto para Senador nunca aponta para uma candidatura a Presidente, nem de outra eleição.

**30. Por que os horários são preenchidos pela aplicação e não por `DEFAULT now()`?** Porque o relógio é injetável e congelado nos testes. Se o banco usasse o horário real, a regra "cadastrado antes da abertura" falharia nos testes.

### Testes, documentação e Git

**31. Qual a diferença entre teste unitário e de integração no projeto?** O unitário testa uma regra pura, sem banco e sem HTTP (por exemplo, `validar_abertura` fora da data). O de integração chama a API de verdade contra um PostgreSQL de teste e confere status, código de erro e o que ficou gravado.

**32. Por que banco real e não SQLite ou mock?** Porque parte das regras mora no PostgreSQL: chave primária, índice parcial, FK composta, trigger e travas. Um mock não testaria nada disso.

**33. Como testam regras de horário?** Com o relógio injetável: nos testes, a dependência `obter_agora` é substituída por um relógio congelado que dá para avançar (`relogio.avancar(minutes=6)`).

**34. O que é o teste de arquitetura?** Um teste que lê os `import` do código e falha se um módulo acessar o que não pode (por exemplo, o repositório de outro módulo). As fronteiras deixam de ser só uma combinação e passam a ser verificadas.

**35. Como a documentação foi gerada?** Use a frase pronta da seção 11.

**36. Como organizaram o Git?** Branch por fase, Pull Request para integrar na `main` só com o CI verde, Conventional Commits em português, tags por marco e CI rodando lint e testes a cada push. A maior parte dos PRs foi integrada sem revisão de outro membro; a revisão cruzada passou a ser exigida na reta final. Diga isso com franqueza se perguntarem.

**37. O que vocês fariam com mais tempo?** Os extras da seção 13 (limite de tentativas de login, parcial em tempo real, deploy público) e atacar as limitações conhecidas do sigilo.

## 18. Rastreabilidade e checklist final

Cada exigência do enunciado aponta para as rotas, regras e testes que a cumprem. Se uma linha não tiver teste verde, a exigência não está entregue.

### Matriz de rastreabilidade

| Exigência do enunciado | Rotas | RN | Testes |
| --- | --- | --- | --- |
| 1. Login de Chefe, Eleitor e Candidato | `/auth/login`, `/auth/me` | RN-01, 02, 05, 06 | TU-07 a 12, TI-01 a 07 |
| 1. Funcionalidades conforme o perfil | Todas | RN-03 | TI-08, TA-02 |
| 2. Cadastrar eleição com data, turno e horários | `POST` e `PATCH /eleicoes` | RN-10 a 12, 14 | TU-13, TU-15, TI-09 a 11 |
| 2. Abrir e encerrar a votação (só o Chefe) | `/abertura`, `/encerramento` | RN-10, 13, 15 a 18 | TU-14, TU-16, TI-12 a 16 |
| 2. Consultar a situação da eleição | `GET /eleicoes`, `GET /eleicoes/{id}` | RN-19 | TU-18, TI-09, TI-17 |
| 3. Cadastrar, alterar, consultar e excluir eleitores | `/eleitores` | RN-20 a 25 | TU-05, TI-18 a 26 |
| 4. Cadastrar, alterar, consultar e excluir candidatos | `/candidatos`, `/partidos` | RN-30 a 33 | TI-27 a 29 |
| 4. Associar candidato a cargo e eleição (número e partido) | `/eleicoes/{id}/candidaturas` | RN-40 a 47 | TU-06, TU-17, TI-30 a 37 |
| 5. Consultar candidatos por cargo | `/votacao/.../cedula` | RN-55 | TI-38 |
| 5. Registrar e confirmar o voto | `/votos/registro`, `/votos/confirmacao` | RN-56 a 58 | TU-21 a 24, TI-39 a 41, TI-54 |
| 5. Impedir voto com eleição não aberta | idem | RN-51, 52 | TU-19, TI-45, TI-52 |
| 5. Impedir voto de quem não é eleitor | idem | RN-50, 53 | TU-20, TI-46, TI-50 |
| 5. Impedir mais de um voto por cargo | idem | RN-54 | TI-42, TI-43, TI-65, TI-73 |
| 5. Impedir alteração de voto confirmado | (não existe rota) | RN-59 | TI-42, TI-63, TI-64 |
| Minimundo: sigilo do voto | — | RN-60, 61 | TI-53, TI-69 a 72 |
| 6. Eleitor acompanha todos os cargos | `/apuracao/.../parcial` | RN-71 | TI-58 |
| 6. Candidato acompanha só o próprio cargo | idem | RN-72 | TI-57 |
| 6. Quantidade de votos por candidato, atualizada | idem | RN-74, 75 | TU-26, TI-55 |
| 7. Resultado final: candidatos, cargos, votos e mais votado | `/apuracao/.../resultado` | RN-70, 73 a 79 | TU-25 a 31, TI-59 a 62 |
| Banco: tabelas, chaves, relacionamentos e restrições | — (seção 6) | — | TI-63 a 69 |
| Estrutura modular clara | — (seção 5) | — | TA-01 |
| Testes unitários e de integração | — (seção 12) | — | Todos |
| Versionamento com histórico coerente | — (seção 13) | — | CI |
| Documentação Swagger | `/docs`, GitHub Pages | — | TA-03, TA-04 |
| Demonstração no Postman ou Insomnia | Roteiro da seção 16 | — | TI-74 |

### Checklist antes de entregar

Situação em 23/11/2026: marcados os itens conferidos no repositório (testes, CI, migrações e documentos); os desmarcados dependem do grupo ou da entrega.

Código e testes

- [x] As 33 rotas implementadas, com `summary`, descrição, exemplos e respostas de erro
- [x] As 58 regras implementadas, cada uma citada na docstring da função e em pelo menos um teste
- [x] `ruff check .` e `ruff format --check .` sem avisos
- [x] `pytest` verde; cobertura de 85% ou mais no total e 90% ou mais nos `dominio.py`
- [x] Testes de arquitetura verdes (nenhum import proibido, todas as rotas protegidas)
- [x] Nenhum segredo no repositório (`.env` fora do Git)

Banco

- [x] `alembic upgrade head` funciona num banco vazio, e `alembic downgrade base` desfaz tudo
- [x] Trigger, índice parcial e FK composta presentes (conferir no psql com `\d votos` e `\d eleicoes`)
- [x] `seed_demo` roda do zero sem erro

Documentação

- [ ] `docs/openapi.json` atualizado (TA-03 verde) e GitHub Pages no ar (o `openapi.json` está em dia; falta o Pages, que exige repositório público)
- [x] README com como rodar, como testar, arquitetura, modularização e modelagem
- [x] `docs/ARQUITETURA.md`, `docs/MODELAGEM.md` e `docs/DEMO.md` prontos
- [x] Coleção do Postman ou Insomnia salva em `docs/`

Git

- [ ] Commits pequenos, no padrão, com autoria de todos os membros
- [ ] Pull Requests revisados por outro membro
- [x] Tag `v1.0.0` e CI verde na `main`

Apresentação

- [ ] Roteiro da seção 16 ensaiado pelo menos duas vezes, do banco limpo
- [ ] Cada membro conduziu o roteiro sozinho pelo menos uma vez
- [ ] Cada membro respondeu em voz alta as 37 perguntas da seção 17

Entrega

- [ ] Link do repositório
- [ ] Link da documentação da API
- [x] README (ou PDF) com arquitetura, modularização e modelagem do banco
