<template>
  <view class="page-wrap">
    <MobileGlobalState state="loading" title="正在打开我的办理" />
  </view>
</template>

<script>
// V3 §7.2 兼容层：「我的申请」已升级为「我的办理 / 业务回执中心」。
// 历史消息深链、旧版首页与旧版个人中心仍可能指向本路由，因此这里保留原路由并
// 重定向到新页面（带上原有 query），刷新不 404，也不会出现两个并列的入口。
export default {
  onLoad(query) {
    const params = []
    for (const key of Object.keys(query || {})) {
      const value = query[key]
      if (value === undefined || value === null || value === '') continue
      // 旧深链用 recordId 指办理记录，新页面按 caseId 聚焦。
      const name = key === 'recordId' ? 'caseId' : key
      params.push(`${encodeURIComponent(name)}=${encodeURIComponent(String(value))}`)
    }
    const target = '/pages/student/my-work/index' + (params.length ? `?${params.join('&')}` : '')
    uni.redirectTo({ url: target, fail() { uni.reLaunch({ url: target }) } })
  }
}
</script>
