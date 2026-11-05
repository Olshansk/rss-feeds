"""Exercise the workflow push retry against real local Git remotes."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github/workflows"


class PublicationRetryTests(unittest.TestCase):
    def exercise_retry(self, mode):
        """Run each workflow retry with an unstaged tracked cache and a rejected push.

        How:
            1. Create an isolated local remote and commit a generated feed separately from its cache.
            2. Reject the push through a server hook or an independent remote commit.
            3. Execute the actual workflow retry and check publication and cache preservation.
        """
        for workflow in ("run_feeds.yml", "run_selenium_feeds.yml"):
            with self.subTest(workflow=workflow, mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                remote, work = root / "remote.git", root / "work"
                env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

                def git(*args, cwd=root, git_env=env):
                    return subprocess.check_output(
                        ["git", *args], cwd=cwd, env=git_env, text=True, stderr=subprocess.STDOUT
                    )

                git("init", "--bare", "--initial-branch=main", str(remote))
                git("clone", str(remote), str(work))
                git("config", "user.name", "Publication test", cwd=work)
                git("config", "user.email", "test@example.invalid", cwd=work)
                (work / "cache.json").write_text("original cache\n")
                (work / "feed.xml").write_text("original feed\n")
                git("add", ".", cwd=work)
                git("commit", "-m", "Initial", cwd=work)
                git("push", "-u", "origin", "main", cwd=work)

                if mode == "remote_advanced":
                    peer = root / "peer"
                    git("clone", str(remote), str(peer))
                    (peer / "independent.xml").write_text("independent publication\n")
                    git("add", ".", cwd=peer)
                    git(
                        "-c",
                        "user.name=Peer",
                        "-c",
                        "user.email=peer@example.invalid",
                        "commit",
                        "-m",
                        "Peer",
                        cwd=peer,
                    )
                    git("push", cwd=peer)
                else:
                    hook = remote / "hooks/pre-receive"
                    hook.write_text(
                        "#!/bin/sh\n"
                        "if [ ! -f rejected-once ]; then touch rejected-once; exit 1; fi\n"
                        + ("exit 1\n" if mode == "persistent_rejection" else "exit 0\n")
                    )
                    hook.chmod(0o755)

                (work / "feed.xml").write_text("generated feed\n")
                (work / "cache.json").write_text("updated cache\n")
                git("add", "feed.xml", cwd=work)
                git("commit", "-m", "Publish", cwd=work)
                data = yaml.safe_load((WORKFLOWS / workflow).read_text())
                steps = next(iter(data["jobs"].values()))["steps"]
                script = next(step["run"] for step in steps if step["name"] == "Commit and push feeds")
                retry = next(line.strip() for line in script.splitlines() if line.strip().startswith("git push ||"))
                result = subprocess.run(["bash", "-e", "-c", retry], cwd=work, env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode == 0, mode != "persistent_rejection", result.stdout + result.stderr)
                expected = "original feed\n" if mode == "persistent_rejection" else "generated feed\n"
                self.assertEqual(git("show", "main:feed.xml", cwd=remote), expected)
                self.assertEqual(git("show", "main:cache.json", cwd=remote), "original cache\n")
                self.assertEqual((work / "cache.json").read_text(), "updated cache\n")
                self.assertEqual(git("status", "--porcelain", cwd=work), " M cache.json\n")
                self.assertEqual(git("stash", "list", cwd=work), "")
                if mode == "remote_advanced":
                    self.assertEqual(git("show", "main:independent.xml", cwd=remote), "independent publication\n")

    def test_transient_remote_rejection_preserves_unstaged_cache(self):
        self.exercise_retry("transient_rejection")

    def test_concurrent_publication_rebases_without_losing_either_feed(self):
        self.exercise_retry("remote_advanced")

    def test_persistent_rejection_still_fails(self):
        self.exercise_retry("persistent_rejection")
