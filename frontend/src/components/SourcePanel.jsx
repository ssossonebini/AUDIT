/**
 * 상세 화면 공통 하단 패널.
 * PDF 본문 수집 여부를 표시하고, 분석은 Claude Code에서 수행하도록 안내한다.
 */
export default function SourcePanel({ hasRawText, url, linkLabel, accentColor = '#1a3a6c' }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '12px 16px',
        borderRadius: 8,
        background: hasRawText ? '#f0f7f2' : '#fdf6f0',
        border: `1px solid ${hasRawText ? '#cce5d5' : '#f0dcc8'}`,
        fontSize: 13,
      }}>
        <span style={{ fontSize: 16 }}>{hasRawText ? '✅' : '⚠️'}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, color: hasRawText ? '#1a5c2e' : '#8a5a1a', marginBottom: 2 }}>
            {hasRawText ? 'PDF 본문 수집 완료' : 'PDF 본문 미수집'}
          </div>
          <div style={{ color: '#6a7a90', fontSize: 12, lineHeight: 1.6 }}>
            {hasRawText
              ? '분석 대상에 포함됩니다. 심층 분석과 카드뉴스 제작은 Claude Code에서 수행하세요.'
              : '첨부 PDF가 없거나 다운로드에 실패했습니다. 원문에서 직접 확인해주세요.'}
          </div>
        </div>
      </div>

      {url && (
        <div style={{ marginTop: 10 }}>
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'inline-block',
              padding: '8px 16px',
              borderRadius: 8,
              border: `1px solid ${accentColor}`,
              color: accentColor,
              fontSize: 13,
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            🔗 {linkLabel || '원문 보기'}
          </a>
        </div>
      )}
    </div>
  )
}
