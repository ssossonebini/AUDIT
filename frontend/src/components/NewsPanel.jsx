/**
 * 회사 뉴스 — 감사 어서션 4분류로 태깅된 목록.
 *
 * 태그가 곧 "무엇을 볼지"다. 산업·업황이면 재고 평가와 손상징후,
 * 리스크면 충당부채·우발부채를 짚어보라는 뜻이다.
 */
import { useMemo, useState } from 'react'

const ACCENT = '#1a5c2e'

// 태그 → [배경, 글자, 감사 시사점]
const TAGS = {
  '산업·업황':    ['#eef3fb', '#1a3a6c', '재고 평가 · 손상징후'],
  '재무·실적':    ['#eaf3ea', '#1a5c2e', '수익인식 · 계속기업'],
  '사업구조 변동': ['#f3eefb', '#4a1a6c', '사업결합 · 무형자산'],
  '리스크':       ['#fdecea', '#a32020', '충당부채 · 우발부채 · 소송'],
}

const fmtDate = (d) => (d ? d.replace(/-/g, '.') : '')

export default function NewsPanel({ rows }) {
  const [tag, setTag] = useState(null)

  const counts = useMemo(() => {
    const m = new Map()
    for (const r of rows) {
      const key = r.tag || '미분류'
      m.set(key, (m.get(key) || 0) + 1)
    }
    // 정해둔 4분류 순서를 지키고, 미분류는 맨 뒤로
    const ordered = Object.keys(TAGS).filter(t => m.has(t)).map(t => [t, m.get(t)])
    if (m.has('미분류')) ordered.push(['미분류', m.get('미분류')])
    return ordered
  }, [rows])

  const shown = tag ? rows.filter(r => (r.tag || '미분류') === tag) : rows
  const hint = tag && TAGS[tag] ? TAGS[tag][2] : null

  if (rows.length === 0) {
    return (
      <div style={{
        padding: '14px 18px', background: '#fdf6f0', border: '1px solid #f0dcc8',
        borderRadius: 8, fontSize: 13, color: '#8a5a1a',
      }}>
        ⚠️ 뉴스가 아직 수집되지 않았습니다. 목록에서 <b>뉴스 수집</b>을 눌러주세요.
      </div>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
        <Chip label="전체" count={rows.length}
              active={tag === null} onClick={() => setTag(null)} />
        {counts.map(([name, count]) => (
          <Chip key={name} label={name} count={count}
                active={tag === name} onClick={() => setTag(name)}
                colors={TAGS[name]} />
        ))}
      </div>

      {hint && (
        <div style={{ fontSize: 12, color: '#8a9ab0', marginBottom: 10 }}>
          감사 시사점: {hint}
        </div>
      )}

      <div style={{ border: '1px solid #eef1f5', borderRadius: 8, overflow: 'hidden' }}>
        {shown.map((r, i) => {
          const [bg, fg] = TAGS[r.tag] || ['#f0f4fa', '#8a9ab0']
          return (
            <div key={r.id} style={{
              padding: '10px 14px', fontSize: 13,
              borderTop: i === 0 ? 'none' : '1px solid #eef1f5',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <span style={{
                  color: '#8a9ab0', fontSize: 12, whiteSpace: 'nowrap',
                  fontVariantNumeric: 'tabular-nums', paddingTop: 2,
                }}>
                  {fmtDate(r.published_at) || '날짜미상'}
                </span>

                <span style={{
                  background: bg, color: fg, fontSize: 11, fontWeight: 700,
                  padding: '2px 8px', borderRadius: 8, whiteSpace: 'nowrap',
                  flexShrink: 0, marginTop: 1,
                }}>
                  {r.tag || '미분류'}
                </span>

                <a
                  href={r.url} target="_blank" rel="noreferrer"
                  style={{ color: '#222', textDecoration: 'none', flex: 1, minWidth: 0 }}
                  onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
                  onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
                >
                  {r.title}
                </a>

                {r.source && (
                  <span style={{ color: '#8a9ab0', fontSize: 12, whiteSpace: 'nowrap' }}>
                    {r.source}
                  </span>
                )}
              </div>

              {r.ai_reason && (
                <div style={{
                  marginTop: 4, marginLeft: 86, fontSize: 12,
                  color: '#6a82a0', lineHeight: 1.5,
                }}>
                  🤖 {r.ai_reason}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 8, fontSize: 12, color: '#8a9ab0' }}>
        제목을 누르면 기사 원문이 열립니다.
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
