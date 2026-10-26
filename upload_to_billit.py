#!/usr/bin/env python3
"""
Scans a Dropbox source folder for files and emails each one as an attachment
to Billit's document intake address, then moves it to the Dropbox done folder.
Integrates with Healthchecks.io for cron monitoring.
"""

import logging
import mimetypes
import posixpath
import smtplib
import sys
import tomllib
from email.message import EmailMessage
from pathlib import Path

import dropbox
import requests
from dropbox.files import FileMetadata

log = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict:
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def ping(url: str, suffix: str = "") -> None:
    """Fire-and-forget ping to Healthchecks.io. Never raises."""
    try:
        requests.get(f"{url.rstrip('/')}{suffix}", timeout=10)
    except Exception:
        pass


def connect_dropbox(cfg: dict) -> dropbox.Dropbox:
    dbx_cfg = cfg["dropbox"]
    return dropbox.Dropbox(
        oauth2_refresh_token=dbx_cfg["refresh_token"],
        app_key=dbx_cfg["app_key"],
        app_secret=dbx_cfg["app_secret"],
    )


def list_files(dbx: dropbox.Dropbox, folder: str) -> list[FileMetadata]:
    result = dbx.files_list_folder(folder)
    entries = list(result.entries)
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        entries.extend(result.entries)
    return [e for e in entries if isinstance(e, FileMetadata) and not e.name.startswith(".")]


def send_file(name: str, content: bytes, cfg: dict) -> None:
    email_cfg = cfg["email"]

    msg = EmailMessage()
    msg["From"] = email_cfg["from_address"]
    msg["To"] = email_cfg["to_address"]
    msg["Subject"] = email_cfg["subject"]
    msg.set_content(f"Document in bijlage: {name}")

    mime_type, mime_subtype = guess_mime_type(name)
    msg.add_attachment(
        content,
        maintype=mime_type,
        subtype=mime_subtype,
        filename=name,
    )

    with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"]) as smtp:
        smtp.starttls()
        smtp.login(email_cfg["username"], email_cfg["password"])
        smtp.send_message(msg)


def guess_mime_type(name: str) -> tuple[str, str]:
    mime, _ = mimetypes.guess_type(name)
    if mime and "/" in mime:
        return tuple(mime.split("/", 1))
    return "application", "octet-stream"


def ensure_folder(dbx: dropbox.Dropbox, folder: str) -> None:
    try:
        dbx.files_create_folder_v2(folder)
    except dropbox.exceptions.ApiError as e:
        # Folder already exists
        if not (e.error.is_path() and e.error.get_path().is_conflict()):
            raise


def main() -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("dropbox").setLevel(logging.WARNING)

    config_path = Path(__file__).parent / "config.toml"
    cfg = load_config(config_path)

    hc_url = cfg["healthchecks"]["url"]
    ping(hc_url, "/start")

    source_dir = cfg["directories"]["source"]
    done_dir = cfg["directories"]["done"]

    try:
        dbx = connect_dropbox(cfg)
        files = list_files(dbx, source_dir)
        ensure_folder(dbx, done_dir)
    except Exception as e:
        log.error(f"Dropbox error: {e}")
        ping(hc_url, "/fail")
        sys.exit(1)

    if not files:
        log.info("No files found, nothing to do.")
        ping(hc_url)
        sys.exit(0)

    failed = []
    for entry in files:
        try:
            log.info(f"Sending {entry.name}...")
            _, response = dbx.files_download(entry.path_lower)
            send_file(entry.name, response.content, cfg)
            # autorename avoids overwriting if a file with the same name already exists
            result = dbx.files_move_v2(
                entry.path_lower,
                posixpath.join(done_dir, entry.name),
                autorename=True,
            )
            log.info(f"  Moved to {result.metadata.path_display}")
        except Exception as e:
            log.error(f"  Failed for {entry.name}: {e}")
            failed.append(entry.name)

    if failed:
        log.error(f"Failed files: {', '.join(failed)}")
        ping(hc_url, "/fail")
        sys.exit(1)

    ping(hc_url)
    log.info("Done.")


if __name__ == "__main__":
    main()
