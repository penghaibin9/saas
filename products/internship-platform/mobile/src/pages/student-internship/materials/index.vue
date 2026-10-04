<template>
  <view class="page-wrap">
    <MobileNavBar title="实习材料" subtitle="按学校收件要求下载模板、提交和重交" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="context.batchId">
        <MobileInlineAlert type="info" description="材料类型由学校配置。每次重交都会生成新的不可变文件版本，旧版不会覆盖；病毒扫描未通过的文件不能进入审核和归档。" />
        <MobileGlobalState v-if="!items.length" state="empty" title="当前批次暂无材料任务" description="学校发布收件要求后会显示在这里。" />
        <view v-for="item in items" :key="item.id" class="card mat">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">{{ item.materialName }}</text>
              <text class="mat__code">{{ item.isRequired ? '必交材料' : '选交材料' }}</text>
            </view>
            <MobileStatusTag :label="statusLabel(item)" :type="statusTone(item)" />
          </view>

          <text v-if="item.description" class="mat__desc">{{ item.description }}</text>
          <view class="mat__facts">
            <view><text>允许格式</text><text>{{ item.allowedFormatLabel }}</text></view>
            <view><text>文件数量</text><text>{{ item.minFiles }}～{{ item.maxFiles }} 份</text></view>
            <view><text>截止时间</text><text>{{ item.dueAt ? fmt(item.dueAt) : '未设置' }}</text></view>
            <view v-if="item.template"><text>模板版本</text><text>第{{ item.template.versionNo }}版</text></view>
          </view>

          <view v-if="item.template" class="mat__template">
            <view class="flex-1"><text class="mat__template-name">{{ item.template.fileName || '学校模板' }}</text></view>
            <button class="btn btn-ghost" :disabled="busyId === item.id" @click="downloadTemplate(item)">下载模板</button>
          </view>

          <view v-if="item.submission" class="mat__submission">
            <text class="mat__submission-title">最近一次提交 · {{ item.submission.statusLabel }}</text>
            <view v-for="file in item.submission.files" :key="file.slotNo" class="mat__file-row">
              <view class="flex-1"><text>{{ file.fileName || ('第' + file.slotNo + '份材料') }}</text><text class="mat__hash">第{{ file.versionNo }}版 · {{ file.statusText }}</text></view>
              <button class="mat__preview" @click="preview(file.fileId)">查看</button>
            </view>
            <text v-if="item.submission.reviewComment" class="mat__review">审核意见：{{ item.submission.reviewComment }}</text>
          </view>

          <view v-if="canSubmit(item)" class="mat__upload">
            <view class="row-between">
              <text class="mat__upload-title">{{ item.submission?.status === 'RETURNED' ? '按意见重新提交' : '提交材料' }}</text>
              <text class="mat__count">{{ pending(item.id).length }}/{{ item.maxFiles }}</text>
            </view>
            <view v-for="(file, index) in pending(item.id)" :key="file.fileId" class="mat__pending">
              <view class="flex-1"><text>{{ file.fileName }}</text><text class="mat__hash">{{ file.statusText }}</text></view>
              <button :disabled="!!busyId" @click="removePending(item.id, index)">移除</button>
            </view>
            <text v-if="materialErrors[String(item.id)]" class="mat__review">{{ materialErrors[String(item.id)] }}</text>
            <button v-if="pending(item.id).length" class="btn btn-ghost" :disabled="!!busyId || !!scanningId" @click="refreshPending(item)">{{ scanningId===String(item.id) ? '读取中…' : '读取扫描结果' }}</button>
            <view class="mat__actions">
              <button class="btn btn-ghost flex-1" :disabled="busyId === item.id || pending(item.id).length >= item.maxFiles" @click="pick(item)">
                {{ busyId === item.id ? '上传中…' : '添加文件' }}
              </button>
              <button class="btn btn-primary flex-1" :disabled="!!busyId || !!scanningId || !pendingReady(item)" @click="submit(item)">提交审核</button>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, openBusinessFile, uploadBusinessFile } from '@/services/fileApi'
