import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { initPreContext, preCss } from '@dcloudio/uni-cli-shared/dist/preprocess/index.js'
import postcss from 'postcss'

const source = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')

for (const platform of ['mp-weixin', 'h5']) {
  test(`${platform} theme tokens use a supported root selector`, () => {
    initPreContext(platform)
    const css = postcss.parse(preCss(source))
    const variables = new Map()
    css.walkRules(rule => {
      if (platform === 'mp-weixin') assert.equal(rule.selector.trim(), 'page')
      else assert.ok(rule.selectors.includes(':root'))
      rule.walkDecls(decl => variables.set(decl.prop, decl.value))
    })
    assert.equal(variables.get('--page-padding-mobile'), '16px')
    assert.equal(variables.get('--space-3'), '12px')
    assert.match(variables.get('--brand-gradient-teacher'), /^linear-gradient/)
  })
}
