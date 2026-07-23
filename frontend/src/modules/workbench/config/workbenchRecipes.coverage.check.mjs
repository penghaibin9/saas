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
    }
  }
}

assert(resolveRecipe('PLATFORM_SUPER_ADMIN') === RECIPES.DEFAULT, 'platform super must DEFAULT')
assert(resolveRecipe('UNKNOWN_ROLE_XYZ') === RECIPES.DEFAULT, 'unknown must DEFAULT')
assert(resolveRecipe('STUDENT_AFFAIRS').template === 'T5', 'STUDENT_AFFAIRS alias T5')
assert(resolveRecipe('GD_COLLEGE_ADMIN').template === 'T8', 'GD_COLLEGE_ADMIN alias T8')
assert(resolveRecipe('GD_MAJOR_ADMIN').template === 'T8', 'GD_MAJOR_ADMIN alias T8')

// 无真实待办写入的角色不得挂分类假磁贴
for (const role of ['ACADEMIC_TEACHER', 'YOUTH_LEAGUE', 'DORM_MANAGER', 'EMPLOYMENT_TEACHER', 'GD_DEFENSE_EXPERT', 'LEADER']) {
  assert((resolveRecipe(role).typeCues || []).length === 0, `${role} must not invent typeCues`)
}

console.log('workbenchRecipes coverage OK:', templates.join(','))
