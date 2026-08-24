import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/esma' })

export const getEsmaYears = () => api.get('/years').then(r => r.data)

export const getEsmaReports = (year) =>
  api.get('/reports', { params: year ? { year } : {} }).then(r => r.data)

export const getEsmaReport = (id) =>
  api.get(`/reports/${id}`).then(r => r.data)

export const startEsmaCrawl = (maxItems = 20) =>
  api.post('/crawl', null, { params: { max_items: maxItems } }).then(r => r.data)

export const getEsmaCrawlStatus = () => api.get('/crawl/status').then(r => r.data)

