# StarIA Debug Gate — uso e limites (v1.3)

Esta versão é uma **proteção operacional opt-in para incidentes de depuração**, não segurança do sistema operacional.

## Compatibilidade

Codex local com hooks habilitados e **confiados**: procura `hooks/hooks.json` na raiz do plugin. `PreToolUse` intercepta ferramentas suportadas, especialmente Bash e `apply_patch`. Alguns caminhos de execução podem ignorar hooks. O ChatGPT web pode usar a skill como instrução, mas **não** executa automaticamente o hook local. Plugins não distribuem scripts para a máquina apenas por serem instalados na web. No Codex CLI, use `/hooks` para revisar/confiar a definição instalada; alterações de hook exigem nova confiança. Python 3 no executor é obrigatório.

Referências oficiais:
- https://developers.openai.com/codex/hooks
- https://developers.openai.com/plugins/build/plugins

## Ativar em um repositório

O próprio agente deve iniciar o incidente de bug. Chamadas típicas em terminal, usando o caminho real de instalação do plugin:

```bash
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO protect  # Uma única vez, pelo operador
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO begin --issue "Falha observável na rota de login" --scope src/login.py tests/test_login.py
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO capture -- python3 -m pytest tests/test_login.py -q
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO probe -- git status --short
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO inspect --path src/login.py --line 23
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO explain --hypothesis "..." --investigation "... AssertionError ..." --root-cause "... trecho literal do código observado ..." --regression "..." --evidence-path src/login.py --evidence-line 23 --code-quote "trecho literal" --failure-tag AssertionError
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO approve
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO verify -- python3 -m pytest tests/test_login.py -q  # Após correção: MESMO comando do capture
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO status
python3 /CAMINHO/DO/PLUGIN/hooks/debug_gate.py --repo /CAMINHO/DO/PROJETO close
```

No Windows use `py -3` no lugar de `python3` e caminhos reais do Windows; os scripts não precisam de dependências pip. O argumento `--repo` vem **antes** do subcomando. `capture` aceita executores conhecidos de teste (`python -m unittest`, `python -m pytest`, `pytest`, `npm test`, `pnpm test`, `yarn test`, `node --test`, `cargo test`, `go test`, `dotnet test`, `mvn test` ou `gradle test`), com timeout de 30 segundos; registra código de saída, hashes e tamanho, **não** stdout/stderr em texto. Não aceita `python -c`, `bash -c` ou comandos shell arbitrários. Evite segredos na linha de comando e em logs.

Se o projeto tiver uma falha que não retorna exit code diferente de zero, a v1 exige um teste de regressão que sinalize falha por código de saída; não fabrique evidências.

## Estados e escopo

- Sem `protect` e sem incidente: não há bloqueio de alterações por padrão (preserva outras skills e o fluxo de novas funcionalidades).
- Depois de `protect`: o repositório permanece protegido mesmo sem `begin`, depois de `close` e se o JSON de incidente estiver corrompido. Apenas o operador deve usar `unprotect`, **fora de uma sessão Codex**. A chamada `unprotect` pelo Bash interceptado é negada.
- `protect` aplica-se a todo trabalho de edição no repositório (incluindo novas funcionalidades). Selecione os repositórios com cuidado.
- Com `begin` ativo: ferramentas desconhecidas ou de gravação são negadas, enquanto leituras básicas podem continuar; `apply_patch` fica bloqueado até `approve`.
- O `approve` precisa de reprodução observada com uma categoria de erro reconhecida, **ao menos um `probe` real com exit 0**, `inspect` de uma linha real dentro do escopo e análise escrita vinculada a essa evidência; a liberação dura até 15 minutos e fica vinculada a HEAD Git e hash dos alvos. Mudanças no arquivo exigem nova aprovação. O incidente expira após 2h.
- `--scope` aceita arquivo ou diretório terminado em `/`; escopos de diretórios de mais de 4000 entradas devem ser reduzidos. Arquivos fora do escopo são bloqueados. Symlinks escapando do repositório são recusados.
- Com `STARIA_DEBUG_GATE_ENFORCE=1` no ambiente do hook, gravações podem ser bloqueadas mesmo sem `begin` (modo estrito, bloqueia também trabalho não relacionado). Não habilite globalmente sem testar.
- `verify` executa **exatamente o comando que falhou em `capture`**, confirma exit 0 e registra a impressão dos arquivos editados. `close` não aceita uma correção aprovada sem verificação bem-sucedida, salvo com `--abort`. Alterações depois de `verify` invalidam o fechamento.
- `probe` aceita apenas diagnósticos `git` ou `rg`, sem shell embutido; o comando é realmente executado e tem exit/output hash registrado, sem stdout/stderr bruto. `inspect` lê uma linha existente de texto UTF-8 dentro do escopo, registra apenas seu SHA256 e não exibe conteúdo no terminal. `explain` requer `--evidence-path`, `--evidence-line`, `--code-quote` (trecho literal da linha) e `--failure-tag` (categoria efetivamente detectada no teste); a investigação deve conter o marcador de falha, e a causa raiz deve conter o trecho citado. Mudar a linha invalida aprovação até nova inspeção e análise.
- Por padrão, o estado fica em `~/.staria-debug-gate/`; defina `STARIA_DEBUG_GATE_HOME` para compartilhamento controlado. O estado **não é atestado criptograficamente**; o arquivo `.protected` separa a proteção persistente do incidente. Um agente com permissões para remover a proteção fora do hook, alterar os scripts ou desativar o runtime ainda pode contornar a política. Não é sandbox nem mecanismo de segurança inviolável.

## Limitações de segurança / classificação

Inspeção de comando shell é conservadora e não é um parser shell completo. Alguns comandos de diagnóstico são recusados e outros marcados como leitura podem ter efeitos indiretos. `capture` executa o comando indicado sob as permissões do usuário e não constitui isolamento. Bloqueios efetivos dependem da confiança/ativação dos hooks e do suporte do executor, que pode falhar aberto se o hook não carregar ou der timeout. Também não se garante interceptação de todas as ferramentas MCP. Use revisão humana, Git, permissões do sandbox e CI como controles independentes.

## Testar

Na raiz do pacote: `python3 -m unittest discover -s tests -v`. O teste chama o hook real via stdin JSON e usa repositórios temporários para validar bloqueio, liberação, expiração e escopo. Testes locais não substituem um teste de integração ao vivo no Codex com `/hooks` confiado.

## Aceitação da fase 2

O teste automatizado comprova decisões `deny` usando a mesma entrada JSON esperada pelo Codex; um teste **real** requer Codex instalado, plugin disponível localmente e confiado em `/hooks`. Consulte `docs/debug-gate-smoke-test.md`. Nenhum resultado de hooks locais valida por si só a integração real do executor.

## Evidência vinculada — fase 3 (v0.1.3)

O campo `failure_tag` aceita somente categorias reconhecidas na saída do `capture`, como `AssertionError` e `TypeError`; nenhuma saída completa de teste é armazenada. O código citado deve coincidir com uma linha que `inspect` leu, no escopo aprovado. Referenciar uma linha inexistente, um erro não observado ou uma frase sem o trecho de código impede o `approve`.

**Limite honesto:** coerência sintática verificável não é uma prova matemática/semântica de causalidade. Uma explicação falsa que copie trechos verdadeiros ainda pode satisfazer as regras; revisão humana ou avaliação adicional é necessária para comprovar a causa. Não armazene segredos em campos de análise. Testes internos não confirmam hooks em um Codex real.
