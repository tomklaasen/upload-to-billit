# upload-to-billit

Scans a Dropbox folder for files and emails each one as an attachment to Billit's document intake address. Processed files are moved to a done folder in Dropbox. Because it talks to the Dropbox API directly, it can run on any server — no Dropbox client needed. Designed to run as a hourly cron job, monitored via Healthchecks.io.

## Setup

**1. Create and activate the virtual environment:**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**2. Create a Dropbox app:**

- Go to [dropbox.com/developers/apps](https://www.dropbox.com/developers/apps) → *Create app* → *Scoped access* → *Full Dropbox*
- On the *Permissions* tab, enable `files.metadata.read`, `files.content.read` and `files.content.write`, then click *Submit*
- Note the *App key* and *App secret* from the *Settings* tab
- Get a refresh token (one-time):

```bash
.venv/bin/python3 get_dropbox_token.py <app_key> <app_secret>
```

**3. Create your config file:**

```bash
cp config.toml.example config.toml
```

Then fill in `config.toml` with your values:

- `directories.source` — Dropbox folder to scan for files (e.g. `/Invoices/To Billit`)
- `directories.done` — Dropbox folder to move processed files to
- `dropbox.app_key` / `dropbox.app_secret` / `dropbox.refresh_token` — from the step above
- `email.username` / `email.from_address` — your Gmail address
- `email.password` — a Gmail App Password (generate one at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), requires 2FA)
- `email.to_address` — Billit's document intake email address
- `healthchecks.url` — your Healthchecks.io check URL

## Usage

```bash
.venv/bin/python3 upload_to_billit.py
```

## Cron job

Runs every hour at :23. Add to crontab with `crontab -e`:

```
23 * * * * /path/to/upload-to-billit/.venv/bin/python3 /path/to/upload-to-billit/upload_to_billit.py >> /path/to/upload-to-billit/upload.log 2>&1
```

Set the Healthchecks.io check period to 1 hour with a few minutes grace period.
