#!/usr/bin/env python3
"""
ดึงอัตราแลกเปลี่ยนเงินตรา (อิง 1 USD) จากแหล่งฟรี ไม่ต้องใช้ API key
แล้วสร้างไฟล์ rates.json ให้เว็บ world_dispatch_board.html โหลดไปแสดงผล

ลองหลายแหล่งเรียงตามลำดับ ถ้าแหล่งแรกล่มหรือข้อมูลไม่ครบจะลองแหล่งถัดไปอัตโนมัติ
รันพร้อมกับ fetch_news.py ใน GitHub Actions workflow เดียวกัน
"""
import json
import urllib.request
from datetime import datetime, timezone

BASE = "USD"

# สกุลเงินที่จะแสดงในเว็บ (THB ไว้บนสุดเพราะกลุ่มเป้าหมายหลักเป็นคนไทย)
CURRENCIES = [
    "THB", "EUR", "GBP", "JPY", "CNY", "KRW", "SGD", "AUD",
    "CAD", "CHF", "HKD", "INR", "MYR", "PHP", "IDR", "VND", "TWD"
]

# เรียงลำดับความสำคัญ: ลองแหล่งแรกก่อน ถ้าพังค่อยลองแหล่งถัดไป
SOURCES = [
    ("frankfurter", "https://api.frankfurter.dev/v1/latest?base=USD"),
    ("fawazahmed0-cdn", "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"),
    ("open-er-api", "https://open.er-api.com/v6/latest/USD"),
]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (rates-bot)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize(source_name, data):
    """แปลงรูปแบบข้อมูลจากแต่ละแหล่งให้เป็น dict {รหัสสกุลเงิน: อัตราเทียบ USD=1} แบบเดียวกัน"""
    if source_name == "frankfurter":
        rates = dict(data.get("rates", {}))
        rates["USD"] = 1.0
        return rates
    if source_name == "fawazahmed0-cdn":
        # โครงสร้างของแหล่งนี้: {"date": "...", "usd": {"thb": 36.5, "eur": 0.92, ...}}
        raw = data.get("usd", {})
        return {k.upper(): v for k, v in raw.items()}
    if source_name == "open-er-api":
        return dict(data.get("rates", {}))
    return {}


def main():
    rates = {}
    used_source = None

    for name, url in SOURCES:
        try:
            data = fetch_json(url)
            normalized = normalize(name, data)
            # เช็คว่าข้อมูลที่ได้มีสกุลเงินหลักที่ต้องการจริง ไม่ใช่ dict ว่างหรือพัง
            if normalized and any(c in normalized for c in CURRENCIES):
                rates = normalized
                used_source = name
                print(f"OK   ใช้ข้อมูลอัตราแลกเปลี่ยนจาก: {name} ({url})")
                break
            else:
                print(f"SKIP {name} -> ข้อมูลที่ได้ไม่ครบสกุลเงินที่ต้องการ")
        except Exception as e:
            print(f"FAIL {name} ({url}) -> {e}")

    if not rates:
        print("ดึงอัตราแลกเปลี่ยนไม่สำเร็จจากทุกแหล่ง จะไม่แก้ไข rates.json เดิม (ถ้ามี)")
        return

    output = {
        "base": BASE,
        "source": used_source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "rates": {c: rates[c] for c in CURRENCIES if c in rates},
    }

    with open("rates.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"เขียน rates.json แล้ว รวม {len(output['rates'])} สกุลเงิน (แหล่งข้อมูล: {used_source})")


if __name__ == "__main__":
    main()
