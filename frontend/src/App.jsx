import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import YearSelector from './components/YearSelector'
import ArticleCard from './components/ArticleCard'
import ArticleDetail from './components/ArticleDetail'
import CrawlPanel from './components/CrawlPanel'
import PcaobCrawlPanel from './components/PcaobCrawlPanel'
import PcaobPublicationCard from './components/PcaobPublicationCard'
import PcaobPublicationDetail from './components/PcaobPublicationDetail'
import EsmaCrawlPanel from './components/EsmaCrawlPanel'
import EsmaReportCard from './components/EsmaReportCard'
import EsmaReportDetail from './components/EsmaReportDetail'
import FssCaseCrawlPanel from './components/FssCaseCrawlPanel'
import FssCaseCard from './components/FssCaseCard'
import FssCaseDetail from './components/FssCaseDetail'
import KasbCrawlPanel from './components/KasbCrawlPanel'
import KasbStandardCard from './components/KasbStandardCard'
import KasbStandardDetail from './components/KasbStandardDetail'
import AuditNewsCrawlPanel from './components/AuditNewsCrawlPanel'
import AuditNewsCard from './components/AuditNewsCard'
import AuditNewsDetail from './components/AuditNewsDetail'
import { getYears, getArticles } from './api/fss'
import { getPcaobYears, getPcaobPublications } from './api/pcaob'
import { getEsmaYears, getEsmaReports } from './api/esma'
import { getFssCaseYears, getFssCases } from './api/fssCase'
import { getKasbEffectiveYears, getKasbStandards } from './api/kasb'
import { getAuditNewsYears, getAuditNews } from './api/auditNews'

function App() {
  const [activeTab, setActiveTab] = useState('fss') // 'fss' | 'fss-case' | 'kasb' | 'pcaob' | 'esma' | 'audit-news'

  return (
    <div style={{ minHeight: '100vh', background: '#f4f6f9' }}>
      <Header activeTab={activeTab} onTabChange={setActiveTab} />
      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 20px' }}>
        {activeTab === 'fss' && <FssView />}
        {activeTab === 'fss-case' && <FssCaseView />}
        {activeTab === 'kasb' && <KasbView />}
        {activeTab === 'pcaob' && <PcaobView />}
        {activeTab === 'esma' && <EsmaView />}
        {activeTab === 'audit-news' && <AuditNewsView />}
      </main>
    </div>
  )
}

/* ── 금감원 뷰 ──────────────────────────────────────── */

function FssView() {
  const [years, setYears] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [articles, setArticles] = useState([])
  const [selectedArticleId, setSelectedArticleId] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [yrs, arts] = await Promise.all([getYears(), getArticles(selectedYear)])
      setYears(yrs)
      setArticles(arts)
    } finally {
      setLoading(false)
    }
  }, [selectedYear])

  useEffect(() => { loadData() }, [loadData])

  if (selectedArticleId) {
    return (
      <ArticleDetail
        articleId={selectedArticleId}
        onBack={() => setSelectedArticleId(null)}
      />
    )
  }

  return (
    <>
      <CrawlPanel onComplete={loadData} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#1a3a6c' }}>연도별 중점심사 회계이슈</h2>
        <span style={{ fontSize: 13, color: '#8a9ab0' }}>총 {articles.length}건</span>
      </div>
      <YearSelector years={years} selected={selectedYear} onChange={y => setSelectedYear(y)} />
      {loading ? <LoadingBox /> : articles.length === 0 ? (
        <EmptyState message="위의 크롤링 버튼을 눌러 금감원 보도자료를 수집해주세요." />
      ) : (
        <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
          {articles.map(a => (
            <ArticleCard key={a.id} article={a} onClick={() => setSelectedArticleId(a.id)} />
          ))}
        </div>
      )}
    </>
  )
}

/* ── PCAOB 뷰 ──────────────────────────────────────── */

