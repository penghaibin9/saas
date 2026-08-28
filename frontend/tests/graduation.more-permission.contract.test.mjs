import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const moreView = fs.readFileSync(
  new URL('../src/modules/graduation/views/GraduationMoreView.vue', import.meta.url),
  'utf8',
)

test('graduation extension workspace only exposes panels allowed by current permission patterns', () => {
  assert.match(moreView, /v-for="t in visibleTabs"/)
  assert.match(moreView, /graduationDesign\.review\.view/)
  assert.match(moreView, /graduationDesign\.defense\.groupManage/)
  assert.match(moreView, /graduationDesign\.grade\.appealReview/)
  assert.match(moreView, /MORE_TABS\.filter\(\(item\) => matchPermission\(this\.permissionPatterns, item\.permissionKey\)\)/)
})

test('review.view alone cannot surface peer assignment controls', () => {
  assert.match(moreView, /canPeerAssign\(\)[\s\S]*graduationDesign\.review\.assign/)
  assert.match(moreView, /<template v-if="canPeerAssign" #actions>/)
  assert.match(moreView, /this\.tab === 'peer' && this\.canPeerAssign/)
  assert.match(moreView, /k === 'assignPeer' && this\.canPeerAssign/)
})

test('unauthorized panel query and direct action attempts fail closed in the page', () => {
  assert.match(moreView, /this\.tab = this\.isTabAllowed\(requested\) \? requested : fallback/)
  assert.match(moreView, /if \(!this\.isTabAllowed\(t\)\) return/)
  assert.match(moreView, /if \(!this\.isTabAllowed\(this\.tab\)\)[\s\S]*this\.rows = \[\][\s\S]*return/)
  assert.match(moreView, /if \(!this\.canManageExperts\) return toast\.error/)
  assert.match(moreView, /if \(!this\.canReviewAppeal\) return toast\.error/)
})
