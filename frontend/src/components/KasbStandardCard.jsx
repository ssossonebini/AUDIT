const TYPE_COLORS = {
  '신규제정': { bg: '#eaf5ea', color: '#1a5c2e', border: '#a8d8b0' },
  '개정':     { bg: '#fff8e6', color: '#8b6000', border: '#f0d080' },
  '해석서':   { bg: '#e8f0ff', color: '#1a3a8c', border: '#b0c4ee' },
}

const CATEGORY_COLORS = {
  'ISSB':        { bg: '#f0e8ff', color: '#5a1a8c' },
  'K-IFRS':      { bg: '#e8f5ff', color: '#005c8c' },
  '일반기업':    { bg: '#fff0e8', color: '#8c3a00' },
}

export default function KasbStandardCard({ standard, onClick }) {
  const typeColor = TYPE_COLORS[standard.amendment_type] || TYPE_COLORS['개정']
  const catColor = CATEGORY_COLORS[standard.category] || CATEGORY_COLORS['K-IFRS']
  const isUpcoming = standard.effective_year && standard.effective_year >= new Date().getFullYear()

  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff',
        border: '1px solid #dde2ea',
        borderLeft: '4px solid #1a5c2e',
        borderRadius: '0 12px 12px 0',
        padding: '18px 22px',
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(26,92,46,0.10)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.transform = 'none'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* 태그 영역 */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
            <span style={{
              background: typeColor.bg,
              color: typeColor.color,
              border: `1px solid ${typeColor.border}`,
              fontSize: 11, fontWeight: 700,
              padding: '2px 10px', borderRadius: 10,
            }}>
              {standard.amendment_type}
            </span>
            <span style={{
              background: catColor.bg, color: catColor.color,
              fontSize: 11, fontWeight: 600, padding: '2px 10px', borderRadius: 10,
            }}>
              {standard.category}
            </span>
            {isUpcoming && (
              <span style={{
                background: '#fff3cd', color: '#856404',
                fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 10,
                border: '1px solid #ffc107',
              }}>
                ⚠ 시행예정
              </span>
            )}
            {standard.summary && (
              <span style={{
                background: '#f0f7ff', color: '#1a3a6c',
                fontSize: 11, fontWeight: 600, padding: '2px 10px', borderRadius: 10,
              }}>
                ✨ AI요약
              </span>
            )}
          </div>

          {/* 기준서 번호 + 명칭 */}
          {standard.standard_number && (
            <div style={{ fontSize: 12, color: '#1a5c2e', fontWeight: 700, marginBottom: 3 }}>
              {standard.standard_number}
            </div>
          )}
          <div style={{
            fontWeight: 600, fontSize: 15, color: '#1a1a1a', lineHeight: 1.4, marginBottom: 6,
          }}>
            {standard.standard_name}
          </div>

          {/* 개요 설명 */}
          {standard.description && (
            <div style={{
              fontSize: 12, color: '#666', lineHeight: 1.6,
              overflow: 'hidden', display: '-webkit-box',
              WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            }}>
              {standard.description}
            </div>
          )}

          {/* 대체 기준서 */}
          {standard.replaced_standard && (
            <div style={{ fontSize: 11, color: '#e07000', marginTop: 6 }}>
              ↩ 대체: {standard.replaced_standard}
            </div>
          )}
        </div>

        {/* 우측 메타 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 5, flexShrink: 0, minWidth: 110 }}>
          {standard.effective_date && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: '#8a9ab0', marginBottom: 1 }}>시행일</div>
              <div style={{
                fontSize: 13, fontWeight: 700,
                color: isUpcoming ? '#1a5c2e' : '#555',
              }}>
                {standard.effective_date}
              </div>
            </div>
          )}
          {standard.early_adoption === 'Y' && (
            <span style={{ fontSize: 10, color: '#1a5c2e', background: '#eaf5ea', padding: '2px 7px', borderRadius: 8 }}>
              조기적용 가능
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
