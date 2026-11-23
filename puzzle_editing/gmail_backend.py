"""Django email backend that sends through the Gmail API over HTTPS.

Hosts like Render's free plan block outbound SMTP ports, so PuzzUp sends mail
as the Google account it already signs in with (settings.DRIVE_SETTINGS["oauth"]).
That sign-in needs the gmail.send scope; see scripts/google_oauth_login.py.
"""
import base64
import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from google.oauth2 import credentials as user_credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class EmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._service = None

    def _get_service(self):
        if self._service is None:
            oauth = settings.DRIVE_SETTINGS.get("oauth")
            if not oauth:
                raise RuntimeError(
                    "Gmail email backend needs GOOGLE_OAUTH_* settings to be set"
                )
            creds = user_credentials.Credentials(
                token=None,
                refresh_token=oauth["refresh_token"],
                client_id=oauth["client_id"],
                client_secret=oauth["client_secret"],
                token_uri="https://oauth2.googleapis.com/token",
            )
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                raw = base64.urlsafe_b64encode(message.message().as_bytes()).decode()
                self._get_service().users().messages().send(
                    userId="me", body={"raw": raw}
                ).execute()
                sent += 1
            except Exception:  # noqa: BLE001
                if not self.fail_silently:
                    raise
                logger.exception("Gmail API send failed: %r", message.subject)
        return sent
