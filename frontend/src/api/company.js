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
