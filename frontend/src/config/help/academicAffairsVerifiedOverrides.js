/**
 * 教务历史帮助下线策略。
 *
 * 知识清洗 V2 后，学籍 / 成绩 / 选课 / 考务正式正文已迁移到
 * academicAffairsCleanHelpCards.js。这里不再承担“旧正文错误、运行时再覆盖”的修补职责，
 * 只保留历史长文的显式隔离原因，便于审计追溯。
 */
export const ACADEMIC_AFFAIRS_LEGACY_EXCLUSIONS = {
  docs: {
    'doc-aa-grade': '旧长文仍把成绩写成固定“平时/期末→自动总评”，与当前1–12个动态成绩项、特殊状态和方案锁定机制冲突'
  },
  cards: {},
  flows: {}
}

/**
 * 兼容历史测试/引用的退役导出。运行时不再消费此对象；必须保持为空。
 * 新的教务正式知识只能进入 ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS。
 */
export const ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES = Object.freeze({})
