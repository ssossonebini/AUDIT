/**
 * AI 요약 텍스트(마크다운)를 구조화된 UI로 렌더링
 * ## 헤더, **bold**, | 표, - 목록을 파싱
 */
export default function SummaryRenderer({ text }) {
  const sections = parseMarkdown(text)
  return (
    <div style={{ fontSize: 14, color: '#222', lineHeight: 1.8 }}>
      {sections.map((section, i) => renderSection(section, i))}
    </div>
  )
}

/* ── 파서 ──────────────────────────────────────────── */

function parseMarkdown(text) {
  const lines = text.split('\n')
  const sections = []
  let current = null

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // ## 헤더
    const h2 = line.match(/^##\s+(.+)/)
    if (h2) {
      if (current) sections.push(current)
      current = { type: 'section', title: h2[1].trim(), children: [] }
      continue
    }

    // ### 소헤더
    const h3 = line.match(/^###\s+(.+)/)
    if (h3) {
      if (!current) { current = { type: 'section', title: '', children: [] } }
      current.children.push({ type: 'h3', text: h3[1].trim() })
      continue
    }

    // 표 행: | col | col |
    if (line.trim().startsWith('|')) {
      const isSep = /^\|[-\s|:]+\|$/.test(line.trim())
      if (isSep) continue

      // 앞 블록이 table이면 행 추가
      const last = current?.children?.at(-1)
      if (last?.type === 'table') {
        last.rows.push(parseCells(line))
      } else {
        const row = parseCells(line)
        if (!current) { current = { type: 'section', title: '', children: [] } }
        current.children.push({ type: 'table', header: row, rows: [] })
      }
      continue
    }

    // - 목록 항목
    const li = line.match(/^-\s+(.+)/)
    if (li) {
      if (!current) { current = { type: 'section', title: '', children: [] } }
      const last = current.children.at(-1)
      if (last?.type === 'list') {
        last.items.push(li[1].trim())
      } else {
        current.children.push({ type: 'list', items: [li[1].trim()] })
      }
      continue
    }

    // 구분선
    if (/^---+$/.test(line.trim())) continue

    // 빈 줄
    if (!line.trim()) continue

    // 일반 텍스트
    if (!current) { current = { type: 'section', title: '', children: [] } }
    current.children.push({ type: 'p', text: line.trim() })
  }

  if (current) sections.push(current)
  return sections
}

function parseCells(line) {
  return line
    .split('|')
    .map(c => c.trim())
    .filter(Boolean)
}

/* ── 렌더러 ─────────────────────────────────────────── */

function renderSection(section, key) {
  return (
    <div key={key} style={styles.section}>
      {section.title && (
        <div style={styles.sectionTitle}>{section.title}</div>
      )}
      {section.children.map((child, i) => renderChild(child, i))}
    </div>
  )
}

function renderChild(child, key) {
  if (child.type === 'h3') {
    return <div key={key} style={styles.h3}>{child.text}</div>
  }

  if (child.type === 'table') {
    return (
      <div key={key} style={{ overflowX: 'auto', marginBottom: 12 }}>
        <table style={styles.table}>
          <thead>
            <tr>
              {child.header.map((h, i) => (
                <th key={i} style={styles.th}>{renderInline(h)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {child.rows.map((row, ri) => (
              <tr key={ri} style={ri % 2 === 0 ? styles.trEven : styles.trOdd}>
                {row.map((cell, ci) => (
                  <td key={ci} style={ci === 0 ? styles.tdFirst : styles.td}>
                    {renderInline(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (child.type === 'list') {
    return (
      <ul key={key} style={styles.ul}>
        {child.items.map((item, i) => (
          <li key={i} style={styles.li}>{renderInline(item)}</li>
        ))}
      </ul>
    )
  }

  if (child.type === 'p') {
    return <p key={key} style={styles.p}>{renderInline(child.text)}</p>
  }

  return null
}

/** **bold** 인라인 파싱 */
function renderInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  if (parts.length === 1) return text
  return parts.map((part, i) => {
    const m = part.match(/^\*\*(.+)\*\*$/)
    return m ? <strong key={i}>{m[1]}</strong> : part
  })
}

/* ── 스타일 ─────────────────────────────────────────── */

const styles = {
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: 700,
    color: '#1a3a6c',
    borderLeft: '4px solid #1a3a6c',
    paddingLeft: 10,
    marginBottom: 12,
    lineHeight: 1.5,
  },
  h3: {
    fontSize: 13,
    fontWeight: 700,
    color: '#334',
    marginBottom: 6,
    marginTop: 10,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 13,
    marginBottom: 4,
  },
  th: {
    background: '#1a3a6c',
    color: '#fff',
    padding: '8px 12px',
    textAlign: 'left',
    fontWeight: 700,
    whiteSpace: 'nowrap',
  },
  trEven: { background: '#fff' },
  trOdd: { background: '#f4f7fb' },
  td: {
    padding: '8px 12px',
    borderBottom: '1px solid #dde2ea',
    verticalAlign: 'top',
    lineHeight: 1.6,
  },
  tdFirst: {
    padding: '8px 12px',
    borderBottom: '1px solid #dde2ea',
    verticalAlign: 'top',
    lineHeight: 1.6,
    fontWeight: 600,
    whiteSpace: 'nowrap',
    color: '#1a3a6c',
  },
  ul: {
    margin: '4px 0 8px 0',
    paddingLeft: 20,
  },
  li: {
    marginBottom: 4,
    lineHeight: 1.7,
  },
  p: {
    margin: '0 0 8px',
    lineHeight: 1.8,
  },
}
