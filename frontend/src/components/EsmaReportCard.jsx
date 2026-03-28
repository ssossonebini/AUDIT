export default function EsmaReportCard({ report, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff',
        border: '1px solid #dde2ea',
        borderLeft: '4px solid #003399',
        borderRadius: '0 12px 12px 0',
        padding: '20px 24px',
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,51,153,0.13)'
        e.currentTarget.style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)'
        e.currentTarget.style.transform = 'none'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            {report.year && (
              <span style={{
                display: 'inline-block',
                background: '#e8ecf8',
                color: '#003399',
                fontSize: 12,
                fontWeight: 700,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {report.year}
              </span>
            )}
            {report.category && (
              <span style={{
                display: 'inline-block',
                background: '#003399' + '18',
                color: '#003399',
                fontSize: 12,
                fontWeight: 600,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {report.category}
              </span>
            )}
          </div>
          <div style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.5, marginBottom: 6, color: '#111' }}>
            {report.title}
          </div>
          {report.pub_date && (
            <div style={{ fontSize: 12, color: '#8a9ab0' }}>📅 {report.pub_date}</div>
          )}
        </div>
        {report.pdf_url && (
          <div style={{
            minWidth: 40, height: 40, borderRadius: '50%',
            background: '#e8ecf8', color: '#003399',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, flexShrink: 0,
          }}>
            📄
          </div>
        )}
      </div>

      {report.summary && (
        <div style={{
          marginTop: 12, fontSize: 13, color: '#555', lineHeight: 1.6,
          background: '#f5f7fd', borderRadius: 8, padding: '10px 12px', whiteSpace: 'pre-line',
        }}>
          {report.summary.slice(0, 200)}{report.summary.length > 200 ? '...' : ''}
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: '#003399', fontWeight: 600 }}>
        View Details →
      </div>
    </div>
  )
}
