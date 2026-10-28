<script>
import { useSessionStore } from '@/stores/session'

export default {
  onLaunch() {
    useSessionStore().restore()
  }
}
</script>

<style>
@import './styles/tokens.css';
@import './styles/common.css';
@import './styles/internship-flow.css';

page {
  background: var(--bg-page);
  color: var(--text-primary);
  font-size: var(--font-size-md);
  line-height: var(--line-height-base);
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue',
    Helvetica, 'Microsoft YaHei', Arial, sans-serif;
}
</style>
