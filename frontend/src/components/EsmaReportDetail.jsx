import { useEffect, useState } from 'react'
import { getEsmaReport, summarizeEsmaReport } from '../api/esma'
import SummaryRenderer from './SummaryRenderer'

export default function EsmaReportDetail({ reportId, onBack }) {
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
    getEsmaReport(reportId)
      .then(setReport)
      .finally(() => setLoading(false))
  }, [reportId])

  const handleSummarize = async () => {
    setSummarizing(true)
    setSummarizeError(null)
    setAiSummary(null)
    setAiStructured(null)
    try {
      const result = await summarizeEsmaReport(reportId)
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
  if (!report) return <div style={centerStyle}>Report not found.</div>

  const accent = '#003399'

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={{ ...backBtnStyle, color: accent }}>← 목록으로</button>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #dde2ea', padding: '32px 36px', marginTop: 16 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          {report.year && (
            <span style={{ ...tagStyle, background: '#e8ecf8', color: accent }}>{report.year}</span>
          )}
          {report.category && (
            <span style={{ ...tagStyle, background: '#f0f2fc', color: '#1a3a9c' }}>{report.category}</span>
          )}
        </div>

        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.4, color: '#111' }}>
          {report.title}
        </h1>

        <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#8a9ab0', marginBottom: 28, flexWrap: 'wrap' }}>
          {report.pub_date && <span>📅 {report.pub_date}</span>}
          {report.url && (
            <a href={report.url} target="_blank" rel="noreferrer" style={{ color: accent }}>
              🔗 View Source (ESMA)
            </a>
          )}
          {report.pdf_url && (
            <a href={report.pdf_url} target="_blank" rel="noreferrer" style={{ color: accent, fontWeight: 600 }}>
              📄 Download PDF
            </a>
          )}
        </div>

        <div style={{ marginBottom: 28 }}>
          <button
            onClick={handleSummarize}
            disabled={summarizing}
            style={summarizeBtnStyle(summarizing, accent)}
          >
            {summarizing ? '⏳ AI 요약 중...' : '✨ AI로 PDF 요약하기'}
          </button>

          {summarizeError && (
            <div style={{ marginTop: 12, padding: '12px 16px', background: '#fff5f5', border: '1px solid #fcc', borderRadius: 8, color: '#c00', fontSize: 13 }}>
              {summarizeError}
            </div>
          )}

          {aiSummary && (
            <div style={{ marginTop: 16, padding: '20px 24px', background: '#f0f2fc', border: `1px solid ${accent}44`, borderRadius: 10 }}>
              <div style={{ fontWeight: 700, fontSize: 15, color: accent, marginBottom: 16 }}>
                ✨ AI 요약 결과
              </div>
              <SummaryRenderer text={aiSummary} structured={aiStructured} />
            </div>
          )}
        </div>

        {report.summary && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: accent, marginBottom: 12, paddingBottom: 8, borderBottom: '2px solid #e8ecf8' }}>
              📄 요약
            </h2>
            <div style={{ fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line' }}>
              {report.summary}
            </div>
          </div>
        )}

        {!report.summary && (
          <div style={{ color: '#8a9ab0', fontSize: 14, padding: '20px 0' }}>
            위의 버튼을 눌러 AI 요약을 실행하거나, PDF를 직접 다운로드하여 확인하세요.
          </div>
        )}
      </div>
    </div>
  )
}

const centerStyle = { textAlign: 'center', padding: 60, color: '#8a9ab0' }
const backBtnStyle = {
  background: 'none', border: '1px solid #dde2ea', borderRadius: 8,
  padding: '8px 16px', cursor: 'pointer', fontSize: 14, fontWeight: 600,
}
const tagStyle = {
  display: 'inline-block', fontSize: 12, fontWeight: 700,
  padding: '3px 12px', borderRadius: 12,
}
const summarizeBtnStyle = (disabled, color) => ({
  background: disabled ? '#8a9ab0' : color,
  color: '#fff', border: 'none', borderRadius: 8,
  padding: '10px 20px', fontSize: 14, fontWeight: 700,
  cursor: disabled ? 'not-allowed' : 'pointer', transition: 'background 0.2s',
})
