import assert from 'node:assert/strict'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { baseParse, NodeTypes } from '@vue/compiler-dom'
import { parseExpression } from '@babel/parser'

const COPY_ATTRIBUTES = new Set(['title', 'aria-label', 'placeholder', 'alt', 'label', 'description', 'subtitle', 'text'])

/** Inspect template copy, not identifiers used for permission/version bindings.
 * This is source-level copy screening; actual visibility and permissions still
 * require the browser and business-command tests. Closed evidence details are
 * intentionally secondary, while their summary remains part of the main UI.
 */
export function graduationTemplateCopy(source) {
  const parsed = parseSfc(source)
  assert.equal(parsed.errors.length, 0, 'the Vue SFC must parse before inspecting copy')
  assert.ok(parsed.descriptor.template, 'a real Vue template is required')
  const ast = baseParse(parsed.descriptor.template.content)
  const text = []
  const directOutputs = []

  function expressionCopy(expression, output = false) {
    const code = String(expression || '').trim()
    if (!code) return
    const expr = parseExpression(code)
    if (output && ['Identifier', 'MemberExpression', 'OptionalMemberExpression'].includes(expr.type)) {
      directOutputs.push(code)
    }
    function walk(value) {
      if (!value || typeof value !== 'object') return
      if (value.type === 'StringLiteral') { text.push(value.value); return }
      if (value.type === 'TemplateElement') { text.push(value.value.cooked ?? value.value.raw); return }
      for (const [key, child] of Object.entries(value)) {
        if (['loc', 'comments', 'leadingComments', 'trailingComments', 'tokens'].includes(key)) continue
        if (Array.isArray(child)) child.forEach(walk)
        else if (child && typeof child === 'object') walk(child)
      }
    }
    walk(expr)
  }

  function visit(node) {
    if (node.type === NodeTypes.TEXT) { text.push(node.content); return }
    if (node.type === NodeTypes.INTERPOLATION) { expressionCopy(node.content.content, true); return }
    if (node.type === NodeTypes.COMMENT) return
    if (node.type === NodeTypes.ELEMENT) {
      for (const prop of node.props) {
        if (prop.type === NodeTypes.ATTRIBUTE && COPY_ATTRIBUTES.has(prop.name)) text.push(prop.value?.content || '')
        if (prop.type === NodeTypes.DIRECTIVE && prop.name === 'bind'
          && prop.arg?.isStatic && COPY_ATTRIBUTES.has(prop.arg.content)) expressionCopy(prop.exp?.content)
      }
      const opensEvidence = node.props.some((prop) =>
        (prop.type === NodeTypes.ATTRIBUTE && prop.name === 'open')
        || (prop.type === NodeTypes.DIRECTIVE && prop.arg?.content === 'open')
      )
      if (node.tag === 'details' && !opensEvidence) {
        node.children.filter((child) => child.type === NodeTypes.ELEMENT && child.tag === 'summary').forEach(visit)
        return
      }
    }
    for (const child of node.children || []) visit(child)
  }
  visit(ast)
  return { text: text.join(' ').replace(/\s+/g, ' ').trim(), directOutputs }
}
