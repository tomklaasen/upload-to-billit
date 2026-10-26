#!/usr/bin/env python3
"""
One-time helper to obtain a Dropbox refresh token for config.toml.
Usage: get_dropbox_token.py <app_key> <app_secret>
"""

import sys

from dropbox import DropboxOAuth2FlowNoRedirect


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <app_key> <app_secret>", file=sys.stderr)
        sys.exit(1)

    flow = DropboxOAuth2FlowNoRedirect(
        sys.argv[1],
        consumer_secret=sys.argv[2],
        token_access_type="offline",
    )
    print(f"1. Open this URL and click 'Allow':\n   {flow.start()}")
    code = input("2. Paste the authorization code here: ").strip()
    result = flow.finish(code)
    print(f"\nrefresh_token = \"{result.refresh_token}\"")


if __name__ == "__main__":
    main()
