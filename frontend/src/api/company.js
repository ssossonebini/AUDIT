import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/company' })

export const searchCorp = (name, listedOnly = true) =>
  api.get('/search', { params: { name, listed_only: listedOnly } }).then(r => r.data)

export const getCompanies = (auditYear) =>
  api.get('/companies', { params: auditYear ? { audit_year: auditYear } : {} }).then(r => r.data)

export const getCompany = (id) => api.get(`/companies/${id}`).then(r => r.data)

export const createCompany = (corpCode, auditYear) =>
  api.post('/companies', { corp_code: corpCode, audit_year: auditYear }).then(r => r.data)

export const deleteCompany = (id) => api.delete(`/companies/${id}`).then(r => r.data)

export const collectFinancials = (id, bsnsYear) =>
  api.post(`/companies/${id}/financials`, null,
    { params: bsnsYear ? { bsns_year: bsnsYear } : {} }).then(r => r.data)

export const getFinancials = (id, { bsnsYear, fsDiv, sjDiv } = {}) => {
  const params = {}
  if (bsnsYear) params.bsns_year = bsnsYear
  if (fsDiv)    params.fs_div    = fsDiv
  if (sjDiv)    params.sj_div    = sjDiv
  return api.get(`/companies/${id}/financials`, { params }).then(r => r.data)
}

export const collectDisclosures = (id, bsnsYear) =>
  api.post(`/companies/${id}/disclosures`, null,
    { params: bsnsYear ? { bsns_year: bsnsYear } : {} }).then(r => r.data)

export const getDisclosures = (id, { category, bsnsYear } = {}) => {
  const params = {}
  if (category) params.category = category
  if (bsnsYear) params.bsns_year = bsnsYear
  return api.get(`/companies/${id}/disclosures`, { params }).then(r => r.data)
}

export const collectFilings = (id, pblntfTy) =>
  api.post(`/companies/${id}/filings`, null,
    { params: pblntfTy ? { pblntf_ty: pblntfTy } : {} }).then(r => r.data)

export const getFilings = (id, { tag, pblntfTy } = {}) => {
  const params = {}
  if (tag)      params.tag       = tag
  if (pblntfTy) params.pblntf_ty = pblntfTy
  return api.get(`/companies/${id}/filings`, { params }).then(r => r.data)
}

export const collectNews = (id) =>
  api.post(`/companies/${id}/news`).then(r => r.data)

export const getNews = (id, { tag } = {}) =>
  api.get(`/companies/${id}/news`, { params: tag ? { tag } : {} }).then(r => r.data)

export const exportAnalysis = (id) =>
  api.post(`/companies/${id}/export`).then(r => r.data)

export const collectSections = (id) =>
  api.post(`/companies/${id}/sections`).then(r => r.data)

export const getSections = (id, { auditOnly } = {}) =>
  api.get(`/companies/${id}/sections`, {
    params: auditOnly ? { audit_only: true } : {},
  }).then(r => r.data)

export const getSection = (id, sectionId) =>
  api.get(`/companies/${id}/sections/${sectionId}`).then(r => r.data)

export const retagSections = (id) =>
  api.post(`/companies/${id}/sections/retag`).then(r => r.data)
