"""Unit, CLI and hook-contract integration tests; no Codex CLI required."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "debug_gate.py"
spec = importlib.util.spec_from_file_location("debug_gate", SCRIPT)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class DebugGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "src" / "a.py").write_text("x=1\n")
        (self.repo / "src" / "b.py").write_text("x=2\n")
        (self.repo / "test_failure.py").write_text("import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n def test_failure(self): self.assertIn('x=3',Path('src/a.py').read_text())\n")
        (self.repo / "test_success.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_success(self): self.assertEqual(1,1)\n")
        self.home = str(Path(self.tmp.name) / "state")
        self.env = patch.dict(os.environ, {"STARIA_DEBUG_GATE_HOME": self.home}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("STARIA_DEBUG_GATE_ENFORCE", None)

    def run_cli(self, *args, expect=0):
        p = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.repo), *args],
                           capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(p.returncode, expect, (p.stdout, p.stderr))
        return p

    def run_hook(self, tool, command, *, cwd=None):
        event = {"hook_event_name": "PreToolUse", "cwd": str(cwd or self.repo),
                 "tool_name": tool, "tool_input": {"command": command},
                 "session_id": "s1", "turn_id": "t1"}
        p = subprocess.run([sys.executable, str(SCRIPT), "hook"],
                           input=json.dumps(event), capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def forbidden(self, result):
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def patch_a(self):
        return "*** Begin Patch\n*** Update File: src/a.py\n@@\n-x=1\n+x=3\n*** End Patch"

    def begin(self, scope="src/a.py"):
        self.run_cli("begin", "--issue", "falha real durante login", "--scope", scope)

    def capture(self, fail=True):
        self.run_cli("capture", "--", sys.executable, "-m", "unittest", "test_failure" if fail else "test_success")
        self.run_cli("probe", "--", "rg", "x=1", "src/a.py")

    def explain(self):
        self.run_cli("explain", "--hypothesis", "a condição da função falha em entrada vazia",
                     "--investigation", "o comando reproduziu a falha isolando o caminho de entrada",
                     "--root-cause", "a função trata None como string de modo inconsistente",
                     "--regression", "teste de valor ausente deverá retornar mensagem de erro")

    def approved(self):
        self.begin(); self.capture(); self.explain(); self.run_cli("approve")

    def test_original_plugin_not_blocked_without_incident(self):
        self.assertEqual(self.run_hook("apply_patch", self.patch_a()), {})

    def test_strict_without_incident_denies(self):
        os.environ["STARIA_DEBUG_GATE_ENFORCE"] = "1"
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))
        self.assertEqual(self.run_hook("Bash", "git status --short"), {})

    def test_prevent_premature_edit(self):
        self.begin()
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_read_only_allowed(self):
        self.begin()
        for cmd in ("git status --short", "rg TODO src", "cat src/a.py"):
            with self.subTest(cmd=cmd): self.assertEqual(self.run_hook("Bash", cmd), {})

    def test_write_commands_and_chains_denied(self):
        self.begin()
        for cmd in ("echo evil > src/a.py", "python -c 'open(\"src/a.py\",\"w\").write(1)'",
                    "git status; rm -rf src", "cat src/a.py | tee src/b.py", "npm run build"):
            with self.subTest(cmd=cmd): self.forbidden(self.run_hook("Bash", cmd))

    def test_mcp_write_is_denied(self):
        self.begin()
        event = {"hook_event_name": "PreToolUse", "cwd": str(self.repo),
                 "tool_name": "mcp__filesystem__write_file", "tool_input": {"path": "src/a.py", "content": "evil"}}
        self.forbidden(g.evaluate(event))

    def test_capture_rejects_shell_and_python_eval(self):
        self.begin()
        self.run_cli("capture", "--", sys.executable, "-c", "open('src/a.py','w').write('evil')", expect=2)
        self.run_cli("capture", "--", "bash", "-c", "echo evil > src/a.py", expect=2)
        self.assertEqual((self.repo / "src" / "a.py").read_text(), "x=1\n")

    def test_git_diff_output_redirection_denied(self):
        self.begin()
        self.forbidden(self.run_hook("Bash", "git diff --output=src/a.py"))
        self.forbidden(self.run_hook("Bash", "git branch -D feature"))

    def test_no_failure_evidence_fails(self):
        self.begin(); self.capture(fail=False); self.explain()
        self.run_cli("approve", expect=2)

    def test_explanation_missing_fails(self):
        self.begin(); self.capture(); self.run_cli("approve", expect=2)

    def test_no_approval_after_capture(self):
        self.begin(); self.capture(); self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_valid_approval_allows_exact_patch(self):
        self.approved()
        self.assertEqual(self.run_hook("apply_patch", self.patch_a()), {})

    def test_out_of_scope_denied(self):
        self.approved()
        cmd = "*** Begin Patch\n*** Update File: src/b.py\n@@\n-x=2\n+x=4\n*** End Patch"
        self.forbidden(self.run_hook("apply_patch", cmd))

    def test_scope_traversal_denied(self):
        self.approved()
        cmd = "*** Begin Patch\n*** Update File: src/../secret.py\n@@\n-x\n+y\n*** End Patch"
        self.forbidden(self.run_hook("apply_patch", cmd))

    def test_after_file_edit_reapproval_required(self):
        self.approved()
        (self.repo / "src" / "a.py").write_text("x=3\n")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))
        self.run_cli("approve")
        self.assertEqual(self.run_hook("apply_patch", self.patch_a()), {})

    def test_after_git_head_change_reapproval_required(self):
        self.approved()
        with patch.object(g, "git_head", return_value="changed"):
            self.assertFalse(g.approval_valid(self.repo, g.read_state(self.repo)))

    def test_expired_approval_denied(self):
        self.approved()
        state = g.read_state(self.repo)
        state["approval"]["until"] = time.time() - 1
        g.save_state(self.repo, state)
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_expired_incident_denied(self):
        self.approved()
        state = g.read_state(self.repo)
        state["created_at"] = time.time() - 7201
        g.save_state(self.repo, state)
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_capture_does_not_store_secret_stdout(self):
        self.begin()
        (self.repo / "test_secret.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_secret(self):\n  print('DO-NOT-STORE-ME')\n  self.fail('private')\n")
        self.run_cli("capture", "--", sys.executable, "-m", "unittest", "test_secret")
        raw = g.state_path(self.repo).read_text()
        self.assertNotIn("DO-NOT-STORE-ME", raw)
        self.assertNotIn("print(", raw)

    def test_close_disables_guard_default(self):
        self.begin(); self.run_cli("close")
        self.assertEqual(self.run_hook("apply_patch", self.patch_a()), {})

    def test_deny_malformed_hook_payload(self):
        p = subprocess.run([sys.executable, str(SCRIPT), "hook"], input="{",
                           capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(p.returncode, 0)
        self.forbidden(json.loads(p.stdout))

    def test_cli_shell_invocations_allowed_during_incident(self):
        self.begin()
        cmd = f'python3 "{SCRIPT}" --repo "{self.repo}" approve'
        self.assertTrue(g.gate_cli_command(cmd))
        self.assertEqual(self.run_hook("Bash", cmd), {})

    def test_directory_scope_hash_invalidates_on_edit(self):
        self.begin("src/"); self.capture(); self.explain(); self.run_cli("approve")
        self.assertEqual(self.run_hook("apply_patch", self.patch_a()), {})
        (self.repo / "src" / "b.py").write_text("x=4\n")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_multiple_file_patch_rejected_if_one_out_scope(self):
        self.approved()
        cmd = "*** Begin Patch\n*** Update File: src/a.py\n@@\n-x=1\n+x=3\n*** Update File: src/b.py\n@@\n-x=2\n+x=3\n*** End Patch"
        self.forbidden(self.run_hook("apply_patch", cmd))

    def test_symlink_escape_denied(self):
        outside = Path(self.tmp.name) / "outside.txt"
        outside.write_text("keep")
        try: (self.repo / "src" / "link.py").symlink_to(outside)
        except (OSError, NotImplementedError): self.skipTest("symlink unavailable")
        self.begin("src/"); self.capture(); self.explain(); self.run_cli("approve")
        cmd = "*** Begin Patch\n*** Update File: src/link.py\n@@\n-keep\n+bad\n*** End Patch"
        self.forbidden(self.run_hook("apply_patch", cmd))


    def test_shell_tests_are_not_classified_as_read_only(self):
        self.begin()
        self.forbidden(self.run_hook("Bash", "python -m pytest -q"))
        self.forbidden(self.run_hook("Bash", "pytest -q"))

    def test_protection_prevents_edit_without_begin(self):
        self.run_cli("protect")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))
        self.assertEqual(self.run_hook("Bash", "git status --short"), {})
        self.forbidden(self.run_hook("Bash", "python -c 'print(1)'"))

    def test_protection_survives_close_and_does_not_impact_other_repos(self):
        self.run_cli("protect")
        self.begin()
        self.run_cli("close")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        self.assertEqual(self.run_hook("apply_patch", self.patch_a(), cwd=other), {})

    def test_protection_survives_corrupted_incident_state(self):
        self.run_cli("protect")
        g.state_path(self.repo).write_text("NOT JSON", encoding="utf-8")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_protection_cannot_be_unprotected_via_guarded_shell(self):
        self.run_cli("protect")
        self.forbidden(self.run_hook("Bash", f'python3 "{SCRIPT}" --repo "{self.repo}" unprotect'))
        self.assertTrue(g.is_protected(self.repo))

    def test_protection_can_be_unprotected_outside_codex(self):
        self.run_cli("protect")
        self.run_cli("unprotect")
        self.assertFalse(g.is_protected(self.repo))
        self.assertEqual(self.run_hook("apply_patch", self.patch_a()), {})

    def test_approval_requires_executed_probe(self):
        self.begin()
        self.run_cli("capture", "--", sys.executable, "-m", "unittest", "test_failure")
        self.explain()
        self.run_cli("approve", expect=2)

    def test_probe_rejects_unsafe_commands(self):
        self.begin()
        self.run_cli("probe", "--", "git", "config", "--global", "foo", "bar", expect=2)
        self.run_cli("probe", "--", "rg", "--pre", "bash", "x", expect=2)
        self.assertEqual(g.read_state(self.repo)["probes"], [])

    def test_protection_full_lifecycle_with_evidence(self):
        self.run_cli("protect")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))
        self.begin()
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))
        self.capture()
        self.explain()
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))
        self.run_cli("approve")
        self.assertEqual(self.run_hook("apply_patch", self.patch_a()), {})
        (self.repo / "src" / "a.py").write_text("x=3\n")
        self.run_cli("verify", "--", sys.executable, "-m", "unittest", "test_failure")
        self.run_cli("close")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_unknown_mcp_tool_blocked_in_protected_mode(self):
        self.run_cli("protect")
        evt = {"hook_event_name": "PreToolUse", "cwd": str(self.repo),
               "tool_name": "mcp__custom__do_anything", "tool_input": {"path": "src/a.py"}}
        self.forbidden(g.evaluate(evt))
        evt["tool_name"] = "mcp__custom__read_file"
        self.assertEqual(g.evaluate(evt), None)

    def test_protected_status_outside_incident(self):
        self.run_cli("protect")
        self.assertTrue(json.loads(self.run_cli("status").stdout)["protected"])

    def test_corrupted_state_types_do_not_fail_open(self):
        self.run_cli("protect")
        data = {"root": str(self.repo), "status": "active", "created_at": "invalid"}
        g.state_path(self.repo).write_text(json.dumps(data), encoding="utf-8")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_quoted_plugin_paths_are_accepted(self):
        cmd = r'py -3 "C:\Program Files\StarIA Kit\hooks\debug_gate.py" --repo "C:\Users\Example Repo" probe -- rg foo bar'
        self.assertTrue(g.gate_cli_command(cmd))
        self.assertFalse(g.gate_cli_command(cmd + " && echo BAD"))

    def test_cannot_close_approved_incident_without_verification(self):
        self.approved()
        self.run_cli("close", expect=2)
        self.assertTrue(g.read_state(self.repo)["status"] == "active")

    def test_operator_can_abort_approved_incident(self):
        self.run_cli("protect")
        self.approved()
        self.run_cli("close", "--abort")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_verify_requires_exact_original_command(self):
        self.approved()
        (self.repo / "src" / "a.py").write_text("x=3\n")
        self.run_cli("verify", "--", sys.executable, "-m", "unittest", "test_success", expect=2)
        self.run_cli("close", expect=2)

    def test_verify_requires_changed_file(self):
        self.approved()
        self.run_cli("verify", "--", sys.executable, "-m", "unittest", "test_failure", expect=2)
        self.run_cli("close", expect=2)

    def test_verify_failing_test_does_not_close(self):
        self.approved()
        (self.repo / "src" / "a.py").write_text("x=4\n")
        self.run_cli("verify", "--", sys.executable, "-m", "unittest", "test_failure")
        self.run_cli("close", expect=2)

    def test_post_verification_file_change_invalidates_close(self):
        self.approved()
        (self.repo / "src" / "a.py").write_text("x=3\n")
        self.run_cli("verify", "--", sys.executable, "-m", "unittest", "test_failure")
        (self.repo / "src" / "a.py").write_text("x=4\n")
        self.run_cli("close", expect=2)

    def test_verify_cannot_run_without_approval(self):
        self.begin()
        self.run_cli("verify", "--", sys.executable, "-m", "unittest", "test_failure", expect=2)

    def test_git_branch_rename_is_denied(self):
        self.run_cli("protect")
        self.forbidden(self.run_hook("Bash", "git branch -m main renamed"))
        self.forbidden(self.run_hook("Bash", "git grep --open-files-in-pager=sh secret"))

    def test_probe_denies_external_process_switches(self):
        self.begin()
        self.run_cli("probe", "--", "git", "grep", "--open-files-in-pager=sh", "foo", expect=2)
        self.run_cli("probe", "--", "git", "branch", "-M", "danger", expect=2)
        self.assertEqual(g.read_state(self.repo)["probes"], [])

    def test_approved_tool_still_blocks_shell_changes(self):
        self.approved()
        self.forbidden(self.run_hook("Bash", "git branch -M renamed"))
        self.forbidden(self.run_hook("Bash", "echo attack > src/a.py"))

    def test_guard_script_still_denies_before_begin_after_protection(self):
        self.run_cli("protect")
        self.forbidden(self.run_hook("apply_patch", self.patch_a()))

    def test_hook_manifest_matches_official_contract(self):
        obj = json.loads((SCRIPT.parent / "hooks.json").read_text())
        hook = obj["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(hook["type"], "command")
        self.assertIn("${PLUGIN_ROOT}", hook["command"])
        self.assertIn("commandWindows", hook)


if __name__ == "__main__":
    unittest.main()
