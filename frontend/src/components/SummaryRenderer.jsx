/**
 * AI 요약 결과를 구조화된 UI로 렌더링
 * - structured(JSON) 우선, 없으면 plain text fallback
 */
export default function SummaryRenderer({ text, structured }) {
  if (structured) return <StructuredView data={structured} />
  return <PlainView text={text} />
}

/* ── 구조화 뷰 (JSON 파싱 성공 시) ─────────────────── */

function StructuredView({ data }) {
  const { overview, issues = [], implications } = data

  return (
    <div style={{ fontSize: 14, color: '#222' }}>

      {/* 1. 전체 개요 */}
      {overview && (
        <Section title="1. 전체 개요">
          <p style={s.p}>{overview}</p>
        </Section>
      )}

      {/* 2. 주요 회계이슈 목록 */}
      {issues.length > 0 && (
        <Section title="2. 주요 회계이슈 목록">
          <div style={{ overflowX: 'auto' }}>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={{ ...s.th, width: 50 }}>번호</th>
                  <th style={{ ...s.th, width: 200 }}>이슈명</th>
                  <th style={s.th}>설명</th>
                </tr>
              </thead>
              <tbody>
                {issues.map((issue, i) => (
                  <tr key={i} style={i % 2 === 0 ? s.trEven : s.trOdd}>
                    <td style={{ ...s.td, textAlign: 'center', fontWeight: 700, color: '#1a3a6c' }}>
                      {issue.number}
                    </td>
                    <td style={{ ...s.td, fontWeight: 600, whiteSpace: 'nowrap', color: '#1a3a6c' }}>
                      {issue.title}
                    </td>
                    <td style={{ ...s.td, lineHeight: 1.7 }}>
                      {issue.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* 3. 기업 및 감사인 시사점 */}
      {implications && (
        <Section title="3. 기업 및 감사인에 대한 주요 시사점">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <ImplicationBox title="기업 대상" items={implications.companies} color="#1a3a6c" />
            <ImplicationBox title="감사인 대상" items={implications.auditors} color="#b45309" />
          </div>
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div style={s.section}>
      <div style={s.sectionTitle}>{title}</div>
      {children}
    </div>
  )
}

function ImplicationBox({ title, items = [], color }) {
  return (
    <div style={{ ...s.implBox, borderTop: `3px solid ${color}` }}>
      <div style={{ ...s.implTitle, color }}>{title}</div>
      <ul style={s.ul}>
        {items.map((item, i) => (
          <li key={i} style={s.li}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

/* ── Plain text fallback ────────────────────────────── */

function PlainView({ text }) {
  return (
    <div style={{ fontSize: 14, color: '#333', lineHeight: 1.9, whiteSpace: 'pre-line' }}>
      {text}
    </div>
  )
}

/* ── 스타일 ─────────────────────────────────────────── */

const s = {
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: '#1a3a6c',
    borderLeft: '4px solid #1a3a6c',
    paddingLeft: 10,
    marginBottom: 10,
    lineHeight: 1.5,
  },
  p: {
    margin: '0 0 8px',
    lineHeight: 1.8,
    color: '#333',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 13,
    border: '1px solid #dde2ea',
  },
  th: {
    background: '#1a3a6c',
    color: '#fff',
    padding: '9px 14px',
    textAlign: 'left',
    fontWeight: 700,
  },
  trEven: { background: '#fff' },
  trOdd: { background: '#f4f7fb' },
  td: {
    padding: '9px 14px',
    borderBottom: '1px solid #dde2ea',
    verticalAlign: 'top',
    fontSize: 13,
  },
  implBox: {
    background: '#fff',
    border: '1px solid #dde2ea',
    borderRadius: 8,
    padding: '14px 16px',
  },
  implTitle: {
    fontWeight: 700,
    fontSize: 13,
    marginBottom: 8,
  },
  ul: {
    margin: 0,
    paddingLeft: 18,
  },
  li: {
    marginBottom: 5,
    fontSize: 13,
    lineHeight: 1.65,
    color: '#333',
  },
}
