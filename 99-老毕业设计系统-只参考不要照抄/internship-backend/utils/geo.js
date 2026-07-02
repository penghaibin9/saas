/**
 * 地理位置工具
 */

// 两个经纬度坐标之间的球面距离（米），Haversine 公式
function distanceInMeters(lat1, lng1, lat2, lng2) {
  const toRad = (d) => (d * Math.PI) / 180;
  const R = 6371000; // 地球半径(米)
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

function isValidLat(v) {
  const n = Number(v);
  return Number.isFinite(n) && n >= -90 && n <= 90;
}

function isValidLng(v) {
  const n = Number(v);
  return Number.isFinite(n) && n >= -180 && n <= 180;
}

module.exports = { distanceInMeters, isValidLat, isValidLng };
