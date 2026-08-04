<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" :title="title" show-back />
    <MobileGlobalState v-if="!url" state="empty" title="链接未配置"
      description="学校尚未配置该文档链接，请联系学校管理员获取纸质版或电子版原文。" />
    <!-- #ifdef MP-WEIXIN -->
    <web-view v-else :src="url" />
    <!-- #endif -->
    <!-- #ifndef MP-WEIXIN -->
    <view v-else class="page-pad">
      <text class="t-sm t-link" @click="openExternal">在浏览器中打开：{{ url }}</text>
    </view>
    <!-- #endif -->
  </view>
</template>

<script>
export default {
  data() { return { title: '协议', url: '' } },
  onLoad(query) {
    this.title = (query && query.title) || '协议'
    this.url = (query && query.url) || ''
    uni.setNavigationBarTitle({ title: this.title })
  },
  methods: {
    openExternal() {
      // #ifdef H5
      window.open(this.url, '_blank')
      // #endif
    }
  }
}
</script>

<style scoped>
.t-link { color: var(--brand-primary); word-break: break-all; }
</style>
