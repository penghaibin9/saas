/**
 * 工作台十二模板角色覆盖单元核验（纯前端，不依赖 DOM）。
 * 锁住：T1–T12 每个模板至少有一个角色；resolveRecipe 不臆造未知角色业务卡。
 */
import { resolveRecipe, TEMPLATE_ROLE_COVERAGE, RECIPES } from './workbenchRecipes.js'

function assert(cond, msg) {
  if (!cond) throw new Error(msg)
}

const templates = Object.keys(TEMPLATE_ROLE_COVERAGE)
assert(templates.length === 12, `expected 12 templates, got ${templates.length}`)

for (const [tpl, roles] of Object.entries(TEMPLATE_ROLE_COVERAGE)) {
  assert(roles.length > 0, `${tpl} has no roles`)
  for (const role of roles) {
    const r = resolveRecipe(role)
    assert(r && r.label, `${role} missing recipe`)
    assert(Array.isArray(r.summaryCues) && r.summaryCues.length > 0, `${role} missing summaryCues`)
    assert(Array.isArray(r.quickLinks) && r.quickLinks.length > 0, `${role} missing quickLinks`)
    assert(r.template === tpl || (tpl === 'T5' && r.template === 'T5'), `${role} template=${r.template} want ${tpl}`)
    for (const cue of [...(r.typeCues || []), ...(r.statsCues || []), ...r.summaryCues]) {
      assert(cue.to && String(cue.to).startsWith('/'), `${role} cue ${cue.key} missing drill path`)
      // 下钻须带筛选语义（query 或业务已筛选路径）；纯根路径禁止作为分类磁贴
      if (cue.source && String(cue.source).startsWith('todoType.')) {
        assert(String(cue.to).includes('?'), `${role} typeCue ${cue.key} must carry filter query`)
      }
    }
  }
}

assert(resolveRecipe('PLATFORM_SUPER_ADMIN') === RECIPES.DEFAULT, 'platform super must DEFAULT')
assert(resolveRecipe('UNKNOWN_ROLE_XYZ') === RECIPES.DEFAULT, 'unknown must DEFAULT')
assert(resolveRecipe('STUDENT_AFFAIRS').template === 'T5', 'STUDENT_AFFAIRS alias T5')
assert(resolveRecipe('GD_COLLEGE_ADMIN').template === 'T8', 'GD_COLLEGE_ADMIN alias T8')
assert(resolveRecipe('GD_MAJOR_ADMIN').template === 'T8', 'GD_MAJOR_ADMIN alias T8')

// 已有真实 UnifiedTodo 写入的角色必须有分类磁贴
assert((resolveRecipe('ACADEMIC_TEACHER').typeCues || []).some((c) => c.key === 'AA_GRADE_ENTRY'), 'T1 needs AA_GRADE_ENTRY')
assert((resolveRecipe('DORM_MANAGER').typeCues || []).length >= 2, 'DORM_MANAGER needs transfer/exception cues')
assert((resolveRecipe('EMPLOYMENT_TEACHER').typeCues || []).some((c) => c.key === 'EMPLOYMENT_FOLLOWUP'), 'T11 needs followup cue')
assert((resolveRecipe('GD_DEFENSE_EXPERT').typeCues || []).some((c) => c.key === 'GD_DEFENSE_SCORE'), 'expert needs defense score cue')
// 团学无审批节点待办写入：诚实空 typeCues
assert((resolveRecipe('YOUTH_LEAGUE').typeCues || []).length === 0, 'YOUTH_LEAGUE must stay honest empty typeCues')
assert((resolveRecipe('LEADER').typeCues || []).length === 0, 'LEADER must not invent typeCues')
assert(resolveRecipe('ACADEMIC_TEACHER').showSchedule === true, 'T1 must enable B8 schedule')
assert(resolveRecipe('ACADEMIC_ADMIN').showSchedule === true, 'T2 must enable B8 schedule')

console.log('workbenchRecipes coverage OK:', templates.join(','))
