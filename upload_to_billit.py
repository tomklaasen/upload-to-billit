#!/usr/bin/env python3
"""
Scans a source directory for files and emails each one as an attachment
to Billit's document intake address, then moves it to the done directory.
Integrates with Healthchecks.io for cron monitoring.
"""

import shutil
import smtplib
import sys
import tomllib
from email.message import EmailMessage
from pathlib import Path

import requests


def load_config(config_path: Path) -> dict:
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def ping(url: str, suffix: str = "") -> None:
    """Fire-and-forget ping to Healthchecks.io. Never raises."""
    try:
        requests.get(f"{url.rstrip('/')}{suffix}", timeout=10)
    except Exception:
        pass


def send_file(file_path: Path, cfg: dict) -> None:
    email_cfg = cfg["email"]

    msg = EmailMessage()
    msg["From"] = email_cfg["from_address"]
    msg["To"] = email_cfg["to_address"]
    msg["Subject"] = email_cfg["subject"]
    msg.set_content(f"Document in bijlage: {file_path.name}")

    mime_type, mime_subtype = guess_mime_type(file_path)
    with open(file_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype=mime_type,
            subtype=mime_subtype,
            filename=file_path.name,
        )

    with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"]) as smtp:
        smtp.starttls()
        smtp.login(email_cfg["username"], email_cfg["password"])
        smtp.send_message(msg)


def guess_mime_type(file_path: Path) -> tuple[str, str]:
    import mimetypes
    mime, _ = mimetypes.guess_type(file_path)
    if mime and "/" in mime:
        return tuple(mime.split("/", 1))
    return "application", "octet-stream"


def main() -> None:
    config_path = Path(__file__).parent / "config.toml"
    cfg = load_config(config_path)

    hc_url = cfg["healthchecks"]["url"]
    ping(hc_url, "/start")

    source_dir = Path(cfg["directories"]["source"])
    done_dir = Path(cfg["directories"]["done"])

    if not source_dir.exists():
        print(f"Source directory does not exist: {source_dir}", file=sys.stderr)
        ping(hc_url, "/fail")
        sys.exit(1)

    done_dir.mkdir(parents=True, exist_ok=True)

    files = [p for p in source_dir.iterdir() if p.is_file() and not p.name.startswith(".")]

    if not files:
        print("No files found, nothing to do.")
        ping(hc_url)
        sys.exit(0)

    failed = []
    for file_path in files:
        try:
            print(f"Sending {file_path.name}...")
            send_file(file_path, cfg)
            dest = done_dir / file_path.name
            # Avoid overwriting if a file with the same name already exists
            if dest.exists():
                dest = done_dir / f"{file_path.stem}_{file_path.stat().st_mtime_ns}{file_path.suffix}"
            shutil.move(str(file_path), dest)
            print(f"  Moved to {dest}")
        except Exception as e:
            print(f"  ERROR for {file_path.name}: {e}", file=sys.stderr)
            failed.append(file_path.name)

    if failed:
        print(f"Failed files: {', '.join(failed)}", file=sys.stderr)
        ping(hc_url, "/fail")
        sys.exit(1)

    ping(hc_url)
    print("Done.")


if __name__ == "__main__":
    main()
