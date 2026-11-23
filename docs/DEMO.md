# Roteiro da demonstração

Roteiro de cerca de 20 minutos que cobre, na ordem, os 11 itens que o enunciado manda demonstrar. Qualquer membro do grupo deve conseguir conduzi-lo sozinho. As respostas abaixo foram obtidas rodando o roteiro inteiro contra a API real (banco limpo, migrações, seed, uvicorn); tokens e horários aparecem como `<token>` e `<data e hora>`, e as listas longas foram encurtadas.

O mesmo roteiro está automatizado no teste TI-74 (`pytest tests/integracao/test_fluxo_completo.py -v`): se algo der errado ao vivo, rode-o para provar que o sistema funciona.

## Preparação (antes da aula)

1. Banco limpo e API no ar (Docker Desktop aberto; no Windows troque `.venv/bin/python` por `.venv\Scripts\python.exe`). O `.env` precisa existir e ter `POSTGRES_USER` e `POSTGRES_PASSWORD` (copie do `.env.example`), senão o `docker compose` não sobe:

   ```bash
   docker compose down -v
   docker compose up -d
   .venv/bin/python -m alembic upgrade head
   .venv/bin/python -m app.scripts.seed_demo
   .venv/bin/python -m uvicorn app.main:app --no-access-log
   ```

