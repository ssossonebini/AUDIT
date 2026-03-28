import { useState, useEffect, useRef } from 'react'
import { startFssCaseCrawl, getFssCaseCrawlStatus, resetFssCases } from '../api/fssCase'

export default function FssCaseCrawlPanel({ onComplete }) {
  const [status, setStatus] = useState(null)
  const [maxPages, setMaxPages] = useState(3)
  const [resetting, setResetting] = useState(false)
  const pollRef = useRef(null)

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const startPolling = () => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const s = await getFssCaseCrawlStatus()
        setStatus(s)
        if (s.status !== 'running') {
          stopPolling()
          if (s.status === 'idle' && s.processed > 0) {
            onComplete?.()
          }
        }
      } catch {
        stopPolling()
      }
    }, 2000)
  }

  useEffect(() => () => stopPolling(), [])

  const handleStart = async () => {
    try {
      const s = await startFssCaseCrawl(maxPages)
      setStatus(s)
      if (s.status === 'started' || s.status === 'running') {
        startPolling()
      }
    } catch (e) {
      setStatus({ status: 'error', message: e.response?.data?.detail || '오류 발생' })
    }
  }

  const handleReset = async () => {
    if (!window.confirm('기존 지적사례 데이터를 모두 삭제하고 재수집합니다. 계속하시겠습니까?')) return
    setResetting(true)
    try {
      const result = await resetFssCases()
      setStatus({ status: 'idle', message: result.message })
      onComplete?.()
      // 자동으로 재수집 시작
      const s = await startFssCaseCrawl(maxPages)
      setStatus(s)
      if (s.status === 'started' || s.status === 'running') {
        startPolling()
      }
    } catch (e) {
      setStatus({ status: 'error', message: e.response?.data?.detail || '초기화 중 오류 발생' })
    } finally {
      setResetting(false)
    }
  }

  const isRunning = status?.status === 'running' || status?.status === 'started'
  const isBusy = isRunning || resetting
  const progress = status?.total > 0
    ? Math.round((status.processed / status.total) * 100)
    : 0

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
          <div style={{ fontWeight: 700, fontSize: 15, color: '#8b1a1a', marginBottom: 2 }}>
            🔍 금감원 지적사례 수집
          </div>
          <div style={{ fontSize: 12, color: '#8a9ab0' }}>
            금융감독원 회계심사·감리 주요 지적사례 보도자료를 수집합니다
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <label style={{ fontSize: 13, color: '#555', display: 'flex', alignItems: 'center', gap: 6 }}>
            페이지 수:
            <select
              value={maxPages}
              onChange={e => setMaxPages(Number(e.target.value))}
              disabled={isBusy}
              style={{
                border: '1px solid #dde2ea',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 13,
                background: isBusy ? '#f4f6f9' : '#fff',
              }}
            >
              {[1, 2, 3, 5, 10].map(n => (
                <option key={n} value={n}>{n}페이지</option>
              ))}
            </select>
          </label>

          {/* 초기화 후 재수집 버튼 */}
          <button
            onClick={handleReset}
            disabled={isBusy}
            title="기존 데이터를 삭제하고 금감원 사이트에서 실제 데이터를 새로 수집합니다"
            style={{
              background: isBusy ? '#f4f6f9' : '#fff',
              color: isBusy ? '#aaa' : '#8b1a1a',
              border: '1px solid ' + (isBusy ? '#dde2ea' : '#d08080'),
              borderRadius: 8,
              padding: '8px 14px',
              fontSize: 13,
              fontWeight: 600,
              cursor: isBusy ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            🔄 초기화 후 재수집
          </button>

          <button
            onClick={handleStart}
            disabled={isBusy}
            style={{
              background: isBusy ? '#8a9ab0' : '#8b1a1a',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '9px 20px',
              fontSize: 14,
              fontWeight: 700,
              cursor: isBusy ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
            }}
          >
            {isRunning ? '⏳ 수집 중...' : resetting ? '⏳ 초기화 중...' : '🚀 수집 시작'}
          </button>
        </div>
      </div>

      {/* 안내 메시지: AI요약이 안 될 때 */}
      <div style={{
        marginTop: 10,
        padding: '8px 12px',
        background: '#fdf5f0',
        border: '1px solid #f5d0b0',
        borderRadius: 6,
        fontSize: 12,
        color: '#7a4000',
      }}>
        💡 AI 요약 시 "PDF를 찾을 수 없음" 오류가 나타나면 <strong>[초기화 후 재수집]</strong>을 눌러주세요.
        금감원 사이트에서 실제 첨부파일이 있는 데이터를 새로 수집합니다.
      </div>

      {status && (
        <div style={{ marginTop: 12 }}>
          {isRunning && status.total > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#8a9ab0', marginBottom: 4 }}>
                <span>{status.processed} / {status.total}건</span>
                <span>{progress}%</span>
              </div>
              <div style={{ background: '#f4f6f9', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                <div style={{
                  background: '#8b1a1a',
                  height: '100%',
                  width: `${progress}%`,
                  transition: 'width 0.3s',
                }} />
              </div>
            </div>
          )}
          <div style={{
            fontSize: 13,
            color: status.status === 'error' ? '#c00' : '#555',
            padding: '8px 12px',
            background: '#faf8f8',
            borderRadius: 6,
          }}>
            {status.message}
          </div>
        </div>
      )}
    </div>
  )
}
