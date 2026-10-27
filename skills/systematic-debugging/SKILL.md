---
name: systematic-debugging
description: Use when an app has a failing test, runtime crash, unexpected behavior, stale deployment, or difficult-to-reproduce issue.
---

# Depuração sistemática — StarIA Debug Gate

## Regra principal

Para um **bug**, não modifique código antes de investigar a falha. Preserve alterações locais e verifique a intenção do usuário; correções precisam de evidência observável, não apenas de conjectura.

O Debug Gate é uma camada adicional **opt-in**, com hooks de `PreToolUse` onde o Codex os suporta. Ele NÃO é um sandbox, NÃO substitui permissões, e NÃO bloqueia ferramentas remotas/rotas de execução que ignorem os hooks. No ChatGPT sem executor local de hooks, este documento vale como procedimento, não como bloqueio técnico.

## Fluxo obrigatório durante depuração

1. **Garantir proteção no repositório**: quando o usuário desejar bloqueio real, a proteção persistente deve ser ativada uma vez pelo operador com `protect`, fora de uma sessão Codex. Isso impede patches mesmo se o agente esquecer `begin`. Não tente desligar essa proteção pelo agente. No ChatGPT sem hooks, siga o processo como instrução, sem prometer enforcement.
2. **Abrir incidente e reproduzir**: execute `begin --issue ... --scope ...`, depois `capture -- <comando-de-teste>`. Sem comando de reprodução retornando erro, a autorização de patch continua bloqueada nesta versão.
3. **Investigar com evidências executadas e ancoradas**: execute `probe -- git status --short` ou `rg ...` e, adicionalmente, `inspect --path ... --line ...` para registrar o SHA256 de uma linha real no escopo; identifique um `failure-tag` efetivamente observado no teste e relacione os resultados à causa provável. Não alegar certeza quando há só correlação.
4. **Planejar regressão**: indicar teste que falha antes e passará depois, incluindo casos de borda. Reaproveitar `automated-testing`.
5. **Registrar evidências**: `explain --hypothesis ... --investigation ... --root-cause ... --regression ... --evidence-path ... --evidence-line ... --code-quote ... --failure-tag ...` e somente então `approve`. Sem falha reproduzida, `probe` concluído, `inspect` de uma linha real, citação literal dessa linha na causa e referência ao tipo de erro observado, a aprovação é negada. Isso não comprova sozinho que a explicação seja semanticamente correta. A liberação é limitada a paths escolhidos, estado de arquivos e tempo.
6. **Corrigir minimamente**: de preferência `apply_patch` no escopo autorizado; verifique diff, rode testes e siga `code-review`. Não use shell como atalho para escrever código.
7. **Verificar e fechar**: após editar os arquivos autorizados, execute `verify -- <mesmo-comando-do-capture>` e depois `close`. O fechamento exige que o teste original passe e que o estado dos arquivos não tenha mudado após a verificação. Caso vá cancelar, use `close --abort` e explique a ausência de correção. Uma proteção persistente permanece ativa após `close`.

## Como operar o gate

Consulte `references/debug-gate.md` para instalação/trust, comandos, evidências, modos e limites de cobertura.

**Pontos inegociáveis:** não apagar mudanças preexistentes, não usar correção cosmética para ocultar a falha, não inventar logs, não registrar segredos e não pedir dispensa das verificações sem explicar o impacto. Outras skills continuam disponíveis e inalteradas.