2. `pytest` uma vez (confirma que está tudo verde).
3. No Postman (ou Insomnia): **Import** de `docs/colecao-postman.json` e `docs/ambiente-postman.json`; escolha o ambiente **Eleição — local** (`base_url = http://localhost:8000/api/v1`). A coleção traz as requisições abaixo, na ordem, com os scripts de pós-resposta que guardam os tokens (`token_chefe`, `token_eleitor`, `token_candidato`, `token_cedula`) e os ids (`eleicao2_id`, `candidato_renata_id`). Rode uma a uma ou pelo Collection Runner.
4. Abertos: VS Code com o projeto, um terminal com `docker exec -it eleicao-banco psql -U eleicao -d eleicao`, o Swagger local (http://localhost:8000/docs) e, se já estiver publicado, o link da documentação.

O script de pós-resposta do login guarda o token, por exemplo:

```javascript
pm.environment.set("token_chefe", pm.response.json().access_token);
```

E o do registro de voto guarda a cédula:

```javascript
pm.environment.set("token_cedula", pm.response.json().token_cedula);
```

**Logins do seed** (todos com CPF e senha prontos; a tabela completa é impressa ao fim do `seed_demo`): Chefe `291.417.776-38` / `Chefe@2026`; eleitores `Eleitor@123`; candidatos `Candidato@123`.

> Reiniciar a demo: o roteiro altera o banco (abre e encerra a eleição, grava votos). Para repetir, refaça a preparação do passo 1.

## Parte 1: perfis e cadastros (Chefe da Seção)

### 01. Login do Chefe

**O que mostrar:** Login e perfil.

```http
POST {{base_url}}/auth/login
Content-Type: application/x-www-form-urlencoded

username=291.417.776-38&password=Chefe@2026
```

**Esperado:** 200

```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "expira_em": "<data e hora>",
  "usuario": {
    "id": 1,
    "nome": "Chefe da Seção",
    "perfil": "CHEFE_SECAO"
  }
}
```

### 02. Listar eleitores

**O que mostrar:** Listagem paginada.

```http
GET {{base_url}}/eleitores?pagina=1&tamanho=5
Authorization: Bearer {{token_chefe}}
```

**Esperado:** 200

```json
{
  "itens": [
    {
      "id": 1,
      "nome": "Ana Beatriz Souza",
      "cpf": "01152449303",
      "titulo_eleitor": "100000000001",
      "data_nascimento": "1990-04-12",
      "criado_em": "<data e hora>"
    },
    {
      "id": 2,
      "nome": "Bruno Almeida",
      "cpf": "34167211017",
      "titulo_eleitor": "100000000002",
      "data_nascimento": "1985-09-30",
      "criado_em": "<data e hora>"
    },
    "... (mais 3 eleitores na página)"
  ],
  "pagina": 1,
  "tamanho": 5,
  "total": 6
}
```

### 03. Cadastrar eleitor (Igor)

**O que mostrar:** Cadastro de eleitor; a resposta não tem senha.

```http
POST {{base_url}}/eleitores
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "nome": "Igor Barbosa",
  "cpf": "081.836.584-66",
  "titulo_eleitor": "100000000008",
  "data_nascimento": "1999-09-09",
  "senha": "Eleitor@123"
}
```

**Esperado:** 201

```json
{
  "id": 7,
  "nome": "Igor Barbosa",
  "cpf": "08183658466",
  "titulo_eleitor": "100000000008",
  "data_nascimento": "1999-09-09",
  "criado_em": "<data e hora>"
}
```

### 04. Eleitor com CPF inválido

**O que mostrar:** Validação de CPF.

```http
POST {{base_url}}/eleitores
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "nome": "Eleitor Invalido",
  "cpf": "111.111.111-11",
  "titulo_eleitor": "100000000009",
  "data_nascimento": "1990-01-01",
  "senha": "Eleitor@123"
}
```

**Esperado:** 422 `CPF_INVALIDO`

```json
{
  "erro": {
    "codigo": "CPF_INVALIDO",
    "mensagem": "CPF inválido.",
    "detalhes": {}
  }
}
```

### 04. Eleitor menor de 16 anos

**O que mostrar:** Validação de idade.

```http
POST {{base_url}}/eleitores
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "nome": "Eleitor Menor",
  "cpf": "529.982.247-25",
  "titulo_eleitor": "100000000009",
  "data_nascimento": "2015-01-01",
  "senha": "Eleitor@123"
}
```

**Esperado:** 422 `IDADE_MINIMA`

```json
{
  "erro": {
    "codigo": "IDADE_MINIMA",
    "mensagem": "O eleitor deve ter pelo menos 16 anos.",
    "detalhes": {}
  }
}
```

### 05. Cadastrar candidato (Renata)

**O que mostrar:** Cadastro de candidato.

```http
POST {{base_url}}/candidatos
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "nome": "Renata Campos",
  "nome_urna": "Renata Campos",
  "cpf": "241.592.066-54",
  "data_nascimento": "1977-01-20",
  "senha": "Candidato@123"
}
```

**Esperado:** 201

```json
{
  "id": 11,
  "nome": "Renata Campos",
  "nome_urna": "Renata Campos",
  "cpf": "24159206654",
  "data_nascimento": "1977-01-20",
  "criado_em": "<data e hora>"
}
```

### 06. Criar eleição do 2º turno

**O que mostrar:** Cadastro de eleição e `links` (HATEOAS).

```http
POST {{base_url}}/eleicoes
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "descricao": "Eleições Gerais 2026 — 2º turno (simulação)",
  "data": "{{amanha}}",
  "turno": 2,
  "horario_abertura": "08:00",
  "horario_encerramento": "17:00"
}
```

**Esperado:** 201

```json
{
  "id": 2,
  "descricao": "Eleições Gerais 2026 — 2º turno (simulação)",
  "data": "2026-11-22",
  "turno": 2,
  "horario_abertura": "08:00:00",
  "horario_encerramento": "17:00:00",
  "status": "AGENDADA",
  "aberta_em": null,
  "encerrada_em": null,
  "links": [
    {
      "rel": "self",
      "metodo": "GET",
      "href": "/api/v1/eleicoes/2"
    },
    {
      "rel": "editar",
      "metodo": "PATCH",
      "href": "/api/v1/eleicoes/2"
    },
    {
      "rel": "candidaturas",
      "metodo": "GET",
      "href": "/api/v1/eleicoes/2/candidaturas"
    },
    {
      "rel": "nova-candidatura",
      "metodo": "POST",
      "href": "/api/v1/eleicoes/2/candidaturas"
    },
    {
      "rel": "abrir",
      "metodo": "POST",
      "href": "/api/v1/eleicoes/2/abertura"
    }
  ]
}
```

### 07. Candidatura de Senador no 2º turno

**O que mostrar:** Regra do 2º turno.

```http
POST {{base_url}}/eleicoes/{{eleicao2_id}}/candidaturas
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "candidato_id": "{{candidato_renata_id}}",
  "partido_id": 1,
  "cargo": "SENADOR",
  "numero": "404"
}
```

**Esperado:** 409 `CARGO_NAO_PERMITIDO_NO_TURNO`

```json
{
  "erro": {
    "codigo": "CARGO_NAO_PERMITIDO_NO_TURNO",
    "mensagem": "No 2º turno só há Governador e Presidente.",
    "detalhes": {
      "cargo": "SENADOR"
    }
  }
}
```

### 08. Consultar a eleição do seed

**O que mostrar:** Situação AGENDADA e link `abrir`.

```http
GET {{base_url}}/eleicoes/{{eleicao_id}}
Authorization: Bearer {{token_chefe}}
```

**Esperado:** 200

```json
{
  "id": 1,
  "descricao": "Eleições Gerais 2026 — 1º turno (simulação)",
  "data": "2026-11-21",
  "turno": 1,
  "horario_abertura": "00:00:00",
  "horario_encerramento": "23:59:00",
  "status": "AGENDADA",
  "aberta_em": null,
  "encerrada_em": null,
  "links": [
    {
      "rel": "self",
      "metodo": "GET",
      "href": "/api/v1/eleicoes/1"
    },
    {
      "rel": "editar",
      "metodo": "PATCH",
      "href": "/api/v1/eleicoes/1"
    },
    {
      "rel": "candidaturas",
      "metodo": "GET",
      "href": "/api/v1/eleicoes/1/candidaturas"
    },
    {
      "rel": "nova-candidatura",
      "metodo": "POST",
      "href": "/api/v1/eleicoes/1/candidaturas"
    },
    {
      "rel": "abrir",
      "metodo": "POST",
      "href": "/api/v1/eleicoes/1/abertura"
    }
  ]
}
```

### 09. Abrir a eleição

**O que mostrar:** Abertura; os `links` mudam para `encerrar`.

```http
POST {{base_url}}/eleicoes/{{eleicao_id}}/abertura
Authorization: Bearer {{token_chefe}}
```

**Esperado:** 200

```json
{
  "id": 1,
  "descricao": "Eleições Gerais 2026 — 1º turno (simulação)",
  "data": "2026-11-21",
  "turno": 1,
  "horario_abertura": "00:00:00",
  "horario_encerramento": "23:59:00",
  "status": "ABERTA",
  "aberta_em": "<data e hora>",
  "encerrada_em": null,
  "links": [
    {
      "rel": "self",
      "metodo": "GET",
      "href": "/api/v1/eleicoes/1"
    },
    {
      "rel": "encerrar",
      "metodo": "POST",
      "href": "/api/v1/eleicoes/1/encerramento"
    },
    {
      "rel": "apuracao-parcial",
      "metodo": "GET",
      "href": "/api/v1/apuracao/eleicoes/1/parcial"
    }
  ]
}
```

### 10. Candidatura depois da abertura

**O que mostrar:** Candidaturas congeladas.

```http
POST {{base_url}}/eleicoes/{{eleicao_id}}/candidaturas
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "candidato_id": "{{candidato_renata_id}}",
  "partido_id": 1,
  "cargo": "SENADOR",
  "numero": "404"
}
```

**Esperado:** 409 `ELEICAO_NAO_EDITAVEL`

```json
{
  "erro": {
    "codigo": "ELEICAO_NAO_EDITAVEL",
    "mensagem": "Só uma eleição AGENDADA pode ser alterada.",
    "detalhes": {
      "status": "ABERTA"
    }
  }
}
```

## Parte 2: votação (Eleitor) e regras de negócio

### 11. Login de Ana

**O que mostrar:** Perfil Eleitor.

```http
POST {{base_url}}/auth/login
Content-Type: application/x-www-form-urlencoded

username=011.524.493-03&password=Eleitor@123
```

**Esperado:** 200

```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "expira_em": "<data e hora>",
  "usuario": {
    "id": 2,
    "nome": "Ana Beatriz Souza",
    "perfil": "ELEITOR"
  }
}
```

### 12. Consultar a cédula

**O que mostrar:** Cargos na ordem da urna, dígitos e candidatos.

```http
GET {{base_url}}/votacao/eleicoes/{{eleicao_id}}/cedula
Authorization: Bearer {{token_eleitor}}
```

**Esperado:** 200

```json
{
  "eleicao_id": 1,
  "cargos": [
    {
      "cargo": "DEPUTADO_FEDERAL",
      "digitos": 4,
      "ja_votou": false,
      "candidatos": [
        {
          "numero": "1010",
          "nome_urna": "Tiago Freitas",
          "partido_sigla": "PINO"
        },
        {
          "numero": "2020",
          "nome_urna": "Sandra Oliveira",
          "partido_sigla": "UC"
        }
      ]
    },
    {
      "cargo": "DEPUTADO_ESTADUAL",
      "digitos": 5,
      "ja_votou": false,
      "candidatos": [
        {
          "numero": "10100",
          "nome_urna": "Rafael Dias",
          "partido_sigla": "PINO"
        },
        {
          "numero": "30300",
          "nome_urna": "Juliana Torres",
          "partido_sigla": "MV"
        }
      ]
    },
    "... (os outros cargos seguem o mesmo formato)"
  ]
}
```

### 13. Registrar voto: Presidente 10

**O que mostrar:** Prévia + `token_cedula`; nada foi gravado ainda.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/registro
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "cargo": "PRESIDENTE",
  "modo": "NUMERO",
  "numero": "10"
}
```

**Esperado:** 200

```json
{
  "cargo": "PRESIDENTE",
  "tipo_voto": "NOMINAL",
  "candidato": {
    "numero": "10",
    "nome_urna": "Carlos Lima",
    "partido_sigla": "PINO"
  },
  "mensagem": "Confira os dados e confirme o voto.",
  "token_cedula": "<token>",
  "expira_em": "<data e hora>",
  "links": [
    {
      "rel": "confirmar",
      "metodo": "POST",
      "href": "/api/v1/votacao/eleicoes/1/votos/confirmacao"
    }
  ]
}
```

### 14. Confirmar o voto

**O que mostrar:** Voto confirmado; a resposta não diz em quem.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/confirmacao
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "token_cedula": "{{token_cedula}}"
}
```

