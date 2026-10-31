import { formatDateTime, formatDate } from '../src/utils/dateUtils.js'
import { normalizeUiError } from '../src/utils/presentationSafety.js'
import { systemRelationshipReturnTo } from '../src/utils/systemRelationshipNavigation.js'
import { shiftTypeText, shiftTypeValue } from '../src/modules/internship/constants/position.constants.js'

// 旧行为用例剥离页面导入后，仍使用真实公共展示工具；业务接口由各用例显式提供。
export function componentFactory(...parameters) {
  const source = parameters.pop().replace(/\bcomponents:\s*\{[^}]*\},\s*/, '')
  const dependencies = {
    formatDateTime, formatDate, normalizeUiError, systemRelationshipReturnTo, shiftTypeText, shiftTypeValue,
    currentSessionGeneration: () => 0,
    document: { hidden: false, addEventListener() {}, removeEventListener() {} }
  }
  return new Function(...Object.keys(dependencies), ...parameters, source).bind(null, ...Object.values(dependencies))
}
