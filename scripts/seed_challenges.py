#!/usr/bin/env python3
"""
Siege Range CTF - Challenge Seeder
Reads challenges/*/challenge.json and seeds them into the platform API.
"""

import glob
import json
import os
import sys

import requests

# ── ANSI colors ──────────────────────────────────────────────────────────────
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def info(msg: str) -> None:
    print(f"{CYAN}[INFO]{RESET}  {msg}")


def ok(msg: str) -> None:
    print(f"{GREEN}[OK]{RESET}    {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET}  {msg}")


def error(msg: str) -> None:
    print(f"{RED}[ERROR]{RESET} {msg}", file=sys.stderr)


def fatal(msg: str) -> None:
    error(msg)
    sys.exit(1)


def authenticate(base_url: str, email: str, password: str) -> str:
    """Authenticate with the API and return a bearer token."""
    info(f"Authenticating as {BOLD}{email}{RESET} ...")
    try:
        resp = requests.post(
            f"{base_url}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
    except requests.ConnectionError:
        fatal(f"Cannot connect to API at {base_url}")
    except requests.Timeout:
        fatal("Authentication request timed out")

    if resp.status_code != 200:
        fatal(
            f"Authentication failed (HTTP {resp.status_code}): "
            f"{resp.text[:200]}"
        )

    data = resp.json()
    token = data.get("token") or data.get("access_token") or data.get("accessToken")
    if not token:
        fatal("Authentication succeeded but no token found in response")

    ok("Authenticated successfully")
    return token


def create_challenge(base_url: str, headers: dict, challenge: dict) -> bool:
    """Create a single challenge. Returns True if created or already exists."""
    slug = challenge.get("slug", challenge.get("name", "unknown"))
    try:
        resp = requests.post(
            f"{base_url}/challenges",
            json=challenge,
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        error(f"Failed to create '{slug}': {exc}")
        return False

    if resp.status_code == 409:
        warn(f"Challenge '{slug}' already exists -- skipping creation")
        return True
    if resp.status_code in (200, 201):
        ok(f"Created challenge '{slug}'")
        return True

    error(f"Failed to create '{slug}' (HTTP {resp.status_code}): {resp.text[:200]}")
    return False


def release_challenge(base_url: str, headers: dict, slug: str) -> bool:
    """Release (publish) a challenge by slug."""
    try:
        resp = requests.post(
            f"{base_url}/challenges/{slug}/release",
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as exc:
        error(f"Failed to release '{slug}': {exc}")
        return False

    if resp.status_code in (200, 201, 204):
        ok(f"Released challenge '{slug}'")
        return True
    if resp.status_code == 409:
        warn(f"Challenge '{slug}' already released")
        return True

    error(f"Failed to release '{slug}' (HTTP {resp.status_code}): {resp.text[:200]}")
    return False


def main() -> None:
    print(f"\n{BOLD}{CYAN}=== Siege Range CTF - Challenge Seeder ==={RESET}\n")

    # ── Configuration ────────────────────────────────────────────────────
    base_url = os.getenv("API_URL", "http://localhost:3000/api")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@siege.local")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin123!@#")

    # ── Discover challenge files ─────────────────────────────────────────
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    pattern = os.path.join(project_root, "challenges", "*", "challenge.json")
    challenge_files = sorted(glob.glob(pattern))

    if not challenge_files:
        fatal(f"No challenge.json files found matching {pattern}")

    info(f"Found {BOLD}{len(challenge_files)}{RESET} challenge(s)\n")

    # ── Authenticate ─────────────────────────────────────────────────────
    token = authenticate(base_url, admin_email, admin_password)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # ── Seed each challenge ──────────────────────────────────────────────
    created = 0
    released = 0
    failed = 0
    total = len(challenge_files)

    for idx, filepath in enumerate(challenge_files, 1):
        challenge_dir = os.path.basename(os.path.dirname(filepath))
        print(f"\n{BOLD}[{idx}/{total}]{RESET} Processing {CYAN}{challenge_dir}{RESET}")

        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                challenge = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            error(f"Cannot read {filepath}: {exc}")
            failed += 1
            continue

        # Ensure slug is set
        if "slug" not in challenge:
            challenge["slug"] = challenge_dir

        if create_challenge(base_url, headers, challenge):
            created += 1
            slug = challenge.get("slug", challenge_dir)
            if release_challenge(base_url, headers, slug):
                released += 1
        else:
            failed += 1

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{BOLD}{CYAN}=== Seeding Complete ==={RESET}")
    print(f"  {GREEN}Created/Exists:{RESET} {created}/{total}")
    print(f"  {GREEN}Released:{RESET}       {released}/{total}")
    if failed:
        print(f"  {RED}Failed:{RESET}         {failed}/{total}")
    print()

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
