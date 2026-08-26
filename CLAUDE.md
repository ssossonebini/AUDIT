# AUDIT — 회계감사 중점심사사항 아카이브

회계감사에 영향을 주는 국내외 규제기관 발표자료를 수집·정리하고, 이를 바탕으로
회사별 감사위험 분석과 카드뉴스를 제작하기 위한 프로젝트.

---

## 핵심 설계 원칙

### 1. 역할 분담 — 웹호스트는 수집, Claude Code는 분석

| 계층 | 담당 | 하는 일 |
|---|---|---|
| 로컬 웹호스트 | FastAPI + React | 크롤링 · PDF 수집 · 저장 · 대량 필터링 |
| Claude Code | 이 도구 | 심층 분석 · 카드뉴스 제작 |

**웹호스트의 AI는 "많은 것을 걸러내는" 용도로만 사용한다. "깊이 읽는" 작업은 Claude Code가 담당한다.**

- ✅ 유지: `audit_news`의 AI 분류 — 수백 건 보도자료를 기계적으로 선별 (Haiku, 건당 ~$0.001)
- ❌ 제거됨: AI PDF 요약 — Claude Code와 중복이며 품질이 낮았음 (2026-08 삭제)

### 2. `raw_text`는 절대 보존한다

`raw_text`(PDF 전문)와 `pdf_path`는 이 프로젝트의 실질적 자산이다.
분석은 전부 `raw_text`를 읽어서 수행하므로, 어떤 리팩터링에서도 다음을 유지해야 한다.

- PDF 다운로드 (`app/crawler/*_scraper.py`의 `download_pdf()`)
- 텍스트 추출 (`app/crawler/pdf_parser.py`의 `extract_text()`)
- **크롤링 시점** 저장 (`app/crawler/pdf_ingest.py` 경유) — 사용자 클릭에 의존하지 말 것
- `raw_text` · `pdf_path` 컬럼

각 모델의 `has_raw_text` 속성으로 수집 여부를 UI에 노출한다.

---

## 프로젝트 구조

```
AUDIT/
├── app/
│   ├── main.py                 # FastAPI 엔트리 (startup 시 init_db)
│   ├── core/config.py          # 설정 (.env → ANTHROPIC_API_KEY)
│   ├── db/
│   │   ├── database.py         # SQLite: sqlite:///./audit.db
│   │   └── models.py           # 8개 테이블
│   ├── schemas/                # Pydantic 스키마 (소스별)
│   ├── api/routes/             # 소스별 라우터
│   └── crawler/
│       ├── *_scraper.py        # 소스별 크롤러
│       ├── pdf_parser.py       # PDF → 텍스트
│       └── pdf_ingest.py       # 다운로드+추출 공통 헬퍼
├── frontend/src/
│   ├── App.jsx                 # 탭 라우팅 (6개 뷰)
│   ├── api/                    # axios 모듈 (소스별)
│   └── components/             # Card / Detail / CrawlPanel + SourcePanel
├── audit.db                    # ⚠️ gitignore — 로컬에만 존재
├── downloads/                  # ⚠️ gitignore — 수집된 PDF
└── workspace/                  # ⚠️ gitignore — 회사별 작업폴더·카드뉴스
```

---

## 데이터 소스 (6개 탭)

| 탭 | API prefix | 테이블 | 비고 |
|---|---|---|---|
| 🇰🇷 금감원 중점심사 | `/api/v1/fss` | `fss_articles` + `audit_issues` | 이슈 구조화 파싱 |
| 🇰🇷 금감원 지적사례 | `/api/v1/fss-case` | `fss_case_reports` | 회계심사·감리 |
| 📐 KASB | `/api/v1/kasb` | `kasb_standards` | K-IFRS 제·개정, 403 시 seed |
| 🇺🇸 PCAOB | `/api/v1/pcaob` | `pcaob_publications` | 영문 |
| 🇪🇺 ESMA | `/api/v1/esma` | `esma_reports` | ECEP, 403 시 seed |
| 📰 감사 보도자료 | `/api/v1/audit-news` | `audit_news_reports` + `crawl_history` | FSS+FSC, AI 분류 |
| 🏢 회사 프로젝트 | `/api/v1/company` | `companies` + `financial_statements` + `disclosure_items` + `disclosure_filings` + `company_news` | DART 재무제표·공시 + 뉴스 |

