"""기준서 PDF → Claude 스킬 references 폴더 변환기.

회계감사기준 / K-IFRS PDF를 기준서 단위 마크다운으로 쪼개고 INDEX.md 를 만든다.
스킬은 INDEX 를 먼저 보고 → 해당 파일을 Grep 하고 → 맞는 부분만 Read 하는 식으로
쓰도록 설계했다. 파일 하나를 통째로 읽으면 토큰이 과하게 든다.

사용법:
    # 1) 먼저 어떻게 쪼개질지 확인 (파일을 쓰지 않는다)
    python scripts/build_skill_refs.py --pdf "C:/pdf/kifrs" --type kifrs --dry-run

    # 2) 결과가 맞으면 실제 생성
    python scripts/build_skill_refs.py --pdf "C:/pdf/kifrs" --type kifrs ^
        --out "C:/Users/kwony/.claude/skills/kifrs/references"
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pdfplumber  # noqa: E402

# 기준서 시작 줄을 찾는 패턴. (번호, 제목) 두 그룹을 잡는다.
PATTERNS = {
    "kifrs": re.compile(
        r"^\s*(?:기업회계)?기준서\s*제?\s*(\d{4})\s*호\s*[’'\"「]?\s*([^\n」’'\"]{0,40})",
        re.M,
    ),
    "audit": re.compile(
        r"^\s*(?:회계)?감사기준서\s*제?\s*(\d{3,4})\s*호?\s*[’'\"「]?\s*([^\n」’'\"]{0,40})",
        re.M,
    ),
    "kgaap": re.compile(
        r"^\s*제\s*(\d{1,2})\s*장\s*[’'\"「]?\s*([^\n」’'\"]{0,40})",
        re.M,
    ),
}

# 같은 기준서명이 머리말·꼬리말로 매 페이지 반복되므로,
# 직전 절 시작점에서 이만큼은 지나야 새 절로 인정한다.
MIN_SECTION_CHARS = 1500

# --mode file 용. PDF 하나가 기준서 하나일 때 파일명에서 번호·제목을 뽑는다.
#   시행중_K-IFRS_제1001호_재무제표_표시(2023_개정_...).pdf → ("1001", "재무제표_표시")
FILENAME_PATTERNS = {
    "kifrs": re.compile(r"제\s*(\d{4})\s*호[_\s]*(.*?)(?:\(|$)"),
    "audit": re.compile(r"제?\s*(\d{3,4})\s*호[_\s]*(.*?)(?:\(|$)"),
    "kgaap": re.compile(r"제\s*(\d{1,2})\s*장[_\s]*(.*?)(?:\(|$)"),
}


def extract_pages(pdf_path: Path) -> list[str]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages


def strip_running_heads(pages: list[str]) -> list[str]:
    """페이지 절반 이상에 반복되는 머리말·꼬리말 줄을 제거한다."""
    if len(pages) < 4:
        return pages

    counts = Counter()
    for text in pages:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines[:2] + lines[-2:]:          # 상·하단만 후보
            if len(ln) < 60:                       # 본문 문장은 제외
                counts[ln] += 1

    threshold = len(pages) * 0.5
    noise = {ln for ln, c in counts.items() if c >= threshold}
    if not noise:
        return pages

    cleaned = []
    for text in pages:
        kept = [ln for ln in text.splitlines() if ln.strip() not in noise]
        cleaned.append("\n".join(kept))
    return cleaned


def find_sections(text: str, pattern: re.Pattern) -> list[tuple[int, str, str]]:
    """(시작위치, 번호, 제목) 목록. 너무 가까운 중복 매치는 버린다."""
    sections = []
    for m in pattern.finditer(text):
        pos = m.start()
        if sections and pos - sections[-1][0] < MIN_SECTION_CHARS:
            continue
        number = m.group(1)
        title = re.sub(r"\s+", " ", m.group(2)).strip(" ·-–—")
        sections.append((pos, number, title))
    return sections


def slugify(number: str, title: str, prefix: str) -> str:
    safe = re.sub(r"[^\w가-힣]+", "_", title).strip("_")[:24]
    return f"{prefix}_{number}" + (f"_{safe}" if safe else "") + ".md"


def parse_filename(stem: str, kind: str) -> tuple[str, str]:
    """파일명에서 (번호, 제목)을 뽑는다. 번호가 없으면 ('', 정리된 파일명)."""
    m = FILENAME_PATTERNS[kind].search(stem)
    if m:
        title = re.sub(r"[_\s]+", " ", m.group(2)).strip(" _-")
        return m.group(1), title

    # 개념체계·실무서처럼 번호가 없는 문서
    head = stem.split("(")[0]
    head = re.sub(r"^(시행중|시행예정)[_\s]*", "", head)
    head = re.sub(r"^K-?IFRS[_\s]*", "", head, flags=re.I)
    return "", re.sub(r"[_\s]+", " ", head).strip(" _-")


def build_by_filename(pdf_paths: list[Path], kind: str, out_dir: Path, dry_run: bool) -> None:
    """PDF 하나 = 기준서 하나. 분할하지 않고 1:1로 변환한다."""
    prefix = kind
    entries = []
    used: set[str] = set()

    for pdf_path in pdf_paths:
        number, title = parse_filename(pdf_path.stem, kind)

        if number:
            fname = slugify(number, title, prefix)
        else:
            safe = re.sub(r"[^\w가-힣]+", "_", title).strip("_")[:40]
            fname = f"{prefix}_{safe or pdf_path.stem[:40]}.md"

        # 번호가 같은 판본이 둘 이상이어도 덮어쓰지 않는다
        if fname in used:
            stem = fname[:-3]
            n = 2
            while f"{stem}_{n}.md" in used:
                n += 1
            fname = f"{stem}_{n}.md"
        used.add(fname)

        pages = strip_running_heads(extract_pages(pdf_path))
        text = "\n".join(pages).strip()

        if not text:
            print(f"  ⚠️ {pdf_path.name}\n     텍스트 추출 실패 (스캔본 가능성)")
            continue

        label = f"{number}호 {title}" if number else title
        print(f"  {fname:<46} {len(text):>9,}자   ← {label}")
        entries.append((number or "zz", title, fname, len(text)))

        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            header = f"# {label}\n\n> 출처: {pdf_path.name}\n\n---\n\n"
            (out_dir / fname).write_text(header + text, encoding="utf-8")

    finish(entries, out_dir, kind, dry_run)


def build(pdf_paths: list[Path], kind: str, out_dir: Path, dry_run: bool) -> None:
    pattern = PATTERNS[kind]
    prefix = {"kifrs": "kifrs", "audit": "audit", "kgaap": "kgaap"}[kind]
    entries = []

    for pdf_path in pdf_paths:
        print(f"\n▸ {pdf_path.name}")
        pages = strip_running_heads(extract_pages(pdf_path))
        text = "\n".join(pages)

        if not text.strip():
            print("  ⚠️ 텍스트를 추출하지 못했습니다 (스캔본 가능성)")
            continue

        sections = find_sections(text, pattern)
        if not sections:
            print(f"  ⚠️ 기준서 구분을 찾지 못해 통째로 저장합니다 ({len(text):,}자)")
            sections = [(0, pdf_path.stem, "")]

        print(f"  {len(sections)}개 절 발견")

        for i, (pos, number, title) in enumerate(sections):
            end = sections[i + 1][0] if i + 1 < len(sections) else len(text)
            body = text[pos:end].strip()
            fname = slugify(number, title, prefix)
            entries.append((number, title, fname, len(body)))

            print(f"    - {fname:<40} {len(body):>8,}자")
            if not dry_run:
                out_dir.mkdir(parents=True, exist_ok=True)
                header = f"# {title or number}\n\n> 출처: {pdf_path.name}\n\n---\n\n"
                (out_dir / fname).write_text(header + body, encoding="utf-8")

    finish(entries, out_dir, kind, dry_run)


def finish(entries: list, out_dir: Path, kind: str, dry_run: bool) -> None:
    """INDEX.md 와 SKILL.md 를 만든다 (두 모드 공통)."""
    if dry_run:
        print("\n[dry-run] 파일을 쓰지 않았습니다. 결과가 맞으면 --dry-run 을 빼고 다시 실행하세요.")
        return

    if not entries:
        print("\n생성된 파일이 없습니다.")
        return

    lines = [
        "# 기준서 색인",
        "",
        "답변 전 이 표에서 해당 파일을 고르고, **Grep 으로 문단을 찾은 뒤**",
        "필요한 부분만 Read 하세요. 파일 전체를 읽으면 토큰이 과하게 듭니다.",
        "",
        "| 번호 | 제목 | 파일 | 분량 |",
        "|---|---|---|---|",
    ]
    for number, title, fname, size in sorted(entries):
        shown = "" if number == "zz" else number
        lines.append(f"| {shown} | {title} | `{fname}` | {size:,}자 |")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n✅ {len(entries)}개 파일 + INDEX.md 생성 → {out_dir}")

    write_skill_md(out_dir.parent, kind)


SKILL_META = {
    "kifrs": (
        "kifrs",
        "K-IFRS 기준서 조회·해석. 사용자가 K-IFRS, 한국채택국제회계기준, 기업회계기준서, "
        "제11xx호, 수익인식, 리스, 금융상품, 손상, 공정가치, 사업결합, 충당부채, 이연법인세 중 "
        "무엇이든 언급하면 명시적 요청이 없어도 사용할 것. 회계 판단은 지어내면 위험하므로 "
        "반드시 references/ 원문을 확인한 뒤 기준서 번호와 문단번호를 근거로 답한다.",
        "K-IFRS 기준서",
    ),
    "audit": (
        "audit-standards",
        "회계감사기준 조회·해석. 사용자가 감사기준서, 감사절차, 감사증거, 위험평가, 중요성, "
        "표본감사, 감사의견, 감사보고서, 계속기업, 특수관계자, 부정 중 무엇이든 언급하면 "
        "명시적 요청이 없어도 사용할 것. 반드시 references/ 원문을 확인한 뒤 "
        "기준서 번호와 문단번호를 근거로 답한다.",
        "회계감사기준",
    ),
    "kgaap": (
        "kgaap",
        "일반기업회계기준(K-GAAP) 조회·해석. 사용자가 일반기업회계기준, K-GAAP, 비상장 회계처리를 "
        "언급하면 사용할 것. 반드시 references/ 원문을 확인한 뒤 장·문단번호를 근거로 답한다.",
        "일반기업회계기준",
    ),
}


def write_skill_md(skill_dir: Path, kind: str) -> None:
    """SKILL.md 가 없을 때만 생성한다 (직접 다듬은 내용을 덮어쓰지 않는다)."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    if path.exists():
        print(f"   SKILL.md 는 이미 있어 건드리지 않았습니다: {path}")
        return

    name, description, label = SKILL_META[kind]
    path.write_text(
        f"""---
name: {name}
description: {description}
---

# {label}

## 사용 순서

1. `references/INDEX.md` 에서 해당 기준서 파일을 고른다.
2. 그 파일을 **Grep** 으로 검색해 관련 문단 위치를 찾는다.
3. 찾은 부분만 **Read** 한다. 파일 전체를 읽지 않는다.

기준서 하나가 수만 자이므로 통째로 읽으면 토큰이 과하게 든다.

## 답변 규칙

- 기억으로 답하지 말 것. 반드시 위 순서로 원문을 확인한다.
- 출처를 `{label} 제1115호 문단 31` 형식으로 명시한다.
- 원문에서 확인하지 못한 내용은 "기준서에서 확인되지 않는다"고 밝힌다.
- 시행일·경과규정이 있는 항목은 적용 시점을 함께 확인한다.
- 개정 전후가 다를 수 있으므로, 어느 판본인지 불확실하면 사용자에게 확인한다.

## 한계

- `references/` 에 담긴 기준서만 다룬다. 목록에 없으면 없다고 답한다.
- 결론이 사실관계에 좌우되는 사안은 단정하지 말고 판단 기준을 제시한다.
""",
        encoding="utf-8",
    )
    print(f"   SKILL.md 생성 → {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="PDF 파일 또는 폴더 경로")
    ap.add_argument("--type", required=True, choices=list(PATTERNS))
    ap.add_argument(
        "--mode", choices=["file", "split"], default="file",
        help="file: PDF 하나가 기준서 하나 (기본) / split: 한 PDF 안에 여러 기준서",
    )
    ap.add_argument("--out", help="references 폴더 (dry-run 이 아니면 필수)")
    ap.add_argument("--dry-run", action="store_true", help="결과만 확인, 파일은 쓰지 않음")
    args = ap.parse_args()

    src = Path(args.pdf)
    pdfs = sorted(src.glob("*.pdf")) if src.is_dir() else [src]
    if not pdfs:
        sys.exit(f"PDF를 찾지 못했습니다: {src}")

    if not args.dry_run and not args.out:
        sys.exit("--out 을 지정하거나 --dry-run 으로 먼저 확인하세요.")

    out = Path(args.out) if args.out else Path(".")
    print(f"{len(pdfs)}개 PDF · mode={args.mode}")

    if args.mode == "file":
        build_by_filename(pdfs, args.type, out, args.dry_run)
    else:
        build(pdfs, args.type, out, args.dry_run)


if __name__ == "__main__":
    main()
