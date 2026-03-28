import { useState, useEffect, useRef } from 'react'
import { startSecCrawl, getSecCrawlStatus } from '../api/sec'

export default function SecCrawlPanel({ onComplete }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState(20)
  const pollRef = useRef(null)

  const poll = () => {
    pollRef.current = setInterval(async () => {
      const s = await getSecCrawlStatus()
      setStatus(s)
      if (s.status !== 'running') {
        clearInterval(pollRef.current)
        setLoading(false)
        if (s.status === 'idle' && s.processed > 0) onComplete?.()
      }
    }, 2000)
  }

  const handleStart = async () => {
    setLoading(true)
    const s = await startSecCrawl(items)
    setStatus(s)
    if (s.status === 'started' || s.status === 'running') poll()
    else setLoading(false)
  }

  useEffect(() => () => clearInterval(pollRef.current), [])

  const isRunning = status?.status === 'running' || loading

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #dde2ea',
      borderRadius: 12,
      padding: '20px 24px',
      marginBottom: 24,
    }}>
      <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 8, color: '#7b2d00' }}>
        🔄 SEC 연설문 수집
      </div>
      <div style={{ fontSize: 13, color: '#666', marginBottom: 12, lineHeight: 1.6 }}>
        SEC 홈페이지에서 회계·감사 관련 연설문(AICPA 컨퍼런스 등)을 수집합니다.
        페이지 접근이 제한된 경우 사전 등록된 주요 연설문 목록을 자동으로 사용하며,
        수집 시 각 연설문의 본문 텍스트를 자동으로 추출합니다.
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontSize: 13, color: '#555' }}>
          최대 수집 건수:&nbsp;
          <select
            value={items}
            onChange={e => setItems(Number(e.target.value))}
            disabled={isRunning}
            style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #dde2ea', fontSize: 13 }}
          >
            {[10, 20, 30].map(n => <option key={n} value={n}>{n}건</option>)}
          </select>
        </label>
        <button
          onClick={handleStart}
          disabled={isRunning}
          style={{
            padding: '8px 20px',
            background: isRunning ? '#8a9ab0' : '#7b2d00',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            fontWeight: 700,
            fontSize: 14,
            cursor: isRunning ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? '수집 중...' : '수집 시작'}
        </button>
      </div>

      {status && (
        <div style={{ marginTop: 14, fontSize: 13, color: '#555' }}>
          <div style={{ marginBottom: 6 }}>
            <StatusBadge status={status.status} /> {status.message}
          </div>
          {status.total > 0 && (
            <div>
              <div style={{ background: '#fef3ee', borderRadius: 8, height: 8, overflow: 'hidden', marginBottom: 4 }}>
                <div style={{
                  width: `${Math.round((status.processed / status.total) * 100)}%`,
                  background: '#7b2d00',
                  height: '100%',
                  transition: 'width 0.4s',
                }} />
              </div>
              <span style={{ color: '#8a9ab0' }}>{status.processed} / {status.total} 처리됨</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }) {
  const map = {
    running: ['#f59e0b', '처리 중'],
    started: ['#3b82f6', '시작됨'],
    idle: ['#10b981', '완료'],
  }
  const [color, label] = map[status] || ['#8a9ab0', status]
  return (
    <span style={{ background: color, color: '#fff', borderRadius: 10, padding: '2px 10px', fontSize: 11, fontWeight: 700 }}>
      {label}
    </span>
  )
}