### 감사 보도자료의 증분 크롤링

`crawl_history` 테이블이 소스별 마지막 수집일(`last_sdate`)을 보관한다.
다음 크롤링은 그 날짜부터만 조회하므로 2025-01-01 전체를 재수집하지 않는다.
안전장치로 기존 `ntt_id`를 만나면 즉시 중단한다.

`ntt_id`는 `FSS-{id}` / `FSC-{id}` 형식으로 접두사를 붙여 충돌을 막는다.

---

## 실행 방법

`start.bat` 을 더블클릭하면 audit.db 를 백업한 뒤 백엔드·프론트엔드·Claude Code
세 창을 함께 띄운다 (Claude Code 는 설치돼 있을 때만).
백업은 3세대(`audit.db.bak` / `.bak2` / `.bak3`)를 돌린다 — 사본이 하나뿐이면
DB가 비어버린 뒤 서버를 다시 켰을 때 그 빈 DB가 멀쩡한 백업을 덮어쓴다.

수동으로 띄우려면:

**백엔드** (CMD 창 1)
```cmd
cd C:\Users\kwony\AUDIT
python -m uvicorn app.main:app --reload
```

**프론트엔드** (CMD 창 2)
```cmd
cd C:\Users\kwony\AUDIT\frontend
npm run dev
```

접속: http://localhost:3000 (Vite가 `/api` → `localhost:8000` 프록시)

> 다른 PC에서 접속하려면 양쪽에 `--host` 추가
> (`uvicorn ... --host 0.0.0.0`, `npm run dev -- --host`)

**테스트**
```cmd
python -m pytest tests/ -q
```

테스트는 실제 `audit.db` 와 **네트워크를 모두 차단한 상태**로 돈다
(`tests/conftest.py`). 대역을 빠뜨리면 조용히 진짜 API 를 부르는 대신
`NetworkAccessInTests` 로 즉시 실패한다 — 키가 없는 환경에서만 통과하고
로컬에서만 깨지는 사고를 한 번 겪었다.

---

## 분석 작업 (Claude Code에서)

`audit.db`와 `downloads/`는 **로컬 PC에만 존재**한다 (gitignore).
클라우드/웹 세션에서는 접근할 수 없으므로, 데이터 분석은 로컬 Claude Code에서 수행한다.

전형적인 요청:
```
audit.db 에 어떤 데이터가 얼마나 들어있는지 확인해줘
audit.db 의 중점심사 회계이슈와 지적사례로 감사인용 카드뉴스 10장 만들어줘
```

분석 시 `raw_text`를 직접 읽는다. 요약본이 아니라 원문을 근거로 판단할 것.

---

## 향후 계획

작업 프로세스: **자료수집 → 감사영향 분석 → 카드뉴스 제작**

### 추가 예정 기능

| # | 기능 | 내용 |
|---|---|---|
| 1 | 회사 프로젝트 관리 | `workspace/{연도}_{회사명}/` 폴더 자동 생성 |
| 2 | DART 재무제표 수집 | ✅ **완료** — 3개년 재무제표. 공시 수집은 아래 2·3단계 |
| 3 | 뉴스 크롤링 | ✅ **완료** — Google News RSS (키 불필요) |
| 4 | 분석자료 내보내기 | ✅ **완료** — `00_INPUT.md` 생성 → Claude Code 진입점 |
| 5 | PDF 일괄 다운로드 | 목록에서 한 번에 (개별 `download_pdf()` 반복) |

