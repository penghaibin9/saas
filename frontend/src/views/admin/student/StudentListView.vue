<template>
  <div class="sp-page">
    <AppSectionHeader title="学生列表" subtitle="支持多条件筛选；身份证/手机号默认脱敏展示" />

    <StudentSearchBar v-model="filters" :options="options" @search="search" @reset="reset" />

    <div class="sp-actions-row">
      <span class="sp-count">共 {{ total }} 名学生</span>
      <AppButton
        variant="secondary"
        :disabled="!canExport"
        :title="canExport ? '' : '当前账号无导出权限'"
        @click="go('/admin/student/import-export')"
      >
        导出学生主档
      </AppButton>
    </div>

    <StudentStateBlock :loading="loading" :error="error" :empty="!list.length" :no-permission="noPermission" @retry="load">
      <AppCard class="sp-card">
        <table class="sp-table">
          <thead>
            <tr>
              <th>姓名</th><th>学号</th><th>学院/专业/班级</th><th>年级</th>
              <th>手机号</th><th>身份证</th><th>学生状态</th><th>认证</th><th>账号</th><th>风险</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in maskedList" :key="s.studentId">
              <td>{{ s.name }}</td>
              <td>{{ s.studentNo }}</td>
              <td>{{ s.collegeName }} / {{ s.majorName }} / {{ s.className }}</td>
              <td>{{ s.grade }}</td>
              <td>{{ s.phone || '未登记' }}</td>
              <td>{{ s.idCard || '未登记' }}</td>
              <td><StudentStatusTag :status="s.studentStatus" /></td>
              <td><AppBadge :type="identityBadge(s.identityVerifyStatus)">{{ identityText(s.identityVerifyStatus) }}</AppBadge></td>
              <td><AppBadge :type="bindBadge(s.bindStatus)">{{ bindText(s.bindStatus) }}</AppBadge></td>
              <td><StudentRiskFlag :flags="s.riskFlags" /></td>
              <td><AppButton variant="ghost" @click="viewDetail(s)">详情</AppButton></td>
            </tr>
          </tbody>
        </table>
        <div class="sp-pager">
          <AppButton variant="ghost" :disabled="page <= 1" @click="turnPage(-1)">上一页</AppButton>
          <span>第 {{ page }} / {{ maxPage }} 页</span>
          <AppButton variant="ghost" :disabled="page >= maxPage" @click="turnPage(1)">下一页</AppButton>
        </div>
      </AppCard>
    </StudentStateBlock>
  </div>
</template>

<script>
/** 页面 3：/admin/student/list 学生列表（筛选字典来自 options，脱敏展示） */
import { AppCard, AppButton, AppBadge, AppSectionHeader } from '@/components/ui'
import StudentStateBlock from '@/modules/student/components/StudentStateBlock.vue'
import StudentSearchBar from '@/modules/student/components/StudentSearchBar.vue'
import StudentStatusTag from '@/modules/student/components/StudentStatusTag.vue'
import StudentRiskFlag from '@/modules/student/components/StudentRiskFlag.vue'
import {
  studentProvider,
  hasStudentPermission,
  STUDENT_PERMISSION,
  maskStudentForDisplay,
  formatIdentityVerifyStatus,
  formatBindStatus,
  getIdentityBadge,
  getBindBadge
} from '@/modules/student'

const EMPTY_FILTERS = () => ({
  keyword: '',
  collegeId: '',
  majorId: '',
  classId: '',
  grade: '',
  studentStatus: '',
  academicStatus: '',
  identityVerifyStatus: '',
  accountStatus: ''
})

export default {
  name: 'StudentListView',
  components: { AppCard, AppButton, AppBadge, AppSectionHeader, StudentStateBlock, StudentSearchBar, StudentStatusTag, StudentRiskFlag },
  data() {
    return {
      loading: false,
      error: '',
      list: [],
      total: 0,
      page: 1,
      pageSize: 10,
      filters: EMPTY_FILTERS(),
      options: { colleges: [], majors: [], classes: [], grades: [] }
    }
  },
  computed: {
    noPermission() {
      return !hasStudentPermission(STUDENT_PERMISSION.PROFILE_VIEW)
    },
    canExport() {
      return hasStudentPermission(STUDENT_PERMISSION.EXPORT)
    },
    maskedList() {
      return this.list.map(maskStudentForDisplay)
    },
    maxPage() {
      return Math.max(1, Math.ceil(this.total / this.pageSize))
    }
  },
  async created() {
    const opt = await studentProvider.getStudentOptions()
    if (opt.code === 0) this.options = opt.data
    if (!this.noPermission) this.load()
  },
  methods: {
    identityText: formatIdentityVerifyStatus,
    identityBadge: getIdentityBadge,
    bindText: formatBindStatus,
    bindBadge: getBindBadge,
    go(path) {
      this.$router.push(path)
    },
    viewDetail(s) {
      this.$router.push(`/admin/student/${s.studentId}`)
    },
    turnPage(delta) {
      const next = this.page + delta
      if (next < 1 || next > this.maxPage) return
      this.page = next
      this.load()
    },
    search() {
      this.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await studentProvider.getStudentList({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) {
          this.list = res.data.list
          this.total = res.data.total
        } else {
          this.error = res.message
        }
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import './student-page.css';
</style>
