import { useEffect, useState } from 'react'
import { getFssCase } from '../api/fssCase'
import SourcePanel from './SourcePanel'

const ACCENT = '#8b1a1a'

export default function FssCaseDetail({ caseId, onBack }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getFssCase(caseId).then(setReport).finally(() => setLoading(false))
  }, [caseId])

  if (loading) return <div style={centerStyle}>불러오는 중...</div>
  if (!report) return <div style={centerStyle}>지적사례를 찾을 수 없습니다.</div>

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={backBtnStyle}>← 목록으로</button>

      <div style={{
        background: '#fff', borderRadius: 12, border: '1px solid #dde2ea',
        padding: '32px 36px', marginTop: 16,
      }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {report.year && <span style={tagStyle('#fbeaea', ACCENT)}>{report.year}년</span>}
          {report.period && <span style={tagStyle('#fff3f3', '#a33')}>{report.period}</span>}
          <span style={tagStyle('#eaf3ea', '#1a6c2a')}>지적사례</span>
        </div>

        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.5, color: '#1a1a1a' }}>
          {report.title}
        </h1>

        <div style={{ fontSize: 13, color: '#8a9ab0', marginBottom: 24 }}>
          {report.pub_date && <span>📅 {report.pub_date}</span>}
        </div>

        {report.summary && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={sectionTitleStyle}>📄 요약</h2>
            <div style={bodyTextStyle}>{report.summary}</div>
          </div>
        )}

        <SourcePanel
          hasRawText={report.has_raw_text}
          url={report.url}
          linkLabel="원문 보기 (금융감독원)"
          accentColor={ACCENT}
        />
      </div>
    </div>
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
  paddingBottom: 8, borderBottom: '2px solid #fbeaea',
}

const bodyTextStyle = {
  fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line',
}