function PcaobView() {
  const [years, setYears] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [publications, setPublications] = useState([])
  const [selectedPubId, setSelectedPubId] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [yrs, pubs] = await Promise.all([getPcaobYears(), getPcaobPublications(selectedYear)])
      setYears(yrs)
      setPublications(pubs)
    } finally {
      setLoading(false)
    }
  }, [selectedYear])

  useEffect(() => { loadData() }, [loadData])

  if (selectedPubId) {
    return (
      <PcaobPublicationDetail publicationId={selectedPubId} onBack={() => setSelectedPubId(null)} />
    )
  }

  return (
    <>
      <PcaobCrawlPanel onComplete={loadData} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#1a4a8c' }}>PCAOB Staff Publications</h2>
        <span style={{ fontSize: 13, color: '#8a9ab0' }}>총 {publications.length}건</span>
      </div>
      <YearSelector years={years} selected={selectedYear} onChange={y => setSelectedYear(y)} />
      {loading ? <LoadingBox /> : publications.length === 0 ? (
        <EmptyState message='위의 "수집 시작" 버튼을 눌러 PCAOB 게시물을 수집해주세요.' />
      ) : (
        <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
          {publications.map(p => (
            <PcaobPublicationCard key={p.id} publication={p} onClick={() => setSelectedPubId(p.id)} />
          ))}
        </div>
      )}
    </>
  )
}

/* ── 금감원 지적사례 뷰 ──────────────────────────────── */

function FssCaseView() {
  const [years, setYears] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [cases, setCases] = useState([])
  const [selectedCaseId, setSelectedCaseId] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [yrs, cs] = await Promise.all([getFssCaseYears(), getFssCases(selectedYear)])
      setYears(yrs)
      setCases(cs)
    } finally {
      setLoading(false)
    }
  }, [selectedYear])

  useEffect(() => { loadData() }, [loadData])

  if (selectedCaseId) {
    return (
      <FssCaseDetail caseId={selectedCaseId} onBack={() => setSelectedCaseId(null)} />
    )
  }

  return (
    <>
      <FssCaseCrawlPanel onComplete={loadData} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#8b1a1a' }}>회계심사·감리 지적사례</h2>
        <span style={{ fontSize: 13, color: '#8a9ab0' }}>총 {cases.length}건</span>
      </div>
      <YearSelector years={years} selected={selectedYear} onChange={y => setSelectedYear(y)} />
      {loading ? <LoadingBox /> : cases.length === 0 ? (
        <EmptyState message='위의 "수집 시작" 버튼을 눌러 금감원 지적사례를 수집해주세요.' />
      ) : (
        <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
          {cases.map(c => (
            <FssCaseCard key={c.id} report={c} onClick={() => setSelectedCaseId(c.id)} />
          ))}
        </div>
      )}
    </>
  )
}

/* ── KASB 기준서 뷰 ──────────────────────────────────── */

function KasbView() {
  const [years, setYears] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [standards, setStandards] = useState([])
  const [selectedStdId, setSelectedStdId] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [yrs, stds] = await Promise.all([
        getKasbEffectiveYears(),
        getKasbStandards({ effectiveYear: selectedYear }),
      ])
      setYears(yrs)
      setStandards(stds)
    } finally {
      setLoading(false)
    }
  }, [selectedYear])

  useEffect(() => { loadData() }, [loadData])

  if (selectedStdId) {
    return <KasbStandardDetail standardId={selectedStdId} onBack={() => setSelectedStdId(null)} />
  }

  return (
    <>
      <KasbCrawlPanel onComplete={loadData} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#1a5c2e' }}>K-IFRS 제·개정 현황</h2>
        <span style={{ fontSize: 13, color: '#8a9ab0' }}>총 {standards.length}건</span>
      </div>
      <div style={{ marginBottom: 8 }}>
        <YearSelectorLabeled
          label="시행연도"
          years={years}
          selected={selectedYear}
          onChange={y => setSelectedYear(y)}
        />
      </div>
      {loading ? <LoadingBox /> : standards.length === 0 ? (
        <EmptyState message='위의 "수집 시작" 버튼을 눌러 KASB 기준서 제·개정 현황을 수집해주세요.' />
      ) : (
        <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
          {standards.map(s => (
            <KasbStandardCard key={s.id} standard={s} onClick={() => setSelectedStdId(s.id)} />
          ))}
        </div>
      )}
    </>
  )
}

function YearSelectorLabeled({ label, years, selected, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
      <span style={{ fontSize: 12, color: '#8a9ab0', fontWeight: 600 }}>{label}:</span>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button
          onClick={() => onChange(null)}
          style={yearBtnStyle(!selected)}
        >
          전체
        </button>
        {years.map(y => (
          <button
            key={y}
            onClick={() => onChange(y)}
            style={yearBtnStyle(selected === y)}
          >
            {y}년
          </button>
        ))}
      </div>
    </div>
  )
}

function yearBtnStyle(active) {
  return {
    padding: '5px 14px',
    borderRadius: 20,
    border: active ? '2px solid #1a5c2e' : '1px solid #dde2ea',
    background: active ? '#1a5c2e' : '#fff',
    color: active ? '#fff' : '#555',
    fontSize: 13,
    fontWeight: active ? 700 : 400,
    cursor: 'pointer',
    transition: 'all 0.15s',
  }
}

