# -*- coding: utf-8 -*-
"""외교부 3종 API 전량 수집 → data/raw/{visa,alarm,safety}.json
 - 국가·지역별 입국허가요건  1262000/EntranceVisaService2/getEntranceVisaList2 (JSON)
 - 국가·지역별 여행경보      1262000/TravelAlarmService2/getTravelAlarmList2   (JSON)
 - 국가별 안전정보(대사관 공지) 1262000/CountrySafetyService/getCountrySafetyList (XML)
키: DATA_GO_KR_API_KEY 또는 ../hosppass/.env (로컬 전용).  사용: python scripts/fetch_mofa.py"""
import os, sys, re, json, time, pathlib
import requests
sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"; RAW.mkdir(parents=True, exist_ok=True)
B = "https://apis.data.go.kr/1262000/"
S = requests.Session()

def key():
    k = os.environ.get("DATA_GO_KR_API_KEY")
    if k: return k
    for l in open(ROOT.parent / "hosppass" / ".env", encoding="utf-8"):
        if l.startswith("API_KEY"): return l.split("=", 1)[1].strip()
    raise SystemExit("API 키 없음")
K = key()

def get(ep, page, per, extra=None):
    for a in range(6):
        try:
            r = S.get(B + ep, params=dict(serviceKey=K, pageNo=page, numOfRows=per, **(extra or {})), timeout=90)
            return r.text
        except Exception as e:
            print("retry", ep, page, a, str(e)[:60], flush=True); time.sleep(2 + a * 2)
    raise SystemExit("실패 " + ep)

def json_all(ep, per=200):
    rows, p, total = [], 1, None
    while True:
        j = json.loads(get(ep, p, per, dict(returnType="JSON")))
        body = j["response"]["body"]
        total = int(body["totalCount"])
        it = body["items"]["item"] if body.get("items") else []
        if isinstance(it, dict): it = [it]
        rows += it
        if not it or len(rows) >= total: break
        p += 1
    print(ep, len(rows), "/", total)
    return rows

def xml_all(ep, per=200):
    rows, p, total = [], 1, None
    while True:
        t = get(ep, p, per)
        if total is None: total = int(re.search(r"<totalCount>(\d+)", t).group(1))
        its = [dict((m.group(1), m.group(2)) for m in re.finditer(r"<(\w+)>(.*?)</\1>", it, re.S)) for it in re.findall(r"<item>(.*?)</item>", t, re.S)]
        rows += its
        if p % 5 == 0: print(" page", p, len(rows), flush=True)
        if not its or len(rows) >= total: break
        p += 1
    print(ep, len(rows), "/", total)
    return rows

if __name__ == "__main__":
    (RAW / "visa.json").write_text(json.dumps(json_all("EntranceVisaService2/getEntranceVisaList2"), ensure_ascii=False), encoding="utf-8")
    (RAW / "alarm.json").write_text(json.dumps(json_all("TravelAlarmService2/getTravelAlarmList2"), ensure_ascii=False), encoding="utf-8")
    (RAW / "safety.json").write_text(json.dumps(xml_all("CountrySafetyService/getCountrySafetyList"), ensure_ascii=False), encoding="utf-8")
    print("done")
