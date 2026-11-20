# Prompt de apoio — Corrigir um erro

Use quando um comando ou teste falhar e o agente da tarefa não tiver resolvido. Cole abaixo a saída completa do erro.

---

Um erro apareceu no projeto. Siga as regras do `CLAUDE.md`.

**O que eu estava fazendo:** <ex.: rodando os testes depois da tarefa 06 / subindo a API / rodando a migração>

**Comando:** <ex.: .venv\Scripts\python.exe -m pytest tests/integracao/test_candidaturas_api.py>

**Saída completa do erro:**

```text
<cole aqui>
```

Faça assim:

1. Leia o erro, o código envolvido e as seções do `docs/PLANO.md` que tratam dessa parte.
2. Explique a **causa** em 2 ou 3 frases, antes de mudar qualquer coisa.
3. Proponha a correção mínima e espere meu OK. Não enfraqueça testes nem regras de negócio para o erro sumir.
4. Corrija, rode a verificação completa (`ruff check`, `ruff format --check`, `pytest`) e faça um commit `fix(<modulo>): <o que foi corrigido>`.
5. Se a causa for algo do ambiente (Docker parado, porta ocupada, versão do Python), não mexa no código: me diga o que fazer.
