# -*- coding: utf-8 -*-
"""data/raw/{visa,alarm,relations.csv} + countryinfo/babel/zoneinfo + tables.py → _data/countries.json
(로컬 실행 전용: pip install countryinfo babel tzdata). 사용: python scripts/build_data.py"""
import sys, json, re, csv, math, html, datetime as dt, pathlib
from zoneinfo import ZoneInfo
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tables as T
from countryinfo import CountryInfo
from babel import Locale
from babel.core import get_global

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "_data"; OUT.mkdir(exist_ok=True)
KO = Locale("ko")
ICN = (37.4602, 126.4407)
TZ_OVERRIDE = {"RU": "Europe/Moscow", "US": "America/New_York", "BR": "America/Sao_Paulo", "CA": "America/Toronto", "AU": "Australia/Sydney", "MX": "America/Mexico_City",
               "CN": "Asia/Shanghai", "ID": "Asia/Jakarta", "KZ": "Asia/Almaty", "AR": "America/Argentina/Buenos_Aires", "CL": "America/Santiago", "MN": "Asia/Ulaanbaatar",
               "CD": "Africa/Kinshasa", "EC": "America/Guayaquil", "PT": "Europe/Lisbon", "ES": "Europe/Madrid", "FR": "Europe/Paris", "NZ": "Pacific/Auckland", "FM": "Pacific/Pohnpei",
               "KI": "Pacific/Tarawa", "PG": "Pacific/Port_Moresby", "DK": "Europe/Copenhagen", "NL": "Europe/Amsterdam", "NO": "Europe/Oslo", "GB": "Europe/London",
               "UZ": "Asia/Tashkent", "MY": "Asia/Kuala_Lumpur", "KR": "Asia/Seoul", "TL": "Asia/Dili", "SD": "Africa/Khartoum", "GU": "Pacific/Guam", "XK": "Europe/Belgrade"}
CAUCASUS = {"AM", "AZ", "GE"}
def continent(iso, ci):
    reg, sub = ci.get("region") or "", ci.get("subregion") or ""
    if iso in CAUCASUS: return "유럽"
    if reg == "Asia": return "중동" if sub == "Western Asia" else "아시아"
    if reg == "Europe": return "유럽"
    if reg == "Africa": return "아프리카"
    if reg == "Americas": return "미주"
    if reg == "Oceania": return "오세아니아"
    return {"HK": "아시아", "MO": "아시아", "TW": "아시아", "XK": "유럽"}.get(iso, "기타")

def haversine(a, b):
    R = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1]); dp = p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

def offset(tz, when):
    return ZoneInfo(tz).utcoffset(when).total_seconds() / 3600 if False else (dt.datetime(when.year, when.month, when.day, 12, tzinfo=ZoneInfo(tz)).utcoffset().total_seconds() / 3600)

def currency_of(iso):
    try:
        tc = get_global("territory_currencies").get(iso, [])
    except Exception:
        tc = []
    cur = [c for c in tc if c[2] is None and c[3]]  # 현재 법정통화
    if not cur: cur = [c for c in tc if c[2] is None] or tc[-1:]
    codes = [c[0] for c in cur][:2]
    out = []
    for c in codes:
        out.append(dict(code=c, name=KO.currencies.get(c) or c, symbol=(KO.currency_symbols.get(c) or c)))
    return out

def parse_relations():
    rel = {}
    f = RAW / "relations.csv"
    if not f.exists(): return rel
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        iso = (r.get("국가코드(ISO 2자리)") or "").strip()
        if not iso: continue
        d = (r.get("외교관계") or "")
        m = re.search(r"(\d{4}-\d{2}-\d{2})\s*수교", d)
        def num(x):
            try: return int(float(x))
            except Exception: return None
        rel[iso] = dict(since=m.group(1) if m else "", gyomin=re.sub(r"\s+", " ", html.unescape(r.get("교민현황") or "")).strip()[:200], export=num(r.get("수출액")), imp=num(r.get("수입액")))
    return rel

def main():
    visa = json.load(open(RAW / "visa.json", encoding="utf-8"))
    alarm = json.load(open(RAW / "alarm.json", encoding="utf-8"))
    rel = parse_relations()
    al = {}
    for a in alarm:
        al.setdefault(a["country_iso_alp2"], []).append(dict(lvl=int(a["alarm_lvl"]) if str(a.get("alarm_lvl", "")).isdigit() else 0, region=a.get("region_ty", ""), remark=html.unescape((a.get("remark") or "")).strip(),
                                                           cont=a.get("continent_nm", ""), flag=a.get("flag_download_url", ""), map=a.get("map_download_url", "")))
    out = []
    now = dt.datetime(2027, 1, 15); summer = dt.datetime(2027, 7, 15)
    for v in sorted(visa, key=lambda x: x["country_nm"]):
        iso = v["country_iso_alp2"]
        try: ci = CountryInfo(iso).info()
        except Exception: ci = {}
        name = T.NAME_FIX.get(iso, v["country_nm"].replace("공화국", "") if iso in ("KG",) else v["country_nm"])
        tzs = ci.get("timezoneNames") or []
        tz = T_OVER = TZ_OVERRIDE.get(iso) or (tzs[0] if tzs else "")
        off_w = off_s = None
        if tz:
            try: off_w, off_s = offset(tz, now), offset(tz, summer)
            except Exception: pass
        cap_ll = ci.get("capital_latlng") or ci.get("latlng")
        dist = round(haversine(ICN, tuple(cap_ll))) if cap_ll else None
        a = al.get(iso, [])
        cont_kr = continent(iso, ci)
        langs = []
        for l in (ci.get("languages") or [])[:3]:
            try: langs.append(KO.languages.get(l) or l)
            except Exception: pass
        gnrl = (v.get("gnrl_pspt_visa_cn") or "").strip()
        ev = (v.get("nvisa_entry_evdc_cn") or "").replace("\\n", "\n").strip()
        basis = ""
        m = re.search(r"일반여권 소지자\s*:\s*([^\n]+)", ev)
        if m: basis = m.group(1).strip()
        plug = T.PLUG.get(iso)
        out.append(dict(
            iso=iso, name=name, en=v.get("country_eng_nm", ""), cont=cont_kr, capital=T.CAPKR.get(iso, ""), capital_en=ci.get("capital", ""), population=ci.get("population"),
            calling=(ci.get("callingCodes") or [""])[0], tld=(ci.get("tld") or [""])[0], langs=langs, currencies=currency_of(iso), tz=tz, off_w=off_w, off_s=off_s, dist=dist,
            visa=dict(stay=gnrl, free=(gnrl not in ("", "X")), basis=basis, evidence=ev, remark=(v.get("remark") or "").strip()),
            plug=dict(v=plug[0], hz=plug[1], types=plug[2]) if plug else None,
            eta=T.ETA.get(iso), alarm=al.get(iso, []), rel=rel.get(iso)))
    # 표시명 중복 정리
    json.dump(out, open(OUT / "countries.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    free = sum(1 for c in out if c["visa"]["free"])
    print(len(out), "countries; 무비자", free, "; 경보국", sum(1 for c in out if c["alarm"]), "; 플러그표", sum(1 for c in out if c["plug"]), "; 수도(한글)", sum(1 for c in out if c["capital"]))
    miss = [c["name"] for c in out if c["off_w"] is None]
    print("시차 없음:", miss)

if __name__ == "__main__":
    main()
