import { useState, useEffect, useRef } from 'react'
import { startKasbCrawl, getKasbCrawlStatus } from '../api/kasb'

export default function KasbCrawlPanel({ onComplete }) {
  const [status, setStatus] = useState(null)
  const [maxPages, setMaxPages] = useState(3)
  const pollRef = useRef(null)

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  const startPolling = () => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const s = await getKasbCrawlStatus()
        setStatus(s)
        if (s.status !== 'running') {
          stopPolling()
          if (s.status === 'idle' && s.processed > 0) onComplete?.()
        }
      } catch { stopPolling() }
    }, 2000)
  }

  useEffect(() => () => stopPolling(), [])

  const handleStart = async () => {
    try {
      const s = await startKasbCrawl(maxPages)
      setStatus(s)
      if (s.status === 'started' || s.status === 'running') startPolling()
    } catch (e) {
      setStatus({ status: 'error', message: e.response?.data?.detail || '오류 발생' })
    }
  }

  const isRunning = status?.status === 'running' || status?.status === 'started'
  const progress = status?.total > 0 ? Math.round((status.processed / status.total) * 100) : 0

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #dde2ea',
      borderRadius: 12,
      padding: '20px 24px',
      marginBottom: 24,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: '#1a5c2e', marginBottom: 2 }}>
            📐 KASB 기준서 제·개정 현황 수집
          </div>
          <div style={{ fontSize: 12, color: '#8a9ab0' }}>
            한국회계기준원 K-IFRS 제·개정 기준서를 수집합니다
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <label style={{ fontSize: 13, color: '#555', display: 'flex', alignItems: 'center', gap: 6 }}>
            페이지 수:
            <select
              value={maxPages}
              onChange={e => setMaxPages(Number(e.target.value))}
              disabled={isRunning}
              style={{ border: '1px solid #dde2ea', borderRadius: 6, padding: '4px 8px', fontSize: 13 }}
            >
              {[1, 2, 3, 5].map(n => (
                <option key={n} value={n}>{n}페이지</option>
              ))}
            </select>
          </label>

          <button
            onClick={handleStart}
            disabled={isRunning}
            style={{
              background: isRunning ? '#8a9ab0' : '#1a5c2e',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '9px 20px',
              fontSize: 14,
              fontWeight: 700,
              cursor: isRunning ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
            }}
          >
            {isRunning ? '⏳ 수집 중...' : '🚀 수집 시작'}
          </button>
        </div>
      </div>

      {status && (
        <div style={{ marginTop: 14 }}>
          {isRunning && status.total > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#8a9ab0', marginBottom: 4 }}>
                <span>{status.processed} / {status.total}건</span>
                <span>{progress}%</span>
              </div>
              <div style={{ background: '#f4f6f9', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                <div style={{
                  background: '#1a5c2e', height: '100%', width: `${progress}%`, transition: 'width 0.3s',
                }} />
              </div>
            </div>
          )}
          <div style={{
            fontSize: 13,
            color: status.status === 'error' ? '#c00' : '#555',
            padding: '8px 12px',
            background: '#f5faf6',
            borderRadius: 6,
          }}>
            {status.message}
          </div>
        </div>
      )}
    </div>
  )
}
