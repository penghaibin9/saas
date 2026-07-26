<template>
  <ModulePageShell
    title="导入学生"
    subtitle="学生主档由教务学籍导入或系统管理学生导入统一维护"
    :watermark="true"
    watermark-purpose="学生导入入口导航"
  >
    <div class="sig">
      <p class="sig__intro">
        学生主档由教务学籍导入或系统管理学生导入统一维护。本入口将根据学校已开通模块和您的权限，
        引导至正确入口，避免重复建档。
      </p>

      <!-- 无任何正式导入权限：禁止状态，不给可上传的假按钮 -->
      <div v-if="!canAcademic && !canSystem" class="sig__denied">
        <div class="sig__denied-title">当前账号无学生导入权限</div>
        <p>
          请联系教务处完成学籍导入，或联系系统管理员完成学生导入与账号开通。
        </p>
      </div>

      <template v-else>
        <section
          v-for="card in cards"
          :key="card.key"
          class="sig__card"
          :class="{ 'sig__card--primary': card.primary }"
        >
          <div class="sig__card-head">
            <span class="sig__card-title">{{ card.title }}</span>
            <span v-if="card.primary" class="sig__badge">推荐</span>
          </div>
          <p class="sig__card-desc">{{ card.desc }}</p>
          <ul class="sig__card-points">
            <li v-for="(p, i) in card.points" :key="i">{{ p }}</li>
          </ul>
          <AppButton
            :variant="card.primary ? 'primary' : 'default'"
            @click="go(card.to)"
          >{{ card.action }}</AppButton>
        </section>

        <p v-if="canAcademic && canSystem" class="sig__note">
          两个入口都可用时，建议优先由教务处走「教务学籍导入」建立正式学籍；
          若确需同时开通登录账号，可使用「学生导入与账号开通」——统一的查重规则会阻止重复建档。
        </p>
      </template>

      <p class="sig__foot">
        无论从哪个入口导入，学生都写入同一份学生主档：已存在的学生只会被复用并补齐空缺信息，
        不会重复建档；调整院系班请走「教务中心 › 学籍异动」。
      </p>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学生导入入口导航页（学工中心 › 学生主档 › 导入学生）。
 *
 * 本页**不上传、不写入**任何学生数据——学生主档只有两条正式写入路径：
 *   1) 教务中心 › 学籍导入（建学籍，不建账号）
 *   2) 系统管理 › 学生导入与账号开通（建/复用主档 + 开通账号）
 * 学工侧保留这个用户可见入口是为了不打断既有操作习惯，但只负责解释与分流，
 * 避免形成第三套建档链路（原实现直接调用 /import/students/*，已随本次改造删除）。
 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { getModuleEntitlements, getPermissionPatterns } from '@/security/permissionGate'
import { matchPermission } from '@/config/navPlan'

const P_ACADEMIC_IMPORT = 'academicAffairs.roster.import'
const P_SYSTEM_IMPORT = 'systemAdmin.user.import'

export default {
  name: 'StudentImportGatewayView',
  components: { ModulePageShell, AppButton },
  computed: {
    patterns() {
      return getPermissionPatterns() || []
    },
    /** 学校是否开通教务中心（模块授权，不是权限） */
    academicEnabled() {
      const mods = getModuleEntitlements()
      // 授权未下发时不做「未开通」判断，避免误导；后端仍是最终边界
      if (!Array.isArray(mods)) return true
      return mods.some((m) => ['academicAffairs', 'academicLegacy', 'academic'].includes(m))
    },
    canAcademic() {
      return this.academicEnabled && matchPermission(this.patterns, P_ACADEMIC_IMPORT)
    },
    canSystem() {
      return matchPermission(this.patterns, P_SYSTEM_IMPORT)
    },
    academicCard() {
      return {
        key: 'academic',
        title: '前往教务学籍导入',
        desc: '适用于教务处建立正式学生主档、学院专业班级和学籍信息，不会创建登录账号。',
        points: [
          '建立学籍：学院、专业、班级、年级、入学与学籍状态',
          '已存在的学生自动复用并补齐空缺，不重复建档',
          '不创建登录账号；学生登录需另行开通'
        ],
        action: '前往教务学籍导入',
        to: '/admin/academic-affairs/roster/import-export?from=student-center'
      }
    },
    systemCard() {
      return {
        key: 'system',
        title: '前往学生导入与账号开通',
        desc: '适用于未使用教务系统的学校。导入时将创建或复用学生主档，并开通登录账号。',
        points: [
          '主档不存在：创建主档后开通账号并绑定 STUDENT 角色',
          '主档已存在：复用原档案后开通账号，不重复建档',
          '生成一次性初始密码回执，请及时下载'
        ],
        action: '前往学生导入与账号开通',
        to: '/admin/system/identity-import/students?from=student-center'
      }
    },
    /** 分流顺序：开通教务且有教务权限时以教务为主推荐 */
    cards() {
      const list = []
      if (this.canAcademic) list.push({ ...this.academicCard, primary: true })
      if (this.canSystem) list.push({ ...this.systemCard, primary: !this.canAcademic })
      return list
    }
  },
  methods: {
    go(to) {
      this.$router.push(to)
    }
  }
}
</script>

<style scoped>
.sig { display: flex; flex-direction: column; gap: 16px; }
.sig__intro { color: var(--mp-text-secondary, #5b6472); line-height: 1.7; margin: 0; }
.sig__card {
  border: 1px solid var(--mp-border, #e3e8ef);
  border-radius: 8px; padding: 16px 18px; background: var(--mp-surface, #fff);
  display: flex; flex-direction: column; gap: 10px; align-items: flex-start;
}
.sig__card--primary { border-color: var(--mp-primary, #2f6fed); box-shadow: 0 0 0 1px var(--mp-primary, #2f6fed) inset; }
.sig__card-head { display: flex; align-items: center; gap: 8px; }
.sig__card-title { font-weight: 600; font-size: 15px; }
.sig__badge {
  font-size: 12px; padding: 1px 8px; border-radius: 10px;
  background: var(--mp-primary-bg, #eaf1ff); color: var(--mp-primary, #2f6fed);
}
.sig__card-desc { margin: 0; color: var(--mp-text-secondary, #5b6472); }
.sig__card-points { margin: 0; padding-left: 18px; color: var(--mp-text-secondary, #5b6472); line-height: 1.8; }
.sig__note, .sig__foot { margin: 0; color: var(--mp-text-tertiary, #8a94a6); font-size: 13px; line-height: 1.7; }
.sig__denied {
  border: 1px solid var(--mp-warning-border, #f0d9a8); background: var(--mp-warning-bg, #fff8e8);
  border-radius: 8px; padding: 16px 18px;
}
.sig__denied-title { font-weight: 600; margin-bottom: 6px; }
.sig__denied p { margin: 0; color: var(--mp-text-secondary, #5b6472); }
</style>
