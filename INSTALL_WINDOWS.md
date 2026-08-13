<div align="center">

# 🖥️ Install &amp; Run Guide

### Ireland Health Evidence — for everyone, not just programmers

**School of Public Health · University College Cork**

<br>

`Windows 10 / 11` · `macOS` · **no admin rights needed** · about **20 minutes**, once

<br>

> **You do not need to know how to code to follow this guide.**
> Every command is written out in full. Copy it, paste it, press Enter.
> Nothing here installs anything outside your own user folder.

</div>

---

## 📖 Contents

| | Section | Time |
|---|---|---|
| **①** | [What you are about to install](#-what-you-are-about-to-install) | 1 min read |
| **②** | [First: do you have admin rights?](#-first-do-you-have-admin-rights) | 1 min |
| **③** | [The shopping list](#-the-shopping-list) | 1 min read |
| **④** | [**Windows — full step-by-step**](#-windows--full-step-by-step) | ~20 min |
| **⑤** | [**Mac — full step-by-step**](#-mac--full-step-by-step) | ~20 min |
| **⑥** | [Using it every day after that](#-using-it-every-day-after-that) | 30 sec |
| **⑦** | [If something goes wrong](#-if-something-goes-wrong) | — |
| **⑧** | [Removing everything again](#-removing-everything-again) | 2 min |
| **⑨** | [Plain-English glossary](#-plain-english-glossary) | — |

---

## ① What you are about to install

This project is a **dashboard** — a web page with charts of Global Burden of
Disease indicators for Ireland. It runs **entirely on your own computer**. No
data leaves your machine, and you do not need an internet connection to use it
once it is set up.

When you finish this guide, you will type one command, then open your web
browser at **`http://127.0.0.1:8000`** and see the dashboard.

<div align="center">

```
   Your computer                                    Your browser
   ┌───────────────────────┐                    ┌──────────────────┐
   │  the project files    │  ──────────────▶   │   the dashboard  │
   │  + a small program    │   127.0.0.1:8000   │   with charts    │
   └───────────────────────┘                    └──────────────────┘
```

</div>

> [!NOTE]
> `127.0.0.1` always means **"this computer"**. That address is not on the
> internet — only you can reach it. Nobody else can see your dashboard.

---

## ② First: do you have admin rights?

This changes **nothing** about whether you can run the project — it only
changes which optional extras are available to you. **The main path in this
guide works either way.**

<table>
<tr><td width="50%" valign="top">

### 🔎 How to check — Windows

1. Press the **Windows key**
2. Type `Your info` and press **Enter**
3. Look under your name

If it says **"Administrator"** you have admin rights.
If it says **"Standard User"**, or says nothing, you do not.

</td><td width="50%" valign="top">

### 🔎 How to check — Mac

1. Click the **&#63743; Apple menu** → **System Settings**
2. Click **Users &amp; Groups**
3. Look under your name

If it says **"Admin"** you have admin rights.
If it says **"Standard"**, you do not.

</td></tr>
</table>

> [!TIP]
> **No admin rights? Good news — keep reading.** This guide deliberately uses
> a tool called **pyenv**, which installs Python *inside your own user folder*
> (`C:\Users\YourName\.pyenv`). Windows never asks for an administrator
> password for that. This is the recommended route **even if you are an
> admin**, because it keeps this project's Python separate from anything else
> on the machine.

---

## ③ The shopping list

<div align="center">

### Everyone installs these — **none require admin rights**

</div>

| | What | Why you need it | Admin? |
|:--:|---|---|:--:|
| 1️⃣ | **Windows PowerShell** (Win) / **Terminal** (Mac) | The window where you type commands. **Already on your computer** — nothing to install. | ✅ n/a |
| 2️⃣ | **pyenv** | Installs and manages Python for you, in your own folder. | ✅ No |
| 3️⃣ | **Python 3.12** | The language this project is written in. Installed *by* pyenv in step 2. | ✅ No |
| 4️⃣ | **The project files** | Downloaded as a ZIP from GitHub. | ✅ No |

<div align="center">

### Optional extras

</div>

| What | Worth it? | Admin? |
|---|---|:--:|
| **Visual Studio Code** — a nicer editor for looking at the files | Nice to have. Choose the **"User Installer"** download and it needs no admin. | ✅ No |
| **Git** — for pulling future updates instead of re-downloading the ZIP | Only if you will update often. | ✅ No (user install) |
| **Docker Desktop** — an alternative, fully-automatic way to run the project | **Skip it.** It needs admin rights *and* usually a reboot. The pyenv route below is simpler. | ⛔ **Yes** |

> [!IMPORTANT]
> **Why Python 3.12 and not the newest version?**
> This project is tested against Python **3.12** and pins exact versions of its
> components. Newer Pythons (3.13, 3.14…) will fail to install `pandas 2.2.2`
> with a long, alarming red error. Please use **3.12.10** exactly as written
> below. It is not out of date — it is the tested version.

---

<div align="center">

# 🪟 Windows — full step-by-step

**Do steps 1 → 7 once. After that you only ever need [step 7](#step-7--start-the-dashboard-).**

</div>

---

### Step 1 — Open PowerShell 🖱️

1. Press the **Windows key**
2. Type `powershell`
3. Click **Windows PowerShell** — **left-click normally**

> [!WARNING]
> **Do _not_ choose "Run as administrator".** This guide is written for a
> normal, everyday window. Running as administrator will install things in the
> wrong place.

A blue or black window opens with a blinking cursor. **This window is where
every command below goes.** Keep it open for the whole guide.

<details>
<summary><b>💡 How to copy and paste into this window</b></summary>

<br>

- **To copy from this page:** highlight the command and press `Ctrl + C`
  (or click the small 📋 copy icon in the top-right corner of each grey box on GitHub)
- **To paste into PowerShell:** click once inside the black window, then press
  **`Ctrl + V`** or simply **right-click**
- Then press **Enter** to run it

**Paste one command at a time**, wait for it to finish, then do the next.

</details>

---

### Step 2 — Give yourself permission to run the installer 🔓

Paste this and press Enter:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

When it asks **"Do you want to change the execution policy?"** type **`Y`**
and press Enter.

> [!NOTE]
> This is a standard, safe setting that applies **only to your own user
> account** (`-Scope CurrentUser`) — which is exactly why it does not ask for
> an administrator password. Without it, Windows blocks the pyenv installer.

---

### Step 3 — Install pyenv 🧰

Paste this **entire block** in one go and press Enter:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"
```

It downloads and installs pyenv into `C:\Users\YourName\.pyenv`.
It should finish in under a minute with a line saying **pyenv-win is
successfully installed**.

> [!CAUTION]
> ### 🔁 Now close the PowerShell window completely — and open a new one
>
> This step is **not optional and is the most commonly skipped one.** Windows
> only notices the new pyenv installation in windows opened *after* it was
> installed. Close it, then reopen PowerShell exactly as in [Step 1](#step-1--open-powershell-).

**In the new window, check it worked:**

```powershell
pyenv --version
```

✅ You should see something like `pyenv 3.1.1`.
❌ If you see *"not recognized"*, see [If something goes wrong](#-if-something-goes-wrong).

---

### Step 4 — Install Python 3.12 🐍

```powershell
pyenv install 3.12.10
```

⏳ **This one takes 2–5 minutes** and looks like it has frozen. It has not —
it is downloading and installing Python. Leave it alone until you get your
cursor back.

Then make it your default Python:

```powershell
pyenv global 3.12.10
```

**Check it worked:**

```powershell
python --version
```

✅ You should see `Python 3.12.10`.

<details>
<summary>❌ <b>Instead you saw a Microsoft Store page, or "Python was not found"?</b> — click here</summary>

<br>

Windows ships with a placeholder that hijacks the word `python`. Turn it off:

1. Press the **Windows key**, type `Manage app execution aliases`, press Enter
2. Find **`python.exe`** and **`python3.exe`** — labelled *App Installer*
3. Switch **both to Off**
4. Close PowerShell, open a new one, and run `python --version` again

This needs no admin rights.

</details>

---

### Step 5 — Download the project 📦

1. Go to **<https://github.com/abdulrazakucc/ucc_gbd_pipeline>**
2. Click the green **`< > Code`** button
3. Click **Download ZIP**
4. Open your **Downloads** folder, **right-click** the ZIP → **Extract All…**
5. Change the destination to your **Documents** folder and click **Extract**

You should now have a folder called **`ucc_gbd_pipeline-main`** in your
Documents.

> [!NOTE]
> The `-main` on the end of the folder name is normal — GitHub adds it. Leave
> it exactly as it is, because the commands below expect that name.

Now tell PowerShell to work inside that folder:

```powershell
cd "$HOME\Documents\ucc_gbd_pipeline-main"
```

**Check it worked:**

```powershell
dir
```

✅ You should see `Makefile`, `README.md`, `requirements.txt`, and folders
called `app`, `data`, `etl`, `static`, `tests`.

<details>
<summary>💡 <b>Alternative: use Git instead of the ZIP</b> (only if you'll update often)</summary>

<br>

Download the **standalone / portable** Git for Windows from
<https://git-scm.com/download/win> — the *portable* build unzips into your own
folder and needs no admin rights. Then:

```powershell
cd "$HOME\Documents"
git clone https://github.com/abdulrazakucc/ucc_gbd_pipeline.git
cd ucc_gbd_pipeline
```

Note the folder is then called `ucc_gbd_pipeline` (**without** `-main`), so
adjust the `cd` commands later in this guide to match.

To get updates later: `git pull`.

</details>

---

### Step 6 — Set up the project 🔧

Four commands. Run them **in order**, one at a time, waiting for each to finish.

**6a — Lock this folder to Python 3.12:**

```powershell
pyenv local 3.12.10
```

**6b — Create a private, self-contained workspace for the project:**

```powershell
python -m venv .venv
```

**6c — Switch into that workspace:**

```powershell
.\.venv\Scripts\Activate.ps1
```

✅ Your prompt now starts with **`(.venv)`** — like this:

```
(.venv) PS C:\Users\YourName\Documents\ucc_gbd_pipeline-main>
```

> [!IMPORTANT]
> That **`(.venv)`** at the start of the line is your "engine is on" light.
> If you ever open a fresh PowerShell window, it will be gone, and you must
> run commands **6c** again before anything else works. See
> [Using it every day](#-using-it-every-day-after-that).

**6d — Install the project's components:**

```powershell
pip install -r requirements.txt
```

⏳ **Takes 1–3 minutes.** Lots of text scrolls past — that is normal and
correct. You want the last line to say **`Successfully installed …`**.

<details>
<summary>⚠️ <b>Seeing yellow warnings?</b> — click here</summary>

<br>

Yellow text is a *warning*, not an error, and can be ignored — including
`WARNING: You are using pip version …`. Only **red** text ending in
`ERROR:` means something actually failed. If you get one, see
[If something goes wrong](#-if-something-goes-wrong).

</details>

**6e — Build the database from the bundled data:**

```powershell
python etl\load_seed.py
```

✅ Finishes in about a second and prints `Loaded 68 trend rows.`,
`Loaded 19 ranked rows.` and the location of the database it just built
(`data\gbd.db`).

> [!IMPORTANT]
> **Do not skip this step.** The database is *not* included in the download —
> it is built on your machine from the CSV files in `data\`. Without it the
> dashboard will start but the charts will be empty.

---

### Step 7 — Start the dashboard 🚀

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

You will see something like:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

<div align="center">

### 🎉 That's it. Now open your web browser and go to:

# [http://127.0.0.1:8000](http://127.0.0.1:8000)

</div>

> [!WARNING]
> ### 🪟 Leave the PowerShell window open
>
> That window **is** the dashboard. It will sit there looking like it has
> frozen — that is exactly right; it is waiting to serve pages. Minimise it if
> it is in your way, but **do not close it** while you are using the
> dashboard.

**To stop the dashboard:** click the PowerShell window and press **`Ctrl + C`**.

---

<div align="center">

# 🍎 Mac — full step-by-step

</div>

Same idea, different commands. Open **Terminal** first: press
**`Cmd + Space`**, type `Terminal`, press **Enter**.

---

### Step 1 — Install Apple's developer tools

```bash
xcode-select --install
```

A dialog appears — click **Install** and wait (5–10 minutes).

> [!NOTE]
> **If it asks for an administrator password you do not have:** stop here and
> ask your IT support for *"Xcode Command Line Tools"* — it is a standard,
> one-off request. Everything after this step needs no admin rights.
>
> If it says *"command line tools are already installed"*, you are fine —
> carry on.

---

### Step 2 — Install pyenv

```bash
curl -fsSL https://pyenv.run | bash
```

This installs into `~/.pyenv`, inside your own home folder — no admin needed.

Then tell your Terminal where to find it (paste all four lines together):

```bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init - zsh)"' >> ~/.zshrc
exec zsh
```

**Check it worked:**

```bash
pyenv --version
```

---

### Step 3 — Install Python 3.12

```bash
pyenv install 3.12.10
pyenv global 3.12.10
python --version
```

⏳ The first command takes **5–10 minutes** on a Mac — it builds Python from
source. It is not stuck.

✅ `python --version` should print `Python 3.12.10`.

---

### Step 4 — Download the project

Either download and unzip the ZIP from
<https://github.com/abdulrazakucc/ucc_gbd_pipeline> exactly as in the
[Windows step 5](#step-5--download-the-project-), or, since Macs already have
Git:

```bash
cd ~/Documents
git clone https://github.com/abdulrazakucc/ucc_gbd_pipeline.git
cd ucc_gbd_pipeline
```

---

### Step 5 — Set up and run

Macs come with a tool called `make`, which does the whole setup for you.
From inside the project folder:

```bash
pyenv local 3.12.10
make dev
```

**`make dev` does everything**: creates the workspace, installs the
components, builds the database, starts the dashboard, and opens your browser
at **<http://127.0.0.1:8000>**. It takes about a minute the first time.

When you are finished:

```bash
make stop
```

> [!TIP]
> **`make doctor`** checks your machine has everything it needs and tells you
> exactly what is missing. Run it first if anything misbehaves. The
> [README](README.md) lists all the other `make` commands.
>
> *These `make` shortcuts do **not** work on Windows — which is why the
> Windows steps above are spelled out in full.*

<details>
<summary><b>Prefer to run it by hand, without <code>make</code>?</b></summary>

<br>

Exactly the same steps the Windows guide uses:

```bash
pyenv local 3.12.10
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python etl/load_seed.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open **<http://127.0.0.1:8000>** and stop it with **`Ctrl + C`**.

</details>

---

## 🔁 Using it every day after that

You never repeat the installation. From now on it is **three commands**:

<table>
<tr><th width="50%">🪟 Windows</th><th width="50%">🍎 Mac</th></tr>
<tr><td valign="top">

```powershell
cd "$HOME\Documents\ucc_gbd_pipeline-main"
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --port 8000
```

</td><td valign="top">

```bash
cd ~/Documents/ucc_gbd_pipeline
source .venv/bin/activate
python -m uvicorn app.main:app --port 8000
```

</td></tr>
</table>

Then open **<http://127.0.0.1:8000>**, and press **`Ctrl + C`** in the window
when you are finished.

<details>
<summary>💡 <b>Make it a one-click shortcut on Windows</b></summary>

<br>

1. Open **Notepad**
2. Paste these two lines:

   ```
   cd /d "%USERPROFILE%\Documents\ucc_gbd_pipeline-main"
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```

3. **File → Save As**, set *Save as type* to **All Files**, and save it to your
   **Desktop** as **`Start Dashboard.bat`**

Double-clicking that file now starts the dashboard. Close the black window to
stop it. No admin rights required.

</details>

---

## 🆘 If something goes wrong

> **Read the *last* few lines of the error, not the first.** The useful
> sentence is almost always at the very bottom.

<br>

<details>
<summary><b>❌ "running scripts is disabled on this system"</b></summary>

<br>

You skipped [Step 2](#step-2--give-yourself-permission-to-run-the-installer-).
Run this, answer `Y`, then try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

</details>

<details>
<summary><b>❌ "pyenv is not recognized as the name of a cmdlet"</b></summary>

<br>

Almost always because the PowerShell window was opened *before* pyenv was
installed. **Close every PowerShell window, open a brand new one**, and try
again.

Still failing? Check pyenv actually landed by running:

```powershell
dir "$HOME\.pyenv"
```

If that folder does not exist, re-run [Step 3](#step-3--install-pyenv-).
If it does exist, repair the path with:

```powershell
[System.Environment]::SetEnvironmentVariable('PATH', "$HOME\.pyenv\pyenv-win\bin;$HOME\.pyenv\pyenv-win\shims;" + [System.Environment]::GetEnvironmentVariable('PATH','User'), 'User')
```

then close and reopen PowerShell.

</details>

<details>
<summary><b>❌ A Microsoft Store window opens when you type <code>python</code></b></summary>

<br>

Press the **Windows key**, type `Manage app execution aliases`, press Enter,
and switch **`python.exe`** and **`python3.exe`** to **Off**. Close PowerShell
and open a new one.

</details>

<details>
<summary><b>❌ Red errors mentioning <code>pandas</code>, <code>meson</code>, <code>wheel</code> or "building from source"</b></summary>

<br>

You are on the wrong Python version. Check it:

```powershell
python --version
```

If it does **not** say `3.12.10`, fix it from inside the project folder:

```powershell
pyenv install 3.12.10
pyenv local 3.12.10
```

Then delete the half-built workspace and redo [Step 6](#step-6--set-up-the-project-):

```powershell
Remove-Item -Recurse -Force .venv
```

</details>

<details>
<summary><b>❌ "Address already in use" / "error while attempting to bind on address"</b></summary>

<br>

The dashboard is **already running** in another window. Either find that
window and use it, or run this one on a different door number:

```powershell
python -m uvicorn app.main:app --port 8010
```

…then visit **`http://127.0.0.1:8010`** instead.

</details>

<details>
<summary><b>❌ <code>pip install</code> fails with SSL, certificate, proxy or timeout errors</b></summary>

<br>

Common on university and hospital networks that inspect traffic. Try:

```powershell
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

If that still fails, try again from a home or mobile-hotspot connection, or
ask IT to allow **`pypi.org`** and **`files.pythonhosted.org`**.

</details>

<details>
<summary><b>❌ Windows SmartScreen or antivirus blocks the download</b></summary>

<br>

pyenv and Python are open-source and unsigned by Microsoft, so SmartScreen
sometimes warns. On the warning dialog click **More info → Run anyway**, and
confirm the download address begins with `https://raw.githubusercontent.com/pyenv-win/`
or `https://www.python.org/`.

If your organisation blocks it outright, that is a policy decision — send your
IT support this guide and ask for pyenv to be permitted, or ask for Python
3.12 to be installed for you. Once Python 3.12 exists on the machine, you can
skip straight to [Step 5](#step-5--download-the-project-).

</details>

<details>
<summary><b>❌ The browser says "can't reach this page" / "connection refused"</b></summary>

<br>

Check, in order:

1. Is the PowerShell/Terminal window **still open**, showing
   `Application startup complete`? If you closed it, the dashboard stopped —
   restart it.
2. Did you type the address exactly: **`http://127.0.0.1:8000`** — with
   `http`, **not** `https`?
3. Did you use the same port number the window printed?

</details>

<details>
<summary><b>❌ "No such file or directory" / "cannot find path"</b></summary>

<br>

You are in the wrong folder. Check where you are, then go back:

```powershell
Get-Location
cd "$HOME\Documents\ucc_gbd_pipeline-main"
dir
```

`dir` must list `requirements.txt`. If it lists another `ucc_gbd_pipeline-main`
folder instead, you are one level too high — `cd` into it.

</details>

<details>
<summary><b>❌ The charts are blank or the page looks broken</b></summary>

<br>

The database was probably never built — it does not come with the download.
Stop the dashboard with `Ctrl + C` and run:

```powershell
python etl\load_seed.py
```

Then start it again. (On Mac: `python etl/load_seed.py`, or `make reseed`.)

</details>

<br>

> [!TIP]
> **Still stuck?** Take a **screenshot of the whole window** — including the
> commands above the error — and send it on. The text just before the error is
> usually what identifies the problem.

---

## 🧹 Removing everything again

Nothing here touches system folders or the Windows registry, so removal is
just deleting folders:

| What | Windows | Mac |
|---|---|---|
| The project | Delete `Documents\ucc_gbd_pipeline-main` | Delete `~/Documents/ucc_gbd_pipeline` |
| Python + pyenv | Delete `C:\Users\YourName\.pyenv` | Delete `~/.pyenv` |

That is the whole footprint. No admin rights needed to remove it either.

---

## 📚 Plain-English glossary

| Term | What it actually means |
|---|---|
| **PowerShell / Terminal** | A window where you type instructions instead of clicking buttons. |
| **Command** | One line of text you paste in and press Enter on. |
| **Python** | The programming language this project is written in. |
| **pyenv** | A tool that installs Python *for you*, in your own folder, so it needs no admin rights and cannot clash with other software. |
| **pip** | Python's downloader for add-on components. |
| **Virtual environment (`.venv`)** | A private box holding just this project's components, so it can never interfere with anything else on your computer. Safe to delete and rebuild. |
| **`cd`** | "Change directory" — move the window into a folder. |
| **Server / uvicorn** | The small program that hands the dashboard to your browser. It runs only while its window is open. |
| **Port `8000`** | A numbered door on your own computer. `127.0.0.1:8000` = "door 8000 on this machine". |
| **`Ctrl + C`** | The universal "stop this" in a terminal window. |
| **ETL** | *Extract, Transform, Load* — the step that reads the data files and builds the dashboard's database. |

---

<div align="center">

<br>

**Ireland Health Evidence** · School of Public Health, University College Cork

Principal Investigator — Dr. Zubair Kabir

For the technical documentation, see [README.md](README.md)

<br>

*Not for clinical or diagnostic use.*

</div>
