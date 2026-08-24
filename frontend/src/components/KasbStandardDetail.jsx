import { useEffect, useState } from 'react'
import { getKasbStandard } from '../api/kasb'
import SourcePanel from './SourcePanel'

const ACCENT = '#1a5c2e'

export default function KasbStandardDetail({ standardId, onBack }) {
  const [std, setStd] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getKasbStandard(standardId).then(setStd).finally(() => setLoading(false))
  }, [standardId])

  if (loading) return <div style={centerStyle}>불러오는 중...</div>
  if (!std) return <div style={centerStyle}>기준서를 찾을 수 없습니다.</div>

  const currentYear = new Date().getFullYear()
  const isUpcoming = std.effective_year && std.effective_year > currentYear

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={backBtnStyle}>← 목록으로</button>

      <div style={{
        background: '#fff', borderRadius: 12, border: '1px solid #dde2ea',
        padding: '32px 36px', marginTop: 16,
      }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {std.amendment_type && <span style={tagStyle('#eaf3ea', ACCENT)}>{std.amendment_type}</span>}
          {std.category && <span style={tagStyle('#f0f4fa', '#555')}>{std.category}</span>}
          {isUpcoming && <span style={tagStyle('#fff3e0', '#a8631a')}>⚠ 시행예정</span>}
        </div>

        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 6px', lineHeight: 1.5, color: '#1a1a1a' }}>
          {std.standard_number} {std.standard_name}
        </h1>

        {/* 메타 정보 표 */}
        <table style={{ width: '100%', borderCollapse: 'collapse', margin: '20px 0 24px', fontSize: 13 }}>
          <tbody>
            <MetaRow label="시행일" value={std.effective_date} />
            <MetaRow label="공포일" value={std.issued_date} />
            <MetaRow label="조기적용" value={std.early_adoption === 'Y' ? '가능' : '불가'} />
            {std.replaced_standard && <MetaRow label="대체기준서" value={std.replaced_standard} />}
          </tbody>
        </table>

        {std.description && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={sectionTitleStyle}>📖 개요</h2>
            <div style={bodyTextStyle}>{std.description}</div>
          </div>
        )}

        {std.summary && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={sectionTitleStyle}>📄 요약</h2>
            <div style={bodyTextStyle}>{std.summary}</div>
          </div>
        )}

        <SourcePanel
          hasRawText={std.has_raw_text}
          url={std.url || std.pdf_url}
          linkLabel="원문 보기 (KASB)"
          accentColor={ACCENT}
        />
      </div>
    </div>
  )
}

function MetaRow({ label, value }) {
  if (!value) return null
  return (
    <tr style={{ borderBottom: '1px solid #eef1f5' }}>
      <td style={{ padding: '8px 12px 8px 0', color: '#8a9ab0', fontWeight: 600, width: 110 }}>
        {label}
      </td>
      <td style={{ padding: '8px 0', color: '#333' }}>{value}</td>
    </tr>
  )
}

const centerStyle = { textAlign: 'center', padding: 60, color: '#8a9ab0' }

const backBtnStyle = {
  background: 'none', border: '1px solid #dde2ea', borderRadius: 8,
  padding: '8px 16px', cursor: 'pointer', fontSize: 14,
  color: ACCENT, fontWeight: 600,
}

const tagStyle = (bg, color) => ({
  display: 'inline-block', background: bg, color, fontSize: 12,
  fontWeight: 700, padding: '3px 12px', borderRadius: 12,
})

const sectionTitleStyle = {
  fontSize: 16, fontWeight: 700, color: ACCENT, marginBottom: 12,
  paddingBottom: 8, borderBottom: '2px solid #eaf3ea',
}

const bodyTextStyle = {
  fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line',
}
