# PSA.WF torrent link helper

Python + Playwright helper to search PSA.WF for a movie and save `.torrent` downloads when you click links in its browser. Use only for content you have permission to download.

## Setup (Windows PowerShell)

```powershell
git clone https://github.com/anuroop2271-coder/psa.git
cd psa
py -m pip install -r requirements.txt
py -m playwright install chromium
```

## Run

```powershell
py psa.py "Movie Title 2025"
```

Or run `py psa.py` to enter the title interactively. Add `--output "D:\\Torrents"` to select a destination.

Select a search result number, then click a torrent download link in Chromium. Complete any CAPTCHA or intermediate verification manually. Downloads named `.torrent` are saved to `torrents/`. Press Enter in the terminal to close the browser. Direct magnet links on the selected page are displayed but not automatically launched.

The script does not bypass protection or download movie media. PSA.WF's search/links may change. End-to-end live site downloading has not been verified.

Files: `psa.py`, `requirements.txt`, `.gitignore`.
