/**
 * 사업보고서 원문 목차.
 *
 * 목록은 제목·분량만 받고, 본문은 구간을 눌렀을 때만 가져온다. 주석 하나가
 * 5만 자를 넘기도 해서 전부 미리 불러오면 화면이 멈춘다.
 */
import { useMemo, useState } from 'react'
import { getSection } from '../api/company'

const ACCENT = '#1a5c2e'

export default function SectionPanel({ companyId, rows }) {
  const [auditOnly, setAuditOnly] = useState(true)
  const [doc, setDoc] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [body, setBody] = useState(null)
  const [loading, setLoading] = useState(false)

  const documents = useMemo(() => {
    const seen = []
    for (const r of rows) if (!seen.includes(r.doc_label)) seen.push(r.doc_label)
    return seen
  }, [rows])

  const activeDoc = doc && documents.includes(doc) ? doc : documents[0]
  const shown = rows.filter(r =>
    r.doc_label === activeDoc && (!auditOnly || r.audit_relevant))

  const relevantCount = rows.filter(r => r.audit_relevant).length

  const toggle = async (row) => {
    if (openId === row.id) {
      setOpenId(null); setBody(null)
      return
    }
    setOpenId(row.id); setBody(null); setLoading(true)
    try {
      setBody((await getSection(companyId, row.id)).body)
    } catch {
      setBody('본문을 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }

  if (rows.length === 0) {
    return (
      <div style={{
        padding: '14px 18px', background: '#fdf6f0', border: '1px solid #f0dcc8',
        borderRadius: 8, fontSize: 13, color: '#8a5a1a',
      }}>
        ⚠️ 사업보고서 원문이 아직 수집되지 않았습니다.
        목록에서 <b>보고서 원문 수집</b>을 눌러주세요.
      </div>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
        {documents.map(d => (
          <button
            key={d}
            onClick={() => { setDoc(d); setOpenId(null) }}
            style={{
              padding: '6px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer',
              border: `1px solid ${activeDoc === d ? ACCENT : '#dde2ea'}`,
              background: activeDoc === d ? ACCENT : '#fff',
              color: activeDoc === d ? '#fff' : '#555', fontWeight: 700,
            }}
          >
            {d}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 12, alignItems: 'center' }}>
        {[[true, `감사 관련 ${relevantCount}`], [false, `전체 ${rows.length}`]].map(
          ([value, label]) => (
            <button
              key={String(value)}
              onClick={() => { setAuditOnly(value); setOpenId(null) }}
              style={{
                padding: '5px 14px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
                border: auditOnly === value ? `2px solid ${ACCENT}` : '1px solid #dde2ea',
                background: auditOnly === value ? ACCENT : '#fff',
                color: auditOnly === value ? '#fff' : '#555',
                fontWeight: auditOnly === value ? 700 : 400,
              }}
            >
              {label}
            </button>
          ))}
      </div>

      <div style={{ border: '1px solid #eef1f5', borderRadius: 8, overflow: 'hidden' }}>
        {shown.map((r, i) => (
          <div key={r.id} style={{ borderTop: i === 0 ? 'none' : '1px solid #eef1f5' }}>
            <div
              onClick={() => r.chars > 0 && toggle(r)}
              style={{
                display: 'flex', alignItems: 'baseline', gap: 10,
                padding: '9px 14px',
                paddingLeft: 14 + (r.level - 1) * 18,     // 목차 깊이만큼 들여쓴다
                fontSize: 13,
                cursor: r.chars > 0 ? 'pointer' : 'default',
                background: openId === r.id ? '#f0f7f2' : 'transparent',
              }}
            >
              <span style={{
                color: r.chars > 0 ? '#8a9ab0' : 'transparent',
                fontSize: 11, width: 10, flexShrink: 0,
              }}>
                {openId === r.id ? '▾' : '▸'}
              </span>

              <span style={{
                flex: 1, minWidth: 0,
                color: r.chars > 0 ? '#222' : '#8a9ab0',
                fontWeight: r.level === 1 ? 700 : r.level === 2 ? 600 : 400,
              }}>
                {r.title}
              </span>

              {r.audit_relevant && (
                <span style={{
                  background: '#eaf3ea', color: ACCENT, fontSize: 10, fontWeight: 700,
                  padding: '1px 7px', borderRadius: 8, flexShrink: 0,
                }}>
                  감사
                </span>
              )}

              <span style={{
                color: '#8a9ab0', fontSize: 12, whiteSpace: 'nowrap',
                fontVariantNumeric: 'tabular-nums', flexShrink: 0,
              }}>
                {r.chars > 0 ? `${r.chars.toLocaleString('ko-KR')}자` : '—'}
              </span>
            </div>

            {openId === r.id && (
              <div style={{
                padding: '12px 18px 16px', background: '#fafbfc',
                borderTop: '1px solid #eef1f5',
              }}>
                {loading ? (
                  <div style={{ color: '#8a9ab0', fontSize: 13 }}>불러오는 중...</div>
                ) : (
                  <div style={{
                    fontSize: 12.5, lineHeight: 1.7, color: '#333',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                    maxHeight: 480, overflowY: 'auto',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                  }}>
                    {body}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {shown.length === 0 && (
          <div style={{ padding: '14px 18px', fontSize: 13, color: '#8a9ab0' }}>
            이 문서에는 감사 관련 구간이 없습니다. 전체로 바꿔보세요.
          </div>
        )}
      </div>

      <div style={{ marginTop: 8, fontSize: 12, color: '#8a9ab0' }}>
        구간을 누르면 본문이 열립니다. 표는 <code>|</code> 로 칸을 구분합니다.
      </div>
    </>
  )
}
