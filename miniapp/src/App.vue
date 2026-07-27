<script>
import { useSessionStore } from '@/stores/session'
import { applyBrandTheme } from '@/config'

export default {
  onLaunch() {
    // 启动时应用学校品牌主题（来自 tenantBrandConfig，禁止硬编码学校名）
    applyBrandTheme()
    // 恢复上次登录会话（mock）
    const session = useSessionStore()
    session.restore()
  },
  onShow() {},
  onHide() {}
}
</script>

<style>
/* 全局设计令牌 + 通用样式。移动端组件/页面禁止硬编码颜色/字号/间距。 */
@import './styles/tokens.css';
@import './styles/common.css';

page {
  background: var(--bg-page);
  color: var(--text-primary);
  font-size: var(--font-size-base);
  line-height: var(--line-height-base);
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue',
    Helvetica, 'Microsoft YaHei', Arial, sans-serif;
}
</style>
