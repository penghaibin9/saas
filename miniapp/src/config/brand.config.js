/**
 * 学校品牌配置（tenantBrandConfig）
 * ------------------------------------------------------------
 * 平台名称统一为「高校学生全生命周期管理平台」。
 * 学校名称 / Logo / 主色 全部来自此处，页面禁止硬编码学校名。
 * 真实环境中该配置应由后端按租户下发；未下发时只保留平台级安全默认值，
 * 不展示虚构学校、联系方式或认证信息。
 */
export const tenantBrandConfig = {
  tenantId: '',
  // 平台主名称（固定）
  platformName: '高校学生全生命周期管理平台',
  platformShortName: '学生全周期平台',
  // 学校信息（占位，可由后端下发覆盖；请勿在页面里写死真实校名）
  schoolName: '',
  schoolShortName: '',
  schoolEnName: '',
  // Logo 占位：留空时页面用校名首字生成文字 Logo
  logo: '',
  // 品牌色（运行时会写入 --brand-primary 等 CSS 变量）
  colors: {
    primary: '#2563EB',
    primaryStrong: '#1D4ED8',
    teacher: '#0D9488'
  },
  slogan: '教务、学工、实习与毕业设计一站协同',
  supportPhone: '',
  copyright: '湖南跃科信息工程有限公司 · 湘ICP备2026031107号'
}

export default tenantBrandConfig
