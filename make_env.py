"""First-run helper used by run.sh / run.bat: creates .env from .env.example and gives the back office a random key.

The shipped demo key ("accel-demo") is never left in place: a server with a published key is not safe to share.
"""
import re
import secrets
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent
env, example = root / ".env", root / ".env.example"
if not env.exists():
    shutil.copy(example, env)
text = env.read_text(encoding="utf-8")
match = re.search(r"^BACKOFFICE_KEY=(.*)$", text, re.M)
if not match or match.group(1).strip() in ("", "accel-demo"):
    key = secrets.token_urlsafe(18)
    if match:
        text = re.sub(r"^BACKOFFICE_KEY=.*$", f"BACKOFFICE_KEY={key}", text, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\nBACKOFFICE_KEY={key}\n"
    env.write_text(text, encoding="utf-8")
    print(f"Back-office key (saved in .env): {key}")
else:
    print("Back-office key: see BACKOFFICE_KEY in .env")
