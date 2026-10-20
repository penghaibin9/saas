<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="发布通知" show-back />
    <view class="page-pad stack">
      <view class="card stack-sm">
        <input class="np__input" v-model="form.title" placeholder="通知标题（必填）" placeholder-class="np__ph" />
        <textarea class="np__textarea" v-model="form.content" :maxlength="500"
                  placeholder="通知内容（必填，不少于5字）" placeholder-class="np__ph" />

        <text class="np__label">接收范围</text>
        <view class="np__scopes">
          <text class="np__scope" :class="{ 'is-on': form.scopeType === 'CLASS' }" @click="form.scopeType = 'CLASS'">按班级</text>
          <text v-if="isAdmin" class="np__scope" :class="{ 'is-on': form.scopeType === 'COLLEGE' }" @click="form.scopeType = 'COLLEGE'">按学院</text>
          <text v-if="isAdmin" class="np__scope" :class="{ 'is-on': form.scopeType === 'SCHOOL' }" @click="form.scopeType = 'SCHOOL'">全校</text>
        </view>

        <template v-if="form.scopeType === 'CLASS'">
          <view class="np__class-search">
            <input v-model="classKeywordInput" class="np__input" maxlength="100" confirm-type="search"
                   placeholder="按班级名称或年级搜索" placeholder-class="np__ph" @confirm="applyClassSearch" />
            <button class="btn np__class-search-button" size="mini" :disabled="classesLoading" @click="applyClassSearch">搜索</button>
          </view>
          <text v-if="classesLoading" class="np__hint">正在加载本人负责班级…</text>
          <view v-else-if="classesError" class="np__class-error">
            <text>班级列表加载失败，请检查网络后重试。</text>
            <text class="np__retry" @click="loadClasses(classPage)">重新加载</text>
          </view>
          <MobileGlobalState v-else-if="!myClasses.length" state="empty"
                             :title="classKeyword ? '未找到匹配班级' : '暂无负责班级'"
                             description="如信息有误请联系系统管理员核实。" />
          <template v-else>
            <picker mode="selector" :range="myClasses" range-key="className" @change="onClassChange">
              <view class="np__input">{{ selectedClassLabel }}</view>
            </picker>
            <view v-if="classTotal > 0 || classPage > 1" class="np__class-pager">
              <button class="btn np__class-page-button" size="mini" :disabled="classPage <= 1 || classesLoading" @click="previousClassPage">上一页</button>
              <text>第 {{ classPage }} / {{ classPageCount }} 页</text>
              <button class="btn np__class-page-button" size="mini" :disabled="!classHasMore || classesLoading" @click="nextClassPage">下一页</button>
            </view>
          </template>
        </template>
        <template v-else-if="form.scopeType === 'COLLEGE'">
          <input class="np__input" type="number" v-model="form.collegeId" placeholder="学院ID（必填）" placeholder-class="np__ph" />
        </template>
        <text v-else-if="form.scopeType === 'SCHOOL'" class="np__hint">将发送给全校在校学生，请谨慎操作。</text>

        <button class="btn btn-primary" :disabled="submitting || !canSubmit" @click="submit">
          {{ submitting ? '发布中…' : '发布通知' }}
        </button>
      </view>
    </view>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const ADMIN_ROLES = ['college_admin', 'academic']
const CLASS_PAGE_SIZE = 20

function normalizeClassPage(result, requestedPage) {
  const items = result?.items
  const page = result?.page
  const pageSize = result?.pageSize
  const total = result?.total
  const hasMore = result?.hasMore
  if (!Array.isArray(items) || !Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== CLASS_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || items.length > pageSize
    || hasMore !== page * pageSize < total) {
    throw new Error('班级分页信息无法核对')
  }
  return { items, page, pageSize, total, hasMore }
}

