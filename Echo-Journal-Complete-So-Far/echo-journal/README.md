# Echo Journal — Milestone 2

A private journaling website. You write entries; only you can read them.

> Echo Journal is a tool for self-reflection. It does not diagnose or treat anything and it is not a substitute for professional care.

## Where the project is (Milestone 2 of 6)

**Works now:** create an account, sign in and out, write / read / edit / delete entries, search, download everything (JSON or Markdown), delete your account and all your data.

**Milestone 2 added:** optional on-demand sentiment and emotion estimates for an entry, saved as metadata. The base website still runs without AI packages.

**Still not built yet (so please don't expect it):**

| Milestone | What it adds |
|---|---|
| 3 | Topics, recurring themes, similar past entries, personal insights, dashboard |
| 4 | Admin dashboard (totals only, never entry text) |
| 5 | GitHub repository |
| 6 | Hardening, hosting, a persistent online database, automatic deploys |

## Run it on Windows

Use **Command Prompt** (not PowerShell). Each step says what you should see.

1. **Install Python 3.13 (64-bit).** Open <https://www.python.org/downloads/release/python-31316/>, scroll to *Files* and download **Windows installer (64-bit)**. Don't use the big yellow button on the main page: it offers the newest Python, which some packages don't support yet. In the installer, tick **Add python.exe to PATH**, then click **Install Now**.
2. **Unzip this project.** Right-click the ZIP, then *Extract All*.
3. **Open Command Prompt in the project folder.** In File Explorer, open the `echo-journal` folder, click the address bar, type `cmd` and press Enter.
4. **Check Python:** `python --version` should print `Python 3.13.…`
5. **Create a private environment:** `python -m venv .venv` (prints nothing; a `.venv` folder appears).
6. **Switch it on:** `.venv\Scripts\activate`. The line now starts with `(.venv)`. Do this every time you open a new window.
7. **Install the base packages:** `python -m pip install -r requirements.txt`. It ends with `Successfully installed …`.
8. **Run the tests:** `python -m unittest discover -s tests -t .`. It ends with `OK`.
9. **Create your settings file:** `copy .env.example .env`. Make a secret key with `python -c "import secrets; print(secrets.token_hex(32))"`, copy the long text it prints, run `notepad .env`, replace `change-me` with that text, and save.
10. **Start the site:** `python -m flask --app wsgi run --debug`. You should see `Running on http://127.0.0.1:5000`. Open that address in your browser. Stop the site with `Ctrl+C`.

**macOS / Linux:** the same, except `python3 -m venv .venv`, `source .venv/bin/activate` and `cp .env.example .env`.

### If something goes wrong

| You see | Do this |
|---|---|
| `'python' is not recognized` | Run the installer again and tick *Add python.exe to PATH*, or type `py` instead of `python`. |
| `Python was not found; run without arguments to install from the Microsoft Store` | Type `py` instead of `python`. |
| `No module named flask` | The environment is off (no `(.venv)` at the start of the line) or step 7 was skipped. |
| `Address already in use` | Add `--port 5001` to the start command and open `http://127.0.0.1:5001`. |
| A change to `.env` has no effect | Stop the site (`Ctrl+C`) and start it again. |
| Anything else | Copy the **whole** error message and send it to Claude. |

## What each file does

| File | Job |
|---|---|
| `wsgi.py` | The start button: builds the app. |
| `app/__init__.py` | Builds the website: settings, database, security, pages, error pages. |
| `app/config.py` | Reads settings from `.env` / environment variables. No secrets live in the code. |
| `app/db.py` | The only file that talks to the database (SQLite for now). |
| `app/repository.py` | Every database question. Entry queries always include the owner's id. |
| `app/security.py` | Password hashing, sign-in, CSRF protection, safe redirects, security headers. |
| `app/validation.py` | Checks everything typed into a form. |
| `app/auth.py` | Create account, sign in, sign out. |
| `app/journal.py` | Entries: list, search, write, read, edit, delete, export. |
| `app/account.py` | Account page: download your data or delete your account. |
| `app/pages.py` | Start page, About page, `/healthz` check. |
| `app/schema/sqlite/` | The database tables, as numbered `.sql` files applied in order. |
| `app/templates/`, `app/static/` | The pages, stylesheet and one small script (shows times in your time zone). |
| `tests/` | 64 automated tests. |

## Enable Milestone 2 AI analysis (optional)

First confirm the base website starts normally. Then stop Flask with `Ctrl+C` and install the AI dependencies in your active `.venv`:

```powershell
python -m pip install -r requirements-ai.txt
```

This downloads PyTorch and Transformers and can take a while; PyTorch is a large package. The current AI stack requires a supported Windows/Python version and may not install on Windows 7. If installation fails, keep using the base app and share the full error before changing Python or package versions. Restart Flask after the install.

The base app works without the AI stack. The optional models are downloaded from Hugging Face on the first analysis and then run locally on your computer; this app does not send journal text to a hosted inference API. Model downloads do require an internet connection.

1. Activate your project environment.
2. Install the optional dependencies with `python -m pip install -r requirements-ai.txt`. PyTorch is a large download and needs a supported Python/Windows combination; if installation fails, do not remove the existing base requirements. Check the official PyTorch installation selector for the appropriate wheel.
3. Restart Flask. Open one of your journal entries and click **Analyze sentiment and emotion**. The first run may take a while while model weights download.
4. Later analyses use the locally cached models. You can click **Analyze again** after editing an entry.

Models used: `j-hartmann/emotion-english-distilroberta-base` for emotion labels and `cardiffnlp/twitter-roberta-base-sentiment-latest` for sentiment. These models are English-focused and may misread context, sarcasm, mixed emotions, or unusual writing. Scores are model confidence estimates, not objective measurements. Echo Journal is for self-reflection, not diagnosis or therapy.

Only a short prefix of each entry (up to 4,000 characters) is analyzed to bound compute. The result metadata is stored in the same owner-protected SQLite row. The export format intentionally continues to export journal content, not internal analysis metadata.

## How privacy and security work in this version

- Passwords are stored only as scrypt hashes, never as typed. Wrong-username and wrong-password look identical.
- Sign-in uses a signed, HttpOnly, SameSite cookie. Online it also becomes Secure with HSTS.
- Every form carries a CSRF token; requests without a valid one are refused.
- Every entry query includes `user_id`. Someone else's entry gives a plain "not found" page.
- Entry text is always HTML-escaped. A strict Content-Security-Policy allows only this site's own files, and no page loads anything from other websites.
- Pages are sent with `Cache-Control: no-store`. Entry text is never written to the app's logs (a test checks this).
- Settings come from the environment. In production mode the app refuses to start without a strong `SECRET_KEY`.

## Known limitations (on purpose, for now)

- **No password reset.** There is no email address, so a forgotten password can't be recovered.
- **No rate limiting on sign-in yet.** Added in Milestone 6, before the site goes online.
- **Search words appear in the local server window** (the address of each page is printed, including `?q=…`). That stays on your computer; before going online we switch address logging off.
- **SQLite is one file on one computer.** Fine locally; not suitable for public hosting. Milestone 6 moves to a managed PostgreSQL database.
- Search ignores upper/lower case for English letters only.
- Tested here on Python 3.12 with Flask 3.1. Not yet run on Windows or on a phone.
