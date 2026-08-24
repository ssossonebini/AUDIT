import { useEffect, useState } from 'react'
import { getPcaobPublication } from '../api/pcaob'
import SourcePanel from './SourcePanel'

const ACCENT = '#1a4a8c'

export default function PcaobPublicationDetail({ publicationId, onBack }) {
  const [pub, setPub] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getPcaobPublication(publicationId).then(setPub).finally(() => setLoading(false))
  }, [publicationId])

  if (loading) return <div style={centerStyle}>불러오는 중...</div>
  if (!pub) return <div style={centerStyle}>게시물을 찾을 수 없습니다.</div>

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={backBtnStyle}>← 목록으로</button>

      <div style={{
        background: '#fff', borderRadius: 12, border: '1px solid #dde2ea',
        padding: '32px 36px', marginTop: 16,
      }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {pub.year && <span style={tagStyle('#eef3fb', ACCENT)}>{pub.year}</span>}
          {pub.category && <span style={tagStyle('#f0f4fa', '#555')}>{pub.category}</span>}
          <span style={tagStyle('#eaf3ea', '#1a6c2a')}>PCAOB</span>
        </div>

        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.5, color: '#1a1a1a' }}>
          {pub.title}
        </h1>

        <div style={{ fontSize: 13, color: '#8a9ab0', marginBottom: 24 }}>
          {pub.pub_date && <span>📅 {pub.pub_date}</span>}
        </div>

        {pub.summary && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={sectionTitleStyle}>📄 요약</h2>
            <div style={bodyTextStyle}>{pub.summary}</div>
          </div>
        )}

        <SourcePanel
          hasRawText={pub.has_raw_text}
          url={pub.url || pub.pdf_url}
          linkLabel="원문 보기 (PCAOB)"
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
  paddingBottom: 8, borderBottom: '2px solid #eef3fb',
}

const bodyTextStyle = {
  fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line',
}
