import { useEffect, useState } from 'react'
import { getCompany, getFinancials } from '../api/company'

const ACCENT = '#1a5c2e'

const STATEMENTS = [
  { key: 'BS',  label: '재무상태표' },
  { key: 'IS',  label: '손익계산서' },
  { key: 'CIS', label: '포괄손익계산서' },
  { key: 'CF',  label: '현금흐름표' },
  { key: 'SCE', label: '자본변동표' },
]

export default function CompanyDetail({ companyId, onBack }) {
  const [company, setCompany] = useState(null)
  const [lines, setLines]     = useState([])
  const [sjDiv, setSjDiv]     = useState('BS')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([getCompany(companyId), getFinancials(companyId)])
      .then(([c, f]) => { setCompany(c); setLines(f) })
      .finally(() => setLoading(false))
  }, [companyId])

  if (loading) return <div style={center}>불러오는 중...</div>
  if (!company) return <div style={center}>회사를 찾을 수 없습니다.</div>

  const available = STATEMENTS.filter(s => lines.some(l => l.sj_div === s.key))
  const shown = lines.filter(l => l.sj_div === sjDiv)
  const period = shown[0]?.thstrm_nm

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={backBtn}>← 목록으로</button>

      <div style={{
        background: '#fff', borderRadius: 12, border: '1px solid #dde2ea',
        padding: '28px 32px', marginTop: 16,
      }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {company.audit_year && <span style={tag}>{company.audit_year}년 감사</span>}
          {company.stock_code && <span style={tag}>{company.stock_code}</span>}
          {company.industry_code && <span style={tag}>업종 {company.industry_code}</span>}
        </div>

        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 16px', color: '#1a1a1a' }}>
          {company.corp_name}
        </h1>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginBottom: 24 }}>
          <tbody>
            <Row label="DART 고유번호" value={company.corp_code} />
            <Row label="대표자" value={company.ceo_name} />
            <Row label="결산월" value={company.fiscal_month && `${company.fiscal_month}월`} />
            <Row label="작업폴더" value={company.workspace_path} />
          </tbody>
        </table>

        {lines.length === 0 ? (
          <div style={{
            padding: '14px 18px', background: '#fdf6f0', border: '1px solid #f0dcc8',
            borderRadius: 8, fontSize: 13, color: '#8a5a1a',
          }}>
            ⚠️ 재무제표가 아직 수집되지 않았습니다. 목록에서 <b>재무제표 수집</b>을 눌러주세요.
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
              {available.map(s => (
                <button
                  key={s.key}
                  onClick={() => setSjDiv(s.key)}
                  style={{
                    padding: '5px 14px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
                    border: sjDiv === s.key ? `2px solid ${ACCENT}` : '1px solid #dde2ea',
                    background: sjDiv === s.key ? ACCENT : '#fff',
                    color: sjDiv === s.key ? '#fff' : '#555',
                    fontWeight: sjDiv === s.key ? 700 : 400,
                  }}
                >
                  {s.label}
                </button>
              ))}
            </div>

            {period && (
              <div style={{ fontSize: 12, color: '#8a9ab0', marginBottom: 8 }}>
                당기 기준: {period} · 단위 {shown[0]?.currency || 'KRW'}
              </div>
            )}

            <div style={{ overflowX: 'auto', border: '1px solid #eef1f5', borderRadius: 8 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 620 }}>
                <thead>
                  <tr style={{ background: '#f8fafd' }}>
                    <th style={th('left')}>계정</th>
                    <th style={th('right')}>당기</th>
                    <th style={th('right')}>전기</th>
                    <th style={th('right')}>전전기</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((l, i) => (
                    <tr key={i} style={{ borderTop: '1px solid #eef1f5' }}>
                      <td style={{ padding: '7px 12px', color: '#333' }}>
                        {l.account_nm}
                        {l.account_detail && (
                          <span style={{ color: '#8a9ab0', fontSize: 12 }}> · {l.account_detail}</span>
                        )}
                      </td>
                      <td style={td}>{fmt(l.thstrm_amount)}</td>
                      <td style={td}>{fmt(l.frmtrm_amount)}</td>
                      <td style={td}>{fmt(l.bfefrmtrm_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }) {
  if (!value) return null
  return (
    <tr style={{ borderBottom: '1px solid #eef1f5' }}>
      <td style={{ padding: '7px 12px 7px 0', color: '#8a9ab0', fontWeight: 600, width: 120 }}>
        {label}
      </td>
      <td style={{ padding: '7px 0', color: '#333', wordBreak: 'break-all' }}>{value}</td>
    </tr>
  )
}

const fmt = (n) => (n === null || n === undefined ? '–' : n.toLocaleString('ko-KR'))

const center  = { textAlign: 'center', padding: 60, color: '#8a9ab0' }
const backBtn = {
  background: 'none', border: '1px solid #dde2ea', borderRadius: 8,
  padding: '8px 16px', cursor: 'pointer', fontSize: 14, color: ACCENT, fontWeight: 600,
}
const tag = {
  background: '#eaf3ea', color: ACCENT, fontSize: 12, fontWeight: 700,
  padding: '3px 12px', borderRadius: 12,
}
const th = (align) => ({
  padding: '9px 12px', textAlign: align, color: '#5a7090',
  fontWeight: 700, fontSize: 12, whiteSpace: 'nowrap',
})
const td = {
  padding: '7px 12px', textAlign: 'right', color: '#333',
  fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
}
