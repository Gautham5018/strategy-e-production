"""Fresh daily Kite session helper. Uses no order APIs.

Credentials live in the shared build-independent secrets directory. A new
Strategy E build therefore reuses the same API key/secret and access-token
file without requiring a package-local .env.
"""
from pathlib import Path
import os
from tempfile import NamedTemporaryFile
from kiteconnect import KiteConnect
from env_loader import load_env, SECRETS_DIR, SHARED_ENV_FILE
from shared_paths import ensure_dirs, KITE_ACCESS_TOKEN_FILE


def _write_env_updates(updates: dict[str, str]) -> None:
    """Atomically create/update the shared .env while preserving other values."""
    ensure_dirs()
    env_file = SHARED_ENV_FILE
    existing = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    out=[]; seen=set()
    for line in existing:
        stripped=line.strip()
        key=stripped.split("=",1)[0] if "=" in stripped else ""
        if key in updates and key not in seen:
            out.append(f"{key}={updates[key]}"); seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    with NamedTemporaryFile("w", encoding="utf-8", dir=env_file.parent, delete=False) as f:
        f.write("\n".join(out).rstrip()+"\n"); tmp=Path(f.name)
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(env_file)
    try:
        env_file.chmod(0o600)
    except OSError:
        pass


def write_token(token: str) -> None:
    if not token or not token.strip():
        raise RuntimeError("Generated access token is empty")
    ensure_dirs()
    with NamedTemporaryFile("w", encoding="utf-8", dir=KITE_ACCESS_TOKEN_FILE.parent, delete=False) as f:
        f.write(token.strip()+"\n"); tmp=Path(f.name)
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(KITE_ACCESS_TOKEN_FILE)


def main():
    ensure_dirs()
    env = load_env()
    api=(os.getenv("KITE_API_KEY") or env.get("KITE_API_KEY") or "").strip()
    secret=(os.getenv("KITE_API_SECRET") or env.get("KITE_API_SECRET") or "").strip()
    redirect=(os.getenv("KITE_REDIRECT_URL") or env.get("KITE_REDIRECT_URL") or "").strip()
    if not api or not secret:
        raise SystemExit(f"KITE_API_KEY and KITE_API_SECRET are required in shared secrets file: {SHARED_ENV_FILE}")
    kite=KiteConnect(api_key=api)
    if redirect:
        print("Configured redirect URL:", redirect)
    print("\nOpen this URL in your browser:\n")
    print(kite.login_url())
    print("\nPaste the fresh request_token only.\n")
    req=input("request_token: ").strip()
    if not req: raise SystemExit("request_token is empty")
    session=kite.generate_session(req,api_secret=secret); token=session.get("access_token")
    if not token: raise SystemExit("Kite generate_session returned no access_token")
    kite.set_access_token(token); profile=kite.profile()
    write_token(token)
    print("\nSESSION CREATED: PASS")
    print("User ID:",profile.get("user_id"))
    print("User name:",profile.get("user_name"))
    print("Access token saved to:",KITE_ACCESS_TOKEN_FILE)
    print("No order API was called.")


if __name__=="__main__": main()
