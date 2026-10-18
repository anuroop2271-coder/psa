#!/usr/bin/env python3
"""Find movie listings on PSA.WF and save torrent files after user-approved clicks.

This helper does not circumvent CAPTCHA, ad gates, or site protection.
Use only for content you have permission to download.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

BASE = "https://psa.wf"
TORRENT_EXT = re.compile(r"\.torrent(?:$|[?#])", re.I)
MOVIE_PATH = re.compile(r"^/(?:movie|movies)/", re.I)
SAFE_NAME = re.compile(r"[^\w.()\[\] -]+", re.UNICODE)


def filename(name: str) -> str:
    candidate = SAFE_NAME.sub("_", name).strip(" ._")[:160]
    return candidate or "download.torrent"


def unique_file(folder: Path, name: str) -> Path:
    p = folder / filename(name)
    if not p.suffix.lower() == ".torrent":
        p = p.with_suffix(".torrent")
    count = 1
    while p.exists():
        p = folder / f"{p.stem}-{count}{p.suffix}"
        count += 1
    return p


async def gather_results(page, query: str):
    await page.goto(f"{BASE}/?s={quote_plus(query)}", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(1200)
    results = await page.locator("a[href]").evaluate_all("""links => links.map(a => ({
      title: (a.innerText || a.getAttribute('title') || '').trim().replace(/\\s+/g,' '),
      url: a.href
    }))""")
    unique = {}
    for item in results:
        url, title = item["url"], item["title"]
        parsed = urlparse(url)
        if parsed.hostname not in {"psa.wf", "www.psa.wf"}:
            continue
        if MOVIE_PATH.match(parsed.path) and title and len(title) < 180:
            unique.setdefault(url.split("#")[0], title)
    return list(unique.items())


async def links_on_page(page):
    items = await page.locator("a[href]").evaluate_all("""links => links.map(a => ({
      title: (a.innerText || a.getAttribute('title') || '').trim().replace(/\\s+/g,' '),
      href: a.href
    }))""")
    return [(x["title"], x["href"]) for x in items
            if x["href"].startswith("magnet:") or TORRENT_EXT.search(x["href"])]


async def main():
    parser = argparse.ArgumentParser(description="PSA movie torrent link helper")
    parser.add_argument("movie", nargs="?", help="movie title (optionally including year)")
    parser.add_argument("--output", default="torrents", help="folder for saved .torrent files")
    parser.add_argument("--profile", default=".browser-profile", help="persistent Chromium profile")
    args = parser.parse_args()

    movie = args.movie or input("Movie title: ").strip()
    if not movie:
        parser.error("A movie title is required.")
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    profile = Path(args.profile).expanduser().resolve()
    print("Only download material for which you have the necessary rights.")
    print(f"Saving torrent files in: {output}")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile), headless=False, accept_downloads=True,
            viewport={"width": 1280, "height": 900},
        )
        pending = set()
        found = set()

        async def save(download):
            try:
                target = unique_file(output, download.suggested_filename)
                await download.save_as(str(target))
                print(f"Saved: {target}")
            except Exception as exc:
                print(f"Download couldn't be saved: {exc}")

        def on_download(download):
            if not TORRENT_EXT.search(download.suggested_filename):
                print(f"Ignored non-torrent download: {download.suggested_filename}")
                return
            task = asyncio.create_task(save(download))
            pending.add(task)
            task.add_done_callback(pending.discard)

        def on_page(tab):
            tab.on("download", on_download)
            print(f"Browser tab: {tab.url}")

        browser.on("page", on_page)
        page = browser.pages[0] if browser.pages else await browser.new_page()
        for tab in browser.pages:
            tab.on("download", on_download)

        try:
            results = await gather_results(page, movie)
        except Exception as exc:
            print(f"Search could not load automatically: {exc}")
            results = []

        if results:
            print("\nMatching movie pages:")
            for i, (url, title) in enumerate(results[:25], 1):
                print(f" {i:2}. {title} | {url}")
            response = input("\nChoose result number (Enter to use browser manually): ").strip()
            if response.isdigit() and 1 <= int(response) <= min(len(results), 25):
                try:
                    await page.goto(results[int(response) - 1][0], wait_until="domcontentloaded")
                except PlaywrightTimeoutError:
                    print("Navigation timed out; continue in the visible browser.")
        else:
            print("No search results parsed. Use the browser to search manually.")
        print("\nDirect .torrent and magnet links on current page:")
        for title, href in await links_on_page(page):
            if href not in found:
                found.add(href)
                print(f" - {title or 'Torrent'}: {href}")

        print("\nNavigate and CLICK the desired torrent link in the browser.")
        print("Complete any CAPTCHA/shortener steps yourself. Torrent downloads are saved.")
        print("Press Enter here when finished to close the browser.")
        try:
            await asyncio.to_thread(input)
        except (EOFError, KeyboardInterrupt):
            pass
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await browser.close()
        print(f"Done. Torrent files saved: {output}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
