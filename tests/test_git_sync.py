import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.config import Config
from app.git_sync import commit_and_push, ensure_repository


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


@unittest.skipUnless(shutil.which("git"), "git is required")
class GitSyncTests(unittest.TestCase):
    def _config(self, root: Path, remote: Path) -> Config:
        return Config(
            repo_url=str(remote),
            branch="main",
            ssh_key="",
            ssh_key_b64="",
            ssh_host="github.com",
            git_user_name="test-bot",
            git_user_email="test@example.com",
            interval_days=1,
            hour=6,
            minute=0,
            run_on_start=True,
            run_once=True,
            timezone="Asia/Shanghai",
            provinces=(),
            work_dir=root / "work",
            state_dir=root / "state",
            data_subdir="site/data",
            request_delay=0,
            push_retries=2,
            dry_run=False,
        )

    def test_commit_and_push_to_empty_bare_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote.git"
            _git("init", "--bare", str(remote))
            config = self._config(root, remote)
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"

            ensure_repository(config, env)
            data_dir = config.work_dir / "site" / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "shanghai.json").write_text('[{"date":"2026-10-16","92":8.5}]\n', encoding="utf-8")

            self.assertTrue(commit_and_push(config, env, data_dir, "test data"))

            check = root / "check"
            _git("clone", "--branch", "main", str(remote), str(check))
            pushed = (check / "site" / "data" / "shanghai.json")
            self.assertTrue(pushed.exists())
            self.assertIn("8.5", pushed.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
