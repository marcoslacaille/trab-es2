# Prompt de apoio — Explicar o código (preparação para a arguição)

Use numa sessão nova, sempre que quiser entender uma parte do projeto. Troque `<MÓDULO OU ARQUIVO>` pelo que quer estudar (ex.: `app/votacao/`, `confirmar_voto`, `as migrações`, `os testes de integração`).

---

Quero entender `<MÓDULO OU ARQUIVO>` para explicá-lo sozinho ao professor numa arguição. **Não altere nenhum arquivo.**

1. Leia o código indicado, os testes dele e as seções relacionadas do `docs/PLANO.md`.
2. Explique em português simples, como para um colega de turma:
   - para que serve e qual problema resolve;
   - o caminho de uma requisição de ponta a ponta (rota → serviço → domínio → repositório → banco), citando arquivos e funções;
   - quais regras de negócio (RN-xx) ele implementa e em que linha cada uma é verificada;
   - quais conceitos da disciplina aparecem ali (módulo profundo, ocultação de informação, acoplamento, agregado, bounded context, regra de dependência, HATEOAS) e onde exatamente;
   - quais testes cobrem essa parte e qual a diferença entre o unitário e o de integração nesse caso.
3. No fim, faça **5 perguntas** que um professor faria sobre esse trecho, espere eu responder uma por uma e me corrija.
