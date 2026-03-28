import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/kasb' })

export const getKasbEffectiveYears = () => api.get('/effective-years').then(r => r.data)

export const getKasbStandards = ({ effectiveYear, amendmentType, category } = {}) => {
  const params = {}
  if (effectiveYear) params.effective_year = effectiveYear
  if (amendmentType) params.amendment_type = amendmentType
  if (category) params.category = category
  return api.get('/standards', { params }).then(r => r.data)
}

export const getKasbStandard = (id) => api.get(`/standards/${id}`).then(r => r.data)

export const startKasbCrawl = (maxPages = 3) =>
  api.post('/crawl', null, { params: { max_pages: maxPages } }).then(r => r.data)

export const getKasbCrawlStatus = () => api.get('/crawl/status').then(r => r.data)

export const summarizeKasbStandard = (id) =>
  api.post(`/standards/${id}/summarize`).then(r => r.data)