### OPEN DART 연동 — 검증 완료된 사실

`DART_API_KEY`는 `.env`에서 읽는다 (`app/core/config.py`).

**3개년 재무제표는 사업보고서 1회 호출로 끝난다.**

```
fnlttSinglAcntAll.json
  corp_code, bsns_year, reprt_code=11011(사업보고서), fs_div=CFS|OFS(필수)
  → thstrm_amount(당기) · frmtrm_amount(전기) · bfefrmtrm_amount(전전기)
```

연도별로 3회 호출할 필요가 없다. 다만 다음 네 가지를 지켜야 한다.

- `bfefrmtrm_*`는 **사업보고서에만** 나온다. 분기·반기(11013/11012/11014)에는
  키 자체가 없으므로 `it.get("bfefrmtrm_amount", "")`로 접근한다 (`[]`는 KeyError).
- 분기 손익계산서는 `frmtrm_amount`가 아니라 `frmtrm_q_amount`를 쓴다.
  `sj_div`(BS/IS/CIS/CF/SCE)별로 읽을 필드가 다르다.
- 분기 IS/CIS의 `thstrm_amount`는 3개월 금액이다. 누적은 `thstrm_add_amount`.
- 자본변동표(SCE)는 사업보고서에서도 전기·전전기 일부가 빈다. 정상이다.

데이터는 2015년 이후만 제공된다.

**남은 단계** — 공시 수집은 아직이다.

| 단계 | 범위 | 상태 |
|---|---|---|
| 2 | 정기보고서 주요정보 8종 (`dart_client.MAJOR_INFO_APIS`) | ✅ 완료 |
| 3 | 공시 목록 — `list.json`, 감사 시사점 태깅 | ✅ 완료 |

### 수집 대상 보고서 — 전기말 사업보고서 + 당기중 최신 분·반기보고서

재무제표와 원문은 **두 건**을 받는다. 사업보고서는 3개년 비교와 완전한 주석을
주지만 기말에 멈춰 있고, 중간보고서는 그 반대다. 어느 쪽도 다른 쪽을 대신하지
못한다 — 2026년 기말감사 위험평가를 2025-12-31 숫자로 할 수는 없다.

**어느 보고서를 낼지 판정하지 않는다.** `list.json` 의 정기공시(A) 목록에
실제로 제출된 것이 곧 그 회사의 공시 주기다 (`_periodic_reports()`).
분기를 내는 회사면 분기가, 반기만 내면 반기가 최신으로 잡힌다. 시점이 바뀌면
자동으로 따라간다 — 지금은 반기, 11월 중순 이후엔 3분기.

`parse_periodic_report(report_nm, fiscal_month)` 가 이름을 코드로 옮긴다.

- 「분기보고서」는 **1분기와 3분기가 같은 이름**이다. 괄호 안 기간 종료월이
  사업연도 개시 후 3개월이면 11013, 9개월이면 11014.
- 12월 결산이 아니면 회계연도가 두 역년에 걸치므로 사업연도 = 종료 연도 − 1.
  3월 결산의 「사업보고서 (2026.03)」은 사업연도 **2025** 다.

⚠️ **`financial_statements` 삭제 조건에 `reprt_code` 가 반드시 들어가야 한다.**
빼면 같은 해의 반기와 3분기가 서로를 지운다.

⚠️ **전기도 당기와 같은 기준으로 읽는다.** 분·반기 손익은 `thstrm_add_amount`
(당기 누적)와 `frmtrm_add_amount`(전기 누적)가 짝이다. 당기만 누적으로 읽고
전기를 `frmtrm_q_amount`(3개월)로 읽으면 전년 동기 대비가 **조용히** 어긋난다.
반기라면 두 배로 벌어진다.

중간보고서에 기대를 정확히 걸 것.

