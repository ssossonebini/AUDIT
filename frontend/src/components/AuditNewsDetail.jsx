import { useEffect, useState } from 'react'
import { getAuditNewsItem, summarizeAuditNews } from '../api/auditNews'
import SummaryRenderer from './SummaryRenderer'

export default function AuditNewsDetail({ newsId, onBack }) {
  const [item, setItem]               = useState(null)
  const [loading, setLoading]         = useState(true)
  const [aiSummary, setAiSummary]     = useState(null)
  const [aiStructured, setAiStructured] = useState(null)
  const [summarizing, setSummarizing] = useState(false)
  const [summarizeError, setSummarizeError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setAiSummary(null)
    setAiStructured(null)
    setSummarizeError(null)
    getAuditNewsItem(newsId)
      .then(setItem)
      .finally(() => setLoading(false))
  }, [newsId])

  const handleSummarize = async () => {
    setSummarizing(true)
    setSummarizeError(null)
    setAiSummary(null)
    setAiStructured(null)
    try {
      const result = await summarizeAuditNews(newsId)
      setAiSummary(result.summary)
      setAiStructured(result.structured ?? null)
    } catch (e) {
      const msg = e.response?.data?.detail || 'AI 요약 중 오류가 발생했습니다.'
      setSummarizeError(msg)
    } finally {
      setSummarizing(false)
    }
  }

  if (loading) return <div style={centerStyle}>불러오는 중...</div>
  if (!item) return <div style={centerStyle}>항목을 찾을 수 없습니다.</div>

  const isFSS = item.source === 'FSS'
  const accentColor = isFSS ? '#1a3a6c' : '#1a5c8c'
  const sourceName = isFSS ? '금융감독원(FSS)' : '금융위원회(FSC)'

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={{ ...backBtnStyle, color: accentColor, borderColor: '#dde2ea' }}>
        ← 목록으로
      </button>

      <div style={{
        background: '#fff',
        borderRadius: 12,
        border: '1px solid #dde2ea',
        padding: '32px 36px',
        marginTop: 16,
      }}>
        {/* 태그 */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <span style={tagStyle(isFSS ? '#1a3a6c' : '#1a5c8c', '#fff')}>
            {item.source}
          </span>
          {item.year && (
            <span style={tagStyle('#f0f4fa', '#555')}>{item.year}년</span>
          )}
          {item.department && (
            <span style={tagStyle('#f5f5f5', '#777')}>{item.department}</span>
          )}
        </div>

        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.5, color: '#1a1a1a' }}>
          {item.title}
        </h1>

        <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#8a9ab0', marginBottom: 16, flexWrap: 'wrap' }}>
          {item.pub_date && <span>📅 {item.pub_date}</span>}
          {item.url && (
            <a href={item.url} target="_blank" rel="noreferrer" style={{ color: accentColor }}>
              🔗 원문 보기 ({sourceName})
            </a>
          )}
        </div>

        {/* AI 분류 이유 */}
        {item.ai_reason && (
          <div style={{
            background: '#f8fafd',
            border: '1px solid #dde2ea',
            borderRadius: 8,
            padding: '10px 16px',
            fontSize: 13,
            color: '#5a7090',
            marginBottom: 20,
          }}>
            <span style={{ fontWeight: 700 }}>🤖 AI 분류 이유: </span>{item.ai_reason}
          </div>
        )}

        {/* AI 요약 버튼 */}
        <div style={{ marginBottom: 28 }}>
          <button
            onClick={handleSummarize}
            disabled={summarizing}
            style={{
              background: summarizing ? '#8a9ab0' : accentColor,
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '10px 20px',
              fontSize: 14,
              fontWeight: 700,
              cursor: summarizing ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
            }}
          >
            {summarizing ? '⏳ AI 요약 중...' : '✨ AI로 PDF 요약하기'}
          </button>

          {summarizeError && (
            <div style={{
              marginTop: 12,
              padding: '12px 16px',
              background: '#fff5f5',
              border: '1px solid #fcc',
              borderRadius: 8,
              color: '#c00',
              fontSize: 13,
            }}>
              {summarizeError}
            </div>
          )}

          {aiSummary && (
            <div style={{
              marginTop: 16,
              padding: '20px 24px',
              background: '#f5f8fd',
              border: `1px solid ${accentColor}30`,
              borderRadius: 10,
            }}>
              <div style={{ fontWeight: 700, fontSize: 15, color: accentColor, marginBottom: 16 }}>
                ✨ AI 요약 결과
              </div>
              <SummaryRenderer text={aiSummary} structured={aiStructured} accentColor={accentColor} />
            </div>
          )}
        </div>

        {/* 주요 변경사항 */}
        {aiStructured?.changes?.length > 0 && (
          <div style={{ marginBottom: 28 }}>
            <h2 style={{
              fontSize: 16, fontWeight: 700, color: accentColor,
              marginBottom: 16, paddingBottom: 8,
              borderBottom: `2px solid ${accentColor}20`,
            }}>
              📌 주요 변경·발표 사항
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {aiStructured.changes.map((c, i) => (
                <div key={i} style={{
                  background: '#f8fafd',
                  border: '1px solid #e0e8f4',
                  borderLeft: `4px solid ${accentColor}`,
                  borderRadius: '0 8px 8px 0',
                  padding: '14px 18px',
                }}>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4, color: accentColor }}>
                    {c.number}. {c.title}
                  </div>
                  {c.description && (
                    <div style={{ fontSize: 13, color: '#555', lineHeight: 1.7 }}>
                      {c.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 시사점 */}
        {aiStructured?.implications?.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <h2 style={{
              fontSize: 16, fontWeight: 700, color: accentColor,
              marginBottom: 12, paddingBottom: 8,
              borderBottom: `2px solid ${accentColor}20`,
            }}>
              💡 감사인·회계담당자 시사점
            </h2>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {aiStructured.implications.map((imp, i) => (
                <li key={i} style={{ fontSize: 13, color: '#444', lineHeight: 1.8, marginBottom: 4 }}>
                  {imp}
                </li>
              ))}
            </ul>
          </div>
        )}

        {!aiSummary && !item.summary && (
          <div style={{ color: '#8a9ab0', fontSize: 14, padding: '20px 0' }}>
            위의 AI 요약 버튼을 눌러 PDF 내용을 회계감사 관점에서 요약해보세요.
          </div>
        )}

        {!aiSummary && item.summary && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: accentColor, marginBottom: 12, paddingBottom: 8, borderBottom: `2px solid ${accentColor}20` }}>
              📄 요약
            </h2>
            <div style={{ fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line' }}>
              {item.summary}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const centerStyle = { textAlign: 'center', padding: 60, color: '#8a9ab0' }

const backBtnStyle = {
  background: 'none',
  border: '1px solid #dde2ea',
  borderRadius: 8,
  padding: '8px 16px',
  cursor: 'pointer',
  fontSize: 14,
  fontWeight: 600,
}

const tagStyle = (bg, color) => ({
  display: 'inline-block',
  background: bg,
  color,
  fontSize: 12,
  fontWeight: 700,
  padding: '3px 12px',
  borderRadius: 12,
})
