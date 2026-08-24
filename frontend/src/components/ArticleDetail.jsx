import { useEffect, useState } from 'react'
import { getArticle } from '../api/fss'
import SourcePanel from './SourcePanel'

const ACCENT = '#1a3a6c'

export default function ArticleDetail({ articleId, onBack }) {
  const [article, setArticle] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getArticle(articleId).then(setArticle).finally(() => setLoading(false))
  }, [articleId])

  if (loading) return <div style={centerStyle}>불러오는 중...</div>
  if (!article) return <div style={centerStyle}>보도자료를 찾을 수 없습니다.</div>

  const issues = article.issues || []

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={backBtnStyle}>← 목록으로</button>

      <div style={{
        background: '#fff', borderRadius: 12, border: '1px solid #dde2ea',
        padding: '32px 36px', marginTop: 16,
      }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {article.year && <span style={tagStyle('#eef3fb', ACCENT)}>{article.year}년</span>}
          <span style={tagStyle('#eaf3ea', '#1a6c2a')}>중점심사 회계이슈</span>
        </div>

        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.5, color: '#1a1a1a' }}>
          {article.title}
        </h1>

        <div style={{ fontSize: 13, color: '#8a9ab0', marginBottom: 24 }}>
          {article.pub_date && <span>📅 {article.pub_date}</span>}
        </div>

        {issues.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={sectionTitleStyle}>📌 중점심사 회계이슈</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {issues.map((iss, i) => (
                <div key={iss.id ?? i} style={{
                  background: '#f8fafd', border: '1px solid #e0e8f4',
                  borderLeft: `4px solid ${ACCENT}`, borderRadius: '0 8px 8px 0',
                  padding: '14px 18px',
                }}>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4, color: ACCENT }}>
                    {iss.issue_number}. {iss.issue_title}
                  </div>
                  {iss.description && (
                    <div style={{ fontSize: 13, color: '#555', lineHeight: 1.7 }}>
                      {iss.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {article.summary && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={sectionTitleStyle}>📄 요약</h2>
            <div style={bodyTextStyle}>{article.summary}</div>
          </div>
        )}

        <SourcePanel
          hasRawText={article.has_raw_text}
          url={article.url}
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
  paddingBottom: 8, borderBottom: '2px solid #eef3fb',
}

const bodyTextStyle = {
  fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line',
}
