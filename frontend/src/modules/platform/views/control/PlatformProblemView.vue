<template>
  <ModulePageShell title="问题管理、已知错误与事故复盘" subtitle="未定根因 · 已知错误 · 陈旧问题 · 已解决未挂修复"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'create', label: '＋ 新建问题' }, { key: 'refresh', label: '刷新' }]"
                    @action="onToolbarAction" />
    </template>

    <LoadingState v-if="loading" text="正在加载问题…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else>
      <div class="ppb__grid">
        <AppCard class="ppb__stat"><div class="ppb__stat-num">{{ overview.openCount }}</div><div class="ppb__stat-label">未关闭问题</div></AppCard>
        <AppCard class="ppb__stat"><div class="ppb__stat-num">{{ overview.knownErrorCount }}</div><div class="ppb__stat-label">已知错误</div></AppCard>
        <AppCard class="ppb__stat" :class="{ 'ppb__stat--warn': overview.withoutRootCauseCount }"><div class="ppb__stat-num">{{ overview.withoutRootCauseCount }}</div><div class="ppb__stat-label">未定根因</div></AppCard>
        <AppCard class="ppb__stat" :class="{ 'ppb__stat--warn': overview.agingOpenCount }"><div class="ppb__stat-num">{{ overview.agingOpenCount }}</div><div class="ppb__stat-label">超30天未关闭</div></AppCard>
        <AppCard class="ppb__stat" :class="{ 'ppb__stat--warn': overview.resolvedWithoutFixLinkCount }"><div class="ppb__stat-num">{{ overview.resolvedWithoutFixLinkCount }}</div><div class="ppb__stat-label">已解决未挂修复变更</div></AppCard>
      </div>

      <AppCard v-if="showCreate" class="ppb__panel">
        <AppSectionHeader title="新建问题" />
        <div class="ppb__form">
          <input v-model.trim="form.title" class="ppb__input" placeholder="问题标题" />
          <button class="mp-link" @click="submitCreate">创建</button>
        </div>
      </AppCard>

      <AppCard class="ppb__panel">
        <AppSectionHeader title="问题列表" />
        <DataTable :columns="listColumns" :rows="problems" row-key="id" row-clickable @row-click="selectProblem">
          <template #cell-status="{ row }">
            <StatusTag :type="statusTone(row.status)" :label="row.status" dot />
            <StatusTag v-if="row.knownErrorPublished" type="warning" label="已知错误" />
          </template>
        </DataTable>
      </AppCard>

      <AppCard v-if="selected" class="ppb__panel">
        <AppSectionHeader :title="`问题详情：${selected.title}`" />
        <div class="ppb__form">
          <textarea v-model="rootCauseForm.rootCause" class="ppb__textarea" placeholder="根因" />
          <textarea v-model="rootCauseForm.workaround" class="ppb__textarea" placeholder="临时规避方案（标记为已知错误前必填）" />
          <button class="mp-link" @click="saveRootCause">保存根因/规避方案</button>
        </div>
        <div class="ppb__form">
          <select v-model="nextStatus" class="ppb__input">
            <option v-for="s in statusOptions" :key="s" :value="s">{{ s }}</option>
          </select>
          <button class="mp-link" @click="advanceStatus">流转状态</button>
        </div>
        <div class="ppb__form">
          <input v-model.trim="fixChangeId" class="ppb__input" placeholder="永久修复变更ID" />
          <button class="mp-link" @click="linkFix">链接永久修复变更</button>
        </div>
        <p v-if="selected.permanentFixChangeId" class="ppb__note">已链接变更 #{{ selected.permanentFixChangeId }}</p>

        <AppSectionHeader title="事故复盘" class="ppb__gap" />
        <div class="ppb__form">
          <textarea v-model="postmortemForm.whatHappened" class="ppb__textarea" placeholder="经过说明" />
          <textarea v-model="postmortemForm.impactSummary" class="ppb__textarea" placeholder="影响范围" />
          <input v-model.trim="postmortemForm.actionItemsText" class="ppb__input" placeholder="行动项，逗号分隔" />
          <button class="mp-link" @click="createPostmortem">创建复盘草稿</button>
        </div>
        <ul class="ppb__list">
          <li v-for="pm in (selected.postmortems || [])" :key="pm.id">
            {{ pm.whatHappened || '（未填写经过说明）' }}
            <StatusTag :type="pm.published ? 'success' : 'default'" :label="pm.published ? '已发布' : '草稿'" dot />
            <button v-if="!pm.published" class="mp-link" @click="publishPostmortem(pm)">发布</button>
          </li>
        </ul>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
