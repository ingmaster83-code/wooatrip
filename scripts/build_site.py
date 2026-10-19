# -*- coding: utf-8 -*-
"""우아여행 정적 사이트 생성기: _data/countries.json → _site/.  사용: python scripts/build_site.py"""
import sys, json, re, shutil, collections, time, html
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *

LEVEL = {1: ("여행유의", "신변안전에 유의하고 안전정보를 확인하세요."), 2: ("여행자제", "불필요한 여행을 자제하고 필요한 경우 신변안전에 특별히 유의하세요."),
         3: ("출국권고", "긴요한 용무가 아닌 한 출국을 권고하며 이미 체류 중이면 철수 계획을 세우세요."), 4: ("여행금지", "여권법상 입국이 금지되는 지역으로 방문 시 처벌받을 수 있습니다.")}
PLUG_DESC = {"A": "11자 납작한 2핀(미국·일본형)", "B": "납작한 2핀+접지 둥근 핀(미국·캐나다형)", "C": "둥근 2핀(유럽 표준, 한국 일반 플러그)", "D": "둥근 3핀 삼각형(인도형)", "E": "둥근 2핀+접지 구멍(프랑스형)",
             "F": "둥근 2핀+양옆 접지 클립(독일형, 한국 플러그와 호환)", "G": "납작한 3핀(영국형)", "H": "Y자형 3핀(이스라엘형)", "I": "V자 납작 2핀+접지(호주·중국형)", "J": "둥근 3핀(스위스형)",
             "K": "둥근 3핀(덴마크형)", "L": "일렬 3핀(이탈리아형)", "M": "큰 둥근 3핀(남아공형)", "N": "둥근 3핀(브라질형)", "O": "둥근 3핀(태국형)"}

def slug(c): return c["name"]
def fm(x): return ("%+g" % x).rstrip("0").rstrip(".") if isinstance(x, float) and x != int(x) else "%+d" % int(x)

def diff_txt(off):
    d = off - 9
    if d == 0: return "시차가 없습니다(한국과 같은 시각)"
    return "한국보다 %s시간 %s" % (("%g" % abs(d)), "느립니다" if d < 0 else "빠릅니다")

def clock_example(off):
    d = off - 9
    h = int((12 + d) % 24); m = int(round(((12 + d) % 1) * 60))
    return "한국 낮 12시 = 현지 %s%02d시%s" % ("전날 " if 12 + d < 0 else ("다음날 " if 12 + d >= 24 else ""), h, ("%02d분" % m) if m else "")

def flight_hours(km):
    h = km / 820.0 + 0.8
    return max(1.0, round(h * 2) / 2)

def max_level(c):
    return max([a["lvl"] for a in c["alarm"]] or [0])

def stay_num(stay):
    m = re.search(r"(\d+)\s*(일|개월)", stay or "")
    if not m: return 0
    n = int(m.group(1))
    return n * 30 if m.group(2) == "개월" else n

def table(heads, rows, num=()):
    th = "".join('<th%s>%s</th>' % (' class="num"' if i in num else "", h) for i, h in enumerate(heads))
    body = "".join("<tr>%s</tr>" % "".join('<td%s>%s</td>' % (' class="num"' if i in num else "", v) for i, v in enumerate(r)) for r in rows)
    return '<div class="tbl-wrap"><table class="tbl"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (th, body)

def chips(items): return '<div class="chips">%s</div>' % "".join('<a class="chip" href="%s">%s</a>' % (u, esc(t)) for t, u in items)

# ───────────────────────── 요약 문장 ─────────────────────────
def time_phrase(c):
    if c["off_w"] is None: return ""
    d = diff_txt(c["off_w"])
    base = "시차는 없고 한국과 같은 시각입니다." if c["off_w"] == 9 else "시차는 %s." % d.replace("느립니다", "느립니다").replace("빠릅니다", "빠릅니다")
    if c["off_s"] != c["off_w"]: base = base[:-1] + "(여름 시간제 적용 시 %s)." % diff_txt(c["off_s"]).replace("한국보다 ", "")
    return base

def visa_sentence(c):
    v = c["visa"]
    if v["free"]:
        s = "한국 일반여권(관광 목적)으로 <b>%s 무비자 입국</b>이 가능합니다" % esc(v["stay"])
        if v["basis"]: s += "(근거: %s)" % esc(v["basis"])
        return s + "."
    return "한국 일반여권으로 <b>무비자 입국이 불가</b>해 사전에 비자 등 입국 허가를 받아야 합니다."

def alarm_sentence(c):
    L = max_level(c)
    if not c["alarm"]: return "외교부가 발령한 여행경보가 현재 목록에 없습니다(별도 경보 없음)."
    nm = LEVEL[L][0] if L in LEVEL else ""
    full = [a for a in c["alarm"] if a["region"] == "전체"]
    if full: return "전 지역에 <b>%d단계(%s)</b> 여행경보가 발령돼 있습니다." % (full[0]["lvl"], LEVEL[full[0]["lvl"]][0])
    return "일부 지역에 최고 <b>%d단계(%s)</b> 여행경보가 발령돼 있고 나머지 지역은 경보가 없거나 낮은 단계입니다." % (L, nm)

def plug_sentence(c):
    p = c["plug"]
    if not p: return "전압·플러그 정보는 아직 정리되지 않았습니다. 숙소와 현지 정보를 확인하세요."
    v = p["v"]
    vv = str(v)
    lo = isinstance(v, int) and v < 200
    s = "전압은 <b>%sV·%sHz</b>, 플러그는 <b>%s타입</b>입니다." % (vv, p["hz"], esc(p["types"].replace(",", "·")))
    if lo: s += " 한국(220V)과 전압이 달라 220V 전용 제품은 <b>변압기</b>가 필요합니다(스마트폰·노트북 충전기는 대부분 100–240V 겸용)."
    elif vv.startswith("127/"): s += " 지역에 따라 127V·220V가 섞여 있어 전압 표기를 먼저 확인하세요."
    else: s += " 한국과 같은 220V 계열이라 변압기 없이 <b>플러그 어댑터</b>만 있으면 됩니다."
    return s

