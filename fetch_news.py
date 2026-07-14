#!/usr/bin/env python3
"""
ดึงข่าวจาก RSS feed สาธารณะ (ฟรี ไม่ต้องใช้ API key) แล้วสร้างไฟล์ news.json
ให้เว็บ world_dispatch_board.html โหลดไปแสดงผล

รันสคริปต์นี้เองก็ได้ (python fetch_news.py) หรือปล่อยให้ GitHub Actions
รันให้อัตโนมัติตามตารางเวลาใน .github/workflows/update-news.yml
"""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# ---------------------------------------------------------------
# ตั้งค่าแหล่งข่าว RSS ฟรี แยกตามหมวด ครอบคลุมหลายภูมิภาคทั่วโลก
# (เพิ่ม/ลบ/แก้ URL ได้ตามชอบ)
# ---------------------------------------------------------------
FEEDS = {
    "world": [
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml", "🌐"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "🌍"),
        ("The Guardian World", "https://www.theguardian.com/world/rss", "🇬🇧"),
        ("DW (Germany)", "https://rss.dw.com/xml/rss-en-all", "🇩🇪"),
        ("France24", "https://www.france24.com/en/rss", "🇫🇷"),
        ("NHK World Japan", "https://www3.nhk.or.jp/nhkworld/en/news/all.xml", "🇯🇵"),
        ("Channel News Asia", "https://www.channelnewsasia.com/rssfeeds/8395986", "🇸🇬"),
        ("AllAfrica", "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf", "🌍"),
    ],
    "economy": [
        ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml", "💰"),
        ("The Guardian Business", "https://www.theguardian.com/business/rss", "💰"),
    ],
    "tech": [
        ("BBC Technology", "http://feeds.bbci.co.uk/news/technology/rss.xml", "💻"),
        ("TechCrunch", "https://techcrunch.com/feed/", "💻"),
        ("The Verge", "https://www.theverge.com/rss/index.xml", "💻"),
        ("Ars Technica", "http://feeds.arstechnica.com/arstechnica/index", "💻"),
    ],
}

ITEMS_PER_FEED = 6          # ดึงกี่ข่าวต่อ 1 แหล่ง (เพิ่มจากเดิมเพื่อให้มีข่าวพอสำหรับแบ่งหน้า)
MAX_DETAIL_LEN = 220        # ตัดความยาวคำอธิบายข่าว (ตัวอักษร)

THAI_MONTHS = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
               "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def strip_html(text: str) -> str:
    """เอาแท็ก HTML ออกจากคำอธิบายข่าว แล้วตัดความยาว"""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_DETAIL_LEN:
        text = text[:MAX_DETAIL_LEN].rsplit(" ", 1)[0] + "…"
    return text


def thai_date(dt: datetime) -> str:
    return f"{dt.day} {THAI_MONTHS[dt.month]}"


def fetch_feed(url: str) -> ET.Element:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (news-bot)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return ET.fromstring(resp.read())


def local_tag(elem) -> str:
    """เอาชื่อแท็กออกมาโดยตัด namespace ออก เช่น '{http://...}item' -> 'item'"""
    return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag


def find_items(root: ET.Element):
    """หา <item> ทุกตัวในไฟล์ ไม่ว่าจะมี namespace (RDF/RSS1.0) หรือไม่ก็ตาม"""
    return [el for el in root.iter() if local_tag(el) == "item"]


def find_text(item, *names) -> str:
    """หาเนื้อหาข้อความจากแท็กลูกที่ชื่อตรงกับ names ใดก็ได้ (namespace-agnostic)"""
    for child in item:
        if local_tag(child) in names and child.text:
            return child.text
    return ""


def parse_items(root: ET.Element, source_name: str, flag: str, category: str):
    results = []
    for item in find_items(root)[:ITEMS_PER_FEED]:
        title = find_text(item, "title").strip()
        link = find_text(item, "link").strip()
        desc = find_text(item, "description", "encoded", "summary")
        pub_raw = find_text(item, "pubDate", "date")
        try:
            pub_dt = parsedate_to_datetime(pub_raw) if pub_raw else datetime.now(timezone.utc)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        except Exception:
            pub_dt = datetime.now(timezone.utc)

        if not title or not link:
            continue

        results.append({
            "time": thai_date(pub_dt),
            "sort_ts": pub_dt.timestamp(),
            "region": source_name,
            "flag": flag,
            "category": category,
            "headline": title,
            "detail": strip_html(desc) or "อ่านรายละเอียดเพิ่มเติมได้ที่ลิงก์ต้นฉบับ",
            "source": source_name,
            "url": link,
        })
    return results


def main():
    all_items = []
    for category, sources in FEEDS.items():
        for source_name, url, flag in sources:
            try:
                root = fetch_feed(url)
                all_items.extend(parse_items(root, source_name, flag, category))
                print(f"OK   {source_name} ({category}) - {url}")
            except Exception as e:
                print(f"FAIL {source_name} ({category}) - {url} -> {e}")

    # เรียงข่าวใหม่สุดก่อน แล้วตัด sort_ts ทิ้ง (ไม่ต้องใช้ในหน้าเว็บ)
    all_items.sort(key=lambda x: x["sort_ts"], reverse=True)
    for it in all_items:
        del it["sort_ts"]

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items,
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nเขียน news.json แล้ว รวม {len(all_items)} ข่าว")


if __name__ == "__main__":
    main()
