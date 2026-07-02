<template>
  <div class="sec-error">
    <AppCard variant="elevated" class="sec-error__card">
      <div class="sec-error__code">{{ code }}</div>
      <h1 class="sec-error__title">{{ title }}</h1>
      <p class="sec-error__desc">{{ description }}</p>
      <p v-if="rid" class="sec-error__rid">请求编号：{{ rid }}（联系管理员时提供）</p>
      <div class="sec-error__actions">
        <AppButton variant="primary" @click="goHome">返回首页</AppButton>
        <AppButton variant="secondary" @click="relogin">重新登录</AppButton>
      </div>
    </AppCard>
  </div>
</template>

<script>
/**
 * SecurityErrorShell — 4 个安全错误页的共享骨架。
 * 不暴露堆栈与内部信息；仅展示安全文案 + requestId（可选 query.rid）。
 * "重新登录"为占位：真实登录页在认证后端阶段接入，当前回首页并提示。
 */
import { AppCard, AppButton } from '@/components/ui'
import { toast } from '@/utils/toast'

export default {
  name: 'SecurityErrorShell',
  components: { AppCard, AppButton },
  props: {
    code: { type: [String, Number], required: true },
    title: { type: String, required: true },
    description: { type: String, required: true }
  },
  computed: {
    rid() {
      return this.$route.query.rid || ''
    }
  },
  methods: {
    goHome() {
      this.$router.push('/')
    },
    relogin() {
      // 登录页占位：认证后端接入前先回首页
      toast.info('登录页将在认证服务接入后开放，已返回首页')
      this.$router.push('/')
    }
  }
}
</script>

<style scoped>
.sec-error {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
  padding: var(--space-6);
}
.sec-error__card {
  max-width: 440px;
  width: 100%;
  padding: var(--space-10) var(--space-8);
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.sec-error__code {
  font-size: 44px;
  font-weight: var(--font-weight-semibold);
  color: var(--gray-300);
  font-variant-numeric: var(--font-numeric);
  line-height: 1;
}
.sec-error__title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.sec-error__desc {
  margin: 0;
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  line-height: var(--line-height-base);
}
.sec-error__rid {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sec-error__actions {
  display: flex;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-3);
}
</style>