def currency_txt(c):
    return ", ".join("%s(%s)" % (esc(x["name"]), x["code"]) for x in c["currencies"]) or "-"

def crumb_country(c, extra=None):
    cr = [("홈", "/"), ("국가별", "/country/"), (c["name"], "/country/%s/" % slug(c))]
    if extra: cr.append(extra)
    return cr

def country_links(c):
    n = slug(c)
    return chips([(c["name"] + " 개요", "/country/%s/" % n), (c["name"] + " 비자", "/visa/%s/" % n), (c["name"] + " 시차", "/time/%s/" % n),
                  (c["name"] + " 전압·플러그", "/plug/%s/" % n), (c["name"] + " 여행경보", "/safety/%s/" % n)])

# ───────────────────────── 국가 개요 ─────────────────────────
def page_country(c, byname):
    n = slug(c); path = "/country/%s/" % n
    v = c["visa"]; L = max_level(c)
    rows = [["수도", esc(c["capital"] or c["capital_en"])], ["언어", esc(", ".join(c["langs"]) or "-")], ["통화", currency_txt(c)], ["국가번호", ("+%s" % c["calling"]) if c["calling"] else "-"],
            ["시차", (diff_txt(c["off_w"]) + ((" (여름 시간제 때는 %s)" % diff_txt(c["off_s"]).replace("한국보다 ", "")) if c["off_s"] != c["off_w"] else "")) if c["off_w"] is not None else "-"],
            ["비자(일반여권)", ("무비자 %s" % esc(v["stay"])) if v["free"] else "무비자 입국 불가"], ["여행경보", ("%d단계 %s" % (L, LEVEL[L][0])) if L else "없음"],
            ["전압·플러그", ("%sV %sHz · %s타입" % (c["plug"]["v"], c["plug"]["hz"], c["plug"]["types"])) if c["plug"] else "-"]]
    if c["dist"]: rows.append(["인천~수도 직선거리", "약 %s km (비행시간 대략 %g시간, 경유·노선에 따라 다름)" % ("{:,}".format(c["dist"]), flight_hours(c["dist"]))])
    if c["rel"] and c["rel"].get("since"): rows.append(["한국과 수교", esc(c["rel"]["since"])])
    if c["rel"] and c["rel"].get("gyomin"): rows.append(["교민·체류 현황", esc(c["rel"]["gyomin"])])
    t = table(["항목", "내용"], rows)
    eta_html = ""
    if c["eta"]: eta_html = '<div class="note-box"><b>입국 전 온라인 절차:</b> %s — %s 제도와 수수료는 바뀔 수 있으니 공식 사이트에서 확인하세요.</div>' % (esc(c["eta"][0]), esc(c["eta"][1]))
    checklist = []
    checklist.append("여권 유효기간 확인(체류 기간 이상, 국가에 따라 6개월 이상 요구)")
    checklist.append("무비자 %s 가능 — 입국 목적·체류 기간에 맞는지 확인" % v["stay"] if v["free"] else "비자(또는 전자비자) 사전 발급")
    if c["eta"]: checklist.append(c["eta"][0])
    if c["plug"]:
        p = c["plug"]
        checklist.append("%s타입 플러그 어댑터" % p["types"].replace(",", "·") + ("와 변압기(220V 전용 제품 사용 시)" if isinstance(p["v"], int) and p["v"] < 200 else ""))
    if c["currencies"]: checklist.append("현지 통화 %s 환전 또는 해외 결제 카드" % c["currencies"][0]["name"])
    if L >= 2 or any(a["lvl"] >= 2 for a in c["alarm"]): checklist.append("방문 지역의 여행경보 단계 확인 및 여행자보험 가입")
    else: checklist.append("여행자보험 가입 및 긴급 연락처(대사관) 저장")
    body = f"""
<div class="page-head"><h1>{esc(c['name'])} 여행 정보 — 비자·시차·전압·여행경보</h1><p>{esc(c['cont'])} · {esc(c['en'])}</p></div>
<p class="lead">{visa_sentence(c)} {alarm_sentence(c)} {time_phrase(c)} {plug_sentence(c)}</p>
{ad()}
{t}
{eta_html}
<h2 class="group-title">🧳 {esc(c['name'])} 여행 준비물 체크리스트</h2>
<ul class="lead" style="margin-left:20px">{''.join('<li>%s</li>' % esc(x) for x in checklist)}</ul>
<h2 class="group-title">🔎 주제별 자세히</h2>
{country_links(c)}
<div class="note-box">이 페이지는 외교부 공공데이터와 참고 정보를 바탕으로 합니다. 입국 조건과 여행경보는 수시로 바뀌므로 출발 전 외교부 해외안전여행(0404.go.kr)과 대사관·항공사 안내를 반드시 확인하세요.</div>
"""
    faq = [(f"{c['name']} 여행에 비자가 필요한가요?", visa_sentence(c).replace("<b>", "").replace("</b>", "")),
           (f"{c['name']}은(는) 한국과 시차가 얼마나 나나요?", (("한국과 같은 시각입니다." if c["off_w"] == 9 else diff_txt(c["off_w"]).replace("한국보다 ", "한국보다 ") + ".")) if c["off_w"] is not None else "정보가 없습니다."),
           (f"{c['name']} 전압과 콘센트는 어떤가요?", re.sub(r"<[^>]+>", "", plug_sentence(c)))]
    write(path, layout(path, f"{c['name']} 여행 정보 — 비자·시차·전압·여행경보 총정리", f"{c['name']} 입국 비자(무비자 여부), 시차, 전압·플러그 타입, 통화, 여행경보 단계와 여행 준비물. 외교부 공공데이터 기준.", body, faq, crumb_country(c), coupang=True), "0.8")

