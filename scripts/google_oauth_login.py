"""One-time Google sign-in so PuzzUp can create Drive files as a real account.

Service accounts have no Drive storage quota, so they cannot create sheets.
This script signs in as a normal Google account and saves a long-lived
refresh token into .env. The token is never printed.

Usage (from the repo root):
    uv run --no-project --with google-auth-oauthlib --with google-api-python-client \
        python scripts/google_oauth_login.py path/to/client_secret.json

Then copy GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET and
GOOGLE_OAUTH_REFRESH_TOKEN from .env into your host's environment settings.
"""
import json
import re
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
PORT = 8090


def set_env_values(env_path: Path, values: dict) -> None:
    text = env_path.read_text() if env_path.exists() else ""
    for key, value in values.items():
        line = f"{key}={value}"
        if re.search(rf"^{key}=.*$", text, flags=re.M):
            text = re.sub(rf"^{key}=.*$", lambda _: line, text, flags=re.M)
        else:
            text = text.rstrip("\n") + ("\n" if text else "") + line + "\n"
    env_path.write_text(text)
    env_path.chmod(0o600)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    client_file = Path(sys.argv[1])
    client = json.loads(client_file.read_text())
    client_info = client.get("installed") or client.get("web")
    if not client_info:
        sys.exit("That file is not an OAuth client JSON (expected an 'installed' key).")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
    creds = flow.run_local_server(
        port=PORT,
        open_browser=False,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message=(
            "\nOpen this link in your browser and sign in with the account "
            "PuzzUp should act as:\n\n{url}\n"
        ),
        success_message="Signed in. You can close this tab and go back to the terminal.",
    )
    if not creds.refresh_token:
        sys.exit("Google did not return a refresh token. Run the script again.")

    email = (
        build("drive", "v3", credentials=creds)
        .about()
        .get(fields="user(emailAddress)")
        .execute()["user"]["emailAddress"]
    )

    env_path = Path(__file__).resolve().parent.parent / ".env"
    set_env_values(
        env_path,
        {
            "GOOGLE_OAUTH_CLIENT_ID": client_info["client_id"],
            "GOOGLE_OAUTH_CLIENT_SECRET": client_info["client_secret"],
            "GOOGLE_OAUTH_REFRESH_TOKEN": creds.refresh_token,
        },
    )
    print(f"\nSigned in as {email}. Saved the token to {env_path} (not printed).")


if __name__ == "__main__":
    main()
