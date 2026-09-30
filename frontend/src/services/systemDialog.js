import { reactive } from 'vue'

export const systemDialogState = reactive({ visible:false, mode:'confirm', type:'warning', title:'', message:'', confirmText:'确认', cancelText:'取消', value:'', placeholder:'', minLength:0, error:'' })
let settle = null
function open(options = {}) {
  if (settle) settle(systemDialogState.mode === 'prompt' ? null : false)
  Object.assign(systemDialogState, { visible:true, mode:options.mode || 'confirm', type:options.type || 'warning', title:options.title || (options.mode === 'prompt' ? '请填写信息' : '请确认操作'), message:options.message || '', confirmText:options.confirmText || '确认', cancelText:options.cancelText || '取消', value:options.defaultValue || '', placeholder:options.placeholder || '', minLength:Number(options.minLength || 0), error:'' })
  return new Promise(resolve => { settle = resolve })
}
export const systemConfirm = options => open(typeof options === 'string' ? { message:options } : options)
export const systemPrompt = options => open({ ...(typeof options === 'string' ? { message:options } : options), mode:'prompt' })
export const systemAlert = options => open({ ...(typeof options === 'string' ? { message:options } : options), mode:'alert', cancelText:'' })
export function finishSystemDialog(accepted) {
  if (!settle) return
  if (accepted && systemDialogState.mode === 'prompt') { const value=systemDialogState.value.trim(); if (value.length < systemDialogState.minLength) { systemDialogState.error=`至少填写 ${systemDialogState.minLength} 个字`; return } }
  const resolve=settle; settle=null; systemDialogState.visible=false
  resolve(accepted ? (systemDialogState.mode === 'prompt' ? systemDialogState.value.trim() : true) : (systemDialogState.mode === 'prompt' ? null : false))
}