import fileSdk from '@/services/fileSdk'
import { normalizeFileReadiness, filesReadyForBusiness, refreshFileReadiness, materialRequirementView, allowedFormatText } from '@/services/fileReadiness.mjs'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      state: 'loading',
      context: { batchId: '', internshipId: '' },
      items: [],
      pendingByRequirement: {},
      busyId: '', requestSeq:0, generation:currentSessionGeneration(), hidden:false, requestedBatchId:'', scanningId:'', materialErrors:{}, scanSequence:0
    }
  },
  onLoad(options={}) { this.requestedBatchId=String(options.batchId || '');this.load() },
  onShow() {const wasHidden=this.hidden;this.hidden=false;if(this.generation!==currentSessionGeneration()){this.pendingByRequirement={};this.items=[];this.context={batchId:'',internshipId:''};this.load()}else if(wasHidden && this.state==='loading')return this.load()},
  onHide() {this.hidden=true;this.scanSequence++;this.scanningId=''},
  onUnload() {this.hidden=true;this.requestSeq++;this.scanSequence++},
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    fmt(value) { return String(value || '').slice(0, 16).replace('T', ' ') },
    shortHash(value) { const text = String(value || ''); return text ? text.slice(0, 10) + '…' : '—' },
    pending(id) { return this.pendingByRequirement[String(id)] || [] },
    pendingReady(item) {const files=this.pending(item.id);return files.length>=Number(item.minFiles || 0) && files.length<=Number(item.maxFiles || 1) && filesReadyForBusiness(files)},
    current(seq,generation,allowHidden=false) {return seq===this.requestSeq && generation===currentSessionGeneration() && (!this.hidden || allowHidden)},
    async refreshPending(item) {
      if(this.busyId || this.scanningId) return
      const key=String(item.id),files=this.pending(key),seq=this.requestSeq,generation=this.generation,sequence=++this.scanSequence
      const current=()=>this.current(seq,generation) && sequence===this.scanSequence && this.pending(key)===files
      this.scanningId=key;this.materialErrors={...this.materialErrors,[key]:''}
      try {const updated=await refreshFileReadiness(files,id=>fileSdk.metadata(id),current);if(updated)this.pendingByRequirement={...this.pendingByRequirement,[key]:updated}}
      catch {if(current()){this.pendingByRequirement={...this.pendingByRequirement,[key]:files.map(file=>({...file,readyForBusiness:false,statusText:'扫描结果未能读取，材料已保留'}))};this.materialErrors={...this.materialErrors,[key]:'扫描结果读取失败，材料已保留，请重新读取'}}}
      finally {if(sequence===this.scanSequence)this.scanningId=''}
    },
    statusLabel(item) {
      if (item.isLate && !item.submission) return '已逾期未交'
      return item.submission?.statusLabel || '未提交'
    },
    statusTone(item) {
      const status = item.submission?.status
      if (status === 'APPROVED') return 'success'
      if (status === 'RETURNED' || item.isLate) return 'danger'
      if (status === 'SUBMITTED') return 'warning'
      return 'default'
    },
    canSubmit(item) {
      const status = item.submission?.status
      return !status || status === 'RETURNED' || status === 'DRAFT' || status === 'WITHDRAWN'
    },
    async load(done) {
      const seq=++this.requestSeq,generation=currentSessionGeneration();if(this.generation!==generation)this.pendingByRequirement={};this.generation=generation
      this.scanSequence++;this.scanningId='';this.busyId='';this.items=[]
      this.state = 'loading'
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if(!this.current(seq,generation))return
        const next={batchId:String(dashboard?.batchId || ''),internshipId:String(dashboard?.recordId || '')}
        if(next.batchId!==this.context.batchId || next.internshipId!==this.context.internshipId){this.pendingByRequirement={};this.materialErrors={}}
        this.context=next
        if (!this.context.batchId || !this.context.internshipId) {
          this.items = []
          this.state = 'ready'
          return
        }
        const rows = await studentApi.getInternshipMaterialRequirements(this.context.batchId, this.context.internshipId)
        if(!this.current(seq,generation))return
        this.items = (Array.isArray(rows) ? rows : rows?.items || []).map(item=>({...materialRequirementView(item),allowedFormatLabel:allowedFormatText(item.allowedExtensions)}))
        this.state = 'ready'
      } catch (e) {
        if(!this.current(seq,generation))return
        this.items = []
        this.state = 'error'
        toast('实习材料读取失败，请重新读取')
      } finally { if (done) done() }
    },
    async downloadTemplate(item) {
      if (!item.template || this.busyId || this.hidden || this.generation!==currentSessionGeneration()) return
      const seq=this.requestSeq,generation=this.generation
      this.busyId = item.id
      try {
        const downloaded = await studentApi.downloadInternshipMaterialTemplate(
          item.id, this.context.batchId, this.context.internshipId)
        if(!this.current(seq,generation))return
        if (!downloaded?.tempFilePath) return toast('模板下载失败')
        uni.openDocument({
          filePath: downloaded.tempFilePath,
          showMenu: true,
          fail: () => toast('模板已下载，但当前设备无法直接预览')
        })
      } catch (e) {if(this.current(seq,generation))toast('模板下载未完成，请重试')}
      finally {if(seq===this.requestSeq)this.busyId = ''}
    },
    async preview(fileId) {
      if(this.hidden || this.generation!==currentSessionGeneration())return
      try { await openBusinessFile(fileId) }
      catch (e) { toast('材料暂时无法打开，请重新读取后重试') }
    },
    async pick(item) {
      if (this.busyId || this.pending(item.id).length >= Number(item.maxFiles || 1)) return
      if(this.hidden || this.generation!==currentSessionGeneration() || !this.canSubmit(item))return
      const seq=this.requestSeq,generation=this.generation
      this.busyId = item.id
      try {
        const file = await chooseSingleFile()
        if (!file || !this.current(seq,generation,true)) return
        const ext = String(file.name || '').split('.').pop().toLowerCase()
        const allowed = item.allowedExtensions || []
        if (allowed.length && !allowed.includes(ext)) return toast('文件格式不符合学校要求')
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_CUSTOM_MATERIAL' })
        if(!this.current(seq,generation,true))return
        if(!uploaded?.fileId)throw Error('材料上传结果未能核对')
        const key = String(item.id)
        const normalized=normalizeFileReadiness({...uploaded,fileName:uploaded.fileName || file.name || '材料文件'})
        this.pendingByRequirement = {
          ...this.pendingByRequirement,
          [key]: [...this.pending(key), normalized]
        }
        toast(normalized.readyForBusiness?'材料安全可用':'文件已接收，请读取安全扫描结果')
      } catch (e) {if(this.current(seq,generation,true))this.materialErrors={...this.materialErrors,[String(item.id)]:'材料上传未完成，已选材料保留，请重试'}}
      finally {if(seq===this.requestSeq)this.busyId = ''}
    },
    removePending(id, index) {
      if(this.busyId)return
      const key = String(id)
      const next = [...this.pending(key)]
      next.splice(index, 1)
      this.pendingByRequirement = { ...this.pendingByRequirement, [key]: next }
    },
    async submit(item) {
      if (this.busyId || this.scanningId || this.hidden || this.generation!==currentSessionGeneration() || !this.canSubmit(item)) return
      const files = this.pending(item.id)
      const min = Number(item.minFiles || 0)
      const max = Number(item.maxFiles || 1)
      if (files.length < min || files.length > max) return toast(`请上传 ${min}～${max} 份材料`)
      if(!filesReadyForBusiness(files)){this.materialErrors={...this.materialErrors,[String(item.id)]:'材料尚未安全可用，请读取扫描结果或移除后重新上传'};return}
      const seq=this.requestSeq,generation=this.generation
      this.busyId = item.id
      try {
        await studentApi.submitInternshipMaterial(item.id, {
          ...this.context,
          fileIds: files.map((file) => String(file.fileId)),
          expectedVersion:item.submission?.version ?? 0,
          comment: item.submission?.status === 'RETURNED' ? '按审核意见重新提交' : '学生提交'
        })
        if(!this.current(seq,generation))return
        this.pendingByRequirement = { ...this.pendingByRequirement, [String(item.id)]: [] }
        toast('材料已提交审核')
        await this.load()
      } catch (e) {if(this.current(seq,generation))this.materialErrors={...this.materialErrors,[String(item.id)]:normalizeError(e).text+'；材料已保留，请重新读取原任务核对'}}
      finally {if(seq===this.requestSeq)this.busyId = ''}
    }
  }
}
</script>

