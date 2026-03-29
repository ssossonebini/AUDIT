export default function AuditNewsCard({ item, onClick }) {
  const isFSS = item.source === 'FSS'

  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff',
        border: '1px solid #dde2ea',
        borderLeft: `4px solid ${isFSS ? '#1a3a6c' : '#1a5c8c'}`,
        borderRadius: '0 12px 12px 0',
        padding: '16px 20px',
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(26,58,108,0.10)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.transform = 'none'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{
              background: isFSS ? '#1a3a6c' : '#1a5c8c',
              color: '#fff',
              fontSize: 11,
              fontWeight: 700,
              padding: '2px 10px',
              borderRadius: 10,
            }}>
              {item.source}
            </span>
            {item.year && (
              <span style={{
                background: '#f0f4fa',
                color: '#555',
                fontSize: 11,
                fontWeight: 600,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {item.year}년
              </span>
            )}
            {item.department && (
              <span style={{
                background: '#f5f5f5',
                color: '#777',
                fontSize: 11,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {item.department}
              </span>
            )}
            {item.summary && (
              <span style={{
                background: '#f0f7ff',
                color: '#1a3a6c',
                fontSize: 11,
                fontWeight: 600,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                ✨ AI요약
              </span>
            )}
          </div>

          <div style={{
            fontWeight: 600,
            fontSize: 14,
            color: '#222',
            lineHeight: 1.5,
            marginBottom: item.ai_reason ? 6 : 0,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}>
            {item.title}
          </div>

          {item.ai_reason && (
            <div style={{
              fontSize: 12,
              color: '#6a82a0',
              lineHeight: 1.5,
              overflow: 'hidden',
              display: '-webkit-box',
              WebkitLineClamp: 1,
              WebkitBoxOrient: 'vertical',
            }}>
              🤖 {item.ai_reason}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          {item.pub_date && (
            <span style={{ fontSize: 12, color: '#8a9ab0' }}>📅 {item.pub_date}</span>
          )}
        </div>
      </div>
    </div>
  )
}