**Esperado:** 201

```json
{
  "eleicao_id": 1,
  "cargo": "PRESIDENTE",
  "mensagem": "Voto confirmado.",
  "links": [
    {
      "rel": "cedula",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/cedula"
    },
    {
      "rel": "participacao",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/participacao"
    }
  ]
}
```

### 15. Confirmar de novo (mesmo token)

**O que mostrar:** Voto único e imutável.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/confirmacao
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "token_cedula": "{{token_cedula}}"
}
```

**Esperado:** 409 `VOTO_JA_REGISTRADO`

```json
{
  "erro": {
    "codigo": "VOTO_JA_REGISTRADO",
    "mensagem": "Você já votou para este cargo.",
    "detalhes": {}
  }
}
```

### 16. Registrar voto em branco: Senador

**O que mostrar:** Voto em branco.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/registro
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "cargo": "SENADOR",
  "modo": "BRANCO"
}
```

**Esperado:** 200

```json
{
  "cargo": "SENADOR",
  "tipo_voto": "BRANCO",
  "candidato": null,
  "mensagem": "Voto em BRANCO.",
  "token_cedula": "<token>",
  "expira_em": "<data e hora>",
  "links": [
    {
      "rel": "confirmar",
      "metodo": "POST",
      "href": "/api/v1/votacao/eleicoes/1/votos/confirmacao"
    }
  ]
}
```

