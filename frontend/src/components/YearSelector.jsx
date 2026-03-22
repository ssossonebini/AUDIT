export default function YearSelector({ years, selected, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '24px 0 8px' }}>
      <button
        onClick={() => onChange(null)}
        style={btnStyle(selected === null)}
      >
        전체
      </button>
      {years.map(y => (
        <button
          key={y}
          onClick={() => onChange(y)}
          style={btnStyle(selected === y)}
        >
          {y}년
        </button>
      ))}
    </div>
  )
}

function btnStyle(active) {
  return {
    padding: '6px 18px',
    borderRadius: 20,
    border: active ? '2px solid #1a3a6c' : '2px solid #dde2ea',
    background: active ? '#1a3a6c' : '#fff',
    color: active ? '#fff' : '#444',
    fontWeight: active ? 700 : 400,
    cursor: 'pointer',
    fontSize: 14,
    transition: 'all 0.15s',
  }
}
