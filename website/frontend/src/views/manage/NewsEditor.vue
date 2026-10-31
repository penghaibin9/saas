<template>
  <section class="editor">
    <header><div><p>官网新闻 / 内容撰写</p><h2>{{ article?.revisionId ? '编辑私有修订稿' : article?.id ? '继续编辑新闻' : '撰写新闻' }}</h2></div><button type="button" @click="cancel" :disabled="busy">返回文章</button></header>
    <p class="notice">保存后仍是内部稿件。摘要、正文及来源通过校验，并由发布人员审核确认后，才会出现在官网。</p>
    <form ref="editorForm" @submit.prevent="save('saved')">
      <fieldset class="editor-fields" aria-label="新闻编辑内容" :disabled="busy" style="border:0;padding:0;margin:0;min-width:0">
      <label>新闻标题<input v-model="form.title" maxlength="240" required placeholder="填写清楚、具体的新闻标题"></label>
      <div class="two-columns"><label>新闻分类<select v-model="form.category"><option v-for="item in categories" :key="item.value" :value="item.value">{{ item.label }}</option></select></label><label>内容类型<select v-model="form.contentKind"><option value="original">原创内容</option><option value="product-update">产品更新</option><option value="summary">来源摘要</option></select></label></div>
      <label>摘要<textarea v-model="form.summary" rows="3" maxlength="600" placeholder="概括事件、变化及对读者的意义"></textarea><small>发布前需填写 20 至 600 个字符；未写完也可以先保存。</small></label>
      <label for="news-body">新闻正文</label><div class="format-toolbar" role="group" aria-label="正文格式工具"><button v-for="item in formats" :key="item.key" type="button" :disabled="busy" @click="applyFormat(item.key)">{{ item.label }}</button></div><textarea id="news-body" ref="bodyInput" v-model="bodyText" rows="18" maxlength="50000" placeholder="输入新闻正文，按段落换行。" aria-describedby="news-body-help"></textarea><small id="news-body-help">选中文字后使用格式工具。已写 {{ form.body.length }} 个字符；可先保存，再查看实际排版。保留或移动配图标记即可调整位置，新增配图请保存后添加。</small>
      <h3 class="metadata-title">稿件归属与相关产品</h3>
      <div class="two-columns"><label>内容来源<select v-model="form.sourceType"><option value="original">原创</option><option value="licensed-repost">有授权转载</option><option v-if="form.sourceType === 'unverified'" value="unverified">原有内容，待核对</option></select></label><label>作者／原发布方<input v-model.trim="form.authorName" maxlength="120" placeholder="填写真实责任主体"></label></div>
      <label>负责编辑<input v-model.trim="form.editorName" maxlength="120" placeholder="对稿件事实与使用依据负责的编辑"></label>
      <fieldset><legend>关联产品</legend><label v-for="product in products" :key="product.key" class="checkbox"><input type="checkbox" v-model="form.relatedProducts" :value="product.key">{{ product.name }}</label><small>从已确认公开资料的目录选择，可在文章中进入产品并预约演示。</small></fieldset>
      <section class="sources"><header><div><h3>核验来源</h3><p>填写原始发布机构及公开地址，供审核和读者查证。来源尚未写完也可保存。</p></div><button type="button" :disabled="form.sources.length >= 12" @click="form.sources.push({title:'',url:''})">添加来源</button></header><p v-if="!form.sources.length">尚未添加来源。发布前需补齐至少一条可核验来源。</p><div v-for="(source,index) in form.sources" :key="index" class="source"><label>来源名称<input v-model="source.title" maxlength="240"></label><label>原文地址<input v-model.trim="source.url" type="url" maxlength="1800" placeholder="https://"></label><button type="button" @click="form.sources.splice(index,1)">移除此来源</button></div></section>
      <section class="sources"><h3>正文与配图使用依据</h3><label>依据说明<textarea v-model="form.rightsBasis" rows="2" maxlength="1000" placeholder="原创责任，或可核验的转载授权依据"></textarea></label><label>获准使用范围<textarea v-model="form.rightsScope" rows="2" maxlength="1000" placeholder="说明正文、图片的使用方式、渠道和期限"></textarea></label><label v-if="form.sourceType === 'licensed-repost'">授权凭证说明（仅后台可见）<textarea v-model="form.rightsEvidence" rows="3" maxlength="12000" placeholder="授权方、授权记录、核验方式；不要填写密码或个人敏感信息"></textarea></label><label>授权到期日期（无期限可留空）<input v-model="expiryDate" type="date"></label></section>
      <label class="checkbox"><input v-model="form.aiAssisted" type="checkbox">本稿使用了人工智能辅助整理</label>
      <p v-if="error" role="alert" class="error">{{ error }}</p>
      <footer><span>保存为内部稿件，公开前须审核。</span><div class="save-actions"><button type="button" :disabled="busy || !ready" @click="save('preview')">保存并预览</button><button v-if="allowMedia" type="button" :disabled="busy || !ready" @click="save('media')">保存并配图</button><button type="submit" class="primary" :disabled="busy || !ready">{{ busy ? '正在保存…' : '保存草稿' }}</button></div></footer>
      </fieldset>
    </form>
  </section>