### 16. Confirmar o voto em branco

**O que mostrar:** Confirmação.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/confirmacao
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "token_cedula": "{{token_cedula}}"
}
```

**Esperado:** 201

```json
{
  "eleicao_id": 1,
  "cargo": "SENADOR",
  "mensagem": "Voto confirmado.",
  "links": [
    {
      "rel": "cedula",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/cedula"
    },
    {
      "rel": "participacao",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/participacao"
    }
  ]
}
```

### 17. Registrar número inexistente: Governador 99

**O que mostrar:** Número sem candidato vira nulo.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/registro
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "cargo": "GOVERNADOR",
  "modo": "NUMERO",
  "numero": "99"
}
```

**Esperado:** 200

```json
{
  "cargo": "GOVERNADOR",
  "tipo_voto": "NULO",
  "candidato": null,
  "mensagem": "Voto NULO: número sem candidato para este cargo.",
  "token_cedula": "<token>",
  "expira_em": "<data e hora>",
  "links": [
    {
      "rel": "confirmar",
      "metodo": "POST",
      "href": "/api/v1/votacao/eleicoes/1/votos/confirmacao"
    }
  ]
}
```

### 17. Confirmar o voto nulo

**O que mostrar:** Confirmação.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/confirmacao
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "token_cedula": "{{token_cedula}}"
}
```

**Esperado:** 201

```json
{
  "eleicao_id": 1,
  "cargo": "GOVERNADOR",
  "mensagem": "Voto confirmado.",
  "links": [
    {
      "rel": "cedula",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/cedula"
    },
    {
      "rel": "participacao",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/participacao"
    }
  ]
}
```

### 18. Login de Bruno

**O que mostrar:** Outro eleitor.

```http
POST {{base_url}}/auth/login
Content-Type: application/x-www-form-urlencoded

