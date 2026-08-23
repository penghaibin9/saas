<template>
  <div class="dv-state" :data-state="state">
    <div class="dv-state__title">{{ title }}</div>
    <div v-if="description" class="dv-state__desc">{{ description }}</div>
    <button v-if="retryable" type="button" class="dv-state__retry" @click="$emit('retry')">重新加载</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ state: { type: String, required: true }, error: { type: Object, default: null } })
defineEmits(['retry'])
const title = computed(() => ({ IDLE: '选择文件开始预览', FETCHING: '正在加载安全预览…', UNSUPPORTED: '当前格式暂不支持站内预览', ERROR: '预览未加载成功' }[props.state] || '正在准备预览'))
const description = computed(() => props.error?.message || (props.state === 'UNSUPPORTED' ? '可在业务允许下载时使用下载原文；系统不会自动触发下载。' : ''))
const retryable = computed(() => props.state === 'ERROR' && props.error?.retryable !== false)
</script>

<style scoped>
.dv-state{min-height:320px;display:grid;place-content:center;text-align:center;padding:32px;color:var(--text-secondary)}
.dv-state__title{font-weight:600;color:var(--text-primary);font-size:16px}.dv-state__desc{margin-top:8px;max-width:420px;line-height:1.6}.dv-state__retry{margin:16px auto 0;padding:7px 14px;border:1px solid var(--border-light);border-radius:8px;background:var(--card,#fff);cursor:pointer}
</style>
