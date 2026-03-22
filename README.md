# AUDIT - 금감원 중점심사 회계이슈 아카이브

금융감독원이 매년 발표하는 **재무제표 중점심사 회계이슈 사전예고** 보도자료를 자동으로 수집·정리하는 웹 서비스입니다.

## 주요 기능

- 금융감독원 보도자료 자동 크롤링 (중점심사 회계이슈 검색 결과)
- 첨부 PDF 다운로드 및 텍스트 파싱
- 연도별 이슈 목록/상세 조회
- React 기반 웹 인터페이스

## 프로젝트 구조

```
AUDIT/
├── app/
│   ├── api/routes/
│   │   ├── fss.py          # 크롤링·조회 API
│   │   └── audit.py
│   ├── crawler/
│   │   ├── fss_scraper.py  # 금감원 웹 크롤러
│   │   └── pdf_parser.py   # PDF 텍스트 파싱
│   ├── db/
│   │   ├── database.py     # SQLite 설정
│   │   └── models.py       # DB 모델
│   ├── schemas/fss.py
│   └── main.py
├── frontend/               # React (Vite) 앱
│   └── src/
│       ├── api/fss.js
│       ├── components/
│       │   ├── Header.jsx
│       │   ├── YearSelector.jsx
│       │   ├── ArticleCard.jsx
│       │   ├── ArticleDetail.jsx
│       │   └── CrawlPanel.jsx
│       └── App.jsx
├── downloads/              # 다운로드된 PDF 캐시
└── requirements.txt
```

## 시작하기

### 1. Python 환경 설정

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 백엔드 실행

```bash
uvicorn app.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 3. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## 사용 방법

1. 브라우저에서 `http://localhost:3000` 접속
2. **크롤링 시작** 버튼 클릭 → 금감원 보도자료 자동 수집
3. 연도 탭으로 필터링
4. 카드 클릭 → 회계이슈 상세 내용 확인

## API 엔드포인트

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/v1/fss/years` | 데이터 있는 연도 목록 |
| GET | `/api/v1/fss/articles?year=2024` | 보도자료 목록 (연도 필터) |
| GET | `/api/v1/fss/articles/{id}` | 보도자료 상세 (이슈 포함) |
| POST | `/api/v1/fss/crawl?max_pages=5` | 크롤링 시작 |
| GET | `/api/v1/fss/crawl/status` | 크롤링 진행 상태 |

## 크롤링 대상

금융감독원 보도자료 검색 결과 (`중점심사` 키워드):
```
https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218&searchCnd=1&searchWrd=중점심사
```