def page_visa(c):
    v = c["visa"]; n = slug(c); path = "/visa/%s/" % n
    if v["free"]:
        title = f"{c['name']} 비자 — 무비자 {v['stay']} (한국 일반여권)"
        lead = f"<p class=\"lead\">{visa_sentence(c)} 입국 목적이 관광·단기 방문일 때의 기준이며 취업·유학·장기 체류는 별도 비자가 필요합니다.</p>"
    else:
        title = f"{c['name']} 비자 — 무비자 입국 불가 (사전 비자 필요)"
        lead = f"<p class=\"lead\">{visa_sentence(c)} 도착비자(공항 발급)나 전자비자(e-Visa) 제도가 있는 나라도 있으니 해당국 공식 이민청·대사관 안내를 확인하세요.</p>"
    rows = [["일반여권 무비자 체류", esc(v["stay"]) if v["stay"] and v["stay"] != "X" else "불가(비자 필요)"], ["무비자 근거", esc(v["basis"] or "-")]]
    if v["remark"]: rows.append(["참고(비고)", esc(v["remark"].replace("\\n", " "))])
    t = table(["항목", "내용"], rows)
    eta = ('<div class="note-box"><b>입국 전 온라인 절차:</b> %s — %s</div>' % (esc(c["eta"][0]), esc(c["eta"][1]))) if c["eta"] else ""
    body = f"""
<div class="page-head"><h1>{esc(c['name'])} 비자 — 한국인 무비자 입국 정보</h1><p>입국허가요건 · 일반여권 기준 · 외교부 공공데이터</p></div>
{lead}
{ad()}
{t}
{eta}
<h2 class="group-title">📌 입국 전 확인할 것</h2>
<ul class="lead" style="margin-left:20px"><li>여권 유효기간: 입국일 기준 최소 3~6개월 이상 남아 있어야 하는 나라가 많습니다.</li><li>왕복 항공권(제3국행 포함)과 체류지 정보를 요구할 수 있습니다.</li><li>무비자 체류일수는 입국한 날부터 계산하며, 초과 체류는 벌금·입국 금지 사유가 됩니다.</li><li>정책은 한시 시행·상호주의 조건 변경이 잦으므로 출발 직전 공식 안내를 확인하세요.</li></ul>
{country_links(c)}
{chips([("무비자 입국 국가 전체", "/visa-free/"), ("비자가 필요한 나라", "/visa-needed/")])}
"""
    faq = [(f"{c['name']} 가려면 비자가 필요한가요?", visa_sentence(c).replace("<b>", "").replace("</b>", "")),
           (f"{c['name']} 무비자로 며칠까지 있을 수 있나요?", (f"한국 일반여권 기준 {v['stay']}까지입니다." if v["free"] else "무비자 체류가 허용되지 않습니다.")),
           ("무비자 입국 정보는 정확한가요?", "외교부가 공공데이터로 제공하는 입국허가요건을 바탕으로 합니다. 정책이 수시로 바뀌므로 출국 전 대사관·공식 사이트에서 다시 확인하세요.")]
    write(path, layout(path, title, f"{c['name']} 한국인 비자 정보. " + (f"일반여권으로 {v['stay']} 무비자 입국 가능." if v["free"] else "무비자 입국 불가, 사전 비자 필요.") + " 입국 전 준비사항과 확인 방법.", body, faq, crumb_country(c, ("비자", path))), "0.7")

def page_time(c):
    n = slug(c); path = "/time/%s/" % n
    if c["off_w"] is None: return
    d = diff_txt(c["off_w"])
    dst = c["off_s"] != c["off_w"]
    rows = [["기준 도시/시간대", esc(c["tz"].replace("_", " ")) + (" (UTC%s)" % fm(c["off_w"]))], ["겨울(1월) 시차", diff_txt(c["off_w"])], ["여름(7월) 시차", diff_txt(c["off_s"])], ["한국 낮 12시", clock_example(c["off_w"]).replace("한국 낮 12시 = ", "")]]
    t = table(["항목", "내용"], rows)
    body = f"""
<div class="page-head"><h1>{esc(c['name'])} 시차 — 한국과 몇 시간 차이?</h1><p>{esc(c['tz'].replace('_', ' '))} 시간대 기준</p></div>
<p class="lead"><b>{esc(c['name'])}은(는) {d}.</b> {clock_example(c['off_w'])}입니다.{(' 여름 시간제(서머타임)가 적용되는 기간에는 ' + diff_txt(c['off_s']).replace('한국보다 ', '한국보다 ') + '.') if dst else ' 서머타임이 없어 연중 시차가 같습니다.'}{' 국토가 넓어 지역에 따라 시간대가 여러 개이며 이 페이지는 대표 지역 기준입니다.' if c['iso'] in ('RU','US','BR','CA','AU','MX','CN','ID','KZ','AR','CL') else ''}</p>
{ad()}
{t}
{country_links(c)}
{chips([("전체 시차표", "/time-difference/")])}
"""
    faq = [(f"{c['name']} 시차는 몇 시간인가요?", d + "."), (f"{c['name']}에 서머타임이 있나요?", "있습니다. 여름철에는 시차가 달라집니다." if dst else "없습니다. 연중 시차가 같습니다.")]
    write(path, layout(path, f"{c['name']} 시차 — 한국보다 {('%g' % abs(c['off_w'] - 9))}시간 {'느림' if c['off_w'] < 9 else '빠름' if c['off_w'] > 9 else '(같은 시각)'}" if c["off_w"] != 9 else f"{c['name']} 시차 — 한국과 같은 시각",
          f"{c['name']} 시차: {d}. 서머타임 여부와 한국 시각 대비 현지 시각 계산법.", body, faq, crumb_country(c, ("시차", path))), "0.6")

