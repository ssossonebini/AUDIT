export default function ArticleCard({ article, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff',
        border: '1px solid #dde2ea',
        borderRadius: 12,
        padding: '20px 24px',
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(26,58,108,0.13)'
        e.currentTarget.style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)'
        e.currentTarget.style.transform = 'none'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          {article.year && (
            <span style={{
              display: 'inline-block',
              background: '#eaf0fb',
              color: '#1a3a6c',
              fontSize: 12,
              fontWeight: 700,
              padding: '2px 10px',
              borderRadius: 10,
              marginBottom: 8,
            }}>
              {article.year}년도
            </span>
          )}
          <div style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.5, marginBottom: 8 }}>
            {article.title}
          </div>
          {article.pub_date && (
            <div style={{ fontSize: 12, color: '#8a9ab0' }}>📅 {article.pub_date}</div>
          )}
        </div>
        {article.issue_count > 0 && (
          <div style={{
            minWidth: 44,
            height: 44,
            borderRadius: '50%',
            background: '#1a3a6c',
            color: '#fff',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 11,
            fontWeight: 700,
            flexShrink: 0,
          }}>
            <div style={{ fontSize: 18, lineHeight: 1 }}>{article.issue_count}</div>
            <div style={{ fontSize: 9 }}>이슈</div>
          </div>
        )}
      </div>

      {article.summary && (
        <div style={{
          marginTop: 12,
          fontSize: 13,
          color: '#555',
          lineHeight: 1.6,
          background: '#f8f9fc',
          borderRadius: 8,
          padding: '10px 12px',
          whiteSpace: 'pre-line',
        }}>
          {article.summary.slice(0, 200)}{article.summary.length > 200 ? '...' : ''}
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: '#1a3a6c', fontWeight: 600 }}>
        자세히 보기 →
      </div>
    </div>
  )
}
