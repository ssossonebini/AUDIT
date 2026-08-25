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
| 🏢 회사 프로젝트 | `/api/v1/company` | `companies` + `financial_statements` + `disclosure_items` | DART 재무제표·주요정보 |

### 감사 보도자료의 증분 크롤링

`crawl_history` 테이블이 소스별 마지막 수집일(`last_sdate`)을 보관한다.
다음 크롤링은 그 날짜부터만 조회하므로 2025-01-01 전체를 재수집하지 않는다.
안전장치로 기존 `ntt_id`를 만나면 즉시 중단한다.

`ntt_id`는 `FSS-{id}` / `FSC-{id}` 형식으로 접두사를 붙여 충돌을 막는다.

---

## 실행 방법

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
| 3 | 뉴스 크롤링 | **Google News RSS** (키 불필요). 네이버는 NCP 가입이 필요해 후순위 |
| 4 | 분석자료 내보내기 | `00_INPUT.md` 생성 → Claude Code 진입점 |
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
| 3 | 공시 목록 · 주요사항보고서 — `list.json`(`pblntf_ty=B`,`F`) · DS004 | 미착수 |

**주요정보는 날짜가 아니라 사업연도로 조회된다.** "직전 회계연도 개시일 ~ 오늘"
이라는 수집기간은 `target_business_years()`가 사업연도로 환산한다 — 사업보고서는
사업연도 종료 후 90일 안에 제출되므로 그 창에는 두 해분이 들어온다.

항목마다 응답 컬럼이 달라 `disclosure_items.payload`(JSON 문자열)에 원본을
그대로 담는다. 분석은 Claude Code가 payload를 읽어 수행하므로 타입을 고정할
실익이 없다.

특수관계자 거래는 API로 제공되지 않는다 — 재무제표 **주석**에 있으므로
`document.xml` 원문 파싱이 필요하다. 타법인 출자·최대주주 현황으로 관계도만
잡고 실제 거래는 주석을 직접 확인하는 편이 현실적이다.

### 회사별 작업폴더 구조 (계획)

```
workspace/2026_삼성전자/
├── 00_INPUT.md          # 분석 진입점 (웹호스트 생성)
├── 01_financials/       # DART 수기 다운로드 (3개년)
├── 02_news/             # 뉴스 크롤링 결과
├── 03_regulatory/       # 중점심사·지적사례 + PDF
└── 04_output/           # 분석결과 · 카드뉴스
```

### 뉴스 분류 태그 (계획)

감사 어서션과 직결되도록 4분류한다.

| 태그 | 감사 시사점 |
|---|---|
| 산업·업황 | 재고 평가, 손상징후 |
| 재무·실적 | 수익인식, 계속기업 |
| 사업구조 변동 | 사업결합, 무형자산 |
| 리스크 | 충당부채, 우발부채, 소송 |

---

## 작업 시 주의사항

- **크롤링 대상 사이트가 403을 반환**하는 경우가 있다 (KASB, ESMA).
  이때는 스크래퍼의 seed 데이터로 폴백한다. seed의 ID는 실제 사이트 ID와
  다를 수 있으므로, 상세 페이지 접근이 실패하면 seed 데이터를 의심할 것.
- **두 곳에서 동시에 코드를 수정하지 말 것.** 로컬과 클라우드 세션은 Git으로만
  동기화되며 자동이 아니다. 코드 수정은 한 곳에서, 데이터 분석은 로컬에서.
- 개발 브랜치: `claude/initial-setup-zzcIP`
