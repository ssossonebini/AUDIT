import { useState } from 'react'
import {
  collectFinancials, collectDisclosures, collectFilings, collectNews, collectSections, retagSections,
  exportAnalysis, deleteCompany,
} from '../api/company'

const ACCENT = '#1a5c2e'

export default function CompanyCard({ company, onClick, onChanged }) {
  const [busy, setBusy]     = useState(null)   // 'fs' | 'disc' | 'delete'
  const [notice, setNotice] = useState(null)

  const run = (kind, fn) => async (e) => {
    e.stopPropagation()
    setBusy(kind); setNotice(null)
    try {
      const r = await fn(company.id)
      setNotice({ ok: true, text: r.message })
      onChanged?.()
    } catch (err) {
      setNotice({ ok: false, text: err?.response?.data?.detail || '수집에 실패했습니다.' })
    } finally {
      setBusy(null)
    }
  }

  const handleCollect    = run('fs', collectFinancials)
  const handleDisclosure = run('disc', collectDisclosures)
  const handleFilings    = run('filing', collectFilings)
  const handleNews       = run('news', collectNews)
  const handleSections   = run('sec', collectSections)
  const handleRetag      = run('retag', retagSections)
  const handleExport     = run('export', exportAnalysis)

  const handleDelete = async (e) => {
    e.stopPropagation()
    if (!confirm(`${company.corp_name} 등록을 해제할까요?\n작업폴더와 파일은 남습니다.`)) return
    setBusy('delete')
    try {
      await deleteCompany(company.id)
      onChanged?.()
    } catch (err) {
      setNotice({ ok: false, text: err?.response?.data?.detail || '삭제에 실패했습니다.' })
      setBusy(null)
    }
  }

  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff', border: '1px solid #dde2ea',
        borderLeft: `4px solid ${ACCENT}`, borderRadius: '0 12px 12px 0',
        padding: '16px 20px', cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(26,92,46,0.10)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.transform = 'none'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            {company.audit_year && (
              <span style={tag('#eaf3ea', ACCENT)}>{company.audit_year}년 감사</span>
            )}
            {company.stock_code && (
              <span style={tag('#f0f4fa', '#555')}>{company.stock_code}</span>
            )}
            <span style={tag(
              company.has_financials ? '#eaf3ea' : '#fdf6f0',
              company.has_financials ? '#1a5c2e' : '#8a5a1a',
            )}>
              {company.has_financials ? '✅ 재무제표' : '⚠ 재무제표'}
            </span>
            <span style={tag(
              company.has_sections ? '#eaf3ea' : '#fdf6f0',
              company.has_sections ? '#1a5c2e' : '#8a5a1a',
            )}>
              {company.has_sections ? '✅ 원문' : '⚠ 원문'}
            </span>
            <span style={tag(
              company.has_disclosures ? '#eaf3ea' : '#fdf6f0',
              company.has_disclosures ? '#1a5c2e' : '#8a5a1a',
            )}>
              {company.has_disclosures ? '✅ 주요정보' : '⚠ 주요정보'}
            </span>
            <span style={tag(
              company.has_filings ? '#eaf3ea' : '#fdf6f0',
              company.has_filings ? '#1a5c2e' : '#8a5a1a',
            )}>
              {company.has_filings ? '✅ 공시' : '⚠ 공시'}
            </span>
            <span style={tag(
              company.has_news ? '#eaf3ea' : '#fdf6f0',
              company.has_news ? '#1a5c2e' : '#8a5a1a',
            )}>
              {company.has_news ? '✅ 뉴스' : '⚠ 뉴스'}
            </span>
          </div>

          <div style={{ fontWeight: 700, fontSize: 16, color: '#222', marginBottom: 4 }}>
            {company.corp_name}
          </div>

          {company.workspace_path && (
            <div style={{ fontSize: 12, color: '#8a9ab0', wordBreak: 'break-all' }}>
              📁 {company.workspace_path}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0 }}>
          <button
            onClick={handleCollect}
            disabled={busy !== null}
            style={{
              background: busy === 'fs' ? '#a0b0c8' : ACCENT, color: '#fff',
              border: 'none', borderRadius: 6, padding: '6px 14px',
              fontSize: 12, fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {busy === 'fs' ? '수집 중...' : '재무제표 수집'}
          </button>
          <button
            onClick={handleSections}
            disabled={busy !== null}
            style={{
              background: busy === 'sec' ? '#a0b0c8' : '#fff', color: ACCENT,
              border: `1px solid ${ACCENT}`, borderRadius: 6, padding: '5px 14px',
              fontSize: 12, fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {busy === 'sec' ? '수집 중...' : '보고서 원문 수집'}
          </button>
          {company.has_sections && (
            <button
              onClick={handleRetag}
              title="원문을 다시 받지 않고 감사 관련 표시만 갱신합니다"
              disabled={busy !== null}
              style={{
                background: 'none', color: '#8a9ab0', border: 'none',
                padding: '2px 14px 4px', fontSize: 11,
                textDecoration: 'underline', textUnderlineOffset: 3,
                cursor: busy ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
              }}
            >
              {busy === 'retag' ? '갱신 중...' : '표시만 갱신'}
            </button>
          )}
          <button
            onClick={handleDisclosure}
            disabled={busy !== null}
            style={{
              background: busy === 'disc' ? '#a0b0c8' : '#fff', color: ACCENT,
              border: `1px solid ${ACCENT}`, borderRadius: 6, padding: '5px 14px',
              fontSize: 12, fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {busy === 'disc' ? '수집 중...' : '주요정보 수집'}
          </button>
          <button
            onClick={handleFilings}
            disabled={busy !== null}
            style={{
              background: busy === 'filing' ? '#a0b0c8' : '#fff', color: ACCENT,
              border: `1px solid ${ACCENT}`, borderRadius: 6, padding: '5px 14px',
              fontSize: 12, fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {busy === 'filing' ? '수집 중...' : '공시 수집'}
          </button>
          <button
            onClick={handleNews}
            disabled={busy !== null}
            style={{
              background: busy === 'news' ? '#a0b0c8' : '#fff', color: ACCENT,
              border: `1px solid ${ACCENT}`, borderRadius: 6, padding: '5px 14px',
              fontSize: 12, fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {busy === 'news' ? '수집 중...' : '뉴스 수집'}
          </button>
          <button
            onClick={handleExport}
            disabled={busy !== null}
            style={{
              background: busy === 'export' ? '#a0b0c8' : '#1a3a6c', color: '#fff',
              border: 'none', borderRadius: 6, padding: '6px 14px',
              fontSize: 12, fontWeight: 700, marginTop: 4,
              cursor: busy ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {busy === 'export' ? '생성 중...' : '📤 분석자료 내보내기'}
          </button>
          <button
            onClick={handleDelete}
            disabled={busy !== null}
            style={{
              background: 'none', color: '#c0392b', border: '1px solid #e8a0a0',
              borderRadius: 6, padding: '5px 14px', fontSize: 12,
              cursor: busy ? 'not-allowed' : 'pointer',
            }}
          >
            등록 해제
          </button>
        </div>
      </div>

      {notice && (
        <div style={{
          marginTop: 10, padding: '8px 12px', fontSize: 12, borderRadius: 6,
          background: notice.ok ? '#f0f7f2' : '#fff5f5',
          border: `1px solid ${notice.ok ? '#cce5d5' : '#fcc'}`,
          color: notice.ok ? '#1a5c2e' : '#c00',
        }}>
          {notice.text}
        </div>
      )}
    </div>
  )
}

const tag = (bg, color) => ({
  background: bg, color, fontSize: 11, fontWeight: 700,
  padding: '2px 10px', borderRadius: 10,
})