export default {
  data() {
    return {
      isAdmin: false, myClasses: [], selectedClassId: '', submitting: false,
      form: { title: '', content: '', scopeType: 'CLASS', collegeId: '' },
      classPage: 1, classTotal: 0, classHasMore: false, classKeyword: '', classKeywordInput: '',
      classesLoading: true, classesError: false, _classLoadEpoch: 0, _pageActive: true,
      identity: currentSessionGeneration()
    }
  },
  computed: {
    selectedClassLabel() {
      const c = this.myClasses.find((x) => x.classId === this.selectedClassId)
      return c ? c.className : '选择班级'
    },
    classPageCount() { return this.classTotal ? Math.ceil(this.classTotal / CLASS_PAGE_SIZE) : 1 },
    canSubmit() {
      if (!this.form.title.trim() || this.form.content.trim().length < 5) return false
      if (this.form.scopeType === 'CLASS') return !!this.selectedClassId
      if (this.form.scopeType === 'COLLEGE') return !!this.form.collegeId
      return this.form.scopeType === 'SCHOOL'
    }
  },
  onLoad() {
    this._pageActive = true
    this.isAdmin = ADMIN_ROLES.includes(useSessionStore().currentRole)
    this.loadClasses(1)
  },
  onShow() {
    if (this.identity !== currentSessionGeneration()) {
      this.identity = currentSessionGeneration()
      this.selectedClassId = ''
      this.classPage = 1
      this.classTotal = 0
      this.classHasMore = false
      this.classKeyword = ''
      this.classKeywordInput = ''
      this.myClasses = []
      this._classLoadEpoch += 1
      this.classesLoading = false
      this.classesError = false
      this.loadClasses(1)
    }
  },
  onUnload() {
    this._pageActive = false
    this._classLoadEpoch += 1
  },
  methods: {
    onClassChange(e) { this.selectedClassId = this.myClasses[e.detail.value].classId },
    applyClassSearch() {
      const keyword = String(this.classKeywordInput || '').trim()
      if (keyword === this.classKeyword && !this.classesError) return
      this.classKeyword = keyword
      this.selectedClassId = ''
      this.loadClasses(1)
    },
    previousClassPage() { return this.classPage > 1 ? this.loadClasses(this.classPage - 1) : Promise.resolve(null) },
    nextClassPage() { return this.classHasMore ? this.loadClasses(this.classPage + 1) : Promise.resolve(null) },
    loadClasses(requested = this.classPage) {
      const requestedPage = Number(requested)
      if (!Number.isSafeInteger(requestedPage) || requestedPage < 1 || this.classesLoading && this._classLoadEpoch) return Promise.resolve(null)
      const identity = currentSessionGeneration()
      const epoch = this._classLoadEpoch + 1
      this._classLoadEpoch = epoch
      this.classesLoading = true
      this.classesError = false
      return teacherApi.getMyClasses({ page: requestedPage, pageSize: CLASS_PAGE_SIZE, keyword: this.classKeyword || undefined })
        .then((result) => {
          if (!this._pageActive || epoch !== this._classLoadEpoch || identity !== currentSessionGeneration()) return
          const data = normalizeClassPage(result, requestedPage)
          this.myClasses = data.items
          this.classPage = data.page
          this.classTotal = data.total
          this.classHasMore = data.hasMore
          this.identity = identity
          if (!this.myClasses.some((item) => item.classId === this.selectedClassId)) this.selectedClassId = ''
        })
        .catch(() => {
          if (!this._pageActive || epoch !== this._classLoadEpoch || identity !== currentSessionGeneration()) return
          this.classesError = true
        })
        .finally(() => {
          if (this._pageActive && epoch === this._classLoadEpoch && identity === currentSessionGeneration()) this.classesLoading = false
        })
    },
    submit() {
      if (this.submitting || !this.canSubmit) return
      this.submitting = true
      const body = { title: this.form.title.trim(), content: this.form.content.trim(), scopeType: this.form.scopeType }
      if (this.form.scopeType === 'CLASS') body.classId = this.selectedClassId
      if (this.form.scopeType === 'COLLEGE') body.collegeId = this.form.collegeId
      teacherApi.publishNotice(body).then((d) => {
        const st = d && d.status
        const tip = st === 'PENDING_REVIEW'
          ? '已提交审核'
          : st === 'SCHEDULED'
            ? '已预约发布'
            : `已发布给 ${(d && d.recipientCount) || 0} 名学生`
        uni.showToast({ title: tip, icon: 'success' })
        this.form = { title: '', content: '', scopeType: 'CLASS', collegeId: '' }
        this.selectedClassId = ''
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '发布失败，请稍后重试'))
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.np__input { width: 100%; height: 40px; line-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.np__textarea { width: 100%; min-height: 100px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.np__ph { color: var(--text-tertiary); }
.np__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.np__scopes { display: flex; gap: var(--space-2); }
.np__scope { padding: 6px 16px; border-radius: var(--radius-full); background: var(--bg-secondary); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.np__scope.is-on { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.np__hint { display: block; font-size: var(--font-size-sm); color: var(--warning-700); }
.np__class-search { display: flex; align-items: center; gap: var(--space-2); }
.np__class-search .np__input { flex: 1; min-width: 0; }
.np__class-search-button { flex-shrink: 0; margin: 0; }
.np__class-error { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); color: var(--danger-600); font-size: var(--font-size-sm); }
.np__retry { color: var(--teacher-600); flex-shrink: 0; }
.np__class-pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); color: var(--text-secondary); font-size: var(--font-size-xs); }
.np__class-page-button { margin: 0; }
</style>
