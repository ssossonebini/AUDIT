import { useState } from 'react'
import { collectFinancials, deleteCompany } from '../api/company'

const ACCENT = '#1a5c2e'

export default function CompanyCard({ company, onClick, onChanged }) {
  const [busy, setBusy]     = useState(null)   // 'collect' | 'delete'
  const [notice, setNotice] = useState(null)

  const handleCollect = async (e) => {
    e.stopPropagation()
    setBusy('collect'); setNotice(null)
    try {
      const r = await collectFinancials(company.id)
      setNotice({ ok: true, text: r.message })
      onChanged?.()
    } catch (err) {
      setNotice({ ok: false, text: err?.response?.data?.detail || '수집에 실패했습니다.' })
    } finally {
      setBusy(null)
    }
  }

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
              {company.has_financials ? '✅ 재무제표 수집됨' : '⚠ 재무제표 미수집'}
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
              background: busy === 'collect' ? '#a0b0c8' : ACCENT, color: '#fff',
              border: 'none', borderRadius: 6, padding: '6px 14px',
              fontSize: 12, fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {busy === 'collect' ? '수집 중...' : '재무제표 수집'}
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
