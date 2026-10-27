# StarIA Dev Kit — Debug Gate

**18 reusable full-stack development skills · Evidence-first debugging · No paid API required**

O StarIA Dev Kit é um plugin de desenvolvimento com 18 skills. A skill `systematic-debugging` inclui o **StarIA Debug Gate**, uma camada opcional de verificação que ajuda a impedir alterações prematuras de código enquanto bugs estão sendo investigados.

StarIA Dev Kit is a collection of 18 development skills. Its `systematic-debugging` skill integrates **StarIA Debug Gate**, an optional evidence-first workflow for Codex-compatible environments.

## Debug Gate

- Reproduza uma falha observável antes de propor correções.
- Registre diagnósticos e hipóteses; diferencie sintomas de possíveis causas.
- Restrinja a autorização de patch aos arquivos investigados.
- Execute testes de regressão e verifique os resultados antes de declarar a correção concluída.
- Consulte [o guia do Debug Gate](skills/systematic-debugging/references/debug-gate.md) e [o roteiro de smoke test](docs/debug-gate-smoke-test.md).

> **Limite de segurança:** os hooks são um controle operacional, não um sandbox de segurança. Podem estar ausentes, desabilitados ou ser ignorados por ferramentas não compatíveis. Testes automatizados do validador não comprovam integração real com todas as versões do Codex. Instalar o plugin no ChatGPT não ativa os hooks locais por si só.

## Testes

```bash
python -m unittest discover -s tests -v
```

O validador utiliza somente a biblioteca padrão do Python. Sem servidor próprio, GPU ou assinatura de API. O GitHub Actions executa a suíte quando configurado.

## Estrutura

- `skills/`: 18 skills existentes, preservadas.
- `hooks/`: `PreToolUse` e validador de evidências.
- `tests/`: testes automatizados.
- `docs/`: roteiro de teste em ambiente Codex.
- `skills/frontend-architecture/references/`: catálogo de referências de ferramentas terceirizadas, não redistribuição dessas ferramentas.

## Contribuições

Issues e sugestões são bem-vindas. Leia [CONTRIBUTING.md](CONTRIBUTING.md) e [SECURITY.md](SECURITY.md). Não publique dados de clientes nem credenciais.

**Licença:** ainda não definida. A disponibilidade pública dos arquivos não concede automaticamente direito de redistribuição ou uso sob licença open source.
