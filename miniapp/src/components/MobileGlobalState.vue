<template>
  <view class="mobile-global-state">
    <!-- 组件均会按当前 route 自行决定是否启用。 -->
    <MobileGraduationBatchContext />
    <MobileGraduationDelayQueue />
    <MobileGraduationExtensionPanel />
    <MobileGraduationSectionErrors />
    <MobileGraduationTempFileJanitor />

    <slot v-if="state === 'ready'" />

    <view v-else-if="state === 'loading'" class="mgs-panel mgs-loading">
      <view class="mgs-skeleton mgs-skeleton--title" />
      <view class="mgs-skeleton" />
      <view class="mgs-skeleton" />
      <view class="mgs-skeleton mgs-skeleton--short" />
      <text class="mgs-loading__text">{{ loadingText }}</text>
    </view>

    <view v-else class="mgs-panel">
      <view class="mgs-icon" :class="`mgs-icon--${state}`"><text>{{ meta.icon }}</text></view>
      <text class="mgs-title">{{ title || meta.title }}</text>
      <text class="mgs-desc">{{ description || meta.description }}</text>
      <text v-if="errorCode && state === 'error'" class="mgs-code">错误码：{{ errorCode }}</text>
      <view class="mgs-actions">
        <slot name="actions">
          <button v-if="meta.retry" class="mgs-btn mgs-btn--primary" @click="$emit('retry')">{{ meta.retry }}</button>
          <button v-if="meta.back" class="mgs-btn" @click="$emit('back')">{{ meta.back }}</button>
          <button v-if="meta.contact" class="mgs-btn" @click="$emit('contact')">{{ meta.contact }}</button>
        </slot>
      </view>
    </view>
  </view>
</template>

<script>
const STATE_META = {
  empty: { icon: '▢', title: '暂无数据', description: '当前没有可展示的内容', retry: '', back: '返回', contact: '' },
  error: { icon: '!', title: '加载失败', description: '数据加载出现问题，请重试', retry: '重试', back: '', contact: '' },
  forbidden: { icon: '⊘', title: '当前身份无权查看', description: '不在授权范围内，可切换身份或联系管理员', retry: '', back: '返回', contact: '联系管理员' },
  offline: { icon: '⇅', title: '网络异常', description: '当前网络不可用，请检查网络后重试', retry: '重试', back: '', contact: '' },
  readonly: { icon: '🔒', title: '当前模块只读', description: '模块授权已到期，历史可查看，不可新增修改', retry: '', back: '查看历史', contact: '联系管理员' },
  noLicense: { icon: '◇', title: '模块未开通', description: '学校尚未开通该模块，如需使用请联系学校管理员', retry: '', back: '返回', contact: '联系学校管理员' }
}

export default {
  name: 'MobileGlobalState',
  props: {
    state: {
      type: String,
      default: 'ready',
      validator: (v) => ['ready', 'loading', 'empty', 'error', 'forbidden', 'offline', 'readonly', 'noLicense'].includes(v)
    },
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    errorCode: { type: [String, Number], default: '' },
    loadingText: { type: String, default: '正在加载…' }
  },
  emits: ['retry', 'back', 'contact'],
  computed: { meta() { return STATE_META[this.state] || STATE_META.error } }
}
</script>

<style scoped>
.mobile-global-state { width: 100%; }
.mgs-panel { display:flex; flex-direction:column; align-items:center; padding:var(--space-6) var(--page-padding-mobile); background:var(--bg-card); border-radius:var(--radius-lg); text-align:center; }
.mgs-icon { width:52px; height:52px; border-radius:var(--radius-full); display:flex; align-items:center; justify-content:center; font-size:var(--font-size-2xl); margin-bottom:var(--space-3); }
.mgs-icon--empty { background:var(--gray-100); color:var(--gray-400); }.mgs-icon--error { background:var(--danger-50); color:var(--danger-600); }.mgs-icon--forbidden { background:var(--warning-50); color:var(--warning-600); }.mgs-icon--offline { background:var(--gray-100); color:var(--gray-500); }.mgs-icon--readonly { background:var(--info-50); color:var(--info-600); font-size:var(--font-size-lg); }.mgs-icon--noLicense { background:var(--primary-50); color:var(--primary-600); }
.mgs-title { font-size:var(--font-size-lg); font-weight:var(--font-weight-medium); color:var(--text-primary); margin-bottom:var(--space-2); }.mgs-desc { font-size:var(--font-size-base); color:var(--text-secondary); line-height:var(--line-height-base); }.mgs-code { margin-top:var(--space-2); font-size:var(--font-size-xs); color:var(--text-tertiary); }.mgs-actions { display:flex; gap:var(--space-3); margin-top:var(--space-4); }.mgs-btn { min-height:var(--touch-target-min); line-height:var(--touch-target-min); padding:0 var(--space-5); border-radius:var(--radius-md); border:1px solid var(--border-base); background:var(--bg-card); color:var(--text-secondary); font-size:var(--font-size-md); }.mgs-btn--primary { background:var(--primary-600); border-color:var(--primary-600); color:var(--text-inverse); }.mgs-loading { align-items:stretch; text-align:left; gap:var(--space-3); }.mgs-skeleton { height:14px; border-radius:var(--radius-sm); background:var(--gray-100); }.mgs-skeleton--title { width:45%; height:18px; }.mgs-skeleton--short { width:60%; }.mgs-loading__text { margin-top:var(--space-2); font-size:var(--font-size-sm); color:var(--text-tertiary); text-align:center; }
</style>