/* ── ESMA 뷰 ─────────────────────────────────────────── */

function EsmaView() {
  const [years, setYears] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [reports, setReports] = useState([])
  const [selectedReportId, setSelectedReportId] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [yrs, rpts] = await Promise.all([getEsmaYears(), getEsmaReports(selectedYear)])
      setYears(yrs)
      setReports(rpts)
    } finally {
      setLoading(false)
    }
  }, [selectedYear])

  useEffect(() => { loadData() }, [loadData])

  if (selectedReportId) {
    return (
      <EsmaReportDetail reportId={selectedReportId} onBack={() => setSelectedReportId(null)} />
    )
  }

  return (
    <>
      <EsmaCrawlPanel onComplete={loadData} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#003399' }}>
          ESMA ECEP 보고서
        </h2>
        <span style={{ fontSize: 13, color: '#8a9ab0' }}>총 {reports.length}건</span>
      </div>
      <YearSelector years={years} selected={selectedYear} onChange={y => setSelectedYear(y)} />
      {loading ? <LoadingBox /> : reports.length === 0 ? (
        <EmptyState message='위의 "수집 시작" 버튼을 눌러 ESMA ECEP 보고서를 수집해주세요.' />
      ) : (
        <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
          {reports.map(r => (
            <EsmaReportCard key={r.id} report={r} onClick={() => setSelectedReportId(r.id)} />
          ))}
        </div>
      )}
    </>
  )
}

/* ── 감사 보도자료 뷰 ──────────────────────────────── */

function AuditNewsView() {
  const [years, setYears]               = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [source, setSource]             = useState(null)  // null | 'FSS' | 'FSC'
  const [items, setItems]               = useState([])
  const [selectedId, setSelectedId]     = useState(null)
  const [loading, setLoading]           = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [yrs, news] = await Promise.all([
        getAuditNewsYears(),
        getAuditNews(selectedYear, source),
      ])
      setYears(yrs)
      setItems(news)
    } finally {
      setLoading(false)
    }
  }, [selectedYear, source])

  useEffect(() => { loadData() }, [loadData])

  if (selectedId) {
    return <AuditNewsDetail newsId={selectedId} onBack={() => setSelectedId(null)} />
  }

  return (
    <>
      <AuditNewsCrawlPanel onComplete={loadData} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#1a3a6c' }}>FSS·FSC 감사 관련 보도자료</h2>
        <span style={{ fontSize: 13, color: '#8a9ab0' }}>총 {items.length}건</span>
      </div>

      {/* 출처 필터 */}
      <div style={{ display: 'flex', gap: 6, marginTop: 12, marginBottom: 4 }}>
        {[null, 'FSS', 'FSC'].map(s => (
          <button
            key={s ?? 'all'}
            onClick={() => setSource(s)}
            style={{
              padding: '5px 14px',
              borderRadius: 20,
              border: source === s ? '2px solid #1a3a6c' : '1px solid #dde2ea',
              background: source === s ? '#1a3a6c' : '#fff',
              color: source === s ? '#fff' : '#555',
              fontSize: 13,
              fontWeight: source === s ? 700 : 400,
              cursor: 'pointer',
            }}
          >
            {s ?? '전체'}
          </button>
        ))}
      </div>

      <YearSelector years={years} selected={selectedYear} onChange={y => setSelectedYear(y)} />
      {loading ? <LoadingBox /> : items.length === 0 ? (
        <EmptyState message='위의 "수집 시작" 버튼을 눌러 보도자료를 수집해주세요.' />
      ) : (
        <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
          {items.map(item => (
            <AuditNewsCard key={item.id} item={item} onClick={() => setSelectedId(item.id)} />
          ))}
        </div>
      )}
    </>
  )
}

/* ── 공통 컴포넌트 ──────────────────────────────────── */

function LoadingBox() {
  return <div style={{ textAlign: 'center', padding: 60, color: '#8a9ab0' }}>불러오는 중...</div>
}

function EmptyState({ message }) {
  return (
    <div style={{
      textAlign: 'center', padding: '60px 20px', color: '#8a9ab0',
      background: '#fff', borderRadius: 12, border: '1px dashed #dde2ea', marginTop: 20,
    }}>
      <div style={{ fontSize: 40, marginBottom: 16 }}>📭</div>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>데이터가 없습니다</div>
      <div style={{ fontSize: 13 }}>{message}</div>
    </div>
  )
}

export default App
