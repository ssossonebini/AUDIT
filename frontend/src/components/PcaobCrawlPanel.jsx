import { useState, useEffect, useRef } from 'react'
import { startPcaobCrawl, getPcaobCrawlStatus } from '../api/pcaob'

export default function PcaobCrawlPanel({ onComplete }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState(30)
  const pollRef = useRef(null)

  const poll = () => {
    pollRef.current = setInterval(async () => {
      const s = await getPcaobCrawlStatus()
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
    const s = await startPcaobCrawl(items)
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
      <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 12, color: '#1a4a8c' }}>
        🔄 PCAOB Staff Publications 크롤링
      </div>
      <div style={{ fontSize: 13, color: '#666', marginBottom: 12, lineHeight: 1.6 }}>
        PCAOB 웹사이트에서 Staff Publications 목록을 수집합니다.
        접속이 제한된 경우 사전 등록된 주요 게시물 목록을 자동으로 사용합니다.
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
            {[10, 20, 30, 50].map(n => <option key={n} value={n}>{n}건</option>)}
          </select>
        </label>
        <button
          onClick={handleStart}
          disabled={isRunning}
          style={{
            padding: '8px 20px',
            background: isRunning ? '#8a9ab0' : '#1a4a8c',
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
              <div style={{ background: '#e8f0fb', borderRadius: 8, height: 8, overflow: 'hidden', marginBottom: 4 }}>
                <div style={{
                  width: `${Math.round((status.processed / status.total) * 100)}%`,
                  background: '#1a4a8c',
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
