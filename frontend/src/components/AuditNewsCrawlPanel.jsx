import { useState, useEffect, useRef } from 'react'
import { startCrawl, getCrawlStatus, resetAuditNews } from '../api/auditNews'

export default function AuditNewsCrawlPanel({ onComplete }) {
  const [status, setStatus]     = useState(null)
  const [loading, setLoading]   = useState(false)
  const [maxPages, setMaxPages] = useState(10)
  const pollRef = useRef(null)

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  const fetchStatus = async () => {
    try {
      const s = await getCrawlStatus()
      setStatus(s)
      if (s.status !== 'running') {
        stopPoll()
        setLoading(false)
        if (s.status === 'idle' && s.processed > 0) onComplete?.()
      }
    } catch { /* ignore */ }
  }

  useEffect(() => {
    fetchStatus()
    return stopPoll
  }, [])

  const handleStart = async () => {
    setLoading(true)
    try {
      await startCrawl(maxPages)
      pollRef.current = setInterval(fetchStatus, 2000)
    } catch (e) {
      alert('크롤링 시작 실패: ' + (e?.response?.data?.detail || e.message))
      setLoading(false)
    }
  }

  const handleReset = async () => {
    if (!confirm('수집된 모든 보도자료와 크롤링 이력을 삭제합니다. 계속하시겠습니까?')) return
    try {
      const r = await resetAuditNews()
      alert(r.message)
      onComplete?.()
      setStatus(null)
    } catch (e) {
      alert('초기화 실패: ' + (e?.response?.data?.detail || e.message))
    }
  }

  const isRunning = loading || status?.status === 'running'

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #dde2ea',
      borderRadius: 12,
      padding: '18px 22px',
      marginBottom: 24,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: '#1a3a6c', marginBottom: 4 }}>
            📰 FSS·FSC 회계감사 관련 보도자료 수집
          </div>
          <div style={{ fontSize: 12, color: '#8a9ab0' }}>
            금융감독원(FSS) + 금융위원회(FSC) 보도자료에서 회계감사 관련 항목을 AI로 분류합니다.
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ fontSize: 12, color: '#555' }}>
            페이지 수:
            <select
              value={maxPages}
              onChange={e => setMaxPages(Number(e.target.value))}
              disabled={isRunning}
              style={{ marginLeft: 6, padding: '3px 6px', borderRadius: 6, border: '1px solid #ccc', fontSize: 12 }}
            >
              {[5, 10, 20, 50].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>

          <button
            onClick={handleStart}
            disabled={isRunning}
            style={{
              background: isRunning ? '#a0b0c8' : '#1a3a6c',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '8px 18px',
              fontSize: 13,
              fontWeight: 700,
              cursor: isRunning ? 'not-allowed' : 'pointer',
            }}
          >
            {isRunning ? '수집 중...' : '수집 시작'}
          </button>

          <button
            onClick={handleReset}
            disabled={isRunning}
            style={{
              background: 'none',
              color: '#c0392b',
              border: '1px solid #e8a0a0',
              borderRadius: 8,
              padding: '7px 14px',
              fontSize: 12,
              cursor: isRunning ? 'not-allowed' : 'pointer',
            }}
          >
            초기화
          </button>
        </div>
      </div>

      {/* 진행 상태 */}
      {status && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 12, color: '#555', marginBottom: 6 }}>{status.message}</div>

          {isRunning && status.total > 0 && (
            <div style={{ background: '#f0f4fa', borderRadius: 6, height: 8, overflow: 'hidden', marginBottom: 8 }}>
              <div style={{
                width: `${Math.round((status.processed / status.total) * 100)}%`,
                background: '#1a3a6c',
                height: '100%',
                transition: 'width 0.4s',
              }} />
            </div>
          )}

          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <Stat label="키워드 통과" value={status.total} />
            <Stat label="처리 완료" value={status.processed} />
            <Stat label="AI 분류 저장" value={status.classified} color="#1a5c2e" />
          </div>
        </div>
      )}

      {/* CrawlHistory */}
      {(status?.fss_history || status?.fsc_history) && (
        <div style={{
          marginTop: 12,
          paddingTop: 12,
          borderTop: '1px solid #eee',
          display: 'flex',
          gap: 20,
          flexWrap: 'wrap',
        }}>
          {status.fss_history && <HistoryBadge label="FSS 마지막 수집" h={status.fss_history} />}
          {status.fsc_history && <HistoryBadge label="FSC 마지막 수집" h={status.fsc_history} />}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, color = '#1a3a6c' }) {
  return (
    <div style={{ fontSize: 12 }}>
      <span style={{ color: '#8a9ab0' }}>{label}: </span>
      <span style={{ color, fontWeight: 700 }}>{value ?? 0}건</span>
    </div>
  )
}

function HistoryBadge({ label, h }) {
  return (
    <div style={{ fontSize: 11, color: '#8a9ab0' }}>
      <span style={{ fontWeight: 600 }}>{label}: </span>
      {h.last_sdate ?? '-'}
      {h.total_new_items > 0 && (
        <span style={{ marginLeft: 6, color: '#1a5c2e', fontWeight: 700 }}>
          (누적 {h.total_new_items}건)
        </span>
      )}
    </div>
  )
}
