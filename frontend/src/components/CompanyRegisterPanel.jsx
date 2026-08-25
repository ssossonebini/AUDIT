import { useState } from 'react'
import { searchCorp, createCompany } from '../api/company'

const ACCENT = '#1a5c2e'

export default function CompanyRegisterPanel({ onRegistered }) {
  const [name, setName]           = useState('')
  const [auditYear, setAuditYear] = useState(new Date().getFullYear())
  const [results, setResults]     = useState(null)
  const [searching, setSearching] = useState(false)
  const [busyCode, setBusyCode]   = useState(null)
  const [error, setError]         = useState(null)

  const handleSearch = async (e) => {
    e?.preventDefault()
    if (!name.trim()) return
    setSearching(true); setError(null); setResults(null)
    try {
      setResults(await searchCorp(name.trim()))
    } catch (err) {
      setError(err?.response?.data?.detail || '검색에 실패했습니다.')
    } finally {
      setSearching(false)
    }
  }

  const handleRegister = async (corp) => {
    setBusyCode(corp.corp_code); setError(null)
    try {
      await createCompany(corp.corp_code, Number(auditYear))
      setResults(null); setName('')
      onRegistered?.()
    } catch (err) {
      setError(err?.response?.data?.detail || '등록에 실패했습니다.')
    } finally {
      setBusyCode(null)
    }
  }

  return (
    <div style={{
      background: '#fff', border: '1px solid #dde2ea', borderRadius: 12,
      padding: '18px 22px', marginBottom: 24,
    }}>
      <div style={{ fontWeight: 700, fontSize: 15, color: ACCENT, marginBottom: 4 }}>
        🏢 회사 등록
      </div>
      <div style={{ fontSize: 12, color: '#8a9ab0', marginBottom: 14 }}>
        회사명으로 DART 고유번호를 찾아 등록합니다. 등록 시 작업폴더가 함께 만들어집니다.
      </div>

      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="회사명 (예: 삼성전자)"
          style={{
            flex: 1, minWidth: 200, padding: '8px 12px',
            border: '1px solid #ccd4e0', borderRadius: 8, fontSize: 14,
          }}
        />
        <label style={{ fontSize: 13, color: '#555', display: 'flex', alignItems: 'center', gap: 6 }}>
          감사연도
          <input
            type="number" value={auditYear}
            onChange={e => setAuditYear(e.target.value)}
            style={{
              width: 84, padding: '8px 10px', border: '1px solid #ccd4e0',
              borderRadius: 8, fontSize: 14,
            }}
          />
        </label>
        <button
          type="submit" disabled={searching}
          style={{
            background: searching ? '#a0b0c8' : ACCENT, color: '#fff', border: 'none',
            borderRadius: 8, padding: '8px 20px', fontSize: 13, fontWeight: 700,
            cursor: searching ? 'not-allowed' : 'pointer',
          }}
        >
          {searching ? '검색 중...' : '검색'}
        </button>
      </form>

      {searching && (
        <div style={{ marginTop: 10, fontSize: 12, color: '#8a9ab0' }}>
          첫 검색은 DART 고유번호 파일을 내려받느라 수십 초 걸릴 수 있습니다.
        </div>
      )}

      {error && (
        <div style={{
          marginTop: 12, padding: '10px 14px', background: '#fff5f5',
          border: '1px solid #fcc', borderRadius: 8, color: '#c00', fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {results && (
        <div style={{ marginTop: 14 }}>
          {results.length === 0 ? (
            <div style={{ fontSize: 13, color: '#8a9ab0' }}>
              검색 결과가 없습니다. 상장사 정식 명칭으로 다시 시도해보세요.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {results.map(corp => (
                <div key={corp.corp_code} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 12px', background: '#f8fafd',
                  border: '1px solid #e0e8f4', borderRadius: 8, gap: 12,
                }}>
                  <div style={{ minWidth: 0 }}>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>{corp.corp_name}</span>
                    <span style={{ fontSize: 12, color: '#8a9ab0', marginLeft: 8 }}>
                      {corp.stock_code ? `${corp.stock_code} · ` : ''}{corp.corp_code}
                    </span>
                  </div>
                  <button
                    onClick={() => handleRegister(corp)}
                    disabled={busyCode === corp.corp_code}
                    style={{
                      background: 'none', color: ACCENT, border: `1px solid ${ACCENT}`,
                      borderRadius: 6, padding: '5px 14px', fontSize: 12, fontWeight: 700,
                      cursor: 'pointer', flexShrink: 0,
                    }}
                  >
                    {busyCode === corp.corp_code ? '등록 중...' : '등록'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
