# Codex CLI installation — macOS + Windows 11

Companion to `demo_venv_setup.md`. Install once per machine; then use
Codex inside any project's venv.

## Prerequisites

- Node.js 22+ recommended. 18 is the documented floor, but recent Codex
  releases assume 22.
- Verify: `node --version` should print `v22.x` or newer.
- An OpenAI account. First `codex` run opens a browser tab for ChatGPT
  sign-in — use the account tied to the course access plan.

## macOS

Two paths. Homebrew is smoother if you already have it; npm is the
universal fallback.

### Homebrew (preferred on macOS)

```bash
brew install --cask codex
codex --version
```

Update: `brew upgrade --cask codex`.

### npm

```bash
npm install -g @openai/codex
codex --version
```

Update: `npm update -g @openai/codex`.

## Windows 11

npm is the recommended native path. No Homebrew equivalent worth using.

```powershell
npm install -g @openai/codex
codex --version
```

Update: `npm update -g @openai/codex`.

**If `codex --version` fails immediately after install:** close and
reopen your terminal. If you're inside VS Code, close *all* VS Code
windows and reopen. The new binary is on disk, but VS Code's integrated
terminal cached the environment at launch and doesn't see the updated
PATH until VS Code restarts. This bites Windows harder than macOS
because Windows caches process env more aggressively, but it can hit
macOS too.

## Gotchas

- **Package name matters.** The correct package is `@openai/codex`
  (scoped). The unscoped `codex` on npm is an unrelated 2012 project
  that installs silently and does nothing useful. Wrong install →
  `codex --version` fails with confusing errors → 20 minutes lost. If
  a tutorial or blog post tells you `npm install -g codex`, they're
  wrong.
- **Node version.** If `codex --version` runs but crashes on first
  actual use with a "Cannot find module" error or similar, your Node
  is probably too old. Upgrade to 22+.
- **`sudo` on macOS.** A bare `npm install -g` may complain about
  permissions if you're on system Node. The fix is a Node version
  manager (`nvm`, `fnm`, `volta`) — do NOT `sudo npm install -g`. It
  works, but it corrupts your global module permissions in a way
  you'll pay for later.
- **PATH after install.** If `codex --version` says "command not
  found" after a clean install and reopening the terminal didn't fix
  it: run `npm prefix -g` to see where npm put the binary. On
  macOS/Linux, add `<that path>/bin` to your shell profile. On
  Windows, that path itself goes on `%PATH%` — typically already
  configured by the Node installer, but managed laptops sometimes
  strip it.
- **Browser sign-in loop.** If the first `codex` run opens a browser
  tab that never completes the sign-in handoff, use the device-code
  flow instead: `codex login --device-auth` prints a URL and a
  one-time code you paste into any browser (including one on a
  different machine).
- **Chrome required for authentication.** If your default browser is Safari, when you select `Sign in with ChatGPT`, to use ChatGPT Edu OAuth instead of an API Key, you will likely fail with the error `No eligible workspaces support Codex CLI`.  If this is the case, change your default browser to Chrome, authenticate with `chatgpt.com` using your USC account, and when prompted select to continue with the logged-in account.  


## Verify

```bash
codex --version   # should print a version number
codex             # in any project directory, starts a session
```

First run triggers sign-in. After that, `codex` reads `AGENTS.md` (if
present) at session start and drops you into an interactive prompt.
