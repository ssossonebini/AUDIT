/**
 * 정기보고서 주요정보 표시.
 *
 * 항목마다 응답 컬럼이 달라 고정 표를 쓸 수 없다. payload 키를 그대로
 * 헤더로 삼아 렌더링하고, 자주 나오는 키만 한글 이름을 붙인다.
 */
import { useMemo, useState } from 'react'

const ACCENT = '#1a5c2e'

// 항목별 응답 컬럼명 → 한글. DART 필드명은 항목마다 달라 한데 모아둔다.
const KEY_LABELS = {
  // 공통
  rcept_no: '접수번호', bsns_year: '사업연도', se: '구분', rm: '비고',
  stock_knd: '주식종류', stock_knd2: '주식종류',
  thstrm: '당기', frmtrm: '전기', lwfr: '전전기',

  // 배당
  thstrm_nm: '당기', frmtrm_nm: '전기', lwfr_nm: '전전기',

  // 증자(감자)
  isu_dcrs_de: '주식발행일', isu_dcrs_stle: '발행형태',
  isu_dcrs_stock_knd: '주식종류', isu_dcrs_qy: '수량',
  isu_dcrs_mstvdv_fval_amount: '액면가', isu_dcrs_mstvdv_amount: '발행가',

  // 자기주식
  acqs_mth1: '취득방법', acqs_mth2: '취득구분', acqs_mth3: '취득방법 상세',
  bsis_qy: '기초수량', change_qy_acqs: '취득', change_qy_dsps: '처분',
  change_qy_incnr: '소각', trmend_qy: '기말수량',

  // 타법인 출자
  inv_prm: '법인명', frst_acqs_de: '최초취득일', invstmnt_purps: '출자목적',
  frst_acqs_amount: '최초취득금액',
  bsis_blce_qy: '기초수량', bsis_blce_qota_rt: '기초지분율',
  bsis_blce_acntbk_amount: '기초장부가액',
  incrs_dcrs_acqs_dsps_qy: '증감수량', incrs_dcrs_acqs_dsps_amount: '증감금액',
  incrs_dcrs_evl_lstmn: '평가손익',
  trmend_blce_qy: '기말수량', trmend_blce_qota_rt: '기말지분율',
  trmend_blce_acntbk_amount: '기말장부가액',
  recent_bsns_year_fnnr_sttus_tot_assets: '피출자사 총자산',
  recent_bsns_year_fnnr_sttus_thstrm_ntpf: '피출자사 당기순손익',

  // 최대주주 현황
  nm: '성명', relate: '관계',
  bsis_posesn_stock_co: '기초 주식수', bsis_posesn_stock_qota_rt: '기초 지분율',
  trmend_posesn_stock_co: '기말 주식수', trmend_posesn_stock_qota_rt: '기말 지분율',

  // 최대주주 변동
  change_on: '변동일', mxmm_shrholdr_nm: '최대주주명',
  posesn_stock_co: '보유주식수', qota_rt: '지분율', change_cause: '변동원인',

  // 감사인·감사의견
  adtor: '감사인', adt_opinion: '감사의견',
  adt_reprt_spcmnt_matter: '감사보고서 특기사항',
  emphs_matter: '강조사항', core_adt_matter: '핵심감사사항',

  // 감사용역 체결현황
  cn: '내용', mendng: '보수', tot_reqre_time: '총 소요시간',
  adt_cntrct_dtls_mendng: '계약 보수', adt_cntrct_dtls_time: '계약 시간',
  real_exc_dtls_mendng: '실제 보수', real_exc_dtls_time: '실제 시간',
  adt_cntrct_details: '감사계약내역',
  servc_cn: '용역내용', servc_exc_pd: '용역수행기간',
  servc_mendng: '용역보수', cntrct_cncls_de: '계약체결일',
}

const SKIP = new Set(['corp_code', 'corp_cls', 'corp_name', 'status', 'message'])

export default function DisclosurePanel({ rows }) {
  const categories = useMemo(() => {
    const seen = []
    for (const r of rows) if (!seen.includes(r.category)) seen.push(r.category)
    return seen
  }, [rows])

  const [active, setActive] = useState(null)
  const current = active && categories.includes(active) ? active : categories[0]
  const shown = rows.filter(r => r.category === current)

  const columns = useMemo(() => {
    const keys = []
    for (const r of shown) {
      for (const k of Object.keys(r.payload || {})) {
        if (!SKIP.has(k) && !keys.includes(k)) keys.push(k)
      }
    }
    return keys
  }, [shown])

  if (rows.length === 0) {
    return (
      <div style={{
        padding: '14px 18px', background: '#fdf6f0', border: '1px solid #f0dcc8',
        borderRadius: 8, fontSize: 13, color: '#8a5a1a',
      }}>
        ⚠️ 주요정보가 아직 수집되지 않았습니다. 목록에서 <b>주요정보 수집</b>을 눌러주세요.
      </div>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {categories.map(cat => {
          const count = rows.filter(r => r.category === cat).length
          return (
            <button
              key={cat}
              onClick={() => setActive(cat)}
              style={{
                padding: '5px 14px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
                border: current === cat ? `2px solid ${ACCENT}` : '1px solid #dde2ea',
                background: current === cat ? ACCENT : '#fff',
                color: current === cat ? '#fff' : '#555',
                fontWeight: current === cat ? 700 : 400,
              }}
            >
              {cat} <span style={{ opacity: 0.75 }}>{count}</span>
            </button>
          )
        })}
      </div>

      <div style={{ overflowX: 'auto', border: '1px solid #eef1f5', borderRadius: 8 }}>
        <table style={{
          borderCollapse: 'collapse', fontSize: 12.5,
          width: 'max-content', minWidth: '100%',
        }}>
          <thead>
            <tr style={{ background: '#f8fafd' }}>
              <th style={th}>연도</th>
              {columns.map(k => (
                <th key={k} style={th}>{KEY_LABELS[k] || k}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map(r => (
              <tr key={r.id} style={{ borderTop: '1px solid #eef1f5' }}>
                <td style={{ ...td, color: '#8a9ab0', whiteSpace: 'nowrap' }}>
                  {r.bsns_year}
                </td>
                {columns.map(k => (
                  <td key={k} style={td}>{r.payload?.[k] ?? '–'}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

const th = {
  padding: '9px 12px', textAlign: 'left', color: '#5a7090',
  fontWeight: 700, fontSize: 12, whiteSpace: 'nowrap',
}
const td = {
  padding: '7px 12px', color: '#333', verticalAlign: 'top',
  minWidth: 76, maxWidth: 320, whiteSpace: 'pre-wrap', wordBreak: 'keep-all',
}
