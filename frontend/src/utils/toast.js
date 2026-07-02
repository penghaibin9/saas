import { reactive } from 'vue'

/**
 * 轻提示服务（配合 AppToast.vue 使用，App.vue 挂载一次 <AppToast />）
 * 用法：
 *   import { toast } from '@/utils/toast'
 *   toast.success('已提交，等待导师批阅')
 *   toast.error('上传失败：文件超过 50MB，请压缩后重新上传')
 *   toast.info('演示环境：该功能将在业务阶段开放')
 * 规范（V2.1 §13.2）：成功提示 3 秒自动消失，文案简短；错误提示需给出原因与建议。
 */
export const toastState = reactive({ items: [] })

let seed = 0

function push(type, message, duration) {
  const id = ++seed
  toastState.items.push({ id, type, message })
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
