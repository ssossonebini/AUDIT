export default function FssCaseCard({ report, onClick }) {
  const hasPdf = !!report.pdf_path
  const hasSummary = !!report.summary

  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff',
        border: '1px solid #dde2ea',
        borderLeft: '4px solid #8b1a1a',
        borderRadius: '0 12px 12px 0',
        padding: '18px 22px',
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(139,26,26,0.10)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.transform = 'none'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
            {report.year && (
              <span style={{
                background: '#fbeaea',
                color: '#8b1a1a',
                fontSize: 11,
                fontWeight: 700,
                padding: '2px 10px',
                borderRadius: 10,
              }}>
                {report.year}년
              </span>
            )}
            {report.period && (
              <span style={{
                background: '#fff3f3',
                color: '#a33',
                fontSize: 11,
                fontWeight: 600,
                padding: '2px 10px',
                borderRadius: 10,
                border: '1px solid #f5cccc',
              }}>
                {report.period}
              </span>
            )}
            {hasSummary && (
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
            marginBottom: 6,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}>
            {report.title}
          </div>

          {report.summary && (
            <div style={{
              fontSize: 12,
              color: '#8a9ab0',
              lineHeight: 1.5,
              overflow: 'hidden',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
            }}>
              {report.summary}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          {report.pub_date && (
            <span style={{ fontSize: 12, color: '#8a9ab0' }}>📅 {report.pub_date}</span>
          )}
          {hasPdf && (
            <span style={{ fontSize: 12, color: '#8b1a1a', fontWeight: 600 }}>📄 PDF</span>
          )}
        </div>
      </div>
    </div>
  )
}
