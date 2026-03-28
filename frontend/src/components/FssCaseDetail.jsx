import { useEffect, useState } from 'react'
import { getFssCase, summarizeFssCase } from '../api/fssCase'
import SummaryRenderer from './SummaryRenderer'

export default function FssCaseDetail({ caseId, onBack }) {
  const [report, setReport] = useState(null)
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
    getFssCase(caseId)
      .then(setReport)
      .finally(() => setLoading(false))
  }, [caseId])

  const handleSummarize = async () => {
    setSummarizing(true)
    setSummarizeError(null)
    setAiSummary(null)
    setAiStructured(null)
    try {
      const result = await summarizeFssCase(caseId)
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
  if (!report) return <div style={centerStyle}>지적사례를 찾을 수 없습니다.</div>

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={backBtnStyle}>← 목록으로</button>

      <div style={{
        background: '#fff',
        borderRadius: 12,
        border: '1px solid #dde2ea',
        padding: '32px 36px',
        marginTop: 16,
      }}>
        {/* 태그 */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {report.year && (
            <span style={tagStyle('#fbeaea', '#8b1a1a')}>{report.year}년</span>
          )}
          {report.period && (
            <span style={tagStyle('#fff3f3', '#a33')}>{report.period}</span>
          )}
          <span style={tagStyle('#eaf3ea', '#1a6c2a')}>지적사례</span>
        </div>

        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.5, color: '#1a1a1a' }}>
          {report.title}
        </h1>

        <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#8a9ab0', marginBottom: 28 }}>
          {report.pub_date && <span>📅 {report.pub_date}</span>}
          {report.url && (
            <a href={report.url} target="_blank" rel="noreferrer" style={{ color: '#8b1a1a' }}>
              🔗 원문 보기 (금감원)
            </a>
          )}
        </div>

        {/* AI 요약 */}
        <div style={{ marginBottom: 28 }}>
          <button
            onClick={handleSummarize}
            disabled={summarizing}
            style={summarizeBtnStyle(summarizing)}
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
              background: '#fdf5f5',
              border: '1px solid #f5cccc',
              borderRadius: 10,
            }}>
              <div style={{ fontWeight: 700, fontSize: 15, color: '#8b1a1a', marginBottom: 16 }}>
                ✨ AI 요약 결과
              </div>
              <SummaryRenderer text={aiSummary} structured={aiStructured} accentColor="#8b1a1a" />
            </div>
          )}
        </div>

        {/* 지적사례 구조화 표시 */}
        {aiStructured?.cases?.length > 0 && (
          <div style={{ marginBottom: 28 }}>
            <h2 style={{
              fontSize: 16,
              fontWeight: 700,
              color: '#8b1a1a',
              marginBottom: 16,
              paddingBottom: 8,
              borderBottom: '2px solid #fbeaea',
            }}>
              📌 주요 지적사례
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {aiStructured.cases.map((c, i) => (
                <div key={i} style={{
                  background: '#faf8f8',
                  border: '1px solid #f0dede',
                  borderLeft: '4px solid #8b1a1a',
                  borderRadius: '0 8px 8px 0',
                  padding: '14px 18px',
                }}>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4, color: '#5a1010' }}>
                    사례 {c.number}. {c.title}
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
          <div>
            <h2 style={{
              fontSize: 16,
              fontWeight: 700,
              color: '#8b1a1a',
              marginBottom: 12,
              paddingBottom: 8,
              borderBottom: '2px solid #fbeaea',
            }}>
              💡 주요 시사점
            </h2>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {aiStructured.implications.map((item, i) => (
                <li key={i} style={{ fontSize: 13, color: '#444', lineHeight: 1.8, marginBottom: 4 }}>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {!aiSummary && !report.summary && (
          <div style={{ color: '#8a9ab0', fontSize: 14, padding: '20px 0' }}>
            위의 AI 요약 버튼을 눌러 PDF 내용을 요약해보세요.
          </div>
        )}

        {!aiSummary && report.summary && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: '#8b1a1a', marginBottom: 12, paddingBottom: 8, borderBottom: '2px solid #fbeaea' }}>
              📄 요약
            </h2>
            <div style={{ fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line' }}>
              {report.summary}
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
  color: '#8b1a1a',
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

const summarizeBtnStyle = (disabled) => ({
  background: disabled ? '#8a9ab0' : '#8b1a1a',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  padding: '10px 20px',
  fontSize: 14,
  fontWeight: 700,
  cursor: disabled ? 'not-allowed' : 'pointer',
  transition: 'background 0.2s',
})
