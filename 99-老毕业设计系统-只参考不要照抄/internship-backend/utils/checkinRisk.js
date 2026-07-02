/**
 * 打卡反作弊评估（纯逻辑，可单测）
 * ───────────────────────────────────────────────────────────
 * 对标商业产品的「防代打卡/防虚拟定位」核心检测：
 *   1) 模拟定位标记（客户端检测到 mock location）→ 高风险
 *   2) 定位精度异常（accuracy 过大，可能是 IP/基站粗定位伪装）→ 中风险
 *   3) 位移突变（与上次打卡的距离/时间推算出不可能的移动速度）→ 高风险
 * 返回风险等级 + 分值 + 命中原因，供留痕与教师复核。
 */
const { distanceInMeters } = require('./geo');

const ACCURACY_WARN = Number(process.env.CHECKIN_ACCURACY_WARN || 1000);   // 米，超过视为可疑
const SPEED_LIMIT_KMH = Number(process.env.CHECKIN_SPEED_LIMIT || 250);    // 通勤不可能超过的速度

/**
 * @param {object} cur  本次打卡 { lat, lng, accuracy, isMock }
 * @param {object|null} last 上次打卡 { lat, lng, time }（time 为 Date/可解析时间戳）
 * @returns {{ level:'none'|'low'|'medium'|'high', score:number, reasons:string[], speedKmh:number|null }}
 */
function assess(cur = {}, last = null) {
  const reasons = [];
  let score = 0;

  if (cur.isMock === true || cur.isMock === 1 || cur.isMock === '1') {
    reasons.push('检测到模拟定位');
    score += 70;
  }

  const acc = Number(cur.accuracy);
  if (Number.isFinite(acc) && acc > ACCURACY_WARN) {
    reasons.push(`定位精度异常(${Math.round(acc)}米)`);
    score += 30;
  }

  let speedKmh = null;
  if (last && Number.isFinite(Number(last.lat)) && Number.isFinite(Number(last.lng)) &&
      Number.isFinite(Number(cur.lat)) && Number.isFinite(Number(cur.lng)) && last.time) {
    const meters = distanceInMeters(Number(last.lat), Number(last.lng), Number(cur.lat), Number(cur.lng));
    const hours = (Date.now() - new Date(last.time).getTime()) / 3.6e6;
    if (hours > 0) {
      speedKmh = (meters / 1000) / hours;
      if (speedKmh > SPEED_LIMIT_KMH) {
        reasons.push(`位移突变(推算时速${Math.round(speedKmh)}km/h)`);
        score += 60;
      }
    }
  }

  score = Math.min(100, score);
  let level = 'none';
  if (score >= 60) level = 'high';
  else if (score >= 30) level = 'medium';
  else if (score > 0) level = 'low';

  return { level, score, reasons, speedKmh: speedKmh == null ? null : Math.round(speedKmh) };
}

module.exports = { assess, ACCURACY_WARN, SPEED_LIMIT_KMH };
