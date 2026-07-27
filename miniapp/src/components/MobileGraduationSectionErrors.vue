<template>
  <view v-if="visible && errors.length" class="gdse">
    <view class="gdse__body">
      <text class="gdse__title">部分毕设环节加载失败</text>
      <text class="gdse__desc">{{ errors.join('、') }}。这不是“暂无业务”，请重试后再办理。</text>
    </view>
    <button class="gdse__retry" @click="retry">重试</button>
  </view>
</template>

<script>
function pageStack() { return typeof getCurrentPages === 'function' ? getCurrentPages() : [] }
let owner = null
export default {
  name: 'MobileGraduationSectionErrors',
  data() { return { visible: false, errors: [], timer: null, owns: false } },
  mounted() {
    const pages = pageStack(); const page = pages[pages.length - 1]
    const match = ((page && (page.route || page.__route__)) || '') === 'pages/student/graduation/index'
    if (match && owner == null) {
      owner = this._uid; this.owns = true; this.visible = true
      this.sync(); this.timer = setInterval(this.sync, 500)
    }
  },
  beforeUnmount() {
    if (this.timer) clearInterval(this.timer)
    if (this.owns && owner === this._uid) owner = null
  },
  methods: {
    currentVm() { const pages = pageStack(); const page = pages[pages.length - 1]; return page && page.$vm },
    sync() { const vm = this.currentVm(); this.errors = Array.isArray(vm && vm.processErrors) ? [...vm.processErrors] : [] },
    retry() { const vm = this.currentVm(); if (vm && typeof vm.loadProcess === 'function') vm.loadProcess() }
  }
}
</script>

<style scoped>
.gdse { margin:0 var(--page-padding-mobile) var(--space-3); padding:var(--space-3); display:flex; align-items:flex-start; gap:var(--space-3); border:1px solid var(--danger-100); border-radius:var(--radius-lg); background:var(--danger-50); }
.gdse__body { flex:1; min-width:0; }.gdse__title { display:block; font-size:var(--font-size-base); font-weight:var(--font-weight-medium); color:var(--danger-700); }
.gdse__desc { display:block; margin-top:4px; font-size:var(--font-size-sm); line-height:1.5; color:var(--danger-600); }.gdse__retry { flex:none; margin:0; min-height:34px; line-height:34px; padding:0 var(--space-3); font-size:var(--font-size-sm); color:var(--danger-700); background:var(--bg-card); border:1px solid var(--danger-200); }
</style>