username=341.672.110-17&password=Eleitor@123
```

**Esperado:** 200

```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "expira_em": "<data e hora>",
  "usuario": {
    "id": 3,
    "nome": "Bruno Almeida",
    "perfil": "ELEITOR"
  }
}
```

### 18. Bruno registra Presidente 20

**O que mostrar:** Mais votos para a apuração.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/registro
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "cargo": "PRESIDENTE",
  "modo": "NUMERO",
  "numero": "20"
}
```

**Esperado:** 200

```json
{
  "cargo": "PRESIDENTE",
  "tipo_voto": "NOMINAL",
  "candidato": {
    "numero": "20",
    "nome_urna": "Marina Costa",
    "partido_sigla": "UC"
  },
  "mensagem": "Confira os dados e confirme o voto.",
  "token_cedula": "<token>",
  "expira_em": "<data e hora>",
  "links": [
    {
      "rel": "confirmar",
      "metodo": "POST",
      "href": "/api/v1/votacao/eleicoes/1/votos/confirmacao"
    }
  ]
}
```

### 18. Bruno confirma

**O que mostrar:** Confirmação.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/confirmacao
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "token_cedula": "{{token_cedula}}"
}
```

**Esperado:** 201

```json
{
  "eleicao_id": 1,
  "cargo": "PRESIDENTE",
  "mensagem": "Voto confirmado.",
  "links": [
    {
      "rel": "cedula",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/cedula"
    },
    {
      "rel": "participacao",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/participacao"
    }
  ]
}
```

### 18. Login de Camila

**O que mostrar:** Outro eleitor.

```http
POST {{base_url}}/auth/login
Content-Type: application/x-www-form-urlencoded

username=945.807.302-24&password=Eleitor@123
```

**Esperado:** 200

```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "expira_em": "<data e hora>",
  "usuario": {
    "id": 4,
    "nome": "Camila Rocha",
    "perfil": "ELEITOR"
  }
}
```

### 18. Camila registra Presidente 10

**O que mostrar:** Mais votos para a apuração.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/registro
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "cargo": "PRESIDENTE",
  "modo": "NUMERO",
  "numero": "10"
}
```

**Esperado:** 200

```json
{
  "cargo": "PRESIDENTE",
  "tipo_voto": "NOMINAL",
  "candidato": {
    "numero": "10",
    "nome_urna": "Carlos Lima",
    "partido_sigla": "PINO"
  },
  "mensagem": "Confira os dados e confirme o voto.",
  "token_cedula": "<token>",
  "expira_em": "<data e hora>",
  "links": [
    {
      "rel": "confirmar",
      "metodo": "POST",
      "href": "/api/v1/votacao/eleicoes/1/votos/confirmacao"
    }
  ]
}
```

### 18. Camila confirma

**O que mostrar:** Confirmação.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/confirmacao
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "token_cedula": "{{token_cedula}}"
}
```

**Esperado:** 201

```json
{
  "eleicao_id": 1,
  "cargo": "PRESIDENTE",
  "mensagem": "Voto confirmado.",
  "links": [
    {
      "rel": "cedula",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/cedula"
    },
    {
      "rel": "participacao",
      "metodo": "GET",
      "href": "/api/v1/votacao/eleicoes/1/participacao"
    }
  ]
}
```

### 19. Chefe tenta registrar voto

**O que mostrar:** Só eleitor vota.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/registro
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "cargo": "PRESIDENTE",
  "modo": "NUMERO",
  "numero": "10"
}
```

**Esperado:** 403 `PERFIL_NAO_AUTORIZADO`

```json
{
  "erro": {
    "codigo": "PERFIL_NAO_AUTORIZADO",
    "mensagem": "Seu perfil não tem permissão para esta operação.",
    "detalhes": {
      "perfis_permitidos": [
        "ELEITOR"
      ]
    }
  }
}
```

### 20. Chefe cadastra Gustavo (depois da abertura)

**O que mostrar:** Eleitor cadastrado depois da abertura.

```http
POST {{base_url}}/eleitores
Authorization: Bearer {{token_chefe}}
Content-Type: application/json

{
  "nome": "Gustavo Pereira",
  "cpf": "217.533.772-34",
  "titulo_eleitor": "100000000007",
  "data_nascimento": "1995-05-05",
  "senha": "Eleitor@123"
}
```