<style scoped>
.mat{display:flex;flex-direction:column;gap:12px;padding:14px}.mat__code,.mat__desc,.mat__hash{display:block;margin-top:4px;font-size:11px;color:var(--text-tertiary);line-height:1.5}.mat__facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px;background:var(--gray-50);border-radius:8px}.mat__facts view{display:flex;flex-direction:column;gap:3px}.mat__facts text:first-child{font-size:10px;color:var(--text-tertiary)}.mat__facts text:last-child{font-size:12px;color:var(--text-primary)}.mat__template,.mat__file-row,.mat__pending{display:flex;align-items:center;gap:10px}.mat__template{padding:10px;border:1px solid var(--border-light);border-radius:8px}.mat__template-name,.mat__submission-title,.mat__upload-title{display:block;font-size:13px;font-weight:600;color:var(--text-primary)}.mat__submission{padding:10px;border-radius:8px;background:var(--gray-50)}.mat__file-row{padding:8px 0;border-bottom:1px solid var(--border-light)}.mat__preview,.mat__pending button{margin:0;padding:3px 6px;min-height:0;border:0;background:transparent;color:var(--brand-primary);font-size:11px}.mat__preview::after,.mat__pending button::after{border:none}.mat__review{display:block;margin-top:8px;padding:8px;border-radius:6px;background:var(--warning-50);color:var(--warning-700);font-size:12px}.mat__upload{padding-top:4px}.mat__count{font-size:11px;color:var(--text-tertiary)}.mat__pending{padding:7px 0;border-bottom:1px dashed var(--border-light);font-size:12px}.mat__actions{display:flex;gap:8px;margin-top:10px}
</style>
