# Document Preview Platform Contract

> Contract: `document-preview-contract/v1`  
> Status: W0 FROZEN  
> Baseline: `main@0c786c125ab8de6d0a34820400e0c338fb9e4ad3`  
> Scope: Admin/Teacher PC, Student PC, Teacher Miniapp, Student Miniapp, existing File Center  
> Rule: File Center remains the only authorization and byte authority. Viewer is presentation only.

## 1. Authority and ownership

| Owner | Responsibility | Must not own |
|---|---|---|
| File Center | tenant/object relation/data scope/batch/scan authorization, byte delivery, audit | UI rendering, business approval decisions |
| FileVersion | immutable review source identity | renderer/rendition identity |
| Preview Provider / File SDK | issue/fetch authorized preview transport and normalize errors | business scope decisions |
| AppDocumentViewer | render authorized bytes and viewer lifecycle | issuing business permission, approval truth |
| Business Workspace | what happens after reading: approve/reject/return/next | raw file transport |
| MobileAttachmentPicker | upload/select/bind handoff | preview transport |
| presentationSafety | user-visible safe error presentation | authorization |

`FilePreviewer` remains the compatibility entry for one file. `SecureFileList` remains the secure list/switcher. `AppFilePreview` is legacy attachment-list compatibility and must not become a second transport implementation.

## 2. Preview and download are distinct capabilities

`preview` permission **is not** `download` permission.

- The backend is authoritative for `allowedActions`.
- A client may render only when `allowedActions` contains `preview`.
- A client may download only when `allowedActions` contains `download`.
- A UI must not infer one capability from the other.
- P0 migration may preserve an existing endpoint that currently authorizes both, but its UI semantics and audit action remain distinct; future providers must be able to separate them without changing business pages.

## 3. Preview Descriptor

All clients converge on this semantic shape even when transport endpoints differ:

```ts
export interface PreviewDescriptorV1 {
  fileId: string
  assetId?: string | number | null
  fileVersionId?: string | number | null
  versionNo?: number | null
  sourceSha256?: string | null

  fileName: string
  ext?: string | null
  mimeType?: string | null
  sizeBytes?: number | null

  scanStatus: 'NOT_REQUIRED' | 'PENDING' | 'RUNNING' | 'CLEAN' | 'INFECTED' | 'ERROR'
  statusText: string
  readyForBusiness: boolean
  allowedActions: Array<'viewMetadata' | 'preview' | 'download'>

  preview: {
    kind: 'PDF' | 'IMAGE' | 'DOCX' | 'NATIVE_OFFICE' | 'UNSUPPORTED'
    delivery: 'BUSINESS_TICKET' | 'LOCAL_PROXY' | 'COS_PRESIGNED' | 'RENDITION'
    ticketRequired: boolean
    expiresAt?: string | null
    pageCount?: number | null
    renditionId?: string | number | null
  }

  watermark?: {
    enabled: boolean
    textMode?: 'USER_SCHOOL_TIME' | 'NONE'
  }
}
```

Rules:

1. `preview.kind` is rendering capability, not a blind extension check.
2. `delivery` is backend/provider truth; business pages must not guess transport.
3. `fileVersionId` and `sourceSha256` identify the source being reviewed.
4. A rendition is read-only presentation evidence; review commands always lock the source `FileVersion`.
5. `allowedActions` comes from the authoritative backend response.

## 4. Provider boundary

The Viewer consumes a provider, never a public storage URL:

```ts
interface PreviewProvider {
  describe(input): Promise<PreviewDescriptorV1>
  issue(input): Promise<PreviewSessionV1>
  fetchBytes(session): Promise<Blob | ArrayBuffer>
  dispose?(session): void
}
```

Business pages pass domain context to a provider. Graduation, internship, student-affairs and generic files may use different providers while sharing the Viewer.

### Graduation hard rule

`GRADUATION_MATERIAL` remains high sensitivity:

- no generic `/files/{id}/url` bypass;
- keep the graduation material-center business ticket boundary;
- ticket/byte response stays private/no-store and audited;
- PDF.js or any renderer never becomes authorization authority;
- an opened old version never authorizes approving that old version after the source changed.

## 5. Preview session state machine

```text
IDLE
→ ISSUING_TICKET
→ FETCHING
→ RENDERING
→ READY
→ EXPIRED → REFRESHING → FETCHING
→ ERROR
→ UNSUPPORTED
→ DESTROYED
```

- Ticket-expiry refresh is bounded to one automatic retry.
- Switching files cancels the prior fetch/render generation.
- Late completion from an old generation must not overwrite the current file UI.
- Destroying a session releases Blob/Object URL/render resources.
- A render failure never changes the business review readiness by itself.

