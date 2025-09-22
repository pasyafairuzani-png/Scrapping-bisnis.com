import asyncio
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import json
import os
from crawler import scrape_article
from playwright.async_api import async_playwright
from dateutil import tz

BASE_URL = "https://bisnis.com"
SKIP_DOMAINS = ["premium.bisnis.com", "plus.bisnis.com"]

HARI_TERAKHIR = 3  # Ambil artikel 3 hari terakhir

# Timezone WIB
WIB = tz.gettz("Asia/Jakarta")


async def get_articles_from_page(page, page_num=1):
    """Ambil daftar link artikel dari halaman list bisnis.com"""
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
            domain = urlparse(full_url).netloc
            if domain in SKIP_DOMAINS:
                continue
            urls.add(full_url)
    return list(urls)


async def main_standard(max_articles=50):
    """Standard mode otomatis: ambil artikel terbaru sampai batas tanggal"""
    results = []
    seen_urls = set()
    page_num = 1

    # Batas tanggal dalam WIB
    batas_tanggal = datetime.now(WIB) - timedelta(days=HARI_TERAKHIR)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        while True:
            page = await browser.new_page()
            urls = await get_articles_from_page(page, page_num)
            await page.close()

            if not urls:
                print(f"[STOP] Tidak ada artikel lagi di halaman {page_num}")
                break

            page_has_recent = False

            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                page_article = await browser.new_page()
                data = await scrape_article(page_article, url)
                await page_article.close()

                if data:
                    tgl_str = data.get("Tanggal_terbit")
                    if tgl_str:
                        try:
                            # pastikan tanggal ke WIB
                            tgl_obj = datetime.fromisoformat(tgl_str)
                            if tgl_obj.tzinfo is None:
                                tgl_obj = tgl_obj.replace(tzinfo=WIB)
                            else:
                                tgl_obj = tgl_obj.astimezone(WIB)

                            if tgl_obj < batas_tanggal:
                                continue  # skip artikel lama

                            # simpan tanggal terbit sudah format WIB
                            data["Tanggal_terbit"] = tgl_obj.isoformat()
                            page_has_recent = True
                        except Exception:
                            continue

                    # Buang field yang None sebelum masuk ke results
                    clean_data = {k: v for k, v in data.items() if v is not None}
                    results.append(clean_data)

                    # kalau sudah cukup max_articles langsung berhenti
                    if len(results) >= max_articles:
                        print(f"[STOP] Sudah mencapai {max_articles} artikel")
                        break

            print(f"[PAGE {page_num}] selesai dicek")

            # kalau artikel yang baru tidak ada di halaman ini, berhenti total
            if not page_has_recent or len(results) >= max_articles:
                print(f"[STOP] Tidak ada artikel terbaru di halaman {page_num} atau sudah mencapai limit.")
                break

            page_num += 1

        if results:
            # urutkan dari terbaru ke terlama
            results.sort(key=lambda x: x.get("Tanggal_terbit") or "", reverse=True)
            results = results[:max_articles]

            # versi increment: standard1.json, standard2.json, dst
            i = 1
            while True:
                filename = f"standard{i}.json"
                if not os.path.exists(filename):
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    break
                i += 1

            # versi latest
            with open("standard.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            print(f"[SAVE] {len(results)} artikel disimpan ke {filename}")
        else:
            print("[INFO] Tidak ada artikel terbaru ditemukan.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main_standard(max_articles=50))