**Esperado:** 201

```json
{
  "id": 8,
  "nome": "Gustavo Pereira",
  "cpf": "21753377234",
  "titulo_eleitor": "100000000007",
  "data_nascimento": "1995-05-05",
  "criado_em": "<data e hora>"
}
```

### 20. Login de Gustavo

**O que mostrar:** Login normal.

```http
POST {{base_url}}/auth/login
Content-Type: application/x-www-form-urlencoded

username=217.533.772-34&password=Eleitor@123
```

**Esperado:** 200

```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "expira_em": "<data e hora>",
  "usuario": {
    "id": 20,
    "nome": "Gustavo Pereira",
    "perfil": "ELEITOR"
  }
}
```

### 20. Gustavo tenta abrir a cédula

**O que mostrar:** Não é eleitor apto.

```http
GET {{base_url}}/votacao/eleicoes/{{eleicao_id}}/cedula
Authorization: Bearer {{token_eleitor}}
```

**Esperado:** 403 `ELEITOR_NAO_APTO`

```json
{
  "erro": {
    "codigo": "ELEITOR_NAO_APTO",
    "mensagem": "Você foi cadastrado depois da abertura desta eleição e não pode votar nela.",
    "detalhes": {}
  }
}
```

## Parte 3: acompanhamento da votação

### 21. Login de Ana

**O que mostrar:** Perfil Eleitor.

```http
POST {{base_url}}/auth/login
Content-Type: application/x-www-form-urlencoded

username=011.524.493-03&password=Eleitor@123
```

**Esperado:** 200

```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "expira_em": "<data e hora>",
  "usuario": {
    "id": 2,
    "nome": "Ana Beatriz Souza",
    "perfil": "ELEITOR"
  }
}
```

### 21. Apuração parcial (Eleitor)

**O que mostrar:** Todos os cargos, percentuais, brancos e nulos, comparecimento.

```http
GET {{base_url}}/apuracao/eleicoes/{{eleicao_id}}/parcial
Authorization: Bearer {{token_eleitor}}
```

**Esperado:** 200

```json
{
  "eleicao_id": 1,
  "tipo": "PARCIAL",
  "status_eleicao": "ABERTA",
  "gerado_em": "<data e hora>",
  "comparecimento": {
    "eleitores_aptos": 7,
    "votantes": 3,
    "abstencao": 4
  },
  "cargos": [
    {
      "cargo": "SENADOR",
      "total_votos": 1,
      "votos_validos": 0,
      "brancos": 1,
      "nulos": 0,
      "situacao": "SEM_VOTOS_VALIDOS",
      "criterio": null,
      "mais_votado": null,
      "candidatos": [
        {
          "numero": "202",
          "nome_urna": "Paulo Mendes",
          "partido_sigla": "UC",
          "votos": 0,
          "percentual_validos": "0.00"
        },
        {
          "numero": "303",
          "nome_urna": "Lúcia Ramos",
          "partido_sigla": "MV",
          "votos": 0,
          "percentual_validos": "0.00"
        }
      ]
    },
    {
      "cargo": "PRESIDENTE",
      "total_votos": 3,
      "votos_validos": 3,
      "brancos": 0,
      "nulos": 0,
      "situacao": "DEFINIDO",
      "criterio": "MAIOR_VOTACAO",
      "mais_votado": {
        "numero": "10",
        "nome_urna": "Carlos Lima",
        "partido_sigla": "PINO",
        "votos": 2,
        "percentual_validos": "66.67"
      },
      "candidatos": [
        {
          "numero": "10",
          "nome_urna": "Carlos Lima",
          "partido_sigla": "PINO",
          "votos": 2,
          "percentual_validos": "66.67"
        },
        {
          "numero": "20",
          "nome_urna": "Marina Costa",
          "partido_sigla": "UC",
          "votos": 1,
          "percentual_validos": "33.33"
        }
      ]
    },
    "... (os demais cargos seguem o mesmo formato)"
  ]
}
```

### 22. Login de Carlos Lima

**O que mostrar:** Perfil Candidato.

```http
POST {{base_url}}/auth/login
Content-Type: application/x-www-form-urlencoded

username=398.259.791-94&password=Candidato@123
```

**Esperado:** 200