| | 사업보고서 | 분·반기보고서 |
|---|---|---|
| 확신 수준 | 감사 | **검토** — 감사증거로 쓸 수 없다 |
| 주석 | 전체 명세 | K-IFRS 1034 — 직전 연차 이후 **변동만** |
| 전전기 | 있음 | 키 자체가 없음 |
| 첨부 | 감사보고서 | 검토보고서 |

`00_INPUT.md` 와 화면 모두 두 보고서를 갈라서 보여준다. 섞으면 같은 계정이
두 번 나와 어느 시점 값인지 알 수 없다.

**주요정보는 날짜가 아니라 사업연도로 조회된다.** "직전 회계연도 개시일 ~ 오늘"
이라는 수집기간은 `target_business_years()`가 사업연도로 환산한다 — 사업보고서는
사업연도 종료 후 90일 안에 제출되므로 그 창에는 두 해분이 들어온다.

항목마다 응답 컬럼이 달라 `disclosure_items.payload`(JSON 문자열)에 원본을
그대로 담는다. 분석은 Claude Code가 payload를 읽어 수행하므로 타입을 고정할
실익이 없다.

**주요정보(2단계)와 공시 목록(3단계)은 성격이 다르다.**

| | 2단계 `disclosure_items` | 3단계 `disclosure_filings` |
|---|---|---|
| 성격 | 사업보고서 시점의 **현황** | 기간 중 벌어진 **이벤트** |
| 조회 | 사업연도 | **날짜 범위** (`fiscal_window()`) |
| 예 | 기말 자기주식 수량 | 2026-08-21 자기주식취득결정 |

기중 자기주식취득결정·합병결정은 2단계로는 잡히지 않는다. 3단계가 필요한
이유가 이것이다. 기본 수집 유형은 `DEFAULT_PUBLIC_TYPES` = B(주요사항보고)·
F(외부감사관련)·I(거래소공시)·J(공정위공시).

보고서명은 정형화돼 있어 `tag_filing()`이 규칙만으로 감사 시사점을 붙인다
(AI 호출 불필요). 규칙에 안 걸리면 '미분류'로 남기되 버리지 않는다.

⚠️ `list.json` 응답에는 `pblntf_ty` 필드가 **없다.** 요청할 때 쓴 유형을
저장 시점에 새겨야 한다 (안 하면 전 건이 빈 문자열이 된다).

### 사업보고서 원문 (`document.xml`) — 실측으로 확인한 사실

주석과 회사 기재 내용은 여기서만 나온다. 특수관계자 거래·우발부채가 그렇다.
접수번호는 `disclosure_items.payload` 의 `rcept_no` 에 있다 —
`disclosure_filings` 에는 정기공시(A)를 모으지 않아 없다.

- ZIP 이지만 `Content-Type` 이 `application/x-msdownload` 다. 오류도 200 으로
  오므로 **매직바이트 `PK\x03\x04`** 로 판별한다.
- 엔트리 3개 — 본문(8.3MB) · 감사보고서(0.6MB) · 연결감사보고서(0.7MB).
  감사보고서에 핵심감사사항 본문이 있어 주요정보의 한 줄 요약보다 깊다.
  **첨부가 둘 딸리는 것은 정상이다.** 엔트리 이름은 `{접수번호}_00760.xml`
  처럼 일련번호일 뿐이므로, 탭 이름은 문서 첫머리의 `<DOCUMENT-NAME>` 에서
  읽는다 (`document_labels()`). 이름이 겹치면 일련번호를 덧붙여 가른다.
- 인코딩 UTF-8.
- **엄밀한 XML 이 아니다.** 이스케이프 안 된 `&`(R&D 등)·`<` 가 섞여 있어
  ElementTree 는 실패한다. `lxml` 의 `XMLParser(recover=True)` 를 쓴다.