def page_plug(c):
    n = slug(c); path = "/plug/%s/" % n
    p = c["plug"]
    if not p: return
    types = p["types"].split(",")
    t = table(["항목", "내용"], [["전압", "%sV" % p["v"]], ["주파수", "%sHz" % p["hz"]], ["플러그 타입", esc(", ".join(types))], ["한국 제품(220V)", "변압기 필요(전압이 다름)" if isinstance(p["v"], int) and p["v"] < 200 else "전압 호환(어댑터만)" if not str(p["v"]).startswith("127/") else "지역별 전압 확인"]])
    td = table(["타입", "모양"], [[tp, esc(PLUG_DESC.get(tp, ""))] for tp in types])
    body = f"""
<div class="page-head"><h1>{esc(c['name'])} 전압·콘센트 — 플러그 타입 {esc('·'.join(types))}</h1><p>{p['v']}V · {p['hz']}Hz</p></div>
<p class="lead">{plug_sentence(c)} 한국에서 쓰는 전자제품(220V·60Hz, C·F 타입)을 가져갈 때는 아래 표를 참고하세요.</p>
{ad()}
{t}
<h2 class="group-title">🔌 플러그 타입 설명</h2>
{td}
<ul class="lead" style="margin-left:20px"><li>스마트폰·노트북·카메라 충전기는 보통 100–240V 겸용이라 어댑터만 있으면 됩니다.</li><li>헤어드라이어·고데기 등 열을 내는 제품은 220V 전용이 많아 110V 국가에서는 변압기가 필요하고 용량(W) 확인이 중요합니다.</li><li>숙소에서 멀티 어댑터나 USB 충전 포트를 제공하는지 미리 확인하면 짐을 줄일 수 있습니다.</li></ul>
{country_links(c)}
{chips([("전압·플러그 전체", "/voltage/")] + [(f"{tp}타입 콘센트 국가", f"/plug-type/{tp}/") for tp in types])}
"""
    faq = [(f"{c['name']} 전압은 몇 V인가요?", f"{p['v']}V, 주파수 {p['hz']}Hz입니다."), (f"{c['name']} 콘센트는 어떤 타입인가요?", f"{', '.join(types)}타입을 씁니다."),
           (f"{c['name']}에 한국 전자제품을 써도 되나요?", re.sub(r"<[^>]+>", "", plug_sentence(c)))]
    write(path, layout(path, f"{c['name']} 전압·콘센트 — {p['v']}V, {'·'.join(types)}타입 플러그", f"{c['name']} 전압 {p['v']}V·{p['hz']}Hz, 플러그 {'·'.join(types)}타입. 한국 제품 사용 가능 여부와 변압기·어댑터 준비.", body, faq, crumb_country(c, ("전압·플러그", path))), "0.6")

def page_safety(c):
    n = slug(c); path = "/safety/%s/" % n
    L = max_level(c)
    rows = []
    for a in sorted(c["alarm"], key=lambda a: -a["lvl"]):
        nm, desc = LEVEL.get(a["lvl"], ("", ""))
        rows.append(["%d단계 %s" % (a["lvl"], nm), esc(a["region"]), esc(a["remark"] or "-")])
    t = table(["경보 단계", "범위", "해당 지역"], rows) if rows else '<p class="lead">현재 이 나라에 발령된 여행경보가 목록에 없습니다.</p>'
    legend = table(["단계", "명칭", "의미"], [["%d단계" % k, nm, esc(d)] for k, (nm, d) in LEVEL.items()])
    body = f"""
<div class="page-head"><h1>{esc(c['name'])} 여행경보 — {('최고 %d단계 %s' % (L, LEVEL[L][0])) if L else '경보 없음'}</h1><p>외교부 여행경보 제도 · 공공데이터 기준</p></div>
<p class="lead">{alarm_sentence(c)} 아래는 외교부가 발령한 지역별 경보입니다. 경보는 정세 변화에 따라 수시로 바뀌므로 출국 전 <a href="https://www.0404.go.kr" rel="nofollow noopener" target="_blank">외교부 해외안전여행(0404.go.kr)</a>에서 최신 상태를 확인하세요.</p>
{ad()}
{t}
<h2 class="group-title">📖 여행경보 단계 설명</h2>
{legend}
{country_links(c)}
{chips([("여행경보 국가 전체", "/travel-warning/")])}
<div class="note-box">공공데이터 갱신 시점에 따라 최신 경보와 차이가 있을 수 있습니다. 특별여행주의보 등 단기 경보는 반영되지 않을 수 있습니다.</div>
"""
    faq = [(f"{c['name']} 여행경보 단계는?", re.sub(r"<[^>]+>", "", alarm_sentence(c))), ("여행경보 단계는 무슨 뜻인가요?", "1단계 여행유의, 2단계 여행자제, 3단계 출국권고, 4단계 여행금지입니다. 4단계 지역은 여권법에 따라 방문이 금지됩니다."),
           ("가장 최신 경보는 어디서 확인하나요?", "외교부 해외안전여행 사이트(0404.go.kr)와 앱에서 확인할 수 있습니다.")]
    write(path, layout(path, f"{c['name']} 여행경보 — " + (f"최고 {L}단계 {LEVEL[L][0]}" if L else "경보 없음"), f"{c['name']} 여행경보 단계와 해당 지역. " + re.sub(r"<[^>]+>", "", alarm_sentence(c)), body, faq, crumb_country(c, ("여행경보", path))), "0.7")

# ───────────────────────── 허브 ─────────────────────────
def lnk(c, sec="country"): return '<a href="/%s/%s/">%s</a>' % (sec, slug(c), esc(c["name"]))

