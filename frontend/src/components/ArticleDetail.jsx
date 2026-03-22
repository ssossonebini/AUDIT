import { useEffect, useState } from 'react'
import { getArticle } from '../api/fss'

export default function ArticleDetail({ articleId, onBack }) {
  const [article, setArticle] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getArticle(articleId)
      .then(setArticle)
      .finally(() => setLoading(false))
  }, [articleId])

  if (loading) return <div style={centerStyle}>불러오는 중...</div>
  if (!article) return <div style={centerStyle}>게시글을 찾을 수 없습니다.</div>

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 0' }}>
      <button onClick={onBack} style={backBtnStyle}>← 목록으로</button>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #dde2ea', padding: '32px 36px', marginTop: 16 }}>
        {article.year && (
          <span style={tagStyle}>{article.year}년도</span>
        )}
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '12px 0 8px', lineHeight: 1.4 }}>
          {article.title}
        </h1>
        <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#8a9ab0', marginBottom: 24 }}>
          {article.pub_date && <span>📅 {article.pub_date}</span>}
          <a href={article.url} target="_blank" rel="noreferrer" style={{ color: '#1a3a6c' }}>
            🔗 원문 보기
          </a>
        </div>

        {article.issues && article.issues.length > 0 && (
          <div style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: '#1a3a6c', marginBottom: 16, paddingBottom: 8, borderBottom: '2px solid #eaf0fb' }}>
              📌 중점심사 회계이슈
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {article.issues.map(issue => (
                <div key={issue.id} style={{
                  background: '#f8f9fc',
                  border: '1px solid #dde2ea',
                  borderLeft: '4px solid #1a3a6c',
                  borderRadius: '0 8px 8px 0',
                  padding: '14px 18px',
                }}>
                  <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
                    이슈 {issue.issue_number}. {issue.issue_title}
                  </div>
                  {issue.description && (
                    <div style={{ fontSize: 13, color: '#555', lineHeight: 1.7, whiteSpace: 'pre-line' }}>
                      {issue.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {article.summary && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: '#1a3a6c', marginBottom: 12, paddingBottom: 8, borderBottom: '2px solid #eaf0fb' }}>
              📄 요약
            </h2>
            <div style={{ fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-line' }}>
              {article.summary}
            </div>
          </div>
        )}

        {!article.summary && !article.issues?.length && (
          <div style={{ color: '#8a9ab0', fontSize: 14, padding: '20px 0' }}>
            PDF 파싱 데이터가 없습니다. 원문을 직접 확인해주세요.
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
  color: '#1a3a6c',
  fontWeight: 600,
}
const tagStyle = {
  display: 'inline-block',
  background: '#eaf0fb',
  color: '#1a3a6c',
  fontSize: 12,
  fontWeight: 700,
  padding: '3px 12px',
  borderRadius: 12,
}
