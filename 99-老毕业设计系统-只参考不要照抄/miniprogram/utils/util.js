function pad(n) { return n < 10 ? '0' + n : '' + n; }

function toDate(s) {
  if (!s) return null;
  // iOS 不支持 '2024-01-01 10:00:00'，需替换 '-' 为 '/'
  const str = typeof s === 'string' ? s.replace(/-/g, '/').replace(/\.\d+/, '') : s;
  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d;
}

function fmtDate(s) {
  const d = toDate(s);
  if (!d) return s || '';
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

function fmtTime(s) {
  const d = toDate(s);
  if (!d) return s || '';
  return pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

// 计算两点间距离（米），用于打卡范围判断
function haversine(la1, lo1, la2, lo2) {
  const R = 6371000;
  const rad = function (d) { return d * Math.PI / 180; };
  const dLa = rad(la2 - la1);
  const dLo = rad(lo2 - lo1);
  const a = Math.sin(dLa / 2) * Math.sin(dLa / 2) +
    Math.cos(rad(la1)) * Math.cos(rad(la2)) * Math.sin(dLo / 2) * Math.sin(dLo / 2);
  return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

module.exports = { fmtDate: fmtDate, fmtTime: fmtTime, haversine: haversine, toDate: toDate, pad: pad };