def hub_visa_free(cs):
    free = sorted([c for c in cs if c["visa"]["free"]], key=lambda c: (-stay_num(c["visa"]["stay"]), c["name"]))
    groups = collections.defaultdict(list)
    for c in free: groups[c["visa"]["stay"]].append(c)
    big = [k for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1])) if len(v) >= 4 and len(k) <= 12]
    rows = [[lnk(c, "visa"), esc(c["cont"]), esc(c["visa"]["stay"]), esc(c["visa"]["basis"] or "-")] for c in free]
    t = table(["국가", "지역", "무비자 체류", "근거"], rows)
    n90 = len(groups.get("90일", []))
    body = f"""
<div class="page-head"><h1>한국인 무비자 입국 가능 국가 {len(free)}곳 (체류 기간별)</h1><p>일반여권 · 외교부 입국허가요건 기준</p></div>
<p class="lead">한국 일반여권으로 비자 없이 입국할 수 있는 나라는 외교부 자료 기준 <b>{len(free)}개국</b>이며 이 중 <b>90일</b> 체류가 가능한 나라가 {n90}곳입니다. 체류 기간을 눌러 같은 기간의 국가 목록을 보거나 국가를 눌러 자세한 입국 정보를 확인하세요.</p>
{chips([(f"무비자 {k} ({len(groups[k])}곳)", f"/visa-free/{k}/") for k in big])}
{ad()}
{t}
{chips([("비자가 필요한 나라", "/visa-needed/")])}
<div class="note-box">무비자 정책은 상호주의·한시 시행 조건이 바뀔 수 있습니다. 출국 전 대사관·공식 사이트에서 확인하세요.</div>
"""
    write("/visa-free/", layout("/visa-free/", f"한국인 무비자 입국 가능 국가 {len(free)}곳 — 체류 기간별 목록", f"한국 일반여권 무비자 입국 가능 국가 {len(free)}곳. 90일·30일·60일 등 체류 기간별 국가 목록과 입국 전 확인사항.", body,
        [("한국인은 몇 개 나라에 무비자로 갈 수 있나요?", f"외교부 입국허가요건 기준 {len(free)}개국입니다(관광 목적, 일반여권)."), ("90일 무비자 국가는 어디인가요?", f"{', '.join(c['name'] for c in groups.get('90일', [])[:12])} 등 {n90}곳입니다.")],
        [("홈", "/"), ("무비자 국가", "/visa-free/")], coupang=True), "0.9")
    for k in big:
        lst = groups[k]
        rows = [[lnk(c, "visa"), esc(c["cont"]), esc(c["visa"]["basis"] or "-")] for c in sorted(lst, key=lambda c: c["name"])]
        body = f"""
<div class="page-head"><h1>무비자 {esc(k)} 체류 가능 국가 {len(lst)}곳</h1><p>한국 일반여권 · 외교부 기준</p></div>
<p class="lead">한국 일반여권으로 <b>{esc(k)}</b> 동안 무비자 체류가 가능한 나라는 {len(lst)}곳입니다: {esc(', '.join(c['name'] for c in lst[:10]))}{' 등' if len(lst) > 10 else ''}.</p>
{ad()}
{table(['국가', '지역', '근거'], rows)}
{chips([("무비자 국가 전체", "/visa-free/")])}
"""
        p = "/visa-free/%s/" % k
        write(p, layout(p, f"무비자 {k} 체류 가능 국가 {len(lst)}곳 (한국 일반여권)", f"한국인이 비자 없이 {k} 동안 머물 수 있는 나라 {len(lst)}곳 목록.", body, None, [("홈", "/"), ("무비자 국가", "/visa-free/"), (f"무비자 {k}", p)]), "0.7")
    need = sorted([c for c in cs if not c["visa"]["free"]], key=lambda c: c["name"])
    body = f"""
<div class="page-head"><h1>비자가 필요한 나라 {len(need)}곳 (한국 일반여권)</h1><p>무비자 입국이 불가한 국가</p></div>
<p class="lead">외교부 자료 기준 한국 일반여권으로 무비자 입국이 불가한 나라는 <b>{len(need)}곳</b>입니다. 일부 국가는 도착비자·전자비자 제도가 있어 입국 전 절차가 간단할 수 있으니 국가별 페이지와 공식 사이트에서 확인하세요.</p>
{ad()}
{table(['국가', '지역'], [[lnk(c, 'visa'), esc(c['cont'])] for c in need])}
{chips([("무비자 국가 전체", "/visa-free/")])}
"""
    write("/visa-needed/", layout("/visa-needed/", f"비자가 필요한 나라 {len(need)}곳 — 한국인 무비자 입국 불가 국가", f"한국 일반여권으로 무비자 입국이 불가한 나라 {len(need)}곳 목록.", body, None, [("홈", "/"), ("비자 필요", "/visa-needed/")]), "0.7")

def hub_warning(cs):
    by = collections.defaultdict(list)
    for c in cs:
        L = max_level(c)
        by[L].append(c)
    body = f"""
<div class="page-head"><h1>여행경보 국가 목록 — 1~4단계</h1><p>외교부 여행경보 · 최고 단계 기준</p></div>
<p class="lead">외교부가 여행경보를 발령한 나라는 <b>{sum(len(v) for k, v in by.items() if k)}곳</b>이며 단계는 1 여행유의, 2 여행자제, 3 출국권고, 4 여행금지입니다. 일부 지역에만 발령된 경우 그 나라의 최고 단계로 분류했습니다. 단계를 눌러 국가 목록을 보세요.</p>
{chips([(f"{k}단계 {LEVEL[k][0]} ({len(by[k])}곳)", f"/travel-warning/{k}단계/") for k in (4, 3, 2, 1) if by.get(k)])}
{ad()}
{table(['단계', '의미', '국가 수'], [[f'<a href="/travel-warning/{k}단계/">{k}단계 {LEVEL[k][0]}</a>', esc(LEVEL[k][1]), f'{len(by[k])}곳'] for k in (4, 3, 2, 1) if by.get(k)])}
<div class="note-box">경보는 정세 변화에 따라 수시로 바뀌며 이 목록은 공공데이터 갱신 시점 기준입니다. 최신 정보는 외교부 해외안전여행(0404.go.kr)에서 확인하세요.</div>
"""
    write("/travel-warning/", layout("/travel-warning/", "여행경보 국가 목록 — 1단계 여행유의~4단계 여행금지", "외교부 여행경보 1~4단계 국가 목록과 단계별 의미. 출국 전 확인해야 할 여행경보 현황.", body, None, [("홈", "/"), ("여행경보", "/travel-warning/")], coupang=True), "0.9")
    for k in (4, 3, 2, 1):
        lst = sorted(by.get(k, []), key=lambda c: c["name"])
        if not lst: continue
        rows = []
        for c in lst:
            regs = [a for a in c["alarm"] if a["lvl"] == k]
            rows.append([lnk(c, "safety"), esc(c["cont"]), esc(regs[0]["region"]) if regs else "-", esc((regs[0]["remark"][:80] + ("…" if len(regs[0]["remark"]) > 80 else "")) if regs else "-")])
        p = "/travel-warning/%d단계/" % k
        body = f"""
<div class="page-head"><h1>여행경보 {k}단계({LEVEL[k][0]}) 국가 {len(lst)}곳</h1><p>{esc(LEVEL[k][1])}</p></div>
<p class="lead">최고 단계가 <b>{k}단계({LEVEL[k][0]})</b>인 나라는 {len(lst)}곳입니다: {esc(', '.join(c['name'] for c in lst[:12]))}{' 등' if len(lst) > 12 else ''}. 일부 지역에만 발령된 곳도 포함됩니다.</p>
{ad()}
{table(['국가', '지역', '범위', '해당 지역(일부)'], rows)}
{chips([("여행경보 전체", "/travel-warning/")])}
"""
        write(p, layout(p, f"여행경보 {k}단계({LEVEL[k][0]}) 국가 {len(lst)}곳 목록", f"외교부 여행경보 {k}단계 {LEVEL[k][0]} 국가 {len(lst)}곳과 해당 지역.", body, None, [("홈", "/"), ("여행경보", "/travel-warning/"), (f"{k}단계", p)]), "0.7")