## 6. Mobile Reader Return Contract

Miniapp uses native readers; it does not embed PDF.js/Office renderers.

Before native open, snapshot:

```text
reviewKind
queueIndex
itemId
fileVersionId
sourceSha256
draftComment
openedAt
```

On return:

1. reload the current business detail from the server;
2. compare current `fileVersionId`/source version with the open snapshot;
3. restore draft comment only for the same business object;
4. if the version changed, raise `PREVIEW_VERSION_CHANGED`, lock review actions and require re-preview;
5. preserve the queue index; do not jump to the first row;
6. advance to next only after the business action succeeds **and** server truth reload succeeds.

This is `open snapshot → return reload → version compare → draft preservation → conflict lock → next only after truth reload`.

## 7. Error contract

```text
PREVIEW_FILE_NOT_FOUND
PREVIEW_FORBIDDEN_AS_NOT_FOUND
PREVIEW_SCAN_PENDING
PREVIEW_SCAN_FAILED
PREVIEW_INFECTED
PREVIEW_TICKET_EXPIRED
PREVIEW_FETCH_FAILED
PREVIEW_RENDER_FAILED
PREVIEW_UNSUPPORTED_TYPE
PREVIEW_TOO_LARGE
PREVIEW_VERSION_CHANGED
PREVIEW_OFFLINE
```

User-facing errors must flow through the existing `presentationSafety` owner on PC. Raw SQL, stack traces, storage keys, ticket values, presigned URLs and authorization headers must never be exposed to the UI or Playwright artifacts.

## 8. Type matrix

| Type | Admin/Teacher PC P0 | Student PC P0 | Miniapp | Policy |
|---|---|---|---|---|
| PDF | embedded | embedded | native open | primary review format |
| JPG/JPEG/PNG/WEBP | embedded | embedded | native image preview | P0 |
| DOCX | fallback until W6 | fallback until W6 | native open where supported | adapter only after PDF Gold |
| XLSX/PPTX | unsupported/download policy | unsupported/download policy | native/fallback by product rule | no P0 renderer |
| ZIP/RAR/7z/source/CAD/PSD | unsupported | unsupported | PC/download handoff | never force renderer |

Unsupported must be explicit and must never auto-download without user intent.

## 9. Component owner matrix and compatibility

- `frontend/src/components/file/FilePreviewer.vue`: compatibility entry; W1 may add `mode="inline"` that delegates to `AppDocumentViewer`.
- `frontend/src/components/file/SecureFileList.vue`: list/switcher only.
- `frontend/src/components/common/AppFilePreview.vue`: legacy attachment list only; new business code must not add transport logic here.
- Student PC mirrors the DTO/state/provider contract with a thin local SFC implementation; W0/W1 does not introduce a cross-Vite SFC package.
- `miniapp/src/components/file/FilePreviewer.vue`: delegates to File SDK/native open; it does not own `uni.openDocument`, `uni.previewImage` or `uni.downloadFile`.

## 10. CI source-boundary freeze

W0 freezes these boundaries before business migration:

- PC/student/miniapp `FilePreviewer` components may not implement raw transport.
- `AppFilePreview` may not implement raw transport.
- `uni.previewImage` and `uni.openDocument` are centralized in the miniapp File SDK, except explicitly grandfathered legacy pages identified by the W0 live scan.
- `uni.downloadFile` is centralized in the miniapp request transport.
- Graduation generic URL bypass remains prohibited by backend contract.
- future DocumentViewer code must consume a provider rather than call a domain API directly.

Legacy bypasses discovered on the W0 live scan are debt, not patterns to copy. W5 removes them domain-by-domain; W0 must not expand their set.

## 11. E2E artifact safety

Viewer browser tests use synthetic documents only. Every synthetic PDF payload/page used by the Viewer suite must carry:

`YUEKE E2E SYNTHETIC DOCUMENT`

Fixtures use fictitious identities only. Test screenshots/video/trace/logs must never persist:

- real student documents or PII;
- Authorization/Cookie credentials;
- business preview tickets;
- presigned URLs;
- raw storage object keys.

## 12. Wave gates

- W0: this contract + inventory supplement + CI/source safety freeze; no business behavior.
- W1: Admin/Teacher PC PDF/Image Viewer core.
- W2: Graduation Teacher PC Gold.
- W3: Student PC; re-read latest `portalApi.js` after PR #190 convergence before editing it.
- W4: Miniapp Reader Return Contract.
- W5: domain migration.
- W6: DOCX adapter only after PDF Gold.

No migration is created for W0/W1 unless a later live requirement proves persistent server state is necessary.