/** PLAT-10 问题管理、已知错误与事故复盘：问题状态机 + 已知错误 + 永久修复链接 + 复盘发布。 */
import { AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const STATUS_TRANSITIONS = {
  OPEN: ['INVESTIGATING', 'KNOWN_ERROR'],
  INVESTIGATING: ['KNOWN_ERROR', 'RESOLVED'],
  KNOWN_ERROR: ['INVESTIGATING', 'RESOLVED'],
  RESOLVED: ['CLOSED', 'INVESTIGATING'],
  CLOSED: []
}

export default {
  name: 'PlatformProblemView',
  components: { AppCard, AppSectionHeader, DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      overview: { openCount: 0, knownErrorCount: 0, withoutRootCauseCount: 0, agingOpenCount: 0, resolvedWithoutFixLinkCount: 0 },
      problems: [],
      selected: null,
      showCreate: false,
      form: { title: '' },
      rootCauseForm: { rootCause: '', workaround: '' },
      nextStatus: '',
      fixChangeId: '',
      postmortemForm: { whatHappened: '', impactSummary: '', actionItemsText: '' },
      listColumns: [
        { key: 'title', title: '标题' },
        { key: 'status', title: '状态' },
        { key: 'sourceIncidentId', title: '来源事件' }
      ]
    }
  },
  computed: {
    statusOptions() {
      return this.selected ? (STATUS_TRANSITIONS[this.selected.status] || []) : []
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusTone(status) {
      if (status === 'CLOSED' || status === 'RESOLVED') return 'success'
      if (status === 'KNOWN_ERROR') return 'warning'
      return 'default'
    },
    onToolbarAction(key) {
      if (key === 'create') this.showCreate = !this.showCreate
      if (key === 'refresh') this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const [ovRes, listRes] = await Promise.all([
        platformControlApi.getProblemsOverview(),
        platformControlApi.listProblems()
      ])
      this.loading = false
      if (ovRes.code === 0) this.overview = ovRes.data
      else this.error = ovRes.message
      if (listRes.code === 0) this.problems = listRes.data.items || []
    },
    async submitCreate() {
      if (!this.form.title) {
        toast.error('请填写问题标题')
        return
      }
      const res = await platformControlApi.createProblem({ title: this.form.title })
      if (res.code === 0) {
        toast.success('问题已创建')
        this.form = { title: '' }
        this.showCreate = false
        this.load()
      } else toast.error(res.message)
    },
    async selectProblem(row) {
      const res = await platformControlApi.getProblem(row.id)
      if (res.code === 0) {
        this.selected = res.data
        this.rootCauseForm = { rootCause: this.selected.rootCause, workaround: this.selected.workaround }
        this.nextStatus = (STATUS_TRANSITIONS[this.selected.status] || [])[0] || ''
      } else toast.error(res.message)
    },
    async saveRootCause() {
      const res = await platformControlApi.updateProblemRootCause(this.selected.id, {
        rootCause: this.rootCauseForm.rootCause, workaround: this.rootCauseForm.workaround,
        expectedVersion: this.selected.version
      })
      if (res.code === 0) { toast.success('已保存'); this.selected = res.data; this.load() } else toast.error(res.message)
    },
    async advanceStatus() {
      if (!this.nextStatus) return
      const res = await platformControlApi.transitionProblem(this.selected.id, {
        status: this.nextStatus, expectedVersion: this.selected.version
      })
      if (res.code === 0) { toast.success('状态已更新'); this.selected = res.data; this.load() } else toast.error(res.message)
    },
    async linkFix() {
      if (!this.fixChangeId) return
      const res = await platformControlApi.linkProblemPermanentFix(this.selected.id, {
        changeId: this.fixChangeId, expectedVersion: this.selected.version
      })
      if (res.code === 0) { toast.success('已链接'); this.selected = res.data; this.fixChangeId = ''; this.load() } else toast.error(res.message)
    },
    async createPostmortem() {
      const actionItems = this.postmortemForm.actionItemsText.split(',').map((s) => s.trim()).filter(Boolean)
      const res = await platformControlApi.createPostmortem(this.selected.id, {
        whatHappened: this.postmortemForm.whatHappened,
        impactSummary: this.postmortemForm.impactSummary,
        actionItems
      })
      if (res.code === 0) {
        toast.success('复盘草稿已创建')
        this.postmortemForm = { whatHappened: '', impactSummary: '', actionItemsText: '' }
        this.selectProblem({ id: this.selected.id })
      } else toast.error(res.message)
    },
    async publishPostmortem(pm) {
      const res = await platformControlApi.publishPostmortem(pm.id, { expectedVersion: pm.version })
      if (res.code === 0) { toast.success('已发布'); this.selectProblem({ id: this.selected.id }) } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ppb__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}
.ppb__stat {
  padding: var(--space-4);
}
.ppb__stat--warn {
  border-color: var(--color-warning, #d97706);
}
.ppb__stat-num {
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.ppb__stat-label {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.ppb__panel {
  margin-top: var(--space-3);
  padding: var(--space-4);
}
.ppb__gap {
  margin-top: var(--space-4);
}
.ppb__form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.ppb__input {
  padding: 6px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm, 4px);
  font-size: var(--font-size-sm);
}
.ppb__textarea {
  padding: 6px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm, 4px);
  font-size: var(--font-size-sm);
  min-width: 260px;
  min-height: 60px;
}
.ppb__list {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.ppb__note {
  margin-top: var(--space-2);
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
