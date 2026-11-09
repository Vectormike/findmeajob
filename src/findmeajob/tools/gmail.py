import asyncio
import base64
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]
BODY_LIMIT = 8000


def authorize(credentials_file: Path, token_file: Path) -> None:
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    credentials = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json())


def _header(headers: list[dict[str, str]], name: str) -> str:
    return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")


def _body(payload: dict[str, Any]) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
    for part in payload.get("parts", []):
        text = _body(part)
        if text:
            return text
    return ""


class Gmail:
    def __init__(self, token_file: Path) -> None:
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if not credentials.valid and credentials.refresh_token:
            credentials.refresh(Request())
            token_file.write_text(credentials.to_json())
        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def _read(self, after_epoch: int) -> list[dict[str, Any]]:
        users = self._service.users()
        listed = users.messages().list(userId="me", q=f"after:{after_epoch} -from:me", maxResults=100).execute()
        messages = []
        for ref in listed.get("messages", []):
            raw = users.messages().get(userId="me", id=ref["id"], format="full").execute()
            headers = raw["payload"]["headers"]
            messages.append(
                {
                    "id": raw["id"],
                    "thread_id": raw["threadId"],
                    "from": _header(headers, "From"),
                    "from_email": parseaddr(_header(headers, "From"))[1].lower(),
                    "to": _header(headers, "To"),
                    "subject": _header(headers, "Subject"),
                    "date": _header(headers, "Date"),
                    "message_id": _header(headers, "Message-ID"),
                    "internal_ms": int(raw["internalDate"]),
                    "body": (_body(raw["payload"]) or raw.get("snippet", ""))[:BODY_LIMIT],
                }
            )
        return messages

    def _send(self, to: str, subject: str, body: str, thread_id: str, in_reply_to: str) -> str:
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent = self._service.users().messages().send(userId="me", body={"raw": raw, "threadId": thread_id}).execute()
        return sent["id"]

    async def read_mail(self, after_epoch: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._read, after_epoch)

    async def healthcheck(self) -> str:
        profile = await asyncio.to_thread(self._service.users().getProfile(userId="me").execute)
        return profile.get("emailAddress", "connected")

    async def send_mail(self, to: str, subject: str, body: str, thread_id: str, in_reply_to: str) -> str:
        return await asyncio.to_thread(self._send, to, subject, body, thread_id, in_reply_to)
