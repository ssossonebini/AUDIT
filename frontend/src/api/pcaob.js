import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/pcaob' })

export const getPcaobYears = () => api.get('/years').then(r => r.data)

export const getPcaobPublications = (year, category) =>
  api.get('/publications', {
    params: {
      ...(year ? { year } : {}),
      ...(category ? { category } : {}),
    },
  }).then(r => r.data)

export const getPcaobPublication = (id) =>
  api.get(`/publications/${id}`).then(r => r.data)

export const startPcaobCrawl = (maxItems = 30) =>
  api.post('/crawl', null, { params: { max_items: maxItems } }).then(r => r.data)

export const getPcaobCrawlStatus = () => api.get('/crawl/status').then(r => r.data)

export const summarizePcaobPublication = (id) =>
  api.post(`/publications/${id}/summarize`).then(r => r.data)
