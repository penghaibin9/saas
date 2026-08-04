<template>
  <view class="page-wrap" />
</template>

<script>
// 旧路由兼容：教务中心已收编至 pages/student/academic-affairs/index（课表/成绩/学分/预警/补考/选课/学籍/毕业进度一站式入口）。
// 保留本文件仅为避免旧链接/收藏夹刷新 404，本身不再承载业务逻辑。
export default {
  onLoad() {
    // 兜底用 reLaunch 而非 switchTab：本工程无原生 tabBar，switchTab 必定失败，
    // 会让旧链接在跳转失败时卡在空白页（2026-08-04 复审：即 V2 报告 P2-07）。
    uni.redirectTo({
      url: '/pages/student/academic-affairs/index',
      fail: () => uni.reLaunch({ url: '/pages/student/home/index' })
    })
  }
}
</script>
