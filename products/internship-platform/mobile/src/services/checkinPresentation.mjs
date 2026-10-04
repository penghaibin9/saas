const RESULT_TEXT = Object.freeze({
  NORMAL: '签到成功，位置在岗位围栏内。',
  RECORDED: '签到已记录，岗位未配置围栏，本次仅作留痕。',
  NO_LOCATION: '签到时间已记录，无定位，待教师核验，不作作弊认定。',
  OUT_OF_RANGE: '签到已记录，位置超出岗位围栏，待教师核验。',
  LOW_ACCURACY: '签到已记录，定位精度不足，待教师核验。',
  LOCATION_UNCERTAIN: '签到已记录，定位坐标系或精度需教师核验。',
  MOCK_LOCATION: '签到已记录，设备风险需教师核验。'
})
// Browser geolocation reports WGS84. Never label its unconverted coordinates
// as GCJ02: the server must retain its coordinate-system mismatch review gate.
export function checkinLocationPolicy(overseas, browser = typeof navigator !== 'undefined' && !!navigator.geolocation) {
  return overseas || browser
    ? { type: 'wgs84', coordinateSystem: 'WGS84', locationProvider: browser ? 'BROWSER_WGS84' : 'UNI_WGS84' }
    : { type: 'gcj02', coordinateSystem: 'GCJ02', locationProvider: 'UNI_GCJ02' }
}
const CALENDAR_TEXT = Object.freeze({
  CHECKIN:'已签', NORMAL:'正常', RECORDED:'已签', OUT_OF_RANGE:'超范围',
  NO_LOCATION:'无定位', LOW_ACCURACY:'精度不足', LOCATION_UNCERTAIN:'待核验', MOCK_LOCATION:'待核验',
  PENDING:'待签', ABSENT:'缺卡', MAKEUP:'补卡', EXEMPT:'免签', LEAVE:'请假', FUTURE:'', OUTSIDE:''
})
export function checkinCalendarLabel(status) {
  return Object.hasOwn(CALENDAR_TEXT,status) ? CALENDAR_TEXT[status] : '状态待确认'
}
export function checkinReceipt(result) {
  if (!result || !/^[1-9]\d*$/.test(String(result.id || '')) ||
      !/^\d{4}-\d{2}-\d{2}$/.test(String(result.date || '')) || !Object.hasOwn(RESULT_TEXT,result.result)) return null
  const pending = !['NORMAL','RECORDED'].includes(result.result)
  let summary = RESULT_TEXT[result.result]
  if (typeof result.distanceM === 'number' && Number.isFinite(result.distanceM) && result.distanceM >= 0) {
    summary += `距围栏中心约${Math.round(result.distanceM)}米。`
  }
  if (typeof result.watermarkedFileId === 'string' && result.watermarkedFileId) summary += '水印照片已生成并留存。'
  return {
    title: pending ? '签到已记录，待核验' : result.result === 'NORMAL' ? '签到成功' : '签到已记录',
    summary,
    content: `${summary}\n\n励志语：认真完成今天的每一步，让小小进步积累成成长的力量。`
  }
}
