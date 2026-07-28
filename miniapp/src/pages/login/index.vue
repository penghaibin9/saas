<template>
  <view class="entry-page">
    <view class="entry-brand"><view class="entry-logo">{{ logoText }}</view><text class="entry-name">{{ platformName }}</text><text class="entry-sub">请选择本次使用的身份入口</text></view>
    <view class="entry-card">
      <view class="entry-option student" @click="choose('student')"><view class="entry-option__mark">学</view><view><text class="entry-option__title">我是学生</text><text class="entry-option__desc">办事务、交材料、查结果、看进度</text></view><text class="entry-option__arrow">›</text></view>
      <view class="entry-option teacher" @click="choose('teacher')"><view class="entry-option__mark">教</view><view><text class="entry-option__title">我是教师 / 管理人员</text><text class="entry-option__desc">移动审批、扫码核验、实习指导与风险处置</text></view><text class="entry-option__arrow">›</text></view>
    </view>
    <text class="entry-tip">退出登录、会话过期或旧版入口访问时，可在此重新选择身份。</text>
    <view class="entry-footer"><text>技术支持：湖南跃科信息工程有限公司</text><text>湘ICP备2026031107号</text></view>
  </view>
</template>

<script>
import { tenantBrandConfig } from '@/config'
import { relaunch } from '@/utils/nav'

const ENTRY_KEY = 'gx_login_entry_v1'

export default {
  computed: {
    platformName() { return tenantBrandConfig.platformShortName || tenantBrandConfig.platformName || '校园服务平台' },
    logoText() { return (tenantBrandConfig.schoolShortName || tenantBrandConfig.schoolName || '校').slice(0, 1) }
  },
  methods: {
    choose(entry) {
      try {
        uni.setStorageSync(ENTRY_KEY, entry)
      } catch {
        // 存储不可用时仍可继续进入所选登录页。
      }
      relaunch(`/pages/login/${entry}/index`)
    }
  }
}
</script>

<style scoped>
.entry-page { box-sizing: border-box; min-height: 100vh; padding: calc(76px + env(safe-area-inset-top)) 18px calc(24px + env(safe-area-inset-bottom)); color: #10233f; background: radial-gradient(circle at 85% 6%, #dce9ff 0, transparent 30%), #f4f7fb; }
.entry-brand { display: flex; flex-direction: column; align-items: center; }.entry-logo { display: flex; align-items: center; justify-content: center; width: 66px; height: 66px; border-radius: 20px; color: #fff; background: linear-gradient(145deg, #2f70ea, #1f56c9); box-shadow: 0 15px 30px -16px rgba(31,86,201,.65); font-size: 22px; font-weight: 700; }.entry-name { margin-top: 16px; font-size: 20px; font-weight: 700; }.entry-sub { margin-top: 7px; color: #718096; font-size: 12px; }
.entry-card { margin-top: 42px; }.entry-option { display: flex; align-items: center; gap: 13px; margin-top: 13px; padding: 19px 16px; border: 1px solid #e4eaf1; border-radius: 18px; background: #fff; box-shadow: 0 16px 36px -30px rgba(16,35,63,.5); }.entry-option__mark { flex: none; display: flex; align-items: center; justify-content: center; width: 46px; height: 46px; border-radius: 14px; color: #0f766e; background: #eaf8f5; font-size: 16px; font-weight: 700; }.teacher .entry-option__mark { color: #1f56c9; background: #eef4ff; }.entry-option > view:nth-child(2) { flex: 1; display: flex; flex-direction: column; }.entry-option__title { font-size: 15px; font-weight: 700; }.entry-option__desc { margin-top: 5px; color: #718096; font-size: 10px; line-height: 1.5; }.entry-option__arrow { color: #94a3b8; font-size: 27px; }
.entry-tip { display: block; margin: 25px 18px 0; color: #8290a3; text-align: center; font-size: 10px; line-height: 1.7; }.entry-footer { position: absolute; left: 0; right: 0; bottom: calc(22px + env(safe-area-inset-bottom)); display: flex; flex-direction: column; align-items: center; gap: 3px; color: #9aa7b8; font-size: 9px; }
@media (min-width: 520px) { .entry-page { width: 430px; margin: 0 auto; box-shadow: 0 0 35px rgba(16,35,63,.12); } }
</style>
