import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
from dateutil import parser, tz
from crawler import scrape_article
from urllib.parse import urljoin, urlparse
import json
import re
import os

# Base domain
BASE_URL = "https://bisnis.com"

# Subdomain yang di-skip
SKIP_DOMAINS = ["premium.bisnis.com", "plus.bisnis.com"]

# Timezone WIB
WIB = tz.gettz("Asia/Jakarta")


def extract_date_from_url(url):
    """Ekstrak tanggal dari slug URL (format YYYYMMDD) dalam WIB."""
    match = re.search(r"/(\d{8})/", url)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=WIB)
        except Exception:
            return None
    return None


async def get_articles_from_page(page, page_num=1):
    """Ambil daftar link artikel dari halaman list."""
    if page_num == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}?page={page_num}"

    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    urls = set()
    anchors = await page.query_selector_all("a")
    for a in anchors:
        href = await a.get_attribute("href")
        if href and "/read/" in href:
            full_url = urljoin(BASE_URL, href)

            # skip subdomain yang tidak diinginkan
            domain = urlparse(full_url).netloc
            if domain in SKIP_DOMAINS:
                continue

            urls.add(full_url)

    return list(urls)


async def backtrack_crawler(start_date, end_date):
    """Ambil artikel dalam rentang tanggal, mundur dari end_date ke start_date."""
    start_dt = parser.parse(start_date).replace(tzinfo=WIB)
    end_dt = parser.parse(end_date).replace(hour=23, minute=59, second=59, tzinfo=WIB)

    results = []
    seen_urls = set()
    page_num = 1
    stop = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        while not stop:
            page = await browser.new_page()
            urls = await get_articles_from_page(page, page_num=page_num)
            await page.close()

            if not urls:
                print("[STOP] Tidak ada artikel lagi di halaman", page_num)
                break

            page_stop = False

            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # cek tanggal dari URL
                tgl_url = extract_date_from_url(url)
                if tgl_url:
                    if tgl_url < start_dt:
                        page_stop = True
                        continue
                    elif tgl_url > end_dt:
                        continue

                # scrape artikel
                page_article = await browser.new_page()
                data = await scrape_article(page_article, url)
                await page_article.close()

                if not data or not data.get("Tanggal_terbit"):
                    continue

                try:
                    tgl = parser.parse(data["Tanggal_terbit"])
                    if tgl.tzinfo is None:
                        tgl = tgl.replace(tzinfo=WIB)
                    else:
                        tgl = tgl.astimezone(WIB)

                    if start_dt <= tgl <= end_dt:
                        data["Tanggal_terbit"] = tgl.isoformat()
                        results.append(data)
                except Exception:
                    continue

            if page_stop:
                stop = True

            print(f"[PAGE {page_num}] selesai dicek")
            page_num += 1

        if results:
            # urutkan ascending dari jam terkecil ke terbesar
            results.sort(key=lambda x: parser.parse(x["Tanggal_terbit"]).astimezone(WIB))

            # generate nama file increment backtrack1.json, backtrack2.json, dst
            i = 1
            while True:
                filename = f"backtrack{i}.json"
                if not os.path.exists(filename):
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    print(
                        f"[SAVE] {len(results)} artikel dalam range "
                        f"{start_date} - {end_date} disimpan ke {filename}"
                    )
                    break
                i += 1
        else:
            print(f"[INFO] Tidak ada artikel dalam rentang {start_date} - {end_date}.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(backtrack_crawler("2025-09-19", "2025-09-20"))
