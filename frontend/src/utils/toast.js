import { reactive } from 'vue'

/**
 * 轻提示服务（配合 AppToast.vue 使用，App.vue 挂载一次 <AppToast />）
 * 用法：
 *   import { toast } from '@/utils/toast'
 *   toast.success('已提交，等待导师批阅')
 *   toast.error('上传失败：文件超过 50MB，请压缩后重新上传')
 * 规范：成功提示 3 秒自动消失，错误提示需给出原因与建议。
 */
export const toastState = reactive({ items: [] })

let seed = 0

function normalizeCrossClientMessage(message) {
  const text = String(message || '')
  // 历史开题/成果页面仍可能传入旧“仅线下、未发消息”文案；真实后端已经创建站内消息。
  // 在公共出口纠正，防止老师重复电话/微信催办。页面源码也由毕业设计布局展示真实消息说明。
  return text
    .replace(/^已记录对 (.+) 的线下开题催办（未发送站内消息）$/, '已向 $1 发送开题站内催办并写入留痕')
    .replace(/^已记录对 (.+) 的线下成果催办（未发送站内消息）$/, '已向 $1 发送成果站内催办并写入留痕')
}

function push(type, message, duration) {
  const id = ++seed
  toastState.items.push({ id, type, message: normalizeCrossClientMessage(message) })
  const ms = duration ?? (type === 'error' ? 4500 : 3000)
  setTimeout(() => remove(id), ms)
  return id
}

export function remove(id) {
  const i = toastState.items.findIndex((t) => t.id === id)
  if (i > -1) toastState.items.splice(i, 1)
}

export const toast = {
  success: (message, duration) => push('success', message, duration),
  error: (message, duration) => push('error', message, duration),
  info: (message, duration) => push('info', message, duration),
  warning: (message, duration) => push('warning', message, duration)
}