def hub_time(cs):
    ok = sorted([c for c in cs if c["off_w"] is not None], key=lambda c: (c["off_w"], c["name"]))
    rows = [[lnk(c, "time"), esc(c["cont"]), diff_txt(c["off_w"]).replace("한국보다 ", ""), (diff_txt(c["off_s"]).replace("한국보다 ", "") if c["off_s"] != c["off_w"] else "같음")] for c in ok]
    body = f"""
<div class="page-head"><h1>세계 시차표 — 한국과 몇 시간 차이?</h1><p>국가별 시차 {len(ok)}곳 · 서머타임 반영</p></div>
<p class="lead">한국(UTC+9) 기준으로 국가별 시차를 정리했습니다. 국가를 누르면 자세한 시간 계산을 볼 수 있습니다. 여러 시간대가 있는 나라(미국·러시아·캐나다 등)는 대표 지역 기준입니다.</p>
{ad()}
{table(['국가', '지역', '겨울(1월) 시차', '여름(7월) 시차'], rows)}
"""
    write("/time-difference/", layout("/time-difference/", "세계 시차표 — 한국과 국가별 시차 (서머타임 포함)", f"한국 기준 {len(ok)}개국 시차표. 일본·미국·영국·태국 등 국가별 시차와 서머타임 여부.", body, None, [("홈", "/"), ("시차", "/time-difference/")]), "0.9")

def hub_voltage(cs):
    have = [c for c in cs if c["plug"]]
    low = sorted([c for c in have if isinstance(c["plug"]["v"], int) and c["plug"]["v"] < 200], key=lambda c: c["name"])
    mid = sorted([c for c in have if not (isinstance(c["plug"]["v"], int) and c["plug"]["v"] < 200)], key=lambda c: c["name"])
    tpc = collections.defaultdict(list)
    for c in have:
        for tp in c["plug"]["types"].split(","): tpc[tp].append(c)
    rows = [[lnk(c, "plug"), esc(c["cont"]), "%sV" % c["plug"]["v"], esc(c["plug"]["types"])] for c in sorted(have, key=lambda c: c["name"])]
    body = f"""
<div class="page-head"><h1>나라별 전압·콘센트 타입 총정리</h1><p>{len(have)}개국 · 110V 국가 vs 220V 국가</p></div>
<p class="lead">한국은 220V·60Hz에 C·F 타입 플러그를 씁니다. <b>100–127V를 쓰는 나라</b>는 일본·미국·캐나다·대만·멕시코 등 {len(low)}곳이고 나머지 {len(mid)}곳은 220–240V 계열입니다. 220V 계열 나라는 변압기 없이 플러그 어댑터만 있으면 되는 경우가 많습니다.</p>
{chips([("110V 국가 목록", "/voltage/110v/")] + [(f"{tp}타입", f"/plug-type/{tp}/") for tp in sorted(tpc)])}
{ad()}
{table(['국가', '지역', '전압', '플러그 타입'], rows)}
<div class="note-box">전압·플러그 정보는 일반적인 참고값이며 숙소·지역에 따라 다를 수 있습니다.</div>
"""
    write("/voltage/", layout("/voltage/", "나라별 전압·콘센트 타입 — 110V 국가와 플러그 A~O타입", f"{len(have)}개국 전압(V)·주파수와 플러그 타입 표. 일본·미국 110V, 유럽 220V 구분과 변압기·어댑터 준비.", body, None, [("홈", "/"), ("전압·플러그", "/voltage/")], coupang=True), "0.9")
    body = f"""
<div class="page-head"><h1>110V(100–127V) 전압을 쓰는 나라 {len(low)}곳</h1><p>변압기가 필요한 나라</p></div>
<p class="lead">한국 제품(220V)을 그대로 쓰면 고장 날 수 있는 100–127V 국가는 <b>{len(low)}곳</b>입니다: {esc(', '.join(c['name'] for c in low[:14]))}{' 등' if len(low) > 14 else ''}. 스마트폰 충전기처럼 100–240V 겸용 제품은 어댑터만 있으면 됩니다.</p>
{ad()}
{table(['국가', '전압', '주파수', '플러그'], [[lnk(c, 'plug'), '%sV' % c['plug']['v'], '%sHz' % c['plug']['hz'], esc(c['plug']['types'])] for c in low])}
{chips([("전압·플러그 전체", "/voltage/")])}
"""
    write("/voltage/110v/", layout("/voltage/110v/", f"110V 전압을 쓰는 나라 {len(low)}곳 — 일본·미국·캐나다·대만", f"100–127V를 쓰는 나라 {len(low)}곳과 변압기 필요 여부.", body, None, [("홈", "/"), ("전압·플러그", "/voltage/"), ("110V 국가", "/voltage/110v/")]), "0.7")
    for tp, lst in tpc.items():
        lst = sorted(lst, key=lambda c: c["name"])
        body = f"""
<div class="page-head"><h1>{tp}타입 콘센트를 쓰는 나라 {len(lst)}곳</h1><p>{esc(PLUG_DESC.get(tp, ''))}</p></div>
<p class="lead"><b>{tp}타입</b>은 {esc(PLUG_DESC.get(tp, ''))}입니다. 이 타입을 쓰는 나라는 {len(lst)}곳이며 {esc(', '.join(c['name'] for c in lst[:12]))}{' 등' if len(lst) > 12 else ''}이 있습니다.</p>
{ad()}
{table(['국가', '전압', '플러그 타입'], [[lnk(c, 'plug'), '%sV' % c['plug']['v'], esc(c['plug']['types'])] for c in lst])}
{chips([("전압·플러그 전체", "/voltage/")])}
"""
        p = "/plug-type/%s/" % tp
        write(p, layout(p, f"{tp}타입 콘센트 사용 국가 {len(lst)}곳 — {PLUG_DESC.get(tp, '')[:14]}", f"{tp}타입 플러그를 쓰는 나라 {len(lst)}곳과 전압.", body, None, [("홈", "/"), ("전압·플러그", "/voltage/"), (f"{tp}타입", p)]), "0.5")

