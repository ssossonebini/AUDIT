import { useEffect, useState } from 'react'
import { getKasbStandard, summarizeKasbStandard } from '../api/kasb'
import SummaryRenderer from './SummaryRenderer'

const TYPE_COLORS = {
  '신규제정': '#1a5c2e',
  '개정':     '#8b6000',
  '해석서':   '#1a3a8c',
}

export default function KasbStandardDetail({ standardId, onBack }) {
  const [std, setStd] = useState(null)
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
    getKasbStandard(standardId)
      .then(setStd)
      .finally(() => setLoading(false))
  }, [standardId])

  const handleSummarize = async () => {
    setSummarizing(true)
    setSummarizeError(null)
    setAiSummary(null)
    setAiStructured(null)
    try {
      const result = await summarizeKasbStandard(standardId)
      setAiSummary(result.summary)
      setAiStructured(result.structured ?? null)
    } catch (e) {
      setSummarizeError(e.response?.data?.detail || 'AI 요약 중 오류가 발생했습니다.')
    } finally {
      setSummarizing(false)
    }
  }

  if (loading) return <div style={centerStyle}>불러오는 중...</div>
  if (!std) return <div style={centerStyle}>기준서를 찾을 수 없습니다.</div>

  const accentColor = TYPE_COLORS[std.amendment_type] || '#1a5c2e'
  const isUpcoming = std.effective_year && std.effective_year >= new Date().getFullYear()

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={{ ...backBtnStyle, color: accentColor }}>← 목록으로</button>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #dde2ea', padding: '32px 36px', marginTop: 16 }}>
        {/* 태그 */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {std.amendment_type && (
            <span style={tagStyle(accentColor)}>{std.amendment_type}</span>
          )}
          {std.category && (
            <span style={tagStyle('#005c8c')}>{std.category}</span>
          )}
          {isUpcoming && (
            <span style={tagStyle('#856404', '#fff3cd')}>⚠ 시행예정</span>
          )}
        </div>

        {/* 기준서 번호 */}
        {std.standard_number && (
          <div style={{ fontSize: 13, fontWeight: 700, color: accentColor, marginBottom: 4 }}>
            {std.standard_number}
          </div>
        )}

        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 16px', lineHeight: 1.4 }}>
          {std.standard_name}
        </h1>

        {/* 메타 정보 테이블 */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          gap: 1, marginBottom: 28,
          border: '1px solid #dde2ea', borderRadius: 8, overflow: 'hidden',
        }}>
          {[
            ['시행일', std.effective_date, isUpcoming],
            ['공포(제정)일', std.issued_date, false],
            ['조기적용', std.early_adoption === 'Y' ? '가능' : (std.early_adoption === 'N' ? '불가' : '-'), false],
            ['대체 기준서', std.replaced_standard || '-', false],
          ].map(([label, value, highlight]) => (
            <div key={label} style={{
              display: 'flex', gap: 12, padding: '10px 16px',
              background: '#fafbfc', borderBottom: '1px solid #eee',
              alignItems: 'center',
            }}>
              <span style={{ fontSize: 12, color: '#8a9ab0', minWidth: 80 }}>{label}</span>
              <span style={{ fontSize: 13, fontWeight: highlight ? 700 : 500, color: highlight ? accentColor : '#333' }}>
                {value || '-'}
              </span>
            </div>
          ))}
        </div>

        {/* 개요 설명 */}
        {std.description && (
          <div style={{
            padding: '16px 20px',
            background: '#f5faf6',
            border: `1px solid #b8d8c0`,
            borderRadius: 8,
            marginBottom: 24,
            fontSize: 14,
            lineHeight: 1.8,
            color: '#333',
          }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: accentColor, marginBottom: 8 }}>📋 기준서 개요</div>
            {std.description}
          </div>
        )}

        {/* 외부 링크 */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
          {std.url && (
            <a href={std.url} target="_blank" rel="noreferrer" style={linkBtnStyle(accentColor)}>
              🔗 KASB 원문 보기
            </a>
          )}
          {std.pdf_url && (
            <a href={std.pdf_url} target="_blank" rel="noreferrer" style={linkBtnStyle('#555')}>
              📄 PDF 다운로드
            </a>
          )}
          <a
            href="https://www.kasb.or.kr/fe/accstd/NR_list.do"
            target="_blank" rel="noreferrer"
            style={linkBtnStyle('#1a3a6c')}
          >
            🏛 KASB 기준서 목록
          </a>
        </div>

        {/* AI 요약 */}
        <div style={{ marginBottom: 28 }}>
          <button
            onClick={handleSummarize}
            disabled={summarizing}
            style={{
              background: summarizing ? '#8a9ab0' : accentColor,
              color: '#fff', border: 'none', borderRadius: 8,
              padding: '10px 20px', fontSize: 14, fontWeight: 700,
              cursor: summarizing ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
            }}
          >
            {summarizing ? '⏳ AI 분석 중...' : '✨ AI로 개정 내용 분석하기'}
          </button>

          {summarizeError && (
            <div style={{
              marginTop: 12, padding: '12px 16px',
              background: '#fff5f5', border: '1px solid #fcc',
              borderRadius: 8, color: '#c00', fontSize: 13,
            }}>
              {summarizeError}
            </div>
          )}

          {aiSummary && (
            <div style={{
              marginTop: 16, padding: '20px 24px',
              background: '#f5faf6', border: `1px solid #b8d8c0`,
              borderRadius: 10,
            }}>
              <div style={{ fontWeight: 700, fontSize: 15, color: accentColor, marginBottom: 16 }}>
                ✨ AI 분석 결과
              </div>
              <SummaryRenderer text={aiSummary} structured={aiStructured} accentColor={accentColor} />
            </div>
          )}
        </div>

        {/* 주요 변경사항 (AI 구조화 결과) */}
        {aiStructured?.changes?.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: accentColor, marginBottom: 16, paddingBottom: 8, borderBottom: `2px solid #d4ebd8` }}>
              📌 주요 변경 사항
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {aiStructured.changes.map((c, i) => (
                <div key={i} style={{
                  background: '#f5faf6', border: '1px solid #c8e0cc',
                  borderLeft: `4px solid ${accentColor}`,
                  borderRadius: '0 8px 8px 0', padding: '12px 16px',
                }}>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3, color: '#1a3a1a' }}>
                    {c.number}. {c.title}
                  </div>
                  {c.description && (
                    <div style={{ fontSize: 13, color: '#555', lineHeight: 1.7 }}>{c.description}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 시사점 */}
        {aiStructured?.implications?.length > 0 && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: accentColor, marginBottom: 12, paddingBottom: 8, borderBottom: `2px solid #d4ebd8` }}>
              💡 감사인·회계담당자 시사점
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
      </div>
    </div>
  )
}

const centerStyle = { textAlign: 'center', padding: 60, color: '#8a9ab0' }
const backBtnStyle = {
  background: 'none', border: '1px solid #dde2ea',
  borderRadius: 8, padding: '8px 16px',
  cursor: 'pointer', fontSize: 14, fontWeight: 600,
}
const tagStyle = (color, bg) => ({
  display: 'inline-block',
  background: bg || `${color}18`,
  color,
  fontSize: 12, fontWeight: 700,
  padding: '3px 12px', borderRadius: 12,
})
const linkBtnStyle = (color) => ({
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '7px 14px',
  background: `${color}12`,
  border: `1px solid ${color}40`,
  borderRadius: 8,
  color,
  fontSize: 13, fontWeight: 600,
  textDecoration: 'none',
  transition: 'background 0.15s',
})
