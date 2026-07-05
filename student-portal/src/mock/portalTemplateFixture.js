/**
 * 模块模板页展示脚手架：列头 + 标题（真实数据来自 /mobile/{domain}/my，无数据时展示空态）。
 * 仅用于结构占位，不含任何真实敏感数据；不用于绕过后端。
 */
export const TEMPLATE_META = {
  orientation: { title: '迎新报到', columns: ['环节', '状态', '时间'] },
  'campus-service': { title: '在校服务', columns: ['事项', '状态', '提交时间'] },
  academic: { title: '学业过程', columns: ['课程/项目', '状态', '备注'] },
  internship: { title: '岗位实习', columns: ['单位/岗位', '状态', '周报/打卡'] },
  graduation: { title: '毕业设计', columns: ['课题', '节点', '状态'] },
  employment: { title: '就业服务', columns: ['去向', '单位', '状态'] },
  profile: { title: '我的档案', columns: ['字段', '值'] },
  messages: { title: '消息中心', columns: ['标题', '类型', '状态'] }
}

export function metaFor(path) {
  return TEMPLATE_META[path] || { title: path || '模块', columns: ['项', '值'] }
}
