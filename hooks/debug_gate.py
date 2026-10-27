#!/usr/bin/env python3
"""StarIA Debug Gate: optional Codex PreToolUse guardrail (stdlib only).

This is a workflow guardrail, NOT a security boundary. The Codex runtime can skip
untrusted/unsupported hooks. Agents with filesystem access may modify local state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

STATE_TTL = 2 * 3600
APPROVAL_TTL = 15 * 60
MAX_INPUT = 1024 * 1024
# Only structured, allowlisted error classes: never persist arbitrary test output.
FAILURE_PATTERN = re.compile(r"\b(?:AssertionError|TypeError|ValueError|KeyError|IndexError|AttributeError|NameError|ImportError|ModuleNotFoundError|SyntaxError|ZeroDivisionError|RuntimeError|TimeoutError|TestFailure|FAILED|FAIL|ERROR)\b")
READ_ONLY = re.compile(
    r"^(?:(?:pwd|ls|dir|cat|type|head|tail|rg|grep|Get-ChildItem|Get-Content)\b|"
    r"git\s+(?:status|diff|rev-parse|ls-files)\b)", re.I
)
PATCH_PATH = re.compile(r"^\*\*\*\s+(?:Update File|Add File|Delete File|Move to):\s+(.+?)\s*$", re.M)
WRITE_TOOL = re.compile(r"(write|edit|apply_patch|patch|create|delete|remove|rename|move|update|replace|save|execute|shell|terminal)", re.I)


def root_for(cwd: str) -> Path:
    path = Path(cwd).resolve()
    try:
        p = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=3)
        if p.returncode == 0 and p.stdout.strip():
            return Path(p.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return path


def storage_dir() -> Path:
    return Path(os.environ.get("STARIA_DEBUG_GATE_HOME") or
                (Path.home() / ".staria-debug-gate")).expanduser().resolve()


def state_path(root: Path) -> Path:
    key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:24]
    return storage_dir() / (key + ".json")


def protection_path(root: Path) -> Path:
    # Independent sentinel: malformed or lost incident state must not disable policy.
    return state_path(root).with_suffix(".protected")


def is_protected(root: Path) -> bool:
    return protection_path(root).exists()


def set_protection(root: Path, enabled: bool) -> None:
    target = protection_path(root)
    if enabled:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Never silently replace a policy marker or trust unvalidated state.
        with target.open("a", encoding="utf-8") as f:
            f.write("")
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    else:
        target.unlink(missing_ok=True)


def read_state(root: Path) -> dict | None:
    try:
        obj = json.loads(state_path(root).read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or obj.get("root") != str(root):
            return None
        return obj
    except (OSError, ValueError, TypeError):
        return None


def save_state(root: Path, state: dict) -> None:
    target = state_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp." + str(os.getpid()))
    try:
        with open(tmp, "x", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    finally:
        tmp.unlink(missing_ok=True)


def git_head(root: Path) -> str:
    try:
        p = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=3)
        return p.stdout.strip() if p.returncode == 0 else "no-git"
    except (OSError, subprocess.TimeoutExpired):
        return "no-git"


def valid_scope_path(path: str) -> str:
    norm = path.replace("\\", "/").strip()
    if (not norm or norm.startswith("/") or re.match(r"^[a-zA-Z]:", norm) or
        "\x00" in norm or any(x in ("", ".", "..") for x in norm.rstrip("/").split("/"))):
        raise ValueError(f"Caminho de escopo inválido: {path!r}")
    return norm


def file_hash(root: Path, relative: str) -> str:
    p = root / relative
    if p.is_symlink():
        return "symlink:" + os.readlink(p)
    if p.is_dir():
        h = hashlib.sha256()
        paths = sorted(p.rglob("*"))
        if len(paths) > 4000:
            return "too-many-files"  # cannot be accepted by approve below
        for child in paths:
            if child.is_file() or child.is_symlink():
                h.update(str(child.relative_to(p)).encode())
                if child.is_symlink():
                    h.update(("symlink:" + os.readlink(child)).encode())
                else:
                    h.update(str(child.stat().st_size).encode())
                    h.update(file_hash(root, str(child.relative_to(root))).encode())
        return "tree:" + h.hexdigest()
    if not p.is_file():
        return "missing"
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def baseline(root: Path, paths: list[str]) -> dict:
    return {"head": git_head(root), "files": {p: file_hash(root, p) for p in paths}}


def allowed_path(path: str, scope: list[str]) -> bool:
    try:
        path = valid_scope_path(path)
    except ValueError:
        return False
    return any(path.startswith(s) if s.endswith("/") else path == s for s in scope)


def approval_valid(root: Path, state: dict) -> bool:
    approval = state.get("approval")
    if not isinstance(approval, dict) or approval.get("until", 0) < time.time():
        return False
    recorded = approval.get("baseline")
    return isinstance(recorded, dict) and recorded == baseline(root, list(recorded.get("files", {})))


def source_line(root: Path, relative: str, number: int) -> str:
    relative = valid_scope_path(relative)
    target = root / relative
    if (not isinstance(number, int) or number < 1 or number > 100000 or
        not target.resolve().is_relative_to(root) or target.is_symlink() or
        not target.is_file() or target.stat().st_size > 512000):
        raise ValueError("arquivo de evidência inseguro, inexistente ou acima do limite")
    try:
        data = target.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ValueError("evidência precisa ser texto UTF-8") from exc
    lines = data.splitlines()
    if number > len(lines):
        raise ValueError("linha de evidência não existe")
    line = lines[number - 1].strip()
    if not line or line.startswith(("#", "//", "*", "<!--")):
        raise ValueError("selecione uma linha executável ou de configuração, não um comentário")
    return line


def evidence_problem(root: Path, state: dict) -> str | None:
    analysis = state.get("analysis")
    reproduction = state.get("reproduction")
    if not isinstance(analysis, dict) or not isinstance(reproduction, dict):
        return "evidência estruturada ausente"
    ev = analysis.get("evidence")
    if not isinstance(ev, dict):
        return "ausente vínculo entre erro observado, arquivo e linha inspecionada"
    path, line_no = ev.get("path"), ev.get("line")
    if not isinstance(path, str) or not isinstance(line_no, int) or not allowed_path(path, state.get("scope", [])):
        return "linha de evidência fora do escopo"
    matching = [i for i in state.get("inspections", []) if isinstance(i, dict) and i.get("path") == path and i.get("line") == line_no]
    if not matching:
        return "a linha precisa ter sido inspecionada de verdade com inspect"
    try:
        line = source_line(root, path, line_no)
    except (ValueError, OSError) as exc:
        return "fonte de evidência não verificável: " + str(exc)
    digest = hashlib.sha256(line.encode("utf-8")).hexdigest()
    if not any(i.get("sha256") == digest for i in matching):
        return "linha alterada desde a inspeção; investigue novamente"
    quote = ev.get("quote", "")
    if not isinstance(quote, str) or len(quote.strip()) < 3 or len(quote) > 160 or quote not in line:
        return "trecho citado não existe na linha real do código"
    if quote not in str(analysis.get("root_cause", "")):
        return "causa raiz não cita o trecho real do código"
    tag = ev.get("failure_tag", "")
    if tag not in reproduction.get("failure_tags", []):
        return "categoria de falha não encontrada na execução original"
    if tag not in str(analysis.get("investigation", "")):
        return "investigação não relaciona a falha observada ao diagnóstico"
    return None


def deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": "StarIA Debug Gate: " + reason}}


def extra_context(msg: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}}


def gate_cli_command(command: str) -> bool:
    """Allow this utility's non-destructive operations through Bash.

    Shell chaining and explicit `unprotect` are never approved through hooks.
    """
    if not isinstance(command, str) or len(command) > 64000:
        return False
    if re.search(r"[;&|><\n\r`]", command) or "$(" in command or "${" in command:
        return False
    script = r"""(?:"[^"\r\n]+[/\\]debug_gate\.py"|'[^'\r\n]+[/\\]debug_gate\.py'|(?:[^\s'"]+[/\\])?debug_gate\.py)"""
    return bool(re.match(
        r"^\s*(?:(?:python|python3|py(?:\s+-3)?)\s+)?" + script +
        r"\s+(?:(?:--repo\s+(?:\"[^\"]+\"|'[^']+'|\S+)\s+))?" +
        r"(?:begin|status|capture|probe|inspect|verify|explain|approve|close|protect)(?:\s|$)",
        command, re.I))

def shell_read_only(command: str) -> bool:
    if not isinstance(command, str) or len(command) > 64000:
        return False
    if (re.search(r"[;&|><`\n\r]", command) or
        re.search(r"\$\(|\$\{|--(?:pre|pre-glob|output|delete|force|exec)\b|\s-(?:d|D)\b|\b(?:eval|exec|xargs|tee|sudo|sh|bash|powershell|pwsh)\b", command, re.I)):
        return False
    return bool(READ_ONLY.match(command.strip()))


def evaluate(event: dict) -> dict | None:
    if event.get("hook_event_name") != "PreToolUse":
        return deny("evento inválido")
    cwd = event.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return deny("diretório de trabalho não informado")
    root = root_for(cwd)
    state = read_state(root)
    strict = os.environ.get("STARIA_DEBUG_GATE_ENFORCE") == "1" or is_protected(root)
    active = state is not None and state.get("status") == "active"
    if not active and not strict:
        return None  # Unprotected repositories keep their original behavior.
    if active and (time.time() - state.get("created_at", 0) > STATE_TTL):
        return deny("incidente expirado; abra nova investigação")
    tool = event.get("tool_name", "")
    args = event.get("tool_input") or {}
    if not isinstance(args, dict):
        return deny("argumentos desconhecidos")
    if tool == "Bash":
        command = args.get("command", "")
        if not isinstance(command, str):
            return deny("comando Bash desconhecido")
        if gate_cli_command(command) or shell_read_only(command):
            return None
        return deny("comando não reconhecido como somente leitura; use investigação controlada e apply_patch após liberação")
    if tool == "apply_patch":
        command = args.get("command", "")
        if not isinstance(command, str) or not command.strip().startswith("*** Begin Patch") or "*** End Patch" not in command:
            return deny("patch ausente ou inválido")
        paths = PATCH_PATH.findall(command)
        if not paths:
            return deny("não foi possível identificar os arquivos do patch")
        if not active or not approval_valid(root, state):
            return deny("correção sem evidências aprovadas ou autorização expirada")
        if not all(allowed_path(p, state.get("scope", [])) for p in paths):
            return deny("patch modifica arquivo fora do escopo autorizado")
        try:
            if any(not (root / valid_scope_path(p)).resolve().is_relative_to(root) for p in paths):
                return deny("patch atravessa link simbólico fora do repositório")
        except ValueError:
            return deny("caminho inseguro")
        return None
    if not isinstance(tool, str):
        return deny("nome de ferramenta inválido")
    if tool == "update_plan":
        return None  # Planning is not a repository edit.
    if re.match(r"^mcp__[^_].*?__(?:read|get|list|search|fetch|query|lookup|inspect)_[\w-]+$", tool, re.I):
        if not any(k in args for k in ("content", "new_content", "patch", "command", "data", "file_bytes", "overwrite")):
            return None
    return deny("ferramenta não homologada no modo protegido: " + tool)


def on_hook() -> int:
    try:
        raw = sys.stdin.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            result = deny("entrada acima do limite")
        else:
            event = json.loads(raw)
            result = evaluate(event) if isinstance(event, dict) else deny("evento inválido")
    except Exception as ex:
        result = deny("erro de validação de entrada: " + type(ex).__name__)
    print(json.dumps(result or {}, ensure_ascii=False))
    return 0


def supported_reproduction(cmd: list[str]) -> bool:
    """Allow known test-runner entry points, not general-purpose shell execution."""
    if not cmd:
        return False
    exe = Path(cmd[0].replace("\\", "/")).name.lower()
    rest = [str(x).lower() for x in cmd[1:]]
    if exe in ("python", "python3", "python.exe", "python3.exe", "py", "py.exe"):
        if rest[:1] == ["-3"]:
            rest = rest[1:]
        return rest[:2] in (["-m", "pytest"], ["-m", "unittest"])
    if exe in ("pytest", "pytest.exe", "pytest.cmd"):
        return True
    if exe in ("npm", "npm.cmd", "pnpm", "pnpm.cmd", "yarn", "yarn.cmd"):
        return rest[:1] == ["test"] or rest[:2] == ["run", "test"]
    if exe in ("node", "node.exe"):
        return rest[:1] == ["--test"]
    if exe in ("cargo", "cargo.exe", "go", "go.exe", "dotnet", "dotnet.exe", "mvn", "mvn.cmd", "gradle", "gradle.bat", "gradlew", "gradlew.bat"):
        return rest[:1] == ["test"]
    return False


def supported_probe(cmd: list[str]) -> bool:
    if not cmd or len(cmd) > 30 or any(len(x) > 2000 for x in cmd):
        return False
    exe = Path(cmd[0].replace("\\", "/")).name.lower()
    if exe not in ("git", "git.exe", "rg", "rg.exe"):
        return False
    args = cmd[1:]
    if exe.startswith("git"):
        if not args or args[0] not in ("status", "diff", "rev-parse", "ls-files"):
            return False
    elif not args or any(a.startswith(("--pre", "--pre-glob", "--sort-files", "--files-without-match", "--replace")) for a in args):
        return False
    if any(re.search(r"[;&|><`\n\r]", a) or "$(" in a for a in args):
        return False
    if any(a.startswith(("--output", "--ext-diff", "--textconv", "--exec", "--config", "--no-index", "--no-pager")) for a in args):
        return False
    return True


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="StarIA Debug Gate (v1): investigação antes de correção")
    parser.add_argument("--repo", default=".", help="Diretório do repositório")
    sub = parser.add_subparsers(dest="action", required=True)
    beg = sub.add_parser("begin"); beg.add_argument("--issue", required=True); beg.add_argument("--scope", nargs="+", required=True)
    cap = sub.add_parser("capture"); cap.add_argument("command", nargs=argparse.REMAINDER)
    prb = sub.add_parser("probe"); prb.add_argument("command", nargs=argparse.REMAINDER)
    insp = sub.add_parser("inspect"); insp.add_argument("--path", required=True); insp.add_argument("--line", required=True, type=int)
    ver = sub.add_parser("verify"); ver.add_argument("command", nargs=argparse.REMAINDER)
    sub.add_parser("protect"); sub.add_parser("unprotect")
    exp = sub.add_parser("explain")
    for opt in ("hypothesis", "investigation", "root-cause", "regression", "evidence-path", "code-quote", "failure-tag"):
        exp.add_argument("--" + opt, required=True)
    exp.add_argument("--evidence-line", required=True, type=int)
    sub.add_parser("approve"); sub.add_parser("status")
    close = sub.add_parser("close"); close.add_argument("--abort", action="store_true")
    args = parser.parse_args(argv)
    root = root_for(args.repo)
    st = read_state(root)
    if args.action == "protect":
        set_protection(root, True)
        print("Debug Gate: proteção persistente ativada para este repositório. Edições exigem incidente aprovado.")
        return 0
    if args.action == "unprotect":
        # Manual operator action. The PreToolUse guard never grants the agent's
        # Bash invocation of this command in protected mode.
        set_protection(root, False)
        print("Debug Gate: proteção persistente desativada para este repositório.")
        return 0
    if args.action == "begin":
        scopes = [valid_scope_path(p) for p in args.scope]
        if len(args.issue.strip()) < 12:
            parser.error("descreva o incidente com pelo menos 12 caracteres")
        st = {"schema": 1, "root": str(root), "issue": args.issue.strip(), "scope": scopes,
              "status": "active", "created_at": time.time(), "reproduction": None,
              "probes": [], "inspections": [], "analysis": None, "approval": None, "verified": None}
        save_state(root, st)
        print("Debug Gate: incidente aberto; alterações bloqueadas até approve.")
        return 0
    if args.action == "status" and not st:
        print(json.dumps({"active": False, "protected": is_protected(root), "approved": False}, ensure_ascii=False))
        return 0
    if not st:
        parser.error("nenhum incidente para este repositório; execute begin")
    if args.action == "status":
        print(json.dumps({"active": st.get("status") == "active", "issue": st.get("issue"),
                          "reproduced": bool(st.get("reproduction")),
                          "explained": bool(st.get("analysis")),
                          "approved": approval_valid(root, st), "protected": is_protected(root),
                          "probe_count": len(st.get("probes", [])),
                          "verified": bool(st.get("verified"))}, ensure_ascii=False))
        return 0
    if args.action == "close":
        if st.get("approval") and not args.abort:
            verification = st.get("verified")
            original = st["approval"].get("baseline")
            current = baseline(root, st.get("scope", []))
            if (not isinstance(verification, dict) or verification.get("exit_code") != 0
                or verification.get("post_baseline") != current or current == original):
                parser.error("correção aprovada exige verify bem-sucedido do teste original após alteração; use close --abort para cancelar")
        st["status"] = "closed"; st["approval"] = None; save_state(root, st)
        print("Debug Gate: incidente encerrado" + (" sem validação (--abort)." if args.abort else " e verificado."))
        return 0
    if st.get("status") != "active" or time.time() - st.get("created_at", 0) > STATE_TTL:
        parser.error("incidente encerrado ou expirado; execute begin novamente")
    if args.action == "capture":
        cmd = args.command
        if cmd and cmd[0] == "--": cmd = cmd[1:]
        if not cmd or len(cmd) > 32: parser.error("forneça um comando de reprodução após --")
        if not supported_reproduction(cmd):
            parser.error("capture aceita apenas comandos de teste homologados; não executa shell ou python -c")
        try:
            run = subprocess.run(cmd, cwd=root, capture_output=True, timeout=30)
            rc = run.returncode
            output = run.stdout[:100000] + run.stderr[:100000]
        except subprocess.TimeoutExpired as ex:
            rc = 124; output = (ex.stdout or b"")[:100000] + (ex.stderr or b"")[:100000]
        except OSError as ex:
            parser.error("comando não executado: " + str(ex))
        # Only known error-class markers; no raw traceback or user data in persisted state.
        failure_tags = sorted(set(FAILURE_PATTERN.findall(output.decode("utf-8", errors="replace"))))
        st["reproduction"] = {"exit_code": rc, "observed_at": time.time(),
                              "failure_tags": failure_tags,
                              "command_sha256": hashlib.sha256(json.dumps(cmd).encode()).hexdigest(),
                              "output_sha256": hashlib.sha256(output).hexdigest(), "output_bytes": len(output)}
        st["analysis"] = None; st["approval"] = None; st["probes"] = []; st["inspections"] = []; st["verified"] = None
        save_state(root, st)
        print(f"Reprodução registrada: exit={rc}, bytes={len(output)}; saída bruta não foi armazenada.")
        return 0
    if args.action == "probe":
        cmd = args.command
        if cmd and cmd[0] == "--": cmd = cmd[1:]
        if not supported_probe(cmd):
            parser.error("probe aceita apenas git/rg diagnósticos sem opções perigosas")
        try:
            run = subprocess.run(cmd, cwd=root, capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as ex:
            parser.error("diagnóstico não executado: " + type(ex).__name__)
        output = run.stdout[:100000] + run.stderr[:100000]
        st.setdefault("probes", []).append({"exit_code": run.returncode, "observed_at": time.time(),
            "command_sha256": hashlib.sha256(json.dumps(cmd).encode()).hexdigest(),
            "output_sha256": hashlib.sha256(output).hexdigest(), "output_bytes": len(output)})
        st["analysis"] = None; st["approval"] = None; st["verified"] = None
        save_state(root, st)
        print("Investigação registrada: exit=%s, bytes=%s; saída bruta não armazenada." % (run.returncode, len(output)))
        return 0
    if args.action == "inspect":
        path = valid_scope_path(args.path)
        if not st.get("reproduction") or st["reproduction"].get("exit_code") == 0:
            parser.error("capture uma falha real antes de inspecionar o código")
        if not allowed_path(path, st.get("scope", [])):
            parser.error("evidência fora do escopo do incidente")
        try:
            line = source_line(root, path, args.line)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        observation = {"path": path, "line": args.line,
                       "sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                       "observed_at": time.time()}
        entries = st.setdefault("inspections", [])
        entries[:] = [i for i in entries if i.get("path") != path or i.get("line") != args.line]
        entries.append(observation)
        entries[:] = entries[-8:]
        st["analysis"] = None; st["approval"] = None; st["verified"] = None
        save_state(root, st)
        print(f"Linha inspecionada: {path}:{args.line}; SHA256: {observation['sha256'][:16]}; conteúdo omitido por privacidade.")
        return 0
    if args.action == "verify":
        cmd = args.command
        if cmd and cmd[0] == "--": cmd = cmd[1:]
        if not st.get("approval"):
            parser.error("execute approve antes de verify")
        if not supported_reproduction(cmd):
            parser.error("verify aceita somente comandos de teste homologados")
        digest = hashlib.sha256(json.dumps(cmd).encode()).hexdigest()
        if digest != (st.get("reproduction") or {}).get("command_sha256"):
            parser.error("verify deve repetir exatamente o comando da reprodução original")
        current = baseline(root, st.get("scope", []))
        if current == st["approval"].get("baseline"):
            parser.error("nenhuma alteração no escopo desde a autorização; verify requer a correção")
        try:
            run = subprocess.run(cmd, cwd=root, capture_output=True, timeout=30)
            rc = run.returncode
            output = run.stdout[:100000] + run.stderr[:100000]
        except subprocess.TimeoutExpired as ex:
            rc = 124; output = (ex.stdout or b"")[:100000] + (ex.stderr or b"")[:100000]
        except OSError as ex:
            parser.error("teste de verificação não executado: " + str(ex))
        st["verified"] = {"exit_code": rc, "observed_at": time.time(),
            "command_sha256": digest, "output_sha256": hashlib.sha256(output).hexdigest(),
            "output_bytes": len(output), "post_baseline": current}
        save_state(root, st)
        print("Verificação executada: exit=%s. %s" % (rc, "APROVADA" if rc == 0 else "FALHOU"))
        return 0
    if args.action == "explain":
        analysis = {"hypothesis": args.hypothesis, "investigation": args.investigation,
                    "root_cause": args.root_cause, "regression": args.regression}
        if any(len(v.strip()) < 24 for v in analysis.values()):
            parser.error("cada evidência textual precisa de pelo menos 24 caracteres")
        analysis["evidence"] = {"path": args.evidence_path, "line": args.evidence_line,
                                "quote": args.code_quote, "failure_tag": args.failure_tag}
        problem = evidence_problem(root, {**st, "analysis": analysis})
        if problem:
            parser.error(problem)
        st["analysis"] = analysis; st["approval"] = None; st["verified"] = None
        save_state(root, st)
        print("Hipótese, investigação, causa e plano de regressão registrados.")
        return 0
    if args.action == "approve":
        if not st.get("reproduction") or st["reproduction"].get("exit_code") == 0:
            parser.error("sem reprodução de falha (exit != 0) verificada por capture")
        if not st.get("probes") or not any(p.get("exit_code") == 0 for p in st["probes"]):
            parser.error("faltam diagnósticos executados com sucesso via probe")
        if not st.get("analysis") or not all(len(str(st["analysis"].get(k, "")).strip()) >= 24 for k in ("hypothesis", "investigation", "root_cause", "regression")):
            parser.error("faltam evidências de investigação e causa raiz")
        problem = evidence_problem(root, st)
        if problem:
            parser.error(problem)
        # Approval binds selected targets' hashes and current commit. After a patch,
        # another approve is needed, to review the current worktree before a new patch.
        fingerprint = baseline(root, st["scope"])
        if "too-many-files" in fingerprint["files"].values():
            parser.error("escopo de diretório grande demais; selecione arquivos específicos")
        st["approval"] = {"until": time.time() + APPROVAL_TTL, "baseline": fingerprint}
        st["verified"] = None
        save_state(root, st)
        print("Liberação por 15 minutos; limitada aos arquivos/paths informados. Nova edição invalida baseline.")
        return 0
    return 2


if __name__ == "__main__":
    try:
        if len(sys.argv) == 1 or sys.argv[1] == "hook":
            sys.exit(on_hook())
        sys.exit(cli(sys.argv[1:]))
    except (ValueError, OSError) as e:
        print("StarIA Debug Gate: " + str(e), file=sys.stderr)
        sys.exit(2)