def hub_country(cs):
    byc = collections.defaultdict(list)
    for c in cs: byc[c["cont"]].append(c)
    secs = ""
    for ct in ("아시아", "중동", "유럽", "미주", "오세아니아", "아프리카"):
        if ct not in byc: continue
        secs += f'<h2 class="group-title">🌏 {ct} ({len(byc[ct])}곳)</h2><div class="chips">%s</div>' % "".join('<a class="chip" href="/country/%s/">%s</a>' % (slug(c), esc(c["name"])) for c in sorted(byc[ct], key=lambda c: c["name"]))
    body = f"""
<div class="page-head"><h1>국가별 여행 정보 — 비자·시차·전압·여행경보</h1><p>{len(cs)}개국</p></div>
<p class="lead">외교부 공공데이터를 바탕으로 {len(cs)}개국의 입국 비자(무비자 여부), 여행경보, 시차, 전압·플러그, 통화를 정리했습니다. 국가를 눌러 확인하세요.</p>
{ad()}
{secs}
"""
    write("/country/", layout("/country/", f"국가별 여행 정보 — {len(cs)}개국 비자·시차·전압·여행경보", f"{len(cs)}개국 여행 정보. 한국인 무비자 입국, 여행경보 단계, 시차, 전압·플러그, 통화를 국가별로 확인.", body, None, [("홈", "/"), ("국가별", "/country/")]), "0.9")

def page_home(cs):
    pop = ["일본", "태국", "베트남", "미국", "중국", "대만", "필리핀", "싱가포르", "프랑스", "영국", "이탈리아", "스페인", "튀르키예", "호주", "캐나다", "인도네시아"]
    byn = {c["name"]: c for c in cs}
    cards = "".join('<a class="card" href="/country/%s/"><b>%s</b><span>%s · %s</span></a>' % (n, n, ("무비자 " + byn[n]["visa"]["stay"]) if byn[n]["visa"]["free"] else "비자 필요", (diff_txt(byn[n]["off_w"]).replace("한국보다 ", "시차 ") if byn[n]["off_w"] is not None else "")) for n in pop if n in byn)
    free = sum(1 for c in cs if c["visa"]["free"])
    body = f"""
<div class="hero"><h1>✈️ 해외여행 국가 정보</h1><p>한국인 무비자 입국, 여행경보, 시차, 전압·플러그를 {len(cs)}개국 한곳에서 확인하세요.</p>
<div class="search-box"><input id="q" type="search" placeholder="국가 이름을 입력하세요 (예: 일본, 태국)" autocomplete="off"><div class="sr-list" id="sr"></div></div></div>
{ad()}
<h2 class="group-title">🔥 인기 여행지</h2>
<div class="card-grid">{cards}</div>
<h2 class="group-title">🧭 주제별 모아보기</h2>
<div class="card-grid">
<a class="card" href="/visa-free/"><b>무비자 입국 {free}개국</b><span>체류 기간별 목록</span></a>
<a class="card" href="/travel-warning/"><b>여행경보 국가</b><span>1~4단계</span></a>
<a class="card" href="/time-difference/"><b>세계 시차표</b><span>서머타임 포함</span></a>
<a class="card" href="/voltage/"><b>전압·콘센트</b><span>110V·플러그 A~O</span></a>
<a class="card" href="/country/"><b>국가별 전체</b><span>{len(cs)}개국</span></a>
</div>
<p class="lead">우아여행은 외교부 공공데이터(입국허가요건·여행경보)와 참고 정보를 바탕으로 해외여행 전에 확인할 비자, 시차, 전압·플러그, 통화, 여행경보를 국가별로 정리한 사이트입니다. 정책은 수시로 바뀌므로 출국 전 공식 사이트에서 다시 확인하세요. 자세한 내용은 <a href="/about/">데이터 설명</a>을 참고하세요.</p>
<script src="/assets/js/search.js"></script>
"""
    faq = [("한국인은 비자 없이 몇 개 나라에 갈 수 있나요?", f"외교부 입국허가요건 기준 관광 목적 일반여권으로 {free}개국입니다."), ("여행경보는 어디서 확인하나요?", "외교부 해외안전여행(0404.go.kr)에서 최신 경보를 확인하세요. 이 사이트는 공공데이터 기준이라 갱신 시차가 있을 수 있습니다."),
           ("전압이 다른 나라에서는 어떻게 하나요?", "일본·미국 등 110V 국가에서는 220V 전용 제품에 변압기가 필요합니다. 스마트폰 충전기 등은 대부분 100–240V 겸용이라 플러그 어댑터만 있으면 됩니다.")]
    write("/", layout("/", "우아여행 — 한국인 무비자 입국·여행경보·시차·전압 (해외여행 국가 정보)", f"해외여행 전에 확인할 한국인 무비자 입국, 여행경보, 시차, 전압·플러그를 {len(cs)}개국 기준으로 정리했습니다(외교부 공공데이터).", body, faq), "1.0")