</template>
<script setup>
import { reactive, ref, computed, onMounted, nextTick } from 'vue'
import { websiteNewsApi as api } from '@/services/websiteNews.api.js'
import { systemConfirm } from '@/services/systemDialog.js'
import { formatNewsSelection, newsPictureTokens, pictureText } from '@/services/newsFormatting.js'
const props = defineProps({ article: { type: Object, default: null }, allowMedia: Boolean })
const emit = defineEmits(['saved','cancel'])
const form = reactive({title:props.article?.title || '', summary:props.article?.summary || '', body:props.article?.body || '', category:props.article?.category || 'company', contentKind:props.article?.contentKind || 'original', aiAssisted:props.article?.aiAssisted || false, sources:(props.article?.sources || []).map(source => ({...source}))})
const requestId = crypto.randomUUID()
Object.assign(form,{sourceType:props.article?.sourceType || 'original',authorName:props.article?.authorName || '',editorName:props.article?.editorName || '',rightsBasis:props.article?.rightsBasis || '',rightsScope:props.article?.rightsScope || '',rightsEvidence:props.article?.rightsEvidence || '',relatedProducts:[...(props.article?.relatedProducts || [])]})
const expiryDate=ref(props.article?.rightsValidUntil?.slice(0,10) || '')
const initial=JSON.stringify({...form,expiryDate:expiryDate.value})
const categories = ref([]),products=ref([]), ready = ref(false), busy = ref(false), error = ref('')
const pictureTokens = newsPictureTokens(form.body)
const bodyText = computed({get:()=>pictureText(form.body,pictureTokens),set:value=>{const body=pictureText(value,pictureTokens,true);if(body.length>50000){error.value='正文已到长度上限，请精简后再保存。';return}form.body=body}})
const editorForm = ref(null), bodyInput = ref(null)
const formats = [{key:'heading',label:'小标题'},{key:'bold',label:'重点'},{key:'list',label:'列表'},{key:'quote',label:'引用'}]
function applyFormat(kind) {
  const input=bodyInput.value
  let result
  try { result=formatNewsSelection(bodyText.value,input.selectionStart,input.selectionEnd,kind) } catch(e) { error.value=e.message;return }
  if(pictureText(result.text,pictureTokens,true).length>50000){error.value='正文已到长度上限，请精简后再添加格式。';return}
  bodyText.value=result.text
  nextTick(()=>{input.focus();input.setSelectionRange(result.start,result.end)})
}
onMounted(async () => { try { const result=await Promise.all([api.categories(),api.products()]);categories.value=result[0].items;products.value=result[1].items; ready.value = true } catch(e) { error.value = e.message } })
async function cancel() { if (JSON.stringify({...form,expiryDate:expiryDate.value}) !== initial && !await systemConfirm({title:'放弃本次未保存的修改？',message:'已保存的内容会保留，本次输入尚未保存。',confirmText:'放弃修改',cancelText:'继续编辑'})) return; emit('cancel') }
async function save(action = 'saved') {
  if (busy.value || !ready.value || !editorForm.value.reportValidity()) return
  busy.value = true; error.value = ''
  try {
    const body={...form,rightsValidUntil:expiryDate.value ? new Date(`${expiryDate.value}T23:59:59+08:00`).toISOString() : null}
    const result = props.article?.id ? await api.edit(props.article.id, {...body, expectedVersion:props.article.packageVersion,revisionId:props.article.revisionId || null}) : await api.create({...body, requestId})
    emit('saved', result, { action })
  } catch(e) { error.value = e.message } finally { busy.value = false }
}
</script>
<style scoped>
.editor button{font:inherit;cursor:pointer;border:1px solid #c6d3e2;border-radius:8px;padding:10px 18px;background:white;color:#183857;min-height:44px}.editor button:disabled{opacity:.6;cursor:not-allowed}
.editor{max-width:1060px;margin:24px auto;background:#fff;border:1px solid #d8e3ef;border-radius:14px;padding:32px}.editor header,.editor footer{display:flex;align-items:center;justify-content:space-between;gap:20px}.editor h2,.editor h3{margin:4px 0}.editor p,.editor small,.editor footer span{color:#62768e;line-height:1.7}.editor label{display:block;margin:22px 0;font-weight:600}.editor input:not([type=checkbox]),.editor textarea,.editor select{display:block;width:100%;margin-top:8px;padding:12px;border:1px solid #b9c8da;border-radius:7px;font:inherit;line-height:1.6}.editor small{display:block;margin-top:6px;font-weight:400}.two-columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}.notice,.sources{padding:18px 22px;border-radius:10px;background:#f3f7fc}.sources header p{margin:4px 0}.source{display:grid;grid-template-columns:1fr 2fr auto;gap:16px;align-items:center}.checkbox{display:flex!important;gap:10px;align-items:center;font-weight:400!important}.checkbox input{width:18px;height:18px}.editor .error{color:#a62634}.editor .primary{color:white;background:#1763dc}.editor footer{border-top:1px solid #e0e8f2;padding-top:24px}@media(max-width:680px){.editor{margin:16px 12px;padding:20px}.two-columns,.source{grid-template-columns:1fr;gap:0}.editor header,.editor footer{align-items:flex-start;flex-direction:column}.sources{padding:14px}.editor textarea{min-height:120px}}
</style>

<style scoped>
.save-actions,.format-toolbar{display:flex;flex-wrap:wrap;gap:8px}.save-actions{justify-content:flex-end}.save-actions button{padding:10px 12px}.format-toolbar{margin-bottom:8px}.format-toolbar button{padding:8px 14px}.editor footer{position:sticky;bottom:0;background:#fff;z-index:5;padding-bottom:12px}.editor :focus-visible{outline:3px solid #85b1f5;outline-offset:3px}@media(max-width:680px){.save-actions{width:100%;justify-content:stretch}.save-actions button{flex:1;padding:10px 8px;font-size:13px}.format-toolbar{gap:6px}.format-toolbar button{flex:1;padding:8px}}
</style>

<style scoped>fieldset{border:1px solid #dce5ef;padding:12px 20px;border-radius:8px}fieldset .checkbox{display:inline-flex!important;margin:10px 24px 10px 0}.editor input,.editor textarea{box-sizing:border-box}legend{padding:0 8px;font-weight:600}</style>
