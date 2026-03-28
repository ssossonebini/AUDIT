import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/sec' })

export const getSecYears = () => api.get('/years').then(r => r.data)

export const getSecSpeeches = (year, category) =>
  api.get('/speeches', {
    params: {
      ...(year ? { year } : {}),
      ...(category ? { category } : {}),
    },
  }).then(r => r.data)

export const getSecSpeech = (id) =>
  api.get(`/speeches/${id}`).then(r => r.data)

export const startSecCrawl = (maxItems = 20) =>
  api.post('/crawl', null, { params: { max_items: maxItems } }).then(r => r.data)

export const getSecCrawlStatus = () => api.get('/crawl/status').then(r => r.data)

export const summarizeSecSpeech = (id) =>
  api.post(`/speeches/${id}/summarize`).then(r => r.data)
