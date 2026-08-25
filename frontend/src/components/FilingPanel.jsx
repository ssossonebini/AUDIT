/**
 * 공시 목록 (기중 이벤트).
 *
 * 주요정보가 사업보고서 시점의 '현황'이라면, 이쪽은 기간 중에 실제로 벌어진
 * 일이다 — 자기주식취득결정, 합병결정, 대규모내부거래 같은 것들.
 * 감사 시사점 태그로 걸러 볼 수 있게 한다.
 */
import { useMemo, useState } from 'react'

const ACCENT = '#1a5c2e'

// 태그별 색. 계속기업·특수관계자처럼 위험 신호는 붉게 둔다.
const TAG_COLORS = {
  '계속기업':   ['#fdecea', '#a32020'],
  '특수관계자': ['#fdf0e6', '#a3601a'],
  '사업결합':   ['#eef3fb', '#1a3a6c'],
  '외부감사':   ['#f3eefb', '#4a1a6c'],
  '소송·제재':  ['#fdecea', '#a32020'],
  '자본거래':   ['#eaf3ea', '#1a5c2e'],
  '배당':       ['#eaf3ea', '#1a5c2e'],
  '정기보고서': ['#f0f4fa', '#555'],
}

const fmtDate = (d) =>
  d && d.length === 8 ? `${d.slice(0, 4)}.${d.slice(4, 6)}.${d.slice(6)}` : (d || '')

export default function FilingPanel({ rows }) {
  const [tag, setTag] = useState(null)

  const tags = useMemo(() => {
    const counts = new Map()
    for (const r of rows) {
      const key = r.tag || '미분류'
      counts.set(key, (counts.get(key) || 0) + 1)
    }
    // 미분류는 맨 뒤로
    return [...counts.entries()].sort((a, b) =>
      a[0] === '미분류' ? 1 : b[0] === '미분류' ? -1 : b[1] - a[1])
  }, [rows])

  const shown = tag ? rows.filter(r => (r.tag || '미분류') === tag) : rows

  if (rows.length === 0) {
    return (
      <div style={{
        padding: '14px 18px', background: '#fdf6f0', border: '1px solid #f0dcc8',
        borderRadius: 8, fontSize: 13, color: '#8a5a1a',
      }}>
        ⚠️ 공시 목록이 아직 수집되지 않았습니다. 목록에서 <b>공시 수집</b>을 눌러주세요.
      </div>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        <Chip label="전체" count={rows.length}
              active={tag === null} onClick={() => setTag(null)} />
        {tags.map(([name, count]) => (
          <Chip key={name} label={name} count={count}
                active={tag === name} onClick={() => setTag(name)}
                colors={TAG_COLORS[name]} />
        ))}
      </div>

      <div style={{ border: '1px solid #eef1f5', borderRadius: 8, overflow: 'hidden' }}>
        {shown.map((r, i) => {
          const [bg, fg] = TAG_COLORS[r.tag] || ['#f0f4fa', '#8a9ab0']
          return (
            <div key={r.id} style={{
              display: 'flex', alignItems: 'flex-start', gap: 12,
              padding: '10px 14px', fontSize: 13,
              borderTop: i === 0 ? 'none' : '1px solid #eef1f5',
            }}>
              <span style={{
                color: '#8a9ab0', fontSize: 12, whiteSpace: 'nowrap',
                fontVariantNumeric: 'tabular-nums', paddingTop: 2,
              }}>
                {fmtDate(r.rcept_dt)}
              </span>

              <span style={{
                background: bg, color: fg, fontSize: 11, fontWeight: 700,
                padding: '2px 8px', borderRadius: 8, whiteSpace: 'nowrap',
                flexShrink: 0, marginTop: 1,
              }}>
                {r.tag || '미분류'}
              </span>

              <a
                href={r.dart_url} target="_blank" rel="noreferrer"
                style={{ color: '#222', textDecoration: 'none', flex: 1, minWidth: 0 }}
                onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
                onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
              >
                {r.report_nm}
              </a>

              {r.flr_nm && (
                <span style={{ color: '#8a9ab0', fontSize: 12, whiteSpace: 'nowrap' }}>
                  {r.flr_nm}
                </span>
              )}
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 8, fontSize: 12, color: '#8a9ab0' }}>
        보고서명을 누르면 DART 원문이 열립니다.
      </div>
    </>
  )
}

function Chip({ label, count, active, onClick, colors }) {
  const [bg, fg] = colors || ['#fff', '#555']
  return (
    <button
      onClick={onClick}
      style={{
        padding: '5px 14px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
        border: active ? `2px solid ${ACCENT}` : '1px solid #dde2ea',
        background: active ? ACCENT : bg,
        color: active ? '#fff' : fg,
        fontWeight: active ? 700 : 400,
      }}
    >
      {label} <span style={{ opacity: 0.75 }}>{count}</span>
    </button>
  )
}
