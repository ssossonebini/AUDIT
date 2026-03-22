export default function Header() {
  return (
    <header style={{
      background: '#1a3a6c',
      color: '#fff',
      padding: '0 32px',
      height: 64,
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>
        📋 금감원 중점심사 회계이슈
      </div>
      <div style={{ fontSize: 13, color: '#a8c4e8', marginTop: 2 }}>
        금융감독원 재무제표 중점심사 회계이슈 사전예고 아카이브
      </div>
    </header>
  )
}
