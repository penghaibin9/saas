<template>
  <div v-if="state.visible" class="sd-mask" role="presentation" @click.self="cancel">
    <section class="sd-dialog" role="dialog" aria-modal="true" :aria-labelledby="titleId" @keydown.esc.prevent="cancel">
      <header :class="['sd-head', `is-${state.type}`]">
        <span class="sd-mark" aria-hidden="true">{{ state.type === 'danger' ? '!' : '?' }}</span>
        <h2 :id="titleId">{{ state.title }}</h2>
      </header>
      <div class="sd-body">
        <p>{{ state.message }}</p>
        <textarea v-if="state.mode === 'prompt'" ref="inputEl" v-model="state.value" rows="3" :placeholder="state.placeholder" @input="state.error = ''" />
        <small v-if="state.error" role="alert">{{ state.error }}</small>
      </div>
      <footer>
        <button v-if="state.mode !== 'alert'" ref="cancelEl" type="button" class="sd-btn" @click="cancel">{{ state.cancelText }}</button>
        <button ref="confirmEl" type="button" class="sd-btn sd-btn--primary" @click="confirm">{{ state.confirmText }}</button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { finishSystemDialog, systemDialogState as state } from '../services/systemDialog'

const inputEl = ref(null)
const confirmEl = ref(null)
const titleId = 'student-system-dialog-title'
watch(() => state.visible, async (visible) => {
  if (!visible) return
  await nextTick()
  ;(state.mode === 'prompt' ? inputEl.value : confirmEl.value)?.focus()
})
function cancel() { finishSystemDialog(false) }
function confirm() { finishSystemDialog(true) }
</script>

<style scoped>
.sd-mask{position:fixed;inset:0;z-index:10000;display:grid;place-items:center;padding:24px;background:rgba(15,35,70,.42);backdrop-filter:blur(2px)}
.sd-dialog{width:min(460px,100%);overflow:hidden;border:1px solid var(--line,#d8e2f2);border-radius:16px;background:var(--card,#fff);box-shadow:0 24px 64px rgba(18,53,103,.22)}
.sd-head{display:flex;align-items:center;gap:10px;padding:22px 24px 0}.sd-head h2{margin:0;color:var(--t1,#102a56);font-size:18px}.sd-mark{display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#fff2d8;color:#a35b00;font-weight:800}.sd-head.is-danger .sd-mark{background:#fff0f0;color:#c53535}
.sd-body{padding:16px 24px 20px}.sd-body p{margin:0;color:var(--t2,#405b82);font-size:14px;line-height:1.7;white-space:pre-line}.sd-body textarea{width:100%;min-height:86px;margin-top:14px;padding:10px 12px;border:1px solid var(--line,#d8e2f2);border-radius:9px;color:var(--t1,#102a56);font:inherit;resize:vertical}.sd-body textarea:focus{outline:2px solid rgba(39,99,190,.16);border-color:var(--pri,#2763be)}.sd-body small{display:block;margin-top:6px;color:#c53535}
.sd-dialog footer{display:flex;justify-content:flex-end;gap:10px;padding:14px 24px 22px}.sd-btn{min-width:88px;height:38px;padding:0 16px;border:1px solid var(--line,#d8e2f2);border-radius:9px;background:#fff;color:var(--t2,#405b82);cursor:pointer}.sd-btn--primary{border-color:var(--pri,#2763be);background:var(--pri,#2763be);color:#fff}
@media(max-width:600px){.sd-mask{align-items:end;padding:12px}.sd-dialog{border-radius:16px}.sd-dialog footer{display:grid;grid-template-columns:1fr 1fr}.sd-btn{width:100%}}
</style>