- ⚠️ **꺾쇠로 감싼 한글 표기는 recover 로 못 고친다.** 한글은 XML 이름으로
  유효해서 `<당기말>`·`<전기>` 를 lxml 이 **여는 태그로 읽는다.** 닫는 태그가
  없으니 뒤따르는 요소가 전부 그 안으로 끌려 들어가 SECTION-1 이 서로 중첩되고
  구간이 중복된다 (영풍 제75기: 43 → 124). 삼성전자가 무사했던 건 그 문서의
  표기가 `< TV ... >` 처럼 공백을 품어 lxml 이 버렸기 때문일 뿐이다.
  `escape_stray_markup()` 이 파싱 전에 태그가 아닌 `<` 를 `&lt;` 로 바꾼다 —
  이름이 ASCII 로 시작하고 속성이 `이름=값` 꼴인 것만 태그로 인정한다.
- 목차는 `SECTION-1`(14) → `SECTION-2`(43), 제목은 각 섹션의 `<TITLE>`.
- **주석은 SECTION-3 으로 안 내려간다.** 「3. 연결재무제표 주석」 SECTION-2
  아래에 `TABLE-GROUP` 34개가 놓이고 각각이 `TITLE` 을 하나씩 갖는다.
  TITLE 143개의 부모는 **TABLE-GROUP 83 / SECTION-2 43 / SECTION-1 14** 라,
  SECTION 의 직계 TITLE 만 보면 주석 34개가 통째로 뭉친다.
- 중분류 본문을 자를 때 **TITLE 을 품은 컨테이너에서 멈춰야** 한다. 형제 TITLE
  만 보고 멈추면 중분류가 하위 주석 본문을 전부 삼킨다.
- 표는 `TD` 외에 **`TE`(16,845) · `TU`(631)** 를 쓴다. 빼면 표가 빈다.
- `TABLE` 2,071개 중 SECTION 직계는 **314개뿐**이고 나머지는 TABLE-GROUP·
  LIBRARY·TD 안쪽이다. 텍스트 추출이 **재귀가 아니면 표가 납작해진다.**

본문만 8MB라 통째로 두지 않고 `report_sections` 에 목차 단위로 나눠 저장한다.
`00_INPUT.md` 에는 감사 관련 구간의 목차만 싣고, 본문은 SQL 로 꺼내 읽는다 —
기준서 스킬의 INDEX → Grep → Read 와 같은 방식이다.

### 회사별 작업폴더

```
workspace/2026_삼성전자/
├── 00_INPUT.md                    # 분석 진입점 (내보내기가 생성)
├── 01_financials/재무제표_전체.md   # 전 계정 3개년
├── 02_news/뉴스_전체.md            # 미분류 포함
├── 03_regulatory/
└── 04_output/                     # 분석결과 · 카드뉴스
```

**내보내기는 `raw_text` 를 담지 않는다.** 전부 펼치면 45만 토큰이 넘어
컨텍스트에 들어가지 않는다. `00_INPUT.md` 는 다이제스트만 담고, 원문이
필요해지는 순간 `audit.db` 를 조회하도록 SQL 예시를 함께 적어둔다.
`app/core/exporter.py` 의 회귀 테스트가 이 성질을 고정한다.

분량이 큰 부분(재무제표 전 계정, 미분류 포함 뉴스)은 하위 폴더에 떨어뜨려
Read 한 번 거리에 둔다.

### 뉴스 수집 (Google News RSS)

키가 필요 없다. 다만 한 질의당 약 100건이 상한이라 `QUERY_ANGLES` 로 갈래를
나눠 던지고 제목으로 중복을 제거한다. `link` 는 news.google.com 리디렉션
주소이므로 언론사명은 `<source>` 태그에서 따로 읽는다.