```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "expira_em": "<data e hora>",
  "usuario": {
    "id": 8,
    "nome": "Carlos Henrique Lima",
    "perfil": "CANDIDATO"
  }
}
```

### 22. Apuração parcial (Candidato)

**O que mostrar:** Candidato vê só o próprio cargo.

```http
GET {{base_url}}/apuracao/eleicoes/{{eleicao_id}}/parcial
Authorization: Bearer {{token_candidato}}
```

**Esperado:** 200

```json
{
  "eleicao_id": 1,
  "tipo": "PARCIAL",
  "status_eleicao": "ABERTA",
  "gerado_em": "<data e hora>",
  "comparecimento": {
    "eleitores_aptos": 7,
    "votantes": 3,
    "abstencao": 4
  },
  "cargos": [
    {
      "cargo": "PRESIDENTE",
      "total_votos": 3,
      "votos_validos": 3,
      "brancos": 0,
      "nulos": 0,
      "situacao": "DEFINIDO",
      "criterio": "MAIOR_VOTACAO",
      "mais_votado": {
        "numero": "10",
        "nome_urna": "Carlos Lima",
        "partido_sigla": "PINO",
        "votos": 2,
        "percentual_validos": "66.67"
      },
      "candidatos": [
        {
          "numero": "10",
          "nome_urna": "Carlos Lima",
          "partido_sigla": "PINO",
          "votos": 2,
          "percentual_validos": "66.67"
        },
        {
          "numero": "20",
          "nome_urna": "Marina Costa",
          "partido_sigla": "UC",
          "votos": 1,
          "percentual_validos": "33.33"
        }
      ]
    }
  ]
}
```

### 23. Candidato pede outro cargo

**O que mostrar:** Restrição por cargo.

```http
GET {{base_url}}/apuracao/eleicoes/{{eleicao_id}}/parcial?cargo=SENADOR
Authorization: Bearer {{token_candidato}}
```

**Esperado:** 403 `CARGO_NAO_PERMITIDO`

```json
{
  "erro": {
    "codigo": "CARGO_NAO_PERMITIDO",
    "mensagem": "Você só pode acompanhar o cargo da sua candidatura.",
    "detalhes": {
      "cargo_permitido": "PRESIDENTE"
    }
  }
}
```

### 24. Resultado com a eleição aberta

**O que mostrar:** Resultado só depois do encerramento.

```http
GET {{base_url}}/apuracao/eleicoes/{{eleicao_id}}/resultado
Authorization: Bearer {{token_chefe}}
```

**Esperado:** 409 `APURACAO_INDISPONIVEL`

```json
{
  "erro": {
    "codigo": "APURACAO_INDISPONIVEL",
    "mensagem": "Só é possível consultar o resultado final com a eleição ENCERRADA.",
    "detalhes": {
      "status": "ABERTA"
    }
  }
}
```

## Parte 4: encerramento e resultado final

### 25. Encerrar a eleição

**O que mostrar:** Encerramento.

```http
POST {{base_url}}/eleicoes/{{eleicao_id}}/encerramento
Authorization: Bearer {{token_chefe}}
```

**Esperado:** 200

```json
{
  "id": 1,
  "descricao": "Eleições Gerais 2026 — 1º turno (simulação)",
  "data": "2026-11-21",
  "turno": 1,
  "horario_abertura": "00:00:00",
  "horario_encerramento": "23:59:00",
  "status": "ENCERRADA",
  "aberta_em": "<data e hora>",
  "encerrada_em": "<data e hora>",
  "links": [
    {
      "rel": "self",
      "metodo": "GET",
      "href": "/api/v1/eleicoes/1"
    },
    {
      "rel": "resultado",
      "metodo": "GET",
      "href": "/api/v1/apuracao/eleicoes/1/resultado"
    }
  ]
}
```

### 26. Login de Diego

**O que mostrar:** Eleitor que ainda não votou.

```http
POST {{base_url}}/auth/login
Content-Type: application/x-www-form-urlencoded

username=917.400.297-04&password=Eleitor@123
```

**Esperado:** 200

```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "expira_em": "<data e hora>",
  "usuario": {
    "id": 5,
    "nome": "Diego Martins",
    "perfil": "ELEITOR"
  }
}
```

### 26. Diego tenta registrar voto

**O que mostrar:** Nenhum voto depois do encerramento.

