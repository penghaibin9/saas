<template>
  <ModulePageShell
    :title="record ? '住宿详情 · ' + record.name : '住宿详情'"
    :subtitle="record ? (record.building || '') + ' ' + record.room + '-' + record.bed : '按学生定位住宿记录'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <AppButton variant="ghost" @click="backToList">← 返回住宿台账</AppButton>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!record"
        title="未找到该住宿记录"
        description="记录可能不存在、已超出当前楼栋数据范围，或链接缺少学生参数；请从宿舍服务住宿台账重新进入"
      />
      <DormRecordDetail v-else :record="record" :exceptions="exceptions" :exceptions-loading="exceptionsLoading" :ctx="ctx">
        <template #actions>
          <AppButton variant="ghost" @click="$router.push('/admin/campus-service/students/' + record.studentId)">学生服务</AppButton>
          <AppButton variant="ghost" @click="$router.push('/admin/student/' + record.studentId)">学生360</AppButton>
        </template>
      </DormRecordDetail>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 住宿记录独立详情深链接页（/admin/campus-service/dormitory/records/:recordId?stu=…）— 第一批交互改造。
 * 与住宿台账双栏共用 DormRecordDetail 业务详情组件（避免两套逻辑）；适用于刷新、学生360/风险跳转、
 * 复制链接、窄屏查看。现无单条查询接口：按 ?stu=（学生姓名）走既有列表接口 keyword 定位，未命中翻页兜底。
 * 编辑/标记异常等写操作在住宿台账双栏内进行，本页保持只读查看（权限与数据范围沿用原 key）。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { DormRecordDetail } from '@/modules/campusService/components'
import { getDormitoryRecords, getDormitoryExceptions } from '@/modules/campusService/api/campusService.api'

export default {
  name: 'DormRecordDetailView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, DormRecordDetail, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', record: null, exceptions: [], exceptionsLoading: false }
  },
  created() {
    this.load()
  },
  methods: {
    backToList() {
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (back && String(back).startsWith('/admin/campus-service/dormitory')) this.$router.back()
      else this.$router.push('/admin/campus-service/dormitory')
    },
    async load() {
      this.loading = true
      this.error = ''
      this.record = null
      const id = String(this.$route.params.recordId || '')
      const stu = String(this.$route.query.stu || '')
      try {
        if (stu) {
          const res = await getDormitoryRecords({ keyword: stu, page: 1, pageSize: 50 })
          if (res.code !== 0) throw new Error(res.message)
          this.record = (res.data.list || []).find((r) => r.id === id) || null
        }
        if (!this.record) {
          for (let page = 1; page <= 5 && !this.record; page++) {
            const res = await getDormitoryRecords({ page, pageSize: 100 })
            if (res.code !== 0) throw new Error(res.message)
            this.record = (res.data.list || []).find((r) => r.id === id) || null
            if ((res.data.list || []).length < 100) break
          }
        }
        if (this.record) this.loadExceptions()
      } catch (e) {
        this.error = e.message || '加载失败'
      }
      this.loading = false
    },
    async loadExceptions() {
      this.exceptionsLoading = true
      const res = await getDormitoryExceptions({ keyword: this.record.name, pageSize: 20 })
      this.exceptions = res.code === 0 ? (res.data.list || []).filter((e) => e.studentId === this.record.studentId) : []
      this.exceptionsLoading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