def page_about():
    body = """
<div class="page-head"><h1>데이터 설명</h1><p>출처와 한계</p></div>
<h2 class="group-title">📚 출처</h2>
<p class="lead">입국허가요건·여행경보는 공공데이터포털의 외교부 「국가·지역별 입국허가요건」, 「국가·지역별 여행경보」 API를, 수교·교민·교역 정보는 외교부 「국가(지역)별 우리나라와의 관계」 파일 데이터를 사용했습니다. 시차는 IANA 시간대 데이터로 계산했고, 수도·통화·언어·국가번호는 공개 국가 정보 라이브러리를 바탕으로 정리했습니다. 전압·플러그·전자여행허가 안내는 일반적으로 알려진 정보를 직접 정리한 참고값입니다.</p>
<h2 class="group-title">⚠️ 한계</h2>
<p class="lead">① 입국 조건과 여행경보는 수시로 바뀌며 공공데이터 갱신에는 시차가 있습니다. ② 무비자 체류일수는 관광·단기 방문 목적의 일반여권 기준이며 여권 잔여 유효기간, 왕복 항공권, 입국신고 등 추가 조건이 있을 수 있습니다. ③ 여행경보 목록에는 특별여행주의보 등 단기 조치가 반영되지 않을 수 있습니다. ④ 시차는 국가의 대표 지역 기준이며 서머타임은 2027년 일정으로 계산했습니다. ⑤ 전압·플러그는 참고값입니다. <b>출국 전에 외교부 해외안전여행(0404.go.kr), 해당국 대사관·이민청, 항공사 안내로 반드시 다시 확인하세요.</b></p>
<h2 class="group-title">📬 문의·정정</h2>
<p class="lead">오류 제보는 <a href="mailto:ingmaster83@gmail.com">ingmaster83@gmail.com</a> 으로 보내 주세요.</p>
"""
    write("/about/", layout("/about/", "데이터 설명 — 출처와 한계", "우아여행이 사용하는 외교부 공공데이터의 출처와 정보의 한계, 출국 전 확인 방법.", body, None, [("홈", "/"), ("데이터 설명", "/about/")]), "0.5")

def page_privacy():
    body = """
<div class="page-head"><h1>개인정보처리방침</h1></div>
<p class="lead">우아여행(wooatrip.wooahouse.com, 이하 “서비스”)은 회원가입·로그인을 요구하지 않으며 이용자의 개인정보를 직접 수집하지 않습니다.</p>
<h3>자동 수집 정보</h3><p class="lead">서비스 개선을 위해 Google Analytics로 방문자 수·페이지뷰 등 익명 통계를 수집하며, Google AdSense와 쿠팡 파트너스는 맞춤 광고를 위해 쿠키를 사용할 수 있습니다. 쿠키는 브라우저 설정에서 비활성화할 수 있습니다. (<a href="https://policies.google.com/privacy">Google 개인정보처리방침</a>, <a href="https://policies.google.com/technologies/ads">Google 광고 정책</a>)</p>
<h3>쿠팡 파트너스</h3><p class="lead">일부 페이지에는 쿠팡 파트너스 활동의 일환으로 광고가 포함되어 있으며 이에 따른 수수료를 제공받을 수 있습니다.</p>
<h3>문의</h3><p class="lead"><a href="mailto:ingmaster83@gmail.com">ingmaster83@gmail.com</a></p>
<p class="note">최종 수정일: 2026년 10월 19일</p>
"""
    write("/privacy/", layout("/privacy/", "개인정보처리방침", "우아여행 개인정보처리방침", body, None, [("홈", "/"), ("개인정보처리방침", "/privacy/")]), sitemap=False)

def make_og():
    f = ROOT / "assets" / "og-image.png"
    if f.exists(): return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return
    im = Image.new("RGB", (1200, 630), (14, 116, 144)); dr = ImageDraw.Draw(im)
    def font(sz):
        for n in ("malgunbd.ttf", "malgun.ttf", "NanumGothicBold.ttf"):
            try: return ImageFont.truetype(n, sz)
            except Exception: pass
        return ImageFont.load_default()
    dr.rounded_rectangle((90, 90, 1110, 540), 40, fill=(255, 255, 255))
    dr.text((150, 150), "우아여행", font=font(110), fill=(21, 94, 117))
    dr.text((150, 300), "무비자 · 여행경보 · 시차 · 전압", font=font(54), fill=(31, 41, 55))
    dr.text((150, 380), "해외여행 국가 정보 189개국", font=font(54), fill=(31, 41, 55))
    dr.text((150, 470), "wooatrip.wooahouse.com", font=font(34), fill=(107, 114, 128))
    im.save(f)

def main():
    t0 = time.time(); make_og()
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    cs = json.load(open(ROOT / "_data" / "countries.json", encoding="utf-8"))
    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    for nf in ROOT.glob("naver*.html"): shutil.copy(nf, OUT / nf.name)
    (OUT / "assets" / "search.json").write_text(json.dumps([[c["name"], slug(c), c["en"], c["cont"]] for c in cs], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    byname = {c["name"]: c for c in cs}
    for c in cs:
        page_country(c, byname); page_visa(c); page_time(c); page_plug(c); page_safety(c)
    hub_country(cs); hub_visa_free(cs); hub_warning(cs); hub_time(cs); hub_voltage(cs)
    page_home(cs); page_about(); page_privacy()
    today = time.strftime("%Y-%m-%d")
    urls = "".join("<url><loc>%s%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>" % (BASE, q(p), today, pr) for p, pr in WRITTEN)
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>\n' % urls, encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % BASE, encoding="utf-8")
    (OUT / "CNAME").write_text("wooatrip.wooahouse.com\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    nf = layout("/404.html", "페이지를 찾을 수 없습니다", "요청한 페이지를 찾을 수 없습니다.", '<div class="page-head"><h1>페이지를 찾을 수 없습니다</h1></div><div class="chips"><a class="chip" href="/">홈</a><a class="chip" href="/country/">국가별</a></div>', None, None, noindex=True)
    (OUT / "404.html").write_text(nf, encoding="utf-8")
    print("countries", len(cs), "pages", len(WRITTEN), "elapsed", round(time.time() - t0), "s")

if __name__ == "__main__":
    main()
