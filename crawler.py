from datetime import datetime
from dateutil import parser, tz
from urllib.parse import urljoin
import json

BASE_DOMAIN = "https://bisnis.com"

JKT_TZ = tz.gettz("Asia/Jakarta")

async def get_articles_from_list(page, page_num=1, section="ekonomi"):
    """Ambil daftar artikel dari halaman list (link + tanggal)."""
    url = f"{BASE_DOMAIN}/{section}?page={page_num}"
    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    articles = []
    nodes = await page.query_selector_all("article")

    for node in nodes:
        link_tag = await node.query_selector("a")
        href = await link_tag.get_attribute("href") if link_tag else None

        if not href or "/read/" not in href:
            continue

        full_url = href if href.startswith("http") else urljoin(BASE_DOMAIN, href)

        tgl = None
        tgl_raw = None
        time_tag = await node.query_selector("time")
        if time_tag:
            try:
                tgl_raw = await time_tag.get_attribute("datetime")
                if tgl_raw:
                    # parse dan konversi ke WIB
                    tgl = parser.parse(tgl_raw).astimezone(JKT_TZ)
            except:
                pass

        print("[DEBUG][LIST] URL:", full_url, "Tanggal Raw:", tgl_raw, "Parsed:", tgl)
        articles.append({
            "url": full_url,
            "tanggal": tgl
        })

    return articles

async def scrape_article(page, url):
    """Scrape detail artikel (judul, isi, tanggal)."""
    try:
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector("article, div.article-content", timeout=15000)
        except:
            pass

        judul_tag = (
            await page.query_selector("h1")
            or await page.query_selector("div.article-title h1")
            or await page.query_selector("div.title h1")
            or await page.query_selector("header h1")
        )
        judul = await judul_tag.inner_text() if judul_tag else None

        if not judul:
            og_title = await page.query_selector('meta[property="og:title"]')
            if og_title:
                judul = await og_title.get_attribute("content")

        if not judul or judul.strip() == "":
            judul = "[Judul tidak tersedia]"

        paras = await page.query_selector_all("div.article-content p, article p")
        isi = " ".join([await p.inner_text() for p in paras])
        if not isi or len(isi.strip()) < 50:
            isi = "[Konten tidak tersedia]"

        tanggal = None
        raw_time = None
        time_tag = await page.query_selector("time")
        if time_tag:
            try:
                raw_time = await time_tag.get_attribute("datetime")
                if raw_time:
                    tanggal = parser.parse(raw_time).astimezone(JKT_TZ)
            except:
                pass

        if not tanggal:
            meta_time = await page.query_selector('meta[property="article:published_time"]')
            if meta_time:
                try:
                    raw_time = await meta_time.get_attribute("content")
                    if raw_time:
                        tanggal = parser.parse(raw_time).astimezone(JKT_TZ)
                except:
                    pass

        print("[DEBUG][DETAIL] URL:", url, "Raw:", raw_time, "Parsed:", tanggal)

        return {
            "Link": url,
            "Judul": judul,
            "Isi_artikel": isi,
            "Tanggal_terbit": tanggal.isoformat() if tanggal else None,
        }

    except Exception as e:
        print(f"[ERROR] Gagal scrape {url}: {e}")
        return None

def save_to_json(data, filename):
    """Simpan data ke file JSON dengan format rapi."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