```http
POST {{base_url}}/votacao/eleicoes/{{eleicao_id}}/votos/registro
Authorization: Bearer {{token_eleitor}}
Content-Type: application/json

{
  "cargo": "PRESIDENTE",
  "modo": "NUMERO",
  "numero": "10"
}
```

**Esperado:** 409 `ELEICAO_NAO_ABERTA`

```json
{
  "erro": {
    "codigo": "ELEICAO_NAO_ABERTA",
    "mensagem": "A eleição não está aberta.",
    "detalhes": {
      "status": "ENCERRADA"
    }
  }
}
```

### 27. Resultado final

**O que mostrar:** Votos por candidato, mais votado por cargo, abstenção.

```http
GET {{base_url}}/apuracao/eleicoes/{{eleicao_id}}/resultado
Authorization: Bearer {{token_chefe}}
```

**Esperado:** 200

```json
{
  "eleicao_id": 1,
  "tipo": "FINAL",
  "status_eleicao": "ENCERRADA",
  "gerado_em": "<data e hora>",
  "comparecimento": {
    "eleitores_aptos": 7,
    "votantes": 3,
    "abstencao": 4
  },
  "cargos": [
    {
      "cargo": "SENADOR",
      "total_votos": 1,
      "votos_validos": 0,
      "brancos": 1,
      "nulos": 0,
      "situacao": "SEM_VOTOS_VALIDOS",
      "criterio": null,
      "mais_votado": null,
      "candidatos": [
        {
          "numero": "202",
          "nome_urna": "Paulo Mendes",
          "partido_sigla": "UC",
          "votos": 0,
          "percentual_validos": "0.00"
        },
        {
          "numero": "303",
          "nome_urna": "Lúcia Ramos",
          "partido_sigla": "MV",
          "votos": 0,
          "percentual_validos": "0.00"
        }
      ]
    },
    {
      "cargo": "PRESIDENTE",
      "total_votos": 3,
      "votos_validos": 3,
      "brancos": 0,
      "nulos": 0,
      "situacao": "DEFINIDO",
      "criterio": "MAIOR_VOTACAO",
      "mais_votado": {
        "numero": "10",
        "nome_urna": "Carlos Lima",
        "partido_sigla": "PINO",
        "votos": 2,
        "percentual_validos": "66.67"
      },
      "candidatos": [
        {
          "numero": "10",
          "nome_urna": "Carlos Lima",
          "partido_sigla": "PINO",
          "votos": 2,
          "percentual_validos": "66.67"
        },
        {
          "numero": "20",
          "nome_urna": "Marina Costa",
          "partido_sigla": "UC",
          "votos": 1,
          "percentual_validos": "33.33"
        }
      ]
    },
    "... (os demais cargos seguem o mesmo formato)"
  ]
}
```

## Parte 5: bastidores (o que o professor também pede)

| # | O quê | Como mostrar |
| --- | --- | --- |
| 28 | Sigilo no banco | No psql (`docker exec -it eleicao-banco psql -U eleicao -d eleicao`): `SELECT * FROM registros_votacao;` e `SELECT * FROM votos;` mostram que não existe coluna que ligue uma tabela à outra. Depois `UPDATE votos SET tipo = 'BRANCO';` dá `ERROR:  Votos e registros de votação confirmados são imutáveis` (trigger). Se perguntarem: para quem administra o banco, a ligação ainda é possível pelo `xmin` (as duas linhas são gravadas na mesma transação); está nas limitações do README e da modelagem (D-134). |
| 29 | Testes | Árvore `tests/unitarios`, `tests/integracao`, `tests/arquitetura`; rodar `pytest tests/unitarios -v` (rápido, sem banco) e `pytest tests/integracao -q`; abrir um teste de cada tipo e explicar a diferença; mostrar a cobertura (`pytest --cov=app`). |
| 30 | Estrutura modular | No VS Code: as pastas dos módulos; abrir `app/votacao/` e seguir uma requisição: `rotas.py` → `servico.py` → `dominio.py` / `repositorio.py`; abrir `tests/arquitetura/test_dependencias.py` e explicar que as fronteiras são verificadas automaticamente. |
| 31 | Documentação | Swagger local (`/docs`): tags, Authorize, exemplos e respostas de erro; a especificação em `docs/openapi.json`; a frase sobre *code-first* (a spec sai do código). |
| 32 | Versionamento | `git log --oneline --graph --decorate` (commits pequenos, tags), Pull Requests e o CI verde no GitHub. |
