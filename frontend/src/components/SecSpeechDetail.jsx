import { useEffect, useState } from 'react'
import { getSecSpeech, summarizeSecSpeech } from '../api/sec'
import SummaryRenderer from './SummaryRenderer'

export default function SecSpeechDetail({ speechId, onBack }) {
  const [speech, setSpeech] = useState(null)
  const [loading, setLoading] = useState(true)
  const [aiSummary, setAiSummary] = useState(null)
  const [aiStructured, setAiStructured] = useState(null)
  const [summarizing, setSummarizing] = useState(false)
  const [summarizeError, setSummarizeError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setAiSummary(null)
    setAiStructured(null)
    setSummarizeError(null)
    getSecSpeech(speechId)
      .then(setSpeech)
      .finally(() => setLoading(false))
  }, [speechId])

  const handleSummarize = async () => {
    setSummarizing(true)
    setSummarizeError(null)
    setAiSummary(null)
    setAiStructured(null)
    try {
      const result = await summarizeSecSpeech(speechId)
      setAiSummary(result.summary)
      setAiStructured(result.structured ?? null)
    } catch (e) {
      const msg = e.response?.data?.detail || 'AI summarization failed.'
      setSummarizeError(msg)
    } finally {
      setSummarizing(false)
    }
  }

  if (loading) return <div style={centerStyle}>Loading...</div>
  if (!speech) return <div style={centerStyle}>Speech not found.</div>

  const accentColor = '#7b2d00'

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={{ ...backBtnStyle, color: accentColor, borderColor: '#dde2ea' }}>
        ← 목록으로
      </button>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #dde2ea', padding: '32px 36px', marginTop: 16 }}>
        {/* 태그 영역 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          {speech.year && (
            <span style={{ ...tagStyle, background: '#fef3ee', color: accentColor }}>{speech.year}</span>
          )}
          {speech.category && (
            <span style={{ ...tagStyle, background: '#fff7ed', color: '#92400e' }}>{speech.category}</span>
          )}
        </div>

        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.4, color: '#111' }}>
          {speech.title}
        </h1>

        <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#8a9ab0', marginBottom: 28, flexWrap: 'wrap' }}>
          {speech.pub_date && <span>📅 {speech.pub_date}</span>}
          {speech.speaker && <span>🎤 {speech.speaker}</span>}
          {speech.url && (
            <a href={speech.url} target="_blank" rel="noreferrer" style={{ color: accentColor, fontWeight: 600 }}>
              🔗 원문 보기 (SEC.gov)
            </a>
          )}
        </div>

        {/* AI 요약 버튼 */}
        <div style={{ marginBottom: 28 }}>
          <button
            onClick={handleSummarize}
            disabled={summarizing}
            style={summarizeBtnStyle(summarizing, accentColor)}
          >
            {summarizing ? '⏳ AI 요약 중...' : '✨ AI로 연설문 요약하기'}
          </button>
          <div style={{ fontSize: 12, color: '#8a9ab0', marginTop: 6 }}>
            * 수집 시 본문이 자동 추출됩니다. 요약 버튼 클릭 시 Claude AI가 분석합니다.
          </div>

          {summarizeError && (
            <div style={{ marginTop: 12, padding: '12px 16px', background: '#fff5f5', border: '1px solid #fcc', borderRadius: 8, color: '#c00', fontSize: 13 }}>
              {summarizeError}
            </div>
          )}

          {aiSummary && (
            <div style={{ marginTop: 16, padding: '20px 24px', background: '#fff9f5', border: `1px solid ${accentColor}44`, borderRadius: 10 }}>
              <div style={{ fontWeight: 700, fontSize: 15, color: accentColor, marginBottom: 16 }}>
                ✨ AI 요약 결과
              </div>
              <SummaryRenderer text={aiSummary} structured={aiStructured} />
            </div>
          )}
        </div>

        {speech.summary && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: accentColor, marginBottom: 12, paddingBottom: 8, borderBottom: `2px solid #fef3ee` }}>
              📄 요약
            </h2>
            <div style={{ fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line' }}>
              {speech.summary}
            </div>
          </div>
        )}

        {!speech.summary && (
          <div style={{ color: '#8a9ab0', fontSize: 14, padding: '20px 0' }}>
            위의 버튼을 눌러 AI 요약을 실행하거나, 원문을 직접 확인하세요.
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
const tagStyle = {
  display: 'inline-block',
  fontSize: 12,
  fontWeight: 700,
  padding: '3px 12px',
  borderRadius: 12,
}
const summarizeBtnStyle = (disabled, color) => ({
  background: disabled ? '#8a9ab0' : color,
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  padding: '10px 20px',
  fontSize: 14,
  fontWeight: 700,
  cursor: disabled ? 'not-allowed' : 'pointer',
  transition: 'background 0.2s',
})
