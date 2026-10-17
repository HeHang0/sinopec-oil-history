from __future__ import annotations

import base64
import logging
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from .config import Config


LOG = logging.getLogger(__name__)


class GitError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    LOG.debug("run: %s", " ".join(args))
    completed = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitError(f"{' '.join(args)} failed: {detail}")
    return completed


def prepare_git_environment(config: Config) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    if not config.repo_url:
        return env

    key_text = config.ssh_key
    if config.ssh_key_b64:
        try:
            key_text = base64.b64decode(config.ssh_key_b64).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            raise GitError("GIT_SSH_PRIVATE_KEY_B64 is not valid base64") from exc
    if not key_text:
        raise GitError("GIT_SSH_PRIVATE_KEY or GIT_SSH_PRIVATE_KEY_B64 is required when GIT_REPO_URL is set")

    config.state_dir.mkdir(parents=True, exist_ok=True)
    key_path = config.state_dir / "git_key"
    key_path.write_text(key_text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass

    known_hosts = config.state_dir / "known_hosts"
    if not known_hosts.exists():
        scan = subprocess.run(
            ["ssh-keyscan", "-T", "10", config.ssh_host],
            text=True,
            capture_output=True,
            timeout=20,
        )
        if scan.returncode == 0 and scan.stdout.strip():
            known_hosts.write_text(scan.stdout, encoding="utf-8")
            known_hosts.chmod(0o600)
        else:
            LOG.warning("ssh-keyscan failed for %s; falling back to accept-new", config.ssh_host)

    ssh_parts = [
        "ssh",
        "-i",
        str(key_path),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if known_hosts.exists():
        ssh_parts.extend(["-o", f"UserKnownHostsFile={known_hosts}"])
    env["GIT_SSH_COMMAND"] = " ".join(shlex.quote(part) for part in ssh_parts)
    return env


def ensure_repository(config: Config, env: dict[str, str]) -> None:
    work_dir = config.work_dir
    if not config.repo_url:
        work_dir.mkdir(parents=True, exist_ok=True)
        LOG.info("local mode: writing into %s", work_dir)
        return

    if (work_dir / ".git").exists():
        _run(["git", "fetch", "origin", "--prune"], cwd=work_dir, env=env)
    else:
        if work_dir.exists() and any(work_dir.iterdir()):
            raise GitError(f"WORK_DIR is not empty and is not a Git repository: {work_dir}")
        work_dir.parent.mkdir(parents=True, exist_ok=True)
        LOG.info("cloning %s", config.repo_url)
        _run(["git", "clone", config.repo_url, str(work_dir)], env=env)

    remote_branch = _run(
        ["git", "rev-parse", "--verify", f"origin/{config.branch}"],
        cwd=work_dir,
        env=env,
        check=False,
    )
    if remote_branch.returncode == 0:
        local_branch = _run(
            ["git", "rev-parse", "--verify", config.branch],
            cwd=work_dir,
            env=env,
            check=False,
        )
        if local_branch.returncode == 0:
            _run(["git", "checkout", config.branch], cwd=work_dir, env=env)
        else:
            _run(["git", "checkout", "-B", config.branch, f"origin/{config.branch}"], cwd=work_dir, env=env)
        pull = _run(
            ["git", "pull", "--rebase", "--autostash", "origin", config.branch],
            cwd=work_dir,
            env=env,
            check=False,
        )
        if pull.returncode != 0:
            _run(["git", "rebase", "--abort"], cwd=work_dir, env=env, check=False)
            LOG.warning("startup pull failed: %s", (pull.stderr or pull.stdout or "").strip())
    else:
        _run(["git", "checkout", "-B", config.branch], cwd=work_dir, env=env)

    _run(["git", "config", "user.name", config.git_user_name], cwd=work_dir, env=env)
    _run(["git", "config", "user.email", config.git_user_email], cwd=work_dir, env=env)


def ensure_site_template(config: Config) -> None:
    source = Path(__file__).resolve().parent.parent / "site"
    target = config.work_dir / "site"
    target.mkdir(parents=True, exist_ok=True)
    (target / "data").mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "app.js", "style.css", ".nojekyll"):
        src = source / name
        dst = target / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            LOG.info("installed site template file %s", name)


def commit_and_push(config: Config, env: dict[str, str], data_dir: Path, message: str) -> bool:
    if not config.repo_url or config.dry_run:
        return False

    try:
        relative = data_dir.relative_to(config.work_dir)
    except ValueError:
        relative = Path(config.data_subdir)
    add_paths = [str(relative)]
    site_dir = config.work_dir / "site"
    if site_dir.exists():
        add_paths.append("site")
    _run(["git", "add", "--", *add_paths], cwd=config.work_dir, env=env)
    diff = _run(["git", "diff", "--cached", "--quiet"], cwd=config.work_dir, env=env, check=False)
    if diff.returncode == 0:
        LOG.info("no data changes; nothing to commit")
        return False

    _run(["git", "commit", "-m", message], cwd=config.work_dir, env=env)

    remote_branch = _run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", config.branch],
        cwd=config.work_dir,
        env=env,
        check=False,
    )
    remote_exists = remote_branch.returncode == 0

    last_error = ""
    for attempt in range(1, config.push_retries + 1):
        if remote_exists:
            pull = _run(
                ["git", "pull", "--rebase", "--autostash", "origin", config.branch],
                cwd=config.work_dir,
                env=env,
                check=False,
            )
            if pull.returncode != 0:
                _run(["git", "rebase", "--abort"], cwd=config.work_dir, env=env, check=False)
                last_error = (pull.stderr or pull.stdout or "").strip()
                LOG.warning("git pull failed (attempt %s/%s): %s", attempt, config.push_retries, last_error)
                if attempt < config.push_retries:
                    time.sleep(5 * attempt)
                continue

        push = _run(
            ["git", "push", "origin", f"HEAD:{config.branch}"],
            cwd=config.work_dir,
            env=env,
            check=False,
        )
        if push.returncode == 0:
            LOG.info("pushed data to %s (%s)", config.branch, message)
            return True
        last_error = (push.stderr or push.stdout or "").strip()
        LOG.warning("git push failed (attempt %s/%s): %s", attempt, config.push_retries, last_error)
        if attempt < config.push_retries:
            time.sleep(5 * attempt)
    raise GitError(f"could not push after {config.push_retries} attempts: {last_error}")
