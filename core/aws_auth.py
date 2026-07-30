"""AWS profile / SSO helpers for S3 hosts.

CloudMount can use static keys (Keychain) or an AWS shared profile
(``~/.aws/config`` + credentials), which may be long-lived keys, SSO, or
``credential_process`` (e.g. IAM Roles Anywhere).
"""

from __future__ import annotations

import configparser
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional


def aws_cli_path() -> Optional[str]:
    return shutil.which("aws")


def default_aws_config_path() -> Path:
    return Path.home() / ".aws" / "config"


def default_aws_credentials_path() -> Path:
    return Path.home() / ".aws" / "credentials"


def list_aws_profiles() -> dict[str, Any]:
    """List profile names from ~/.aws/config and credentials."""
    profiles: set[str] = set()
    sources: dict[str, list[str]] = {}

    cred = default_aws_credentials_path()
    if cred.is_file():
        cp = configparser.ConfigParser()
        try:
            cp.read(cred)
            for sec in cp.sections():
                profiles.add(sec)
                sources.setdefault(sec, []).append("credentials")
        except configparser.Error:
            pass

    cfg = default_aws_config_path()
    if cfg.is_file():
        cp = configparser.ConfigParser()
        try:
            cp.read(cfg)
            for sec in cp.sections():
                # config uses "profile foo" except default
                name = sec
                if sec.startswith("profile "):
                    name = sec[len("profile ") :].strip()
                elif sec == "default":
                    name = "default"
                else:
                    # bare section names also appear
                    name = sec
                profiles.add(name)
                sources.setdefault(name, []).append("config")
        except configparser.Error:
            pass

    names = sorted(profiles, key=lambda s: (s != "default", s.lower()))
    return {
        "ok": True,
        "profiles": names,
        "sources": sources,
        "config_path": str(cfg),
        "credentials_path": str(cred),
        "aws_cli": aws_cli_path(),
    }


def _aws_env(profile: str, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    if profile:
        env["AWS_PROFILE"] = profile
        env["AWS_DEFAULT_PROFILE"] = profile
    if extra:
        env.update(extra)
    return env


def _run_aws(
    args: list[str],
    *,
    profile: str = "",
    timeout: float = 120,
) -> subprocess.CompletedProcess[str]:
    aws = aws_cli_path()
    if not aws:
        return subprocess.CompletedProcess(args, 127, "", "aws CLI not found on PATH")
    cmd = [aws] + args
    if profile and "--profile" not in args:
        cmd += ["--profile", profile]
    kw: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "env": _aws_env(profile),
    }
    if platform.system() == "Windows":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.run(cmd, **kw)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "aws command timed out")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def is_auth_failure(text: str) -> bool:
    """True when credentials are missing/expired (SSO login may help)."""
    low = (text or "").lower()
    needles = (
        "expiredtoken",
        "expired token",
        "token has expired",
        "security token included in the request is expired",
        "unable to locate credentials",
        "could not find credentials",
        "no credentials",
        "error when retrieving credentials",
        "sso session",
        "sso token",
        "refresh this sso",
        "to refresh this sso",
        "the sso session associated",
        "invalididentitytoken",
        "invalidclienttokenid",
        "signaturedoesnotmatch",
        "failed to refresh cached credentials",
        "error loading sso token",
        "login required",
        "token is expired",
        "provided token has expired",
    )
    return any(n in low for n in needles)


def is_permission_failure(text: str) -> bool:
    """True when IAM denies the call (credentials may still be valid)."""
    low = (text or "").lower()
    return any(
        n in low
        for n in (
            "accessdenied",
            "access denied",
            "not authorized to perform",
            "forbidden",
            "status code: 403",
            "statuscode: 403",
            "explicit deny",
            "unauthorizedoperation",
        )
    )


