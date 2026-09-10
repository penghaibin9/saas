<template>
  <view>
    <MobileNavBar v-bind="$attrs">
      <template #right><button class="academic-directory-button" aria-label="打开教务目录" @click="open = true"><image class="academic-directory-icon" :src="catalogIcon" mode="aspectFit" /></button></template>
    </MobileNavBar>
    <view v-if="open" class="academic-directory-mask" @click="open = false">
      <view class="academic-directory" @click.stop>
        <view class="academic-directory-head"><text>教务目录</text><button class="academic-directory-close" @click="open = false">关闭</button></view>
        <input v-model="search" class="academic-directory-search" placeholder="搜索教务服务" />
        <scroll-view scroll-y class="academic-directory-list">
          <button v-for="item in filtered" :key="item[0]" class="academic-directory-item" @click="navigate(item[0])">{{ item[1] }}</button>
          <text v-if="!filtered.length" class="academic-directory-empty">没有匹配的教务服务</text>
        </scroll-view>
      </view>
    </view>
  </view>
</template>
<script>
import { go } from '@/utils/nav'
import catalogIcon from './catalog.svg'
const pages = [['index','教务中心'],['registration','学期注册'],['schedule','我的课表'],['selection','网上选课'],['attendance','我的考勤'],['calendar','校历'],['transcript','我的成绩'],['evaluation','学生评教'],['recheck','成绩复查'],['exam','考试与缓考'],['makeup','补考重修 / 免修'],['clearance','清考结果'],['status','学籍与异动'],['credits','学分修读'],['warning','学业预警'],['textbook','教材领用'],['level-exam','等级考试'],['major-split','专业分流'],['recognition','成绩认定'],['graduation','毕业进度']]
export default {
  inheritAttrs: false,
  data() { return { open: false, search: '', catalogIcon } },
  computed: { filtered() { return pages.filter(item => item[1].includes(this.search.trim())) } },
  methods: { navigate(key) { this.open = false; this.search = ''; go('/pages/student/academic-affairs/' + key) } }
}
</script>
<style scoped>
.academic-directory-button { display:flex; align-items:center; justify-content:center; padding:0; margin:0; width:44px; height:44px; background:transparent; border:0; }
.academic-directory-icon { width:20px; height:20px; }
.academic-directory-mask { position:fixed; inset:0; z-index:var(--z-modal, 1000); background:rgba(15,23,42,.35); display:flex; align-items:flex-end; }
.academic-directory { width:100%; box-sizing:border-box; padding:16px 16px calc(16px + env(safe-area-inset-bottom)); border-radius:16px 16px 0 0; background:var(--bg-card); }
.academic-directory-head { display:flex; align-items:center; justify-content:space-between; font-size:17px; font-weight:600; }
.academic-directory-close { min-height:44px; margin:0; font-size:14px; color:var(--brand-primary); background:transparent; border:0; }
.academic-directory-search { height:44px; margin:8px 0; padding:0 12px; box-sizing:border-box; border:1px solid var(--border-base); border-radius:8px; }
.academic-directory-list { height:60vh; }
.academic-directory-item { width:100%; min-height:44px; margin:0; padding:10px 4px; line-height:24px; font-size:14px; text-align:left; color:var(--text-primary); background:transparent; border-bottom:1px solid var(--border-light); border-radius:0; }
.academic-directory-empty { display:block; padding:20px; color:var(--text-secondary); font-size:14px; }
</style>
