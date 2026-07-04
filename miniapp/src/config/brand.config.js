/**
 * 学校品牌配置（tenantBrandConfig）
 * ------------------------------------------------------------
 * 平台名称统一为「高校学生全生命周期管理平台」。
 * 学校名称 / Logo / 主色 全部来自此处，页面禁止硬编码学校名。
 * 真实环境中该配置应由后端按租户下发；此处为 mock 占位，方便本地预览与换肤。
 */
export const tenantBrandConfig = {
  tenantId: 'demo-university',
  // 平台主名称（固定）
  platformName: '高校学生全生命周期管理平台',
  platformShortName: '学生全周期平台',
  // 学校信息（占位，可由后端下发覆盖；请勿在页面里写死真实校名）
  schoolName: '示范高校',
  schoolShortName: '示范高校',
  schoolEnName: 'Demo University',
  // Logo 占位：留空时页面用校名首字生成文字 Logo
  logo: '',
  // 品牌色（运行时会写入 --brand-primary 等 CSS 变量）
  colors: {
    primary: '#2563EB',
    primaryStrong: '#1D4ED8',
    teacher: '#0D9488'
  },
  // 登录页标语占位
  slogan: '一个学生 · 一个平台 · 全周期陪伴',
  // 客服 / 帮助占位
  supportPhone: '400-000-0000',
  // 备案/版权占位
  copyright: '© 高校学生全生命周期管理平台'
}

export default tenantBrandConfig
