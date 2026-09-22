# Demo venv setup — Linux/macOS + Windows 11

Paste-in boilerplate for CSCI 599 demo READMEs. Replace `demo02.py`
with the actual entry-point filename for the demo at hand, and adjust
the `cd` path to the correct lecture directory.

## Linux / macOS

```bash
cd ../lecture-02
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # optional; skip if no requirements file
python demo02.py
deactivate
```

## Windows 11

One-time per machine (not per project) — allow PowerShell to run
activation scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

Then, per project:

```powershell
cd ..\lecture-02
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1        # PowerShell
# Or from Command Prompt:  .venv\Scripts\activate.bat
# Or from Git Bash:        source .venv/Scripts/activate
pip install -r requirements.txt     # optional; skip if no requirements file
python demo02.py
deactivate
```

## Windows notes

- Windows creates `.venv\Scripts\`, not `.venv/bin/`.
- `python3` isn't registered by the python.org installer; the `py`
  launcher (`py -3`) works regardless of how Python was installed.
- If `Set-ExecutionPolicy` is blocked by group policy on a managed
  laptop, use Git Bash — activation via `source` works without any
  policy change.
- `deactivate` works the same in all three Windows shells.
