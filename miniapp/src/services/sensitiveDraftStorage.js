const SENSITIVE_PREFIXES = [
  // 教师成绩录入本机草稿（含学生名单与分数）
  'aa-grade-entry-draft:',
  // 消息详情/搜索池暂存：整条消息正文落到本地，可能含处分、资助、心理关注等敏感内容，
  // 换账号或会话失效后必须一并清除（2026-08-04 复审新增：此前只清成绩草稿，消息正文残留）。
  'gx_msg_detail_v1',
  'gx_msg_search_pool_v1'
]

export function clearSensitiveLocalDrafts() {
  try {
    const info = uni.getStorageInfoSync()
    const keys = Array.isArray(info && info.keys) ? info.keys : []
    keys.forEach((key) => {
      if (SENSITIVE_PREFIXES.some((prefix) => String(key).startsWith(prefix))) {
        uni.removeStorageSync(key)
      }
    })
  } catch (e) {
    // 退出登录继续执行；下一次进入敏感页面仍会以服务器数据为准。
  }
}

export { SENSITIVE_PREFIXES }
