import { useEffect, useState } from 'react'
import { getCompany, getFinancials, getDisclosures, getFilings } from '../api/company'
import DisclosurePanel from './DisclosurePanel'
import FilingPanel from './FilingPanel'

const ACCENT = '#1a5c2e'

const DIVISIONS = [
  { key: 'CFS', label: '연결' },
  { key: 'OFS', label: '별도' },
]

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
  const [discRows, setDiscRows] = useState([])
  const [filings, setFilings] = useState([])
  const [section, setSection] = useState('fs')   // 'fs' | 'disc'
  const [sjDiv, setSjDiv]     = useState('BS')
  const [fsDiv, setFsDiv]     = useState('CFS')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      getCompany(companyId), getFinancials(companyId),
      getDisclosures(companyId), getFilings(companyId),
    ])
      .then(([c, f, d, g]) => { setCompany(c); setLines(f); setDiscRows(d); setFilings(g) })
      .finally(() => setLoading(false))
  }, [companyId])

  if (loading) return <div style={center}>불러오는 중...</div>
  if (!company) return <div style={center}>회사를 찾을 수 없습니다.</div>

  const divisions = DIVISIONS.filter(d => lines.some(l => l.fs_div === d.key))
  const activeFs = divisions.some(d => d.key === fsDiv) ? fsDiv : divisions[0]?.key
  const inDivision = lines.filter(l => l.fs_div === activeFs)

  const available = STATEMENTS.filter(s => inDivision.some(l => l.sj_div === s.key))
  const activeSj = available.some(s => s.key === sjDiv) ? sjDiv : available[0]?.key
  const shown = inDivision.filter(l => l.sj_div === activeSj)
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

        {/* 재무제표 / 주요정보 */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid #dde2ea' }}>
          {[
            { key: 'fs',   label: '재무제표',  count: lines.length },
            { key: 'disc', label: '주요정보',  count: discRows.length },
            { key: 'filing', label: '공시',    count: filings.length },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => setSection(t.key)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                padding: '8px 18px', fontSize: 14,
                fontWeight: section === t.key ? 700 : 400,
                color: section === t.key ? ACCENT : '#8a9ab0',
                borderBottom: section === t.key ? `2px solid ${ACCENT}` : '2px solid transparent',
                marginBottom: -1,
              }}
            >
              {t.label} <span style={{ fontSize: 12, opacity: 0.8 }}>{t.count}</span>
            </button>
          ))}
        </div>

        {section === 'filing' ? <FilingPanel rows={filings} />
         : section === 'disc' ? <DisclosurePanel rows={discRows} /> : lines.length === 0 ? (
          <div style={{
            padding: '14px 18px', background: '#fdf6f0', border: '1px solid #f0dcc8',
            borderRadius: 8, fontSize: 13, color: '#8a5a1a',
          }}>
            ⚠️ 재무제표가 아직 수집되지 않았습니다. 목록에서 <b>재무제표 수집</b>을 눌러주세요.
          </div>
        ) : (
          <>
            {/* 연결 / 별도 */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
              {divisions.map(d => (
                <button
                  key={d.key}
                  onClick={() => setFsDiv(d.key)}
                  style={{
                    padding: '6px 18px', borderRadius: 8, fontSize: 13, cursor: 'pointer',
                    border: `1px solid ${activeFs === d.key ? ACCENT : '#dde2ea'}`,
                    background: activeFs === d.key ? ACCENT : '#fff',
                    color: activeFs === d.key ? '#fff' : '#555',
                    fontWeight: 700,
                  }}
                >
                  {d.label}재무제표
                </button>
              ))}
              {divisions.length === 1 && (
                <span style={{ fontSize: 12, color: '#8a9ab0', alignSelf: 'center', marginLeft: 4 }}>
                  {divisions[0].key === 'CFS' ? '별도' : '연결'}재무제표는 공시되지 않았습니다
                </span>
              )}
            </div>

            {/* 재무제표 종류 */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
              {available.map(s => (
                <button
                  key={s.key}
                  onClick={() => setSjDiv(s.key)}
                  style={{
                    padding: '5px 14px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
                    border: activeSj === s.key ? `2px solid ${ACCENT}` : '1px solid #dde2ea',
                    background: activeSj === s.key ? ACCENT : '#fff',
                    color: activeSj === s.key ? '#fff' : '#555',
                    fontWeight: activeSj === s.key ? 700 : 400,
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
