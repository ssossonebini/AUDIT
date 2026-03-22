# AUDIT

Python FastAPI 기반 웹 애플리케이션입니다.

## 프로젝트 구조

```
AUDIT/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── __init__.py    # 라우터 등록
│   │       └── audit.py       # audit CRUD 엔드포인트
│   ├── core/
│   │   └── config.py          # 설정 관리
│   ├── models/                # DB 모델 (추후 추가)
│   ├── schemas/
│   │   └── audit.py           # Pydantic 스키마
│   └── main.py                # FastAPI 앱 진입점
├── tests/
│   └── test_audit.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 시작하기

### 1. 가상환경 생성 및 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

### 3. 서버 실행

```bash
uvicorn app.main:app --reload
```

서버가 실행되면 아래 주소에서 확인할 수 있습니다:
- API: http://localhost:8000
- 문서(Swagger): http://localhost:8000/docs
- 문서(ReDoc): http://localhost:8000/redoc

## API 엔드포인트

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/` | 루트 |
| GET | `/health` | 헬스 체크 |
| GET | `/api/v1/audit/` | 감사 목록 조회 |
| POST | `/api/v1/audit/` | 감사 생성 |
| GET | `/api/v1/audit/{id}` | 감사 단건 조회 |
| DELETE | `/api/v1/audit/{id}` | 감사 삭제 |

## 테스트

```bash
pytest tests/
```
