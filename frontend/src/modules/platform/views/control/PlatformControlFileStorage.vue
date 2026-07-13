<template>
  <ModulePageShell title="文件存储设置" subtitle="论文/材料等附件存哪里：服务器本地磁盘 或 腾讯云对象存储 COS" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <LoadingState v-if="loading" text="正在加载存储配置…" />
    <template v-else>
      <!-- 当前状态 -->
      <AppCard class="fs__panel">
        <AppSectionHeader title="当前存储方式" />
        <div class="fs__now">
          <span class="fs__badge" :class="cfg.backend === 'cos' ? 'fs__badge--cos' : 'fs__badge--local'">
            {{ cfg.backend === 'cos' ? '腾讯云 COS（对象存储）' : '本地磁盘（服务器 uploads 目录）' }}
          </span>
          <span class="fs__src">配置来源：{{ cfg.source === 'platform' ? '本页面' : '服务器 .env（尚未在此设置过）' }}</span>
        </div>
      </AppCard>

      <!-- 选后端 -->
      <AppCard class="fs__panel">
        <AppSectionHeader title="选择存储方式" />
        <label class="fs__radio">
          <input type="radio" value="local" v-model="cfg.backend" />
          <span><b>本地磁盘</b>（默认）—— 文件存在这台服务器上，单机使用够用，无需任何配置。</span>
        </label>
        <label class="fs__radio">
          <input type="radio" value="cos" v-model="cfg.backend" />
          <span><b>腾讯云 COS</b> —— 文件存到腾讯云，换服务器、多台机器、防丢更稳。需在下方填写四项参数。</span>
        </label>
      </AppCard>

      <!-- COS 参数：仅选 COS 时展开 -->
      <AppCard v-if="cfg.backend === 'cos'" class="fs__panel">
        <AppSectionHeader title="腾讯云 COS 参数" />
        <div class="fs__grid">
          <label class="fs__field">
            <span>所在地域 Region</span>
            <input v-model="cfg.cosRegion" class="fs__input" placeholder="如 ap-guangzhou（广州）" />
          </label>
          <label class="fs__field">
            <span>存储桶名称 Bucket</span>
            <input v-model="cfg.cosBucket" class="fs__input" placeholder="如 student-files-1250000000" />
          </label>
          <label class="fs__field">
            <span>SecretId <em v-if="cfg.hasSecretId" class="fs__saved">（已保存，留空不改）</em></span>
            <input v-model="cfg.cosSecretId" class="fs__input" placeholder="腾讯云访问密钥 SecretId" autocomplete="off" />
          </label>
          <label class="fs__field">
            <span>SecretKey <em v-if="cfg.hasSecretKey" class="fs__saved">（已保存，留空不改）</em></span>
            <input v-model="cfg.cosSecretKey" class="fs__input" type="password" placeholder="腾讯云访问密钥 SecretKey" autocomplete="new-password" />
          </label>
        </div>
        <p class="fs__hint">🔒 密钥保存后会加密存储，页面只显示后 4 位，不会明文回显。建议用「子账号」密钥并只授权这一个桶的读写权限。</p>
      </AppCard>

      <!-- 操作 -->
      <AppCard class="fs__panel">
        <div class="fs__ops">
          <AppButton variant="primary" :loading="saving" @click="save">保存设置</AppButton>
          <AppButton v-if="cfg.backend === 'cos'" variant="secondary" :loading="testing" @click="test">测试连接</AppButton>
          <span v-if="testResult" class="fs__test" :class="testResult.ok ? 'fs__test--ok' : 'fs__test--bad'">
            {{ testResult.ok ? '✓ ' : '✗ ' }}{{ testResult.message }}
          </span>
        </div>
      </AppCard>

      <!-- 操作步骤说明 -->
      <AppCard class="fs__panel fs__guide">
        <AppSectionHeader title="怎么切换到腾讯云 COS（照着做即可）" />
        <ol class="fs__steps">
          <li>登录 <b>腾讯云控制台</b> → 搜索并进入「<b>对象存储 COS</b>」→ 点「创建存储桶」，地域建议选离你服务器最近的（如广州 ap-guangzhou），权限选「私有读写」。创建后记下<b>桶名称</b>和<b>所属地域</b>。</li>
          <li>进入「<b>访问管理 CAM</b>」→「密钥管理」→「API 密钥管理」，新建一对密钥，拿到 <b>SecretId</b> 和 <b>SecretKey</b>。（更安全的做法：建一个只授权这个桶读写的子账号密钥。）</li>
          <li>回到本页，上方选「<b>腾讯云 COS</b>」，把<b>地域、桶名、SecretId、SecretKey</b> 四项填进去，点「<b>保存设置</b>」。</li>
          <li>点「<b>测试连接</b>」。显示「连接成功」就说明通了；失败会告诉你原因（多半是密钥或桶名填错、地域不对）。</li>
          <li>连接成功后，<b>新上传</b>的论文/材料就会自动存到腾讯云了。<b>以前已上传</b>的老文件还在服务器本地，需要让技术人员在服务器上跑一次搬家命令
            <code class="fs__code">python scripts/migrate_files_to_cos.py --commit</code> 把老文件一次性搬过去（不影响使用）。</li>
        </ol>
        <p class="fs__note">说明：切回「本地磁盘」随时可以，不会丢数据。若「测试连接」提示未安装 SDK，请让技术人员在服务器执行一次
          <code class="fs__code">pip install cos-python-sdk-v5</code>。</p>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
