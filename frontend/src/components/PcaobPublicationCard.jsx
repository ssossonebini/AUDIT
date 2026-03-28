const CATEGORY_COLORS = {
  Spotlight: '#1a4a8c',
  'Staff Guidance': '#065f46',
  'Staff Audit Practice Alert': '#7c3aed',
  'Staff Publication': '#374151',
}

export default function PcaobPublicationCard({ publication, onClick }) {
  const catColor = CATEGORY_COLORS[publication.category] || '#374151'

  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff',
        border: '1px solid #dde2ea',
        borderLeft: `4px solid ${catColor}`,
        borderRadius: '0 12px 12px 0',
        padding: '20px 24px',
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(26,74,140,0.13)'
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
            {publication.year && (
              <span style={{
                display: 'inline-block',
                background: '#e8f0fb',
                color: '#1a4a8c',
                fontSize: 12,
                fontWeight: 700,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {publication.year}
              </span>
            )}
            {publication.category && (
              <span style={{
                display: 'inline-block',
                background: catColor + '18',
                color: catColor,
                fontSize: 12,
                fontWeight: 600,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {publication.category}
              </span>
            )}
          </div>
          <div style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.5, marginBottom: 8, color: '#111' }}>
            {publication.title}
          </div>
          {publication.pub_date && (
            <div style={{ fontSize: 12, color: '#8a9ab0' }}>📅 {publication.pub_date}</div>
          )}
        </div>
        {publication.pdf_url && (
          <div style={{
            minWidth: 40,
            height: 40,
            borderRadius: '50%',
            background: '#e8f0fb',
            color: '#1a4a8c',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
            flexShrink: 0,
          }}>
            📄
          </div>
        )}
      </div>

      {publication.summary && (
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
          {publication.summary.slice(0, 200)}{publication.summary.length > 200 ? '...' : ''}
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: '#1a4a8c', fontWeight: 600 }}>
        View Details →
      </div>
    </div>
  )
}
