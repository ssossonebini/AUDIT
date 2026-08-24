import { useEffect, useState } from 'react'
import { getAuditNewsItem } from '../api/auditNews'
import SourcePanel from './SourcePanel'

export default function AuditNewsDetail({ newsId, onBack }) {
  const [item, setItem] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getAuditNewsItem(newsId).then(setItem).finally(() => setLoading(false))
  }, [newsId])

  if (loading) return <div style={centerStyle}>불러오는 중...</div>
  if (!item) return <div style={centerStyle}>항목을 찾을 수 없습니다.</div>

  const isFSS = item.source === 'FSS'
  const accent = isFSS ? '#1a3a6c' : '#1a5c8c'
  const sourceName = isFSS ? '금융감독원(FSS)' : '금융위원회(FSC)'

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={{ ...backBtnStyle, color: accent }}>← 목록으로</button>

      <div style={{
        background: '#fff', borderRadius: 12, border: '1px solid #dde2ea',
        padding: '32px 36px', marginTop: 16,
      }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <span style={tagStyle(accent, '#fff')}>{item.source}</span>
          {item.year && <span style={tagStyle('#f0f4fa', '#555')}>{item.year}년</span>}
          {item.department && <span style={tagStyle('#f5f5f5', '#777')}>{item.department}</span>}
        </div>

        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.5, color: '#1a1a1a' }}>
          {item.title}
        </h1>

        <div style={{ fontSize: 13, color: '#8a9ab0', marginBottom: 20 }}>
          {item.pub_date && <span>📅 {item.pub_date}</span>}
        </div>

        {item.ai_reason && (
          <div style={{
            background: '#f8fafd', border: '1px solid #dde2ea', borderRadius: 8,
            padding: '12px 16px', fontSize: 13, color: '#5a7090', marginBottom: 20,
            lineHeight: 1.6,
          }}>
            <span style={{ fontWeight: 700 }}>🤖 AI 분류 이유: </span>{item.ai_reason}
          </div>
        )}

        {item.summary && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={{
              fontSize: 16, fontWeight: 700, color: accent, marginBottom: 12,
              paddingBottom: 8, borderBottom: `2px solid ${accent}20`,
            }}>
              📄 요약
            </h2>
            <div style={{ fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line' }}>
              {item.summary}
            </div>
          </div>
        )}

        <SourcePanel
          hasRawText={item.has_raw_text}
          url={item.url}
          linkLabel={`원문 보기 (${sourceName})`}
          accentColor={accent}
        />
      </div>
    </div>
  )
}

const centerStyle = { textAlign: 'center', padding: 60, color: '#8a9ab0' }

const backBtnStyle = {
  background: 'none', border: '1px solid #dde2ea', borderRadius: 8,
  padding: '8px 16px', cursor: 'pointer', fontSize: 14, fontWeight: 600,
}

const tagStyle = (bg, color) => ({
  display: 'inline-block', background: bg, color, fontSize: 12,
  fontWeight: 700, padding: '3px 12px', borderRadius: 12,
})
