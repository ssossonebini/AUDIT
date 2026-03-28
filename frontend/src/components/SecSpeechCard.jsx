const CATEGORY_COLORS = {
  'AICPA Conference': '#7b2d00',
  'Staff Statement': '#92400e',
  'Remarks': '#b45309',
  'Staff Publication': '#78350f',
}

export default function SecSpeechCard({ speech, onClick }) {
  const catColor = CATEGORY_COLORS[speech.category] || '#78350f'

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
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(123,45,0,0.13)'
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
            {speech.year && (
              <span style={{
                display: 'inline-block',
                background: '#fef3ee',
                color: catColor,
                fontSize: 12,
                fontWeight: 700,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {speech.year}
              </span>
            )}
            {speech.category && (
              <span style={{
                display: 'inline-block',
                background: catColor + '18',
                color: catColor,
                fontSize: 12,
                fontWeight: 600,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {speech.category}
              </span>
            )}
          </div>
          <div style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.5, marginBottom: 6, color: '#111' }}>
            {speech.title}
          </div>
          <div style={{ display: 'flex', gap: 14, fontSize: 12, color: '#8a9ab0', flexWrap: 'wrap' }}>
            {speech.pub_date && <span>📅 {speech.pub_date}</span>}
            {speech.speaker && <span>🎤 {speech.speaker}</span>}
          </div>
        </div>
        <div style={{
          minWidth: 40,
          height: 40,
          borderRadius: '50%',
          background: '#fef3ee',
          color: catColor,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 18,
          flexShrink: 0,
        }}>
          📝
        </div>
      </div>

      {speech.summary && (
        <div style={{
          marginTop: 12,
          fontSize: 13,
          color: '#555',
          lineHeight: 1.6,
          background: '#fef9f5',
          borderRadius: 8,
          padding: '10px 12px',
          whiteSpace: 'pre-line',
        }}>
          {speech.summary.slice(0, 200)}{speech.summary.length > 200 ? '...' : ''}
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: catColor, fontWeight: 600 }}>
        View Details →
      </div>
    </div>
  )
}
