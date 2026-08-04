<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" :title="doc.title || '协议'" show-back />
    <!-- 学校配置了正式外链版本时优先用外链（需先在小程序后台配置业务域名） -->
    <!-- #ifdef MP-WEIXIN -->
    <web-view v-if="externalUrl" :src="externalUrl" />
    <!-- #endif -->
    <scroll-view v-if="!externalUrl" scroll-y class="ld__scroll">
      <view class="page-pad">
        <view class="ld__head">
          <text class="ld__title">{{ doc.title }}</text>
          <text class="ld__meta">版本 {{ doc.version }} · 更新于 {{ doc.updatedAt }}</text>
        </view>
        <text v-if="doc.intro" class="ld__intro">{{ fill(doc.intro) }}</text>
        <view v-for="(s, si) in doc.sections" :key="si" class="ld__section">
          <text class="ld__h2">{{ s.title }}</text>
          <text v-for="(p, pi) in (s.paragraphs || [])" :key="'p' + pi" class="ld__p">{{ fill(p) }}</text>
          <view v-for="(li, li2) in (s.list || [])" :key="'l' + li2" class="ld__li">
            <text class="ld__dot">•</text><text class="ld__litext">{{ fill(li) }}</text>
          </view>
        </view>
        <view class="ld__foot"><text>如对本文有疑问，请联系学校相关部门。</text></view>
      </view>
    </scroll-view>
  </view>
</template>

<script>
import { ENV } from '@/config/env'
import { LEGAL_DOCS, fillPlaceholders } from '@/config/legalDocs'

export default {
  data() { return { doc: {}, externalUrl: '' } },
  onLoad(query) {
    const kind = (query && query.kind) === 'terms' ? 'terms' : 'privacy'
    this.doc = LEGAL_DOCS[kind] || {}
    // 外链为可选覆盖：学校发布了正式法务版本时配置，否则一律用内置正文
    this.externalUrl = kind === 'terms' ? (ENV.termsUrl || '') : (ENV.privacyUrl || '')
    uni.setNavigationBarTitle({ title: this.doc.title || '协议' })
  },
  methods: { fill(text) { return fillPlaceholders(text) } }
}
</script>

<style scoped>
.ld__scroll { height: calc(100vh - 88px); }
.ld__head { padding-bottom: var(--space-3); border-bottom: 1px solid var(--border-base); }
.ld__title { display: block; font-size: 20px; font-weight: 600; color: var(--text-primary); }
.ld__meta { display: block; margin-top: 6px; font-size: 12px; color: var(--text-tertiary); }
.ld__intro { display: block; margin-top: var(--space-4); font-size: 14px; line-height: 1.8; color: var(--text-secondary); }
.ld__section { margin-top: var(--space-5); }
.ld__h2 { display: block; font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: var(--space-2); }
.ld__p { display: block; font-size: 14px; line-height: 1.85; color: var(--text-secondary); margin-bottom: var(--space-2); }
.ld__li { display: flex; margin-bottom: var(--space-2); }
.ld__dot { flex: none; width: 14px; font-size: 14px; line-height: 1.85; color: var(--text-tertiary); }
.ld__litext { flex: 1; font-size: 14px; line-height: 1.85; color: var(--text-secondary); }
.ld__foot { margin: var(--space-6) 0 var(--space-8); font-size: 12px; color: var(--text-tertiary); }
</style>