def friendly_aws_error(text: str, *, profile: str = "") -> str:
    """Human-readable message for browse/test/mount failures."""
    raw = (text or "").strip()
    low = raw.lower()
    prof = f" profile “{profile}”" if profile else ""

    # Prefer permission messaging when IAM denied an API (even if 403 text is noisy)
    if is_permission_failure(raw) and not is_auth_failure(raw):
        if "listbuckets" in low or "s3:listallmybuckets" in low or "s3:list" in low:
            return (
                f"Permission denied listing buckets{prof}. "
                "This identity cannot list buckets at the root. "
                "Ask an admin for s3:ListAllMyBuckets, or type a bucket name you can access "
                "in the remote path / browse into that path directly."
            )
        return (
            f"Permission denied{prof}. "
            "Credentials may be valid but lack rights for this action.\n\n"
            f"{raw[-500:]}"
        )

    if "unable to locate credentials" in low or "could not find credentials" in low:
        return (
            f"No AWS credentials found{prof}. "
            "Check the profile name, or run: aws sso login --profile … / aws configure."
        )

    if is_auth_failure(raw) or ("sso" in low and "error" in low):
        return (
            f"AWS credentials expired or SSO session missing{prof}. "
            "CloudMount tries “aws sso login” automatically when possible "
            "(Hosts → AWS login). "
            f"\n\n{raw[-400:]}"
        )

    if not raw:
        return "AWS / S3 request failed (no error text)."
    return raw[-800:]


def check_caller_identity(profile: str) -> dict[str, Any]:
    """Return ok + identity via STS GetCallerIdentity."""
    r = _run_aws(["sts", "get-caller-identity", "--output", "json"], profile=profile, timeout=30)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0 and r.stdout:
        return {"ok": True, "raw": r.stdout.strip()[:2000]}
    return {"ok": False, "error": out[-1500:] or f"exit {r.returncode}", "auth_failure": is_auth_failure(out)}


def sso_login(profile: str, *, timeout: float = 300) -> dict[str, Any]:
    """Run `aws sso login --profile …` (opens browser). Blocks until done/timeout."""
    if not aws_cli_path():
        return {
            "ok": False,
            "error": (
                "AWS CLI not found on PATH. Install the AWS CLI v2, then retry, "
                "or run: aws sso login --profile " + (profile or "NAME")
            ),
        }
    if not profile:
        return {"ok": False, "error": "Profile name required for SSO login"}
    # Interactive: may open browser — do not hide console on Windows so user sees prompts
    aws = aws_cli_path()
    cmd = [aws, "sso", "login", "--profile", profile]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_aws_env(profile),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": (
                f"aws sso login timed out after {int(timeout)}s. "
                f"Run manually in a terminal: aws sso login --profile {profile}"
            ),
        }
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode == 0:
        return {"ok": True, "message": out or f"SSO login succeeded for profile {profile}"}
    # Some setups use non-SSO profiles; surface clear error
    if "not configured" in out.lower() or "does not have sso" in out.lower():
        return {
            "ok": False,
            "error": (
                f"Profile “{profile}” is not an SSO profile (or SSO is not configured). "
                "Static-key profiles do not need login. For Roles Anywhere, refresh via "
                "credential_process outside CloudMount.\n\n" + out[-600:]
            ),
            "not_sso": True,
        }
    return {"ok": False, "error": out[-1500:] or f"aws sso login exit {r.returncode}"}


def ensure_profile_credentials(
    profile: str,
    *,
    try_login: bool = False,
) -> dict[str, Any]:
    """Optional STS check. Login is **not** run proactively (try_login default False).

    Prefer calling :func:`sso_login` only after rclone reports an auth failure.
    """
    if not profile:
        return {"ok": False, "error": "AWS profile name is empty"}

    first = check_caller_identity(profile)
    if first.get("ok"):
        return {"ok": True, "identity": first.get("raw"), "login_ran": False}

    err = first.get("error") or "credential check failed"
    if not try_login or not first.get("auth_failure"):
        return {
            "ok": False,
            "error": friendly_aws_error(err, profile=profile),
            "login_ran": False,
            "raw": err,
        }

    login = sso_login(profile)
    if not login.get("ok"):
        if login.get("not_sso"):
            return {
                "ok": False,
                "error": friendly_aws_error(err, profile=profile) + "\n\n" + (login.get("error") or ""),
                "login_ran": True,
                "raw": err,
            }
        return {
            "ok": False,
            "error": login.get("error") or "SSO login failed",
            "login_ran": True,
            "raw": err,
        }

    second = check_caller_identity(profile)
    if second.get("ok"):
        return {
            "ok": True,
            "identity": second.get("raw"),
            "login_ran": True,
            "message": "SSO login refreshed credentials",
        }
    return {
        "ok": False,
        "error": friendly_aws_error(second.get("error") or err, profile=profile),
        "login_ran": True,
        "raw": second.get("error") or err,
    }
