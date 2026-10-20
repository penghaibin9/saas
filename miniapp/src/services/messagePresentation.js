/**
 * 消息来源是后端路由、审计和动作解析使用的机器值，不能直接展示给师生。
 * 此处只做展示投影；保留原对象的 source/module 字段以免影响服务端下发的动作。
 */
const MODULE_LABELS = Object.freeze({
  'student-affairs': '学工服务',
  STUDENT_AFFAIRS: '学工服务',
  'campus-service': '在校服务',
  CAMPUS_SERVICE: '在校服务',
  internship: '岗位实习',
  INTERNSHIP: '岗位实习',
  graduation: '毕业设计',
  GRADUATION: '毕业设计',
  'academic-affairs': '教务服务',
  ACADEMIC_AFFAIRS: '教务服务',
  orientation: '迎新报到',
  ORIENTATION: '迎新报到',
  employment: '就业服务',
  EMPLOYMENT: '就业服务',
  ANNOUNCEMENT: '通知公告',
  BUSINESS: '业务通知',
  REMINDER: '事项提醒',
  EMERGENCY: '紧急通知',
  SYSTEM: '系统通知',
  TODO: '待办提醒',
  TODO_NOTICE: '待办提醒',
  WORK_ORDER: '服务进度'
})

const hasChineseText = (value) => /[\u3400-\u9fff]/.test(String(value || ''))

function moduleKey(value) {
  return String(value || '').trim().replace(/-/g, '_').toUpperCase()
}

/** 未知机器值不可回显；已有中文业务名称可以原样保留。 */
export function messageModuleLabel(value) {
  const raw = String(value || '').trim()
  if (!raw) return '消息通知'
  return MODULE_LABELS[raw] || MODULE_LABELS[moduleKey(raw)] || (hasChineseText(raw) ? raw : '消息通知')
}

/**
 * 给移动端消息视图的安全展示投影。后端仍保留 module/sourceModule 用于鉴权动作，
 * 这里仅替换用户看得到的 module 字段，未知枚举也不会暴露。
 */
export function presentMessage(message) {
  if (!message || typeof message !== 'object') return message
  const source = message.module || message.sourceModule || message.source_module || message.category || message.messageType
  return { ...message, module: messageModuleLabel(source) }
}

export function presentMessagePage(data) {
  if (!data || typeof data !== 'object') return data
  const mapList = (items) => Array.isArray(items) ? items.map(presentMessage) : []
  const groups = Object.fromEntries(Object.entries(data.groups || {}).map(([key, items]) => [key, mapList(items)]))
  return {
    ...data,
    list: Array.isArray(data.list) ? mapList(data.list) : data.list,
    items: Array.isArray(data.items) ? mapList(data.items) : data.items,
    groups,
    emergencyPending: mapList(data.emergencyPending)
  }
}
