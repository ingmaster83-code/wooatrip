# 우아여행 생성 스크립트

외교부 공공데이터(data.go.kr, 활용신청 필요) + 참고 표 → 정적 사이트.

1. `python scripts/fetch_mofa.py` — 입국허가요건(`1262000/EntranceVisaService2/getEntranceVisaList2`)·여행경보(`TravelAlarmService2/getTravelAlarmList2`)·국가별 안전정보(`CountrySafetyService/getCountrySafetyList`, 사이트에서는 미사용: 최신 공지가 2024-07로 멈춰 있음) 수집 → `data/raw/`. 키: `DATA_GO_KR_API_KEY` 또는 `../hosppass/.env`. 한국과의 관계 CSV(15076562)는 `data/raw/relations.csv`.
2. `python scripts/build_data.py` — `_data/countries.json`(로컬 전용: `pip install countryinfo babel tzdata`). 수도(한글)·전압/플러그·전자여행허가 표는 `scripts/tables.py`에서 수정.
3. `python scripts/build_site.py` — `_site/`(약 1초, 913페이지). 배포는 GitHub Actions가 `_data`만으로 빌드.

- 입국 조건·여행경보는 수시로 바뀌므로 정기적으로 1→2→커밋(자동화 안 함). 시차는 2027년 서머타임 기준.
- 점검: `check_site.py`, `peek.py <경로>`.