import { AppButton, AppCard, AppSectionHeader } from '@/components/ui'
import { LoadingState, ModulePageShell } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformControlFileStorage',
  components: { AppButton, AppCard, AppSectionHeader, LoadingState, ModulePageShell },
  data() {
    return {
      loading: true,
      saving: false,
      testing: false,
      cfg: { backend: 'local', cosRegion: '', cosBucket: '', cosSecretId: '', cosSecretKey: '', hasSecretId: false, hasSecretKey: false, source: 'env' },
      testResult: null
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      const res = await platformControlApi.getFileStorage()
      this.loading = false
      if (res.code === 0) {
        // 密钥字段读回是脱敏值，展示但不作为待提交明文——清空输入框，靠 hasSecretId/Key 提示"已保存"
        const c = res.data.config
        this.cfg = { ...c, cosSecretId: '', cosSecretKey: '' }
      } else {
        toast.error(res.message)
      }
    },
    async save() {
      this.saving = true
      this.testResult = null
      const res = await platformControlApi.putFileStorage({ ...this.cfg })
      this.saving = false
      if (res.code === 0) {
        const c = res.data.config
        this.cfg = { ...c, cosSecretId: '', cosSecretKey: '' }
        toast.success('存储设置已保存并生效')
      } else {
        toast.error(res.message)
      }
    },
    async test() {
      this.testing = true
      this.testResult = null
      const res = await platformControlApi.testFileStorage()
      this.testing = false
      if (res.code === 0) {
        this.testResult = res.data
      } else {
        this.testResult = { ok: false, message: res.message }
      }
    }
  }
}
</script>

<style scoped>
.fs__panel {
  padding: var(--space-4);
  margin-bottom: var(--space-3);
}
.fs__now {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-top: var(--space-2);
}
.fs__badge {
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}
.fs__badge--local {
  background: var(--bg-section-blue, #eef2ff);
  color: #3b4a8c;
}
.fs__badge--cos {
  background: #e6f7ee;
  color: #1a7a4a;
}
.fs__src {
  font-size: 12px;
  color: var(--text-tertiary);
}
.fs__radio {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}
.fs__radio input {
  margin-top: 3px;
}
.fs__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-2);
}
.fs__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.fs__saved {
  font-style: normal;
  color: #1a7a4a;
  font-size: 12px;
}
.fs__input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
}
.fs__input:focus {
  outline: none;
  border-color: var(--glow);
}
.fs__hint {
  margin-top: var(--space-3);
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.6;
}
.fs__ops {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.fs__test {
  font-size: 13px;
}
.fs__test--ok {
  color: #1a7a4a;
}
.fs__test--bad {
  color: #c0392b;
}
.fs__guide {
  background: var(--bg-section-blue, #f7f9ff);
}
.fs__steps {
  margin: var(--space-2) 0 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.9;
}
.fs__steps li {
  margin-bottom: var(--space-2);
}
.fs__code {
  background: #2b2f3a;
  color: #e6e6e6;
  padding: 1px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-family: var(--font-mono, monospace);
}
.fs__note {
  margin-top: var(--space-3);
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.7;
}
</style>
