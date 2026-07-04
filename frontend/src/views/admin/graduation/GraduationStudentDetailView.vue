<template>
  <ModulePageShell
    :title="detail ? detail.name + ' · 毕设详情' : '毕设详情'"
    :subtitle="detail ? detail.className + ' · ' + maskNo(detail.studentNo) : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">课题信息</span>
            <StatusTag type="processing" :label="detail.stageLabel" dot />
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">课题名称</span><span class="mp-kv__v">{{ detail.topicTitle }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">课题来源</span><span class="mp-kv__v">{{ detail.topicSource }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ detail.advisorName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">任务书</span><span class="mp-kv__v">{{ detail.taskbook }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">联系电话</span><span class="mp-kv__v">{{ maskPhone(detail.phone) }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">中期检查</span><span class="mp-kv__v">{{ detail.midterm.conclusion }}（{{ detail.midterm.time }}）</span></div>
            <div class="mp-kv"><span class="mp-kv__k">答辩安排</span><span class="mp-kv__v">{{ detail.defense.group }} · {{ detail.defense.time }} · {{ detail.defense.location }}</span></div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">主状态进度</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="s in detail.stateFlow" :key="s.title" class="mp-timeline__item" :class="'is-' + (s.tone === 'processing' ? 'warning' : s.tone)">
                <div class="mp-timeline__title">{{ s.title }}</div>
                <div class="mp-timeline__time">{{ s.time }}</div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-tabs" style="padding: 0 var(--space-4)">
            <button v-for="t in tabs" :key="t.key" class="mp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">
              {{ t.label }}
            </button>
          </div>
          <div class="mp-card__body">
            <table v-if="tab === 'proposals'" class="mp-audit">
              <thead><tr><th>材料</th><th>版本</th><th>提交时间</th><th>状态</th><th>批阅人</th></tr></thead>
              <tbody>
                <tr v-for="p in detail.proposals" :key="p.id">
                  <td class="is-who">{{ p.type }}</td>
                  <td>{{ p.version }}</td>
                  <td>{{ p.submitAt }}</td>
                  <td><StatusTag :status="p.status" dot /></td>
                  <td>{{ p.reviewer }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'finals'" class="mp-audit">
              <thead><tr><th>成果</th><th>版本</th><th>提交时间</th><th>状态</th><th>查重</th></tr></thead>
              <tbody>
                <tr v-for="f in detail.finals" :key="f.id">
                  <td class="is-who">{{ f.type }}</td>
                  <td>{{ f.version }}</td>
                  <td>{{ f.submitAt }}</td>
                  <td><StatusTag :status="f.status" dot /></td>
                  <td>{{ f.plagiarism }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else class="mp-audit">
              <thead><tr><th>检测对象</th><th>查重率</th><th>状态</th><th>时间</th><th>报告</th></tr></thead>
              <tbody>
                <tr v-for="p in detail.plagiarisms" :key="p.id">
                  <td class="is-who">{{ p.version }}</td>
                  <td>{{ p.rate }}</td>
                  <td>{{ p.status }}</td>
                  <td>{{ p.time }}</td>
                  <td><button class="mp-link" @click="download(p)">下载</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审计日志（本学生毕设档案）</span></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>影响数据</th></tr></thead>
              <tbody>
                <tr v-for="(a, i) in detail.auditTrail" :key="i">
                  <td class="is-who">{{ a.who }}</td>
                  <td>{{ a.time }}</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.affected }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕设学生详情（/admin/graduation/students/:id）：课题 + 主状态 + 材料/成果/查重页签 + 审计日志。 */
import { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      tab: 'proposals',
      tabs: [
        { key: 'proposals', label: '开题记录' },
        { key: 'finals', label: '成果提交' },
        { key: 'plagiarisms', label: '查重记录' }
      ]
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'batchRemind', label: '发送提醒' },
        { key: 'editProject', label: '编辑毕设信息', variant: 'primary' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    maskPhone(v) {
      return v ? v.slice(0, 3) + '****' + v.slice(-4) : '未登记'
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    onToolbar(key) {
      if (key === 'batchRemind') toast.success('提醒已发送（站内信 + 学生端），已写入审计日志')
      else toast.info('演示环境：编辑抽屉将在后续批次开放（变更字段将留痕）')
    },
    download(p) {
      toast.success(p.report + ' 下载任务已创建（含水印），下载行为已留痕')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getStudentDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
