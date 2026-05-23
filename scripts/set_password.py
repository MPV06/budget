"""One-time CLI: hash a password and print where to put the hash.

Usage:
    python -m scripts.set_password

Reads the password securely (not echoed). Confirms it. Prints the bcrypt
hash and instructions for storing it in:
  - .env (local dev)
  - .streamlit/secrets.toml (local Streamlit run)
  - Streamlit Cloud dashboard (production deploy)
"""
import getpass
import sys

from services.auth import hash_password, HASH_KEY


def main() -> int:
    print()
    print("=" * 64)
    print(" Budget App — Set Password")
    print("=" * 64)
    print()

    while True:
        password = getpass.getpass("New password (>= 12 chars recommended): ")
        if not password:
            print("✖ Empty password — aborted.")
            return 1
        if len(password) < 8:
            print(f"✖ Password too short ({len(password)} chars). Minimum 8.")
            continue
        if len(password) < 12:
            confirm = input("⚠ Under 12 chars is weak. Continue anyway? [y/N] ")
            if confirm.lower() != "y":
                continue
        confirm_pw = getpass.getpass("Confirm password: ")
        if password != confirm_pw:
            print("✖ Passwords don't match. Try again.\n")
            continue
        break

    h = hash_password(password)

    print()
    print("=" * 64)
    print(" SUCCESS — paste the hash into ONE of these locations:")
    print("=" * 64)
    print()
    print("LOCAL DEV (.env file in project root):")
    print(f"  {HASH_KEY}={h}")
    print()
    print("STREAMLIT (local secrets, .streamlit/secrets.toml):")
    print(f'  {HASH_KEY} = "{h}"')
    print()
    print("STREAMLIT COMMUNITY CLOUD (App Settings → Secrets):")
    print(f'  {HASH_KEY} = "{h}"')
    print()
    print("After setting, restart the app and sign in.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
