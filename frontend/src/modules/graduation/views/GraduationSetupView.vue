<template>
  <ModulePageShell
    class="gs-shell"
    title="开工检查"
    :subtitle="subtitle"
    :role-name="ctx.currentRole?.roleName"
    :data-scope-name="ctx.dataScope?.scopeName"
  >
    <template #actions>
      <button type="button" class="mp-btn" :disabled="loading" @click="load">重新检查</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" text="正在检查…" />
    <EmptyState v-else-if="!hasBatch || !data.batch" title="先新建一个毕设批次" description="批次是一届毕业设计的容器：时间节点、学生、导师都挂在批次下面。">
      <template #actions>
        <button class="mp-btn mp-btn--primary" type="button" @click="$router.push('/admin/graduation/batches/create')">＋ 新建毕设批次</button>
      </template>
    </EmptyState>

    <div v-else class="mp-stack">
      <section class="gs-head" :class="{ 'is-done': data.allDone }">
        <strong v-if="data.allDone">✓ 开工检查全部通过</strong>
        <strong v-else>还差 {{ data.total - data.doneCount }} 步就能开工</strong>
        <p v-if="data.allDone">老师登录后会在「我的毕设工作」里自动看到自己的学生和待办，学生手机上也能看到毕业设计。</p>
        <p v-else>按顺序把下面几项做完。每项做完回到这里点「重新检查」，系统会自动核对。</p>
        <div class="gs-bar" role="progressbar" :aria-valuenow="data.doneCount" aria-valuemin="0" :aria-valuemax="data.total">
          <span :style="{ width: `${Math.round((data.doneCount / Math.max(1, data.total)) * 100)}%` }" />
        </div>
      </section>

      <ol class="gs-steps">
        <li v-for="(step, index) in data.steps" :key="step.key" class="gs-step" :class="{ 'is-done': step.done, 'is-next': !step.done && index === firstTodo }">
          <span class="gs-step__no">{{ step.done ? '✓' : index + 1 }}</span>
          <div class="gs-step__body">
            <strong>{{ step.title }}</strong>
            <p>{{ step.detail }}</p>
            <p v-if="step.key === 'materials' && !step.done && step.names?.length" class="gs-tip">
              缺少：{{ step.names.join('、') }}。点右边的按钮，到「材料规则」页面补上并启用即可。
            </p>
            <p v-if="step.key === 'accounts' && !step.done" class="gs-tip">
              怎么处理：在「导师与分配」里把导师的工号改成他登录系统用的账号；还没有账号的，请在「系统管理 › 教职工账号」里用工号给老师建账号。
            </p>
          </div>
          <button
            v-if="!step.done"
            type="button"
            class="mp-btn"
            :class="{ 'mp-btn--primary': index === firstTodo }"
            @click="go(step)"
          >{{ actionLabel(step) }} →</button>
        </li>
      </ol>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

const EMPTY = () => ({ batch: null, steps: [], doneCount: 0, total: 6, allDone: false, counts: {} })
const LABELS = { timeline: '去设置时间', students: '去导入学生', mentors: '去分配导师', accounts: '去核对导师工号', publish: '去发布批次', materials: '去配置材料规则' }

export default {
  name: 'GraduationSetupView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { batchStore: useGraduationBatchStore(), loading: true, error: '', data: EMPTY(), token: 0 }
  },
  computed: {
    hasBatch() { return !!this.batchStore.selectedBatchId },
    subtitle() {
      const b = this.data.batch
      return b ? `${b.name} · ${b.statusLabel}` : '首次使用按这几步准备，之后每学期新建批次时再来看一眼'
    },
    firstTodo() { return this.data.steps.findIndex((step) => !step.done) }
  },
  watch: { 'batchStore.selectedBatchId'() { this.load() } },
  created() { this.load() },
  methods: {
    async load() {
      const token = ++this.token
      this.error = ''
      if (!this.hasBatch) { this.loading = false; this.data = EMPTY(); return }
      this.loading = true
      try {
        const res = await graduationApi.getSetupCheck({ batchId: this.batchStore.selectedBatchId })
        if (token !== this.token) return
        if (res.code === 0) this.data = { ...EMPTY(), ...(res.data || {}) }
        else this.error = res.message || '开工检查加载失败，请稍后重试。'
      } catch (error) {
        if (token === this.token) this.error = error?.message || '开工检查加载失败，请检查网络后重试。'
      } finally {
        if (token === this.token) this.loading = false
      }
    },
    actionLabel(step) { return LABELS[step.key] || '去处理' },
    go(step) {
      const batchId = this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined
      const id = this.data.batch?.id
      const target = {
        timeline: { path: `/admin/graduation/batches/${id}`, query: { batchId } },
        publish: { path: `/admin/graduation/batches/${id}`, query: { batchId } },
        students: { path: '/admin/graduation/students', query: { panel: 'roster', batchId } },
        mentors: { path: '/admin/graduation/mentors', query: { panel: 'list', batchId } },
        accounts: { path: '/admin/graduation/mentors', query: { panel: 'list', batchId } },
        materials: { path: '/admin/graduation/material-rules', query: { batchId } }
      }[step.key]
      if (target) this.$router.push(target).catch(() => {})
    }
  }
}
</script>

<style scoped>
.gs-head { padding: var(--space-4, 16px); border: 1px solid var(--primary-100, #dbeafe); border-radius: 12px; background: var(--primary-50, #eff6ff); }
.gs-head.is-done { border-color: var(--success-200, #bbf7d0); background: var(--success-50, #f0fdf4); }
.gs-head strong { font-size: 18px; }
.gs-head p { margin: 4px 0 10px; color: var(--text-tertiary, #64748b); }
.gs-bar { height: 8px; border-radius: 999px; background: var(--card, #fff); overflow: hidden; }
.gs-bar span { display: block; height: 100%; border-radius: inherit; background: var(--primary-600, #2563eb); transition: width .3s; }
.gs-head.is-done .gs-bar span { background: var(--success-600, #16a34a); }
.gs-steps { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3, 12px); }
.gs-step { display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; gap: var(--space-3, 12px); align-items: center; padding: var(--space-3, 12px) var(--space-4, 16px); border: 1px solid var(--border-light, #e2e8f0); border-radius: 10px; background: var(--card, #fff); }
.gs-step.is-next { border-color: var(--primary-300, #93c5fd); box-shadow: 0 0 0 3px var(--primary-50, #eff6ff); }
.gs-step__no { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; background: var(--gray-100, #f1f5f9); color: var(--text-secondary, #475569); }
.gs-step.is-next .gs-step__no { background: var(--primary-600, #2563eb); color: #fff; }
.gs-step.is-done .gs-step__no { background: var(--success-600, #16a34a); color: #fff; }
.gs-step__body strong { font-size: 15px; }
.gs-step__body p { margin: 3px 0 0; color: var(--text-tertiary, #64748b); overflow-wrap: anywhere; }
.gs-step.is-done .gs-step__body strong { color: var(--text-secondary, #475569); }
.gs-tip { color: var(--warning-700, #b45309) !important; }
@media (max-width: 640px) { .gs-step { grid-template-columns: 32px minmax(0, 1fr); } .gs-step .mp-btn { grid-column: 2; justify-self: start; } }
</style>
