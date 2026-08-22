import { RECIPES, TODO_TYPE_ROUTES } from './workbenchRecipes'

const FORMAL_REVIEW_ROUTE = '/admin/graduation/review-tasks?caseType=FORMAL_REVIEW'
const FORMAL_REVIEW_TODO = 'GD_FORMAL_REVIEW'

export function installGraduationW76Workbench() {
  TODO_TYPE_ROUTES[FORMAL_REVIEW_TODO] = FORMAL_REVIEW_ROUTE

  const recipe = RECIPES.GD_REVIEWER
  if (!recipe) return

  if (!Array.isArray(recipe.typeCues)) recipe.typeCues = []
  if (!recipe.typeCues.some((item) => item?.key === FORMAL_REVIEW_TODO)) {
    recipe.typeCues.push({
      key: FORMAL_REVIEW_TODO,
      title: '正式评阅待办',
      source: `todoType.${FORMAL_REVIEW_TODO}`,
      accent: 'warning',
      to: `${FORMAL_REVIEW_ROUTE}&todoType=${encodeURIComponent(FORMAL_REVIEW_TODO)}`
    })
  }

  if (!Array.isArray(recipe.quickLinks)) recipe.quickLinks = []
  const existing = recipe.quickLinks.find((item) => item?.label === '教师评阅')
  if (existing) existing.to = FORMAL_REVIEW_ROUTE
  else recipe.quickLinks.push({ label: '教师评阅', to: FORMAL_REVIEW_ROUTE })
}

export { FORMAL_REVIEW_ROUTE, FORMAL_REVIEW_TODO }
