import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/fss' })

export const getYears = () => api.get('/years').then(r => r.data)

export const getArticles = (year) =>
  api.get('/articles', { params: year ? { year } : {} }).then(r => r.data)

export const getArticle = (id) => api.get(`/articles/${id}`).then(r => r.data)

export const startCrawl = (maxPages = 5) =>
  api.post('/crawl', null, { params: { max_pages: maxPages } }).then(r => r.data)

export const getCrawlStatus = () => api.get('/crawl/status').then(r => r.data)