⚠️ **회사명은 `search_name()` 으로 정규화한 뒤 검색한다.** DART 가 주는 이름은
`(주)영풍`·`삼성전자주식회사` 인데 기사 제목은 `영풍`·`삼성전자` 라고 쓴다.
따옴표로 묶은 구문 검색에서 이 차이는 그대로 불일치가 되어, 영풍의 금융위
과징금 기사(2026-07-15)가 통째로 빠졌다. `영풍` 으로 찾으면 `(주)영풍` 이라
쓴 기사도 걸리지만 그 반대는 성립하지 않으므로 넓은 쪽으로 맞춘다.

주가·시황 기사는 `NOISE_KEYWORDS` 로 AI 호출 전에 쳐낸다. 수집 창은 공시와
같은 `fiscal_window()` 다.

**감사 어서션과 직결되도록 4분류한다.**

| 태그 | 감사 시사점 |
|---|---|
| 산업·업황 | 재고 평가, 손상징후 |
| 재무·실적 | 수익인식, 계속기업 |
| 사업구조 변동 | 사업결합, 무형자산 |
| 리스크 | 충당부채, 우발부채, 소송 |

---

## 카드뉴스 제작 규칙

`/design` 으로 만든다. 아트보드는 **1080 × 1350** (세로형 카드뉴스).

### 제목 크기 — 처음 만든 것이 컸다

초판은 표지 118~132px · 슬라이드 제목 60~68px 였는데, 제목이 두 줄로 넘어가는
장이 생기고 본문과의 위계도 오히려 흐려졌다. 아래 크기를 기준으로 삼는다.

| 자리 | 태그 | 크기 |
|---|---|---|
| 표지 대제목 | `<h1>` | **100 ~ 112px** |
| 슬라이드 제목 | `<h2>` | **48 ~ 54px** |

⚠️ **큰 숫자·번호는 제목이 아니다.** `①②③④` 나 통계 수치(`452`, `101`)는
`<span>`·`<div>` 로 두고 68~82px 를 유지한다. 이건 글이 아니라 그래픽이라,
같이 줄이면 화면의 리듬이 무너진다.

### 서체

`--font-display`(제목)는 **Nanum Myeongjo**, `--font-body`(본문)는
**IBM Plex Sans KR**. 둘 다 Google Fonts 에서 불러온다.

아티팩트는 **Google Fonts 외의 외부 호스트를 전부 막는다.** 경기천년체처럼
Google Fonts 에 없는 서체를 쓰려면 파일을 서브셋해 base64 로 페이지에 넣어야
하고, 아트보드 12장에 각각 실려 한 벌이 2.2MB → 8MB 가 된다. 실제로 해봤고
되기는 하지만, 재배포 라이선스(`fsType=4`)까지 걸려 지금은 쓰지 않기로 했다.

---

## 작업 시 주의사항

- **크롤링 대상 사이트가 403을 반환**하는 경우가 있다 (KASB, ESMA).
  이때는 스크래퍼의 seed 데이터로 폴백한다. seed의 ID는 실제 사이트 ID와
  다를 수 있으므로, 상세 페이지 접근이 실패하면 seed 데이터를 의심할 것.
- **두 곳에서 동시에 코드를 수정하지 말 것.** 로컬과 클라우드 세션은 Git으로만
  동기화되며 자동이 아니다. 코드 수정은 한 곳에서, 데이터 분석은 로컬에서.
- **컬럼이 늘어나도 데이터는 그대로 둔다.** `create_all()` 은 없는 테이블만
  만들고 기존 테이블의 새 컬럼은 모른다 — 모델만 고치면 조회 시점에
  "no such column" 으로 터진다. `database.ensure_columns()` 가 startup 마다
  모자란 컬럼을 `ALTER TABLE ... ADD COLUMN` 으로 **덧붙이기만** 한다.
  지우거나 형을 바꾸는 일은 하지 않으므로 기존 행은 어떤 경우에도 남는다.
  테이블을 다시 만드는 방식으로 되돌리지 말 것 — 한 번 데이터를 잃었다.
- 개발 브랜치: `claude/initial-setup-zzcIP`
