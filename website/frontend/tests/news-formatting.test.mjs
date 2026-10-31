import test from 'node:test'
import assert from 'node:assert/strict'
import { formatNewsSelection as format, newsPictureTokens, pictureText } from '../src/services/newsFormatting.js'

test('format buttons retain surrounding text and toggle selected blocks', () => {
  const text = '前段\n学生事项\n教师事项\n后段'
  const result = format(text, 3, 13, 'list')
  assert.equal(result.text, '前段\n- 学生事项\n- 教师事项\n后段')
  assert.equal(format(result.text, result.start, result.end, 'list').text, text)
  assert.equal(format('第一行\n第二行', 0, 4, 'heading').text, '# 第一行\n第二行')
  assert.equal(format('\n正文', 0, 0, 'heading').text, '# 小标题\n正文')
  assert.equal(format('甲重点乙', 1, 3, 'bold').text, '甲**重点**乙')
  assert.equal(format('甲**重点**乙', 1, 7, 'bold').text, '甲重点乙')
  assert.equal(format('原文', 0, 2, 'quote').text, '> 原文')
  assert.throws(() => format('原文', 0, 2, 'unknown'))
  const picture='![配图](assets/example.webp)'
  assert.equal(format('正文\n'+picture,0,30,'list').text,'- 正文\n'+picture)
  assert.throws(() => format(picture,3,8,'bold'),/配图/)
})

test('business picture markers hide storage paths and round-trip exact positions', () => {
  const body='第一段\n\n![教务界面](assets/abcdef.webp)\n\n第二段\n\n![实习界面](assets/123456.webp)'
  const entries=newsPictureTokens(body),display=pictureText(body,entries)
  assert.ok(display.includes('【配图1：教务界面】'))
  assert.ok(!display.includes('assets/'))
  assert.equal(pictureText(display,entries,true),body)
  const reordered=display.replace('【配图1：教务界面】','')+'\n【配图1：教务界面】'
  assert.ok(pictureText(reordered,entries,true).endsWith('![教务界面](assets/abcdef.webp)'))
  assert.ok(format(display,0,display.length,'list').text.includes('\n【配图1：教务界面】'))
  assert.throws(()=>format('【配图1：教务界面】',0,12,'bold'),/配图/)
  const collision='正文示例【配图1：教务界面】\n![教务界面](assets/a.webp)'
  const mapped=newsPictureTokens(collision)
  assert.equal(mapped[0].token,'【配图2：教务界面】')
  assert.equal(pictureText(pictureText(collision,mapped),mapped,true),collision)
})
