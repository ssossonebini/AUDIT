import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import YearSelector from './components/YearSelector'
import ArticleCard from './components/ArticleCard'
import ArticleDetail from './components/ArticleDetail'
import CrawlPanel from './components/CrawlPanel'
import PcaobCrawlPanel from './components/PcaobCrawlPanel'
import PcaobPublicationCard from './components/PcaobPublicationCard'
import PcaobPublicationDetail from './components/PcaobPublicationDetail'
import SecCrawlPanel from './components/SecCrawlPanel'
import SecSpeechCard from './components/SecSpeechCard'
import SecSpeechDetail from './components/SecSpeechDetail'
import { getYears, getArticles } from './api/fss'
import { getPcaobYears, getPcaobPublications } from './api/pcaob'
import { getSecYears, getSecSpeeches } from './api/sec'

function App() {
  const [activeTab, setActiveTab] = useState('fss') // 'fss' | 'pcaob' | 'sec'

  return (
    <div style={{ minHeight: '100vh', background: '#f4f6f9' }}>
      <Header activeTab={activeTab} onTabChange={setActiveTab} />
      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 20px' }}>
        {activeTab === 'fss' && <FssView />}
        {activeTab === 'pcaob' && <PcaobView />}
        {activeTab === 'sec' && <SecView />}
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

/* ── SEC 뷰 ─────────────────────────────────────────── */

function SecView() {
  const [years, setYears] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [speeches, setSpeeches] = useState([])
  const [selectedSpeechId, setSelectedSpeechId] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [yrs, spcs] = await Promise.all([getSecYears(), getSecSpeeches(selectedYear)])
      setYears(yrs)
      setSpeeches(spcs)
    } finally {
      setLoading(false)
    }
  }, [selectedYear])

  useEffect(() => { loadData() }, [loadData])

  if (selectedSpeechId) {
    return (
      <SecSpeechDetail speechId={selectedSpeechId} onBack={() => setSelectedSpeechId(null)} />
    )
  }

  return (
    <>
      <SecCrawlPanel onComplete={loadData} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#7b2d00' }}>
          SEC OCA 회계·감사 연설문
        </h2>
        <span style={{ fontSize: 13, color: '#8a9ab0' }}>총 {speeches.length}건</span>
      </div>
      <YearSelector years={years} selected={selectedYear} onChange={y => setSelectedYear(y)} />
      {loading ? <LoadingBox /> : speeches.length === 0 ? (
        <EmptyState message='위의 "수집 시작" 버튼을 눌러 SEC 연설문을 수집해주세요.' />
      ) : (
        <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
          {speeches.map(s => (
            <SecSpeechCard key={s.id} speech={s} onClick={() => setSelectedSpeechId(s.id)} />
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
