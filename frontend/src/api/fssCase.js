import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/fss-case' })

export const getFssCaseYears = () => api.get('/years').then(r => r.data)

export const getFssCases = (year) =>
  api.get('/cases', { params: year ? { year } : {} }).then(r => r.data)

export const getFssCase = (id) => api.get(`/cases/${id}`).then(r => r.data)

export const startFssCaseCrawl = (maxPages = 5) =>
  api.post('/crawl', null, { params: { max_pages: maxPages } }).then(r => r.data)

export const getFssCaseCrawlStatus = () => api.get('/crawl/status').then(r => r.data)

export const summarizeFssCase = (id) =>
  api.post(`/cases/${id}/summarize`).then(r => r.data)
