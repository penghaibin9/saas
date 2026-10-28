<template>
  <view class="mobile-page mobile-student page-wrap ins">
    <MobileNavBar title="实习保险" show-back :fallback-url="'/pages/student-internship/index' + (context.batchId ? '?batchId=' + encodeURIComponent(context.batchId) : '')" />
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <MobileInlineAlert v-if="historyMode" type="info" description="历史实习保险仅供查阅。" />
        <MobileInlineAlert v-else-if="info?.canRenew" type="warning" title="请更新保险保障" :description="info.coverageReason || '请补充有效保单'" />
        <MobileInlineAlert v-else-if="info?.status === 'REJECTED'" type="warning" title="保险材料已驳回" :description="info.verifyComment || '请核对保单和凭证后重新提交。'" />
        <MobileInlineAlert v-if="submitError" type="warning" title="本次操作未完成" :description="submitError" />
        <button v-if="conflict" class="mobile-control btn btn-ghost" :disabled="submitting || uploading || conflictReading" @click="rereadConflict">读取最新保单并保留填写内容</button>
        <view v-if="conflict && latestInfo" class="card stack">
          <text>最新第{{ latestInfo.version }}版 · {{ latestInfo.statusLabel || '状态待核对' }}</text>
          <text>{{ latestInfo.insurerName }} · {{ latestInfo.policyNo }}</text>
          <text>{{ latestInfo.effectiveDate }} 至 {{ latestInfo.expiryDate }}</text>
          <text>{{ latestInfo.verifyComment }}</text>
          <button class="mobile-control btn btn-ghost" :disabled="conflictReading" @click="adoptLatestInsurance">已核对最新保单，保留填写内容继续</button>
        </view>
        <view v-if="readonly" class="card stack ins__result"><view class="row-between"><text class="card-title">保险核验结果</text><MobileStatusTag :label="info?.statusLabel || '未提交'" :type="statusTone" /></view><text>承保单位：{{ form.insurerName || '未登记' }}</text><text>保单号：{{ form.policyNo || '未登记' }}</text><text>险种：{{ form.coverageType || '未登记' }}</text><text>保障期间：{{ form.effectiveDate || '未登记' }} 至 {{ form.expiryDate || '未登记' }}</text><text v-if="info?.verifyComment">核验意见：{{ info.verifyComment }}</text><text v-if="!historyMode" class="ins__version">学校允许续保时，可更新保障。</text><button v-if="attachmentReady" class="mobile-control btn btn-primary" @click="previewAttachment">查看保险凭证</button><button v-if="attachment" class="mobile-control btn btn-ghost" :aria-expanded="scanDetailsOpen" @click="scanDetailsOpen = !scanDetailsOpen">{{ scanDetailsOpen ? '收起安全检查详情' : '安全检查详情' }}</button><view v-if="scanDetailsOpen" class="stack"><text>{{ attachment?.statusText }}</text><button class="mobile-control btn btn-ghost" :disabled="scanning || uploading || submitting" @click="refreshAttachment">{{ scanning ? '读取中…' : '重新读取扫描结果' }}</button></view></view>
        <view v-else class="card stack">
          <view class="row-between">
            <text class="card-title">保险信息</text>
            <MobileStatusTag :label="info?.statusLabel || '未提交'" :type="statusTone" />
          </view>
          <text v-if="info?.version" class="ins__version">记录版本 {{ info.version }}</text>
          <view class="ins__field"><text class="ins__label">承保单位 *</text><input v-model.trim="form.insurerName" class="mobile-input ins__input" :disabled="readonly" placeholder="如：人保财险" /></view>
          <view class="ins__field"><text class="ins__label">保单号 *</text><input v-model.trim="form.policyNo" class="mobile-input ins__input" :disabled="readonly" placeholder="保险公司出具的保单编号" /></view>
          <view class="ins__field"><text class="ins__label">险种</text><input v-model.trim="form.coverageType" class="mobile-input ins__input" :disabled="readonly" placeholder="如：实习责任险" /></view>
          <view class="ins__field"><text class="ins__label">生效日期 *</text><picker class="mobile-picker" mode="date" :value="form.effectiveDate" :disabled="readonly" @change="form.effectiveDate = $event.detail.value"><view class="ins__date">{{ form.effectiveDate || '请选择生效日期' }}</view></picker></view>
          <view class="ins__field"><text class="ins__label">到期日期 *</text><picker class="mobile-picker" mode="date" :value="form.expiryDate" :disabled="readonly" @change="form.expiryDate = $event.detail.value"><view class="ins__date">{{ form.expiryDate || '请选择到期日期' }}</view></picker></view>
          <view class="ins__file">
            <view class="flex-1">
              <text class="ins__label">保险凭证 *</text>
              <text class="ins__file-name">{{ fileName || (form.fileId ? '已上传保险凭证' : '请上传保单或保险证明') }}</text>
            </view>
            <button v-if="!readonly" class="mobile-control btn btn-ghost" :disabled="uploading" @click="pickFile">{{ uploading ? '上传中…' : (form.fileId ? '重新上传' : '选择文件') }}</button>
          </view>
          <view v-if="attachment" class="ins__scan">
            <text>{{ attachment.statusText }}</text>
            <button class="mobile-control btn btn-ghost" :disabled="scanning || uploading || submitting" @click="refreshAttachment">{{ scanning ? '读取中…' : '读取扫描结果' }}</button>
            <button v-if="attachment.readyForBusiness" class="mobile-control btn btn-ghost" @click="previewAttachment">查看凭证</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="pageState === 'ready' && !readonly">
      <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || uploading || scanning || conflict || !attachmentReady" @click="submit">
        {{ submitting ? '提交中…' : info?.canRenew ? '更新保单并提交核验' : (info?.status === 'REJECTED' ? '修改并重新提交' : '提交保险信息') }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import fileSdk from '@/services/fileSdk'
import { normalizeFileReadiness, refreshFileReadiness } from '@/services/fileReadiness.mjs'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      scanDetailsOpen:false, pageState: 'loading', submitting: false, uploading: false, conflict: false, submitError: '', requestSeq: 0,
      generation:currentSessionGeneration(), hidden:false, requestedBatchId:'', context:{batchId:'',internshipId:''}, attachment:null, scanning:false, attachmentSequence:0,
      info: null, historyMode: false, fileName: '',
      latestInfo: null, conflictReading: false,
      form: { insurerName: '', policyNo: '', coverageType: '', effectiveDate: '', expiryDate: '', fileId: '' }
    }
  },
  computed: {
    attachmentReady() { return this.attachment?.readyForBusiness === true && String(this.attachment.fileId)===String(this.form.fileId) },
    readonly() { return this.historyMode || (this.info?.status === 'VERIFIED' && this.info.canRenew !== true) },
    statusTone() {
      if (this.info?.canRenew) return 'warning'
      if (this.info?.status === 'VERIFIED') return 'success'
      if (this.info?.status === 'REJECTED') return 'danger'
      return 'warning'
    }
  },
  onLoad(options={}) { this.requestedBatchId=String(options.batchId || '');this.load() },
  onShow() {const wasHidden=this.hidden;this.hidden=false;if(this.generation!==currentSessionGeneration()){this.info=null;this.attachment=null;this.conflict=false;this.latestInfo=null;this.form={insurerName:'',policyNo:'',coverageType:'',effectiveDate:'',expiryDate:'',fileId:''};this.load()}else if(wasHidden && this.pageState==='loading')return this.load()},
  onHide() { if(this.submitting){this.conflict=true;this.latestInfo=null;this.submitError='上次提交结果尚未确认，填写内容保留，请读取原单核对'};this.hidden=true;this.requestSeq++;this.conflictReading=false;this.attachmentSequence++;this.scanning=false;this.submitting=false;this.uploading=false },
  onUnload() { this.hidden=true;this.requestSeq++;this.attachmentSequence++ },
  methods: {
    current(seq,generation,allowHidden=false) { return seq===this.requestSeq && generation===currentSessionGeneration() && (!this.hidden || allowHidden) },
    async refreshAttachment() {
      if(!this.form.fileId || this.scanning) return
      const seq=this.requestSeq,generation=this.generation,attachment=this.attachment,sequence=++this.attachmentSequence
      const current=()=>this.current(seq,generation) && sequence===this.attachmentSequence && attachment===this.attachment
      this.scanning=true;this.submitError=''
      try {const updated=await refreshFileReadiness([{...attachment,fileId:this.form.fileId}],id=>fileSdk.metadata(id),current);if(updated) this.attachment=updated[0]}
      catch {if(current()) {this.attachment={...attachment,readyForBusiness:false,statusText:'扫描结果未能读取，凭证已保留'};this.submitError='扫描结果读取失败，填写内容和凭证已保留，请重新读取'}}
      finally {if(sequence===this.attachmentSequence) this.scanning=false}
    },
    async previewAttachment() {
      if(!this.attachmentReady || this.hidden || this.generation!==currentSessionGeneration()) return
      try {await fileSdk.open(String(this.form.fileId))}catch {this.submitError='保险凭证暂时无法打开，请重新读取扫描结果'}
    },
    async load() {
      if (this.conflict) return this.rereadConflict()
      const seq = ++this.requestSeq
      const generation=this.generation=currentSessionGeneration()
      this.attachmentSequence++;this.attachment=null;this.scanning=false
      this.uploading=false;this.submitting=false
      this.pageState = 'loading'
      try {
        const dashboard=await studentApi.getInternship(this.requestedBatchId)
        if(!this.current(seq,generation)) return
        this.context={batchId:String(dashboard?.batchId || ''),internshipId:String(dashboard?.recordId || '')}
        const info=await studentApi.getInternshipInsurance(this.context.batchId,this.context.internshipId)
        if (!this.current(seq,generation)) return
        this.info = info || { status: 'NOT_SUBMITTED', statusLabel: '未提交', version: 0 }
        this.conflict = false; this.submitError = ''
        this.historyMode = !!dashboard?.historyMode
        this.form = {
          insurerName: info?.insurerName || '', policyNo: info?.policyNo || '',
          coverageType: info?.coverageType || '', effectiveDate: info?.effectiveDate || '',
          expiryDate: info?.expiryDate || '', fileId: info?.fileId || ''
        }
        this.fileName = info?.fileId ? '已上传保险凭证' : ''
        if(info?.fileId) {this.attachment=normalizeFileReadiness({fileId:String(info.fileId)});await this.refreshAttachment()}
        if(!this.current(seq,generation)) return
        this.pageState = 'ready'
      } catch (e) { if (this.current(seq,generation)) this.pageState = 'error' }
    },
    async pickFile() {
      if (this.uploading || this.submitting || this.readonly || this.hidden || this.generation!==currentSessionGeneration()) return
      const seq = this.requestSeq
      const generation=this.generation
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!file || !this.current(seq,generation,true)) return
        const result = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_INSURANCE' })
        if (!this.current(seq,generation,true)) return
        if (!result?.fileId) throw new Error('上传结果不完整，原凭证已保留')
        this.form.fileId = result.fileId
        this.attachmentSequence++;this.attachment=normalizeFileReadiness(result)
        this.fileName = result.fileName || file.name || '保险凭证'
        toast(this.attachmentReady?'保险凭证安全可用':'文件已接收，请读取安全扫描结果')
      } catch (e) { if (this.current(seq,generation,true)) this.submitError = '文件上传未完成，原凭证已保留，请重试' }
      finally {if(seq===this.requestSeq)this.uploading = false}
    },
    async submit() {
      if (this.submitting || this.uploading || this.scanning || this.readonly || this.conflict || this.hidden || this.generation!==currentSessionGeneration()) return
      if (this.info?.id && !Number.isInteger(this.info.version)) { this.submitError = '保单版本缺失，请重新读取后再提交'; return }
      if (!this.form.insurerName || !this.form.policyNo) return toast('请填写承保单位和保单号')
      if (!this.form.effectiveDate || !this.form.expiryDate) return toast('请填写保险生效和到期日期')
      if (!this.form.fileId) return toast('请上传保险凭证')
      if(!this.attachmentReady) {this.submitError='凭证尚未安全可用，填写内容已保留，请读取扫描结果或重新上传';return}
      const seq = this.requestSeq
      const generation=this.generation
      this.submitError = ''
      this.submitting = true
      try {
        await studentApi.submitInternshipInsurance({
          ...this.form,
          ...this.context,
          ...(this.info?.id ? { expectedVersion: this.info.version } : {})
        })
        if (!this.current(seq,generation)) return
        toast('已提交，等待学校核验')
        await this.load()
      } catch (e) {
        if (!this.current(seq,generation)) return
        this.conflict = normalizeError(e).kind === 'conflict'
        this.latestInfo = null
        this.submitError = this.conflict ? '保单已变化，原版本和填写内容已保留。读取最新保单核对后再明确采用。' : normalizeError(e).text
      } finally {if(seq===this.requestSeq)this.submitting = false}
    },
    async rereadConflict() {
      if (!this.conflict || this.conflictReading || this.hidden || this.generation !== currentSessionGeneration()) return
      const seq = ++this.requestSeq, generation = this.generation, context = this.context, original = this.info
      const current = () => this.current(seq,generation) && this.conflict && context === this.context && original === this.info
      this.conflictReading = true; this.latestInfo = null
      try {
        const dashboard = await studentApi.getInternship(context.batchId)
        if (!current()) return
        if (dashboard?.historyMode || String(dashboard?.batchId) !== context.batchId || String(dashboard?.recordId) !== context.internshipId) throw new Error('当前实习记录已变化或转为历史只读，填写内容保留')
        const latest = await studentApi.getInternshipInsurance(context.batchId,context.internshipId)
        if (!current()) return
        if (!latest || !Number.isInteger(latest.version) || latest.version < 0 ||
          (original?.id ? String(latest.id) !== String(original.id) : latest.id ? String(latest.internshipId) !== context.internshipId : latest.status !== 'NOT_SUBMITTED' || latest.version !== 0)) throw new Error('保单原单尚未确认，不能自动采用另一份保单')
        this.latestInfo = latest; this.submitError = '请核对最新保单状态和内容，明确采用后仍保留当前输入及凭证。'
      } catch (e) { if (current()) this.submitError = e?.message || '读取失败，填写内容已保留' }
      finally { if (seq === this.requestSeq) this.conflictReading = false }
    },
    adoptLatestInsurance() {
      const latest = this.latestInfo
      if (!this.conflict || !latest || this.conflictReading || this.submitting || this.uploading || this.hidden || this.generation !== currentSessionGeneration()) return
      if (latest.status === 'VERIFIED' && latest.canRenew !== true) { this.submitError = '保单已核验，无需覆盖；当前输入和凭证已保留'; return }
      this.info = latest; this.conflict = false; this.latestInfo = null; this.submitError = ''
    }
  }
}
</script>

<style scoped>
.ins__version { display:block;margin-top:6px;font-size:var(--font-size-base);color:var(--text-tertiary); }
.ins__field { margin-bottom:12px; }
.ins__label { display:block;font-size:var(--font-size-base);margin-bottom:4px; }
.ins__input,.ins__date { height:44px;min-height:44px;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);padding:0 12px;font-size:var(--font-size-base); }.ins__date{display:flex;align-items:center;color:var(--text-primary)}
.ins__file { display:flex;align-items:center;gap:var(--space-3);padding-top:4px; }
.ins__file-name { display:block;font-size:var(--font-size-base);color:var(--text-tertiary); }
.ins__scan { display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px;font-size:var(--font-size-base); }
</style>
