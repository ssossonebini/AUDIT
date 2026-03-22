import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import YearSelector from './components/YearSelector'
import ArticleCard from './components/ArticleCard'
import ArticleDetail from './components/ArticleDetail'
import CrawlPanel from './components/CrawlPanel'
import { getYears, getArticles } from './api/fss'

function App() {
  const [years, setYears] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [articles, setArticles] = useState([])
  const [selectedArticleId, setSelectedArticleId] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [yrs, arts] = await Promise.all([
        getYears(),
        getArticles(selectedYear),
      ])
      setYears(yrs)
      setArticles(arts)
    } finally {
      setLoading(false)
    }
  }, [selectedYear])

  useEffect(() => { loadData() }, [loadData])

  return (
    <div style={{ minHeight: '100vh', background: '#f4f6f9' }}>
      <Header />
      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 20px' }}>
        {selectedArticleId ? (
          <ArticleDetail
            articleId={selectedArticleId}
            onBack={() => setSelectedArticleId(null)}
          />
        ) : (
          <>
            <CrawlPanel onComplete={loadData} />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#1a3a6c' }}>
                연도별 중점심사 회계이슈
              </h2>
              <span style={{ fontSize: 13, color: '#8a9ab0' }}>
                총 {articles.length}건
              </span>
            </div>

            <YearSelector
              years={years}
              selected={selectedYear}
              onChange={y => setSelectedYear(y)}
            />

            {loading ? (
              <div style={{ textAlign: 'center', padding: 60, color: '#8a9ab0' }}>
                불러오는 중...
              </div>
            ) : articles.length === 0 ? (
              <EmptyState />
            ) : (
              <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
                {articles.map(a => (
                  <ArticleCard
                    key={a.id}
                    article={a}
                    onClick={() => setSelectedArticleId(a.id)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{
      textAlign: 'center',
      padding: '60px 20px',
      color: '#8a9ab0',
      background: '#fff',
      borderRadius: 12,
      border: '1px dashed #dde2ea',
      marginTop: 20,
    }}>
      <div style={{ fontSize: 40, marginBottom: 16 }}>📭</div>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>데이터가 없습니다</div>
      <div style={{ fontSize: 13 }}>위의 크롤링 버튼을 눌러 금감원 보도자료를 수집해주세요.</div>
    </div>
  )
}

export default App
