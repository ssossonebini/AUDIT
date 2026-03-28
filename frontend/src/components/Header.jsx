export default function Header({ activeTab, onTabChange }) {
  return (
    <header style={{
      background: '#1a3a6c',
      color: '#fff',
      padding: '0 32px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
    }}>
      {/* 타이틀 영역 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        height: 56,
        borderBottom: '1px solid rgba(255,255,255,0.12)',
      }}>
        <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: -0.5 }}>
          📋 회계감사 중점심사사항 아카이브
        </div>
        <div style={{ fontSize: 12, color: '#a8c4e8', marginTop: 2 }}>
          Audit Inspection Focus Areas
        </div>
      </div>

      {/* 탭 네비게이션 */}
      <div style={{ display: 'flex', gap: 0 }}>
        <TabButton
          active={activeTab === 'fss'}
          onClick={() => onTabChange?.('fss')}
          label="🇰🇷 금감원 (FSS)"
          subLabel="중점심사 회계이슈"
        />
        <TabButton
          active={activeTab === 'pcaob'}
          onClick={() => onTabChange?.('pcaob')}
          label="🇺🇸 PCAOB"
          subLabel="Staff Publications"
        />
        <TabButton
          active={activeTab === 'sec'}
          onClick={() => onTabChange?.('sec')}
          label="🇺🇸 SEC"
          subLabel="OCA 연설문"
        />
      </div>
    </header>
  )
}

function TabButton({ active, onClick, label, subLabel }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'none',
        border: 'none',
        borderBottom: active ? '3px solid #7eb8f7' : '3px solid transparent',
        color: active ? '#fff' : 'rgba(255,255,255,0.55)',
        padding: '10px 24px 8px',
        cursor: 'pointer',
        fontWeight: active ? 700 : 400,
        fontSize: 14,
        transition: 'all 0.15s',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: 1,
      }}
    >
      <span>{label}</span>
      <span style={{ fontSize: 10, opacity: 0.75 }}>{subLabel}</span>
    </button>
  )
}
