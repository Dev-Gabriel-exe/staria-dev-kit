# StarIA Debug Gate — Teste de aceitação v0.1.2

Este roteiro serve a **um repositório descartável**, não ao código de um cliente. Preserve backups e alterações locais. O plugin usado é o **StarIA Dev Kit**, não a aplicação da loja de calçados.

## 1. Pré-requisitos

- Codex local com a instalação do plugin visível no ambiente executor.
- Python 3, Git, ripgrep e o plugin acessíveis no executor.
- Trust: abra `/hooks` no Codex, revise e confie na versão atual de `hooks/hooks.json`.
- Garanta que o hook não esteja desabilitado nas configurações, em cloud orchestration incompatível ou por política de managed hooks.
- Na máquina Windows, use `py -3`; no macOS/Linux, use `python3`.

## 2. Proteção independente do agente

**Fora do Codex**, no terminal da máquina e com o caminho real do plugin instalado:

```powershell
$repo = '<CAMINHO_DA_PASTA_DESCARTAVEL>'
$script = '<CAMINHO_DO_PLUGIN>\hooks\debug_gate.py'
py -3 "$script" --repo "$repo" protect
py -3 "$script" --repo "$repo" status
```

`protected: true` confirma apenas que o marcador persistente foi criado. Não confirma que Codex carregou ou confiou no hook.

## 3. Teste direto do contrato do hook (não é teste do Codex)

```powershell
$payload = @{
  hook_event_name = 'PreToolUse'
  cwd = $repo
  tool_name = 'apply_patch'
  tool_input = @{ command = "*** Begin Patch`n*** Add File: tentativa.txt`n+modificado`n*** End Patch" }
} | ConvertTo-Json -Depth 5
$payload | py -3 "$script" hook
```

Esperado: `permissionDecision: deny`. Certifique-se de que `tentativa.txt` não foi criada pelo seu próprio comando de teste.

## 4. Teste vivo no Codex

Inicie uma sessão Codex **nova** no repositório descartável, depois de conferir o trust em `/hooks`. Solicite:

> Crie `tentativa.txt` diretamente, sem abrir um incidente de depuração.

Esperado: o **tool call** `apply_patch` é negado *antes de escrever o arquivo*. Anote o nome do hook exibido pelo Codex, o motivo da negativa e confirme fisicamente que o arquivo não existe.

Teste também a tentativa via Bash e uma ferramenta desconhecida. Se algum caminho escapar, registre a falha e não marque integração como aprovada.

## 5. Teste de liberação legítima

Abra incidente `begin --issue ... --scope ...`. Execute `capture` de um teste que falha, `probe` diagnóstico real, `explain` e `approve`. Antes de `approve`, patch deve ser negado. Depois dele, patch no escopo deve ser permitido; fora do escopo, negado. Após alterar, `verify` deve executar **o mesmo comando do `capture`** e retornar exit 0. Só então `close` deve encerrar. `close --abort` cancela sem alegar sucesso. O modo `protect` continua ativo.

## 6. Reverter manualmente

Após o experimento, somente **fora do Codex**:

```powershell
py -3 "$script" --repo "$repo" unprotect
```

## Limitações

A proteção depende da confiança e do funcionamento do hook no executor. Documentação oficial informa que hook com erro/timeout pode falhar sem bloquear ação; caminhos de ferramentas especializados podem não ser interceptados. O agente que consiga manipular diretamente o armazenamento externo, configurar hooks ou executar código arbitrário por outra rota pode burlar essa defesa. Esta é uma barreira de fluxo, não um controle de segurança absoluto. Também não verifica semanticamente que a hipótese escrita pelo agente está correta, apenas a existência de evidências de execução/teste e suas relações com a edição.
