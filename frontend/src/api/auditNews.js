import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/audit-news' })

export const getAuditNewsYears  = ()                 => api.get('/years').then(r => r.data)
export const getAuditNews       = (year, source)     => {
  const params = {}
  if (year)   params.year   = year
  if (source) params.source = source
  return api.get('/news', { params }).then(r => r.data)
}
export const getAuditNewsItem   = (id)               => api.get(`/news/${id}`).then(r => r.data)
export const summarizeAuditNews = (id)               => api.post(`/news/${id}/summarize`).then(r => r.data)
export const getCrawlHistory    = ()                 => api.get('/history').then(r => r.data)
export const startCrawl         = (maxPages = 10)    => api.post('/crawl', null, { params: { max_pages: maxPages } }).then(r => r.data)
export const getCrawlStatus     = ()                 => api.get('/crawl/status').then(r => r.data)
export const resetAuditNews     = ()                 => api.delete('/news').then(r => r.data)
