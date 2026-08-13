<template>
  <BasePortalLayout :title="brandTitle" subtitle="甯姪涓績" :ctx="ctx" @menu-select="onMenu">
    <template #menu>
      <nav class="help-nav" aria-label="甯姪鐩綍">
        <button
          type="button"
          class="help-nav__home"
          :class="{ 'is-active': !currentEntry }"
          @click="showOverview"
        >
          <span>鑷姪鏈嶅姟棣栭〉</span>
          <small>{{ overview.total }} 椤?/small>
        </button>

        <details
          v-for="section in visibleSections"
          :key="section.key"
          class="help-nav__section"
          :open="isSectionOpen(section)"
        >
          <summary>
            <span>{{ section.label }}</span>
            <small>{{ section.items.length }}</small>
          </summary>
          <button
            v-for="entry in section.items"
            :key="entry.id"
            type="button"
            class="help-nav__item"
            :class="{ 'is-active': entry.id === currentId }"
            @click="selectTopic(entry.id)"
          >
            {{ entry.title }}
          </button>
        </details>

        <div v-if="!visibleSections.length" class="help-nav__empty">
          褰撳墠绛涢€変笅娌℃湁鐩綍椤广€?
        </div>
      </nav>
    </template>

    <div class="help-shell">
      <header class="help-hero">
        <div>
          <p class="help-eyebrow">璺冪 SaaS 路 鍏嶅煿璁嚜鍔╂湇鍔?/p>
          <h1>鑷姪鍔炵悊涓庨棶棰樿В鍐充腑蹇?/h1>
          <p>涓嶇敤鍏堣璇存槑涔︺€傜洿鎺ュ憡璇夌郴缁熲€滄垜瑕佸姙浠€涔堚€濇垨鈥滃摢閲屽仛涓嶄簡鈥濓紝涔熷彲浠ユ部鏍稿績涓氬姟娴佺▼鐪嬬幇鍦ㄥ湪鍝竴姝ャ€佷笅涓€姝ヨ皝澶勭悊銆?/p>
        </div>
        <dl class="help-metrics" aria-label="甯姪鍐呭缁熻">
          <div><dt>宸叉牳楠屼换鍔?/dt><dd>{{ overview.taskCards }}</dd></div>
          <div><dt>涓氬姟娴佺▼</dt><dd>{{ overview.flowGuides }}</dd></div>
          <div><dt>鍙鎸囧崡</dt><dd>{{ overview.visualGuides }}</dd></div>
        </dl>
      </header>

      <section v-if="qualityMetrics" class="help-quality" aria-label="甯姪涓績杩?0澶╄川閲忔寚鏍?>
        <div class="help-quality__heading">
          <div>
            <p class="help-eyebrow">V3-08 路 杩?{{ qualityMetrics.windowDays }} 澶?/p>
            <h2>甯姪涓績璐ㄩ噺</h2>
          </div>
          <small>鍙粺璁＄湡瀹炴悳绱㈠拰鐢ㄦ埛鏄庣‘鍙嶉锛涙湭鎵撻€氫汉宸ュ伐鍗曞墠锛屼笉浼€犫€滅湡瀹炶嚜鍔╄В鍐崇巼鈥濄€?/small>
        </div>
        <dl class="help-quality__metrics">
          <div>
            <dt>鎼滅储鍛戒腑鐜?/dt>
            <dd>{{ formatRate(qualityMetrics.searchHitRate) }}</dd>
            <small>{{ qualityMetrics.searches }} 娆℃悳绱?路 {{ metricStatusLabel(qualityMetrics.quality?.search) }}</small>
          </div>
          <div>
            <dt>鏄庣‘鍙嶉瑙ｅ喅鐜?/dt>
            <dd>{{ formatRate(qualityMetrics.explicitResolutionRate) }}</dd>
            <small>{{ qualityMetrics.feedbackVotes }} 娆″弽棣?路 {{ metricStatusLabel(qualityMetrics.quality?.resolution) }}</small>
          </div>
          <div>
            <dt>鐪熸鑷姪瑙ｅ喅鐜?/dt>
            <dd>鈥?/dd>
            <small>绛夊緟浜哄伐鍗囩骇/宸ュ崟闂幆鍚庤绠?/small>
          </div>
        </dl>
      </section>

      <section class="help-controls" aria-label="甯姪绛涢€?>
        <label class="help-control help-control--search">
          <span>鐩存帴鎻忚堪浣犺鍔炵殑浜嬫垨閬囧埌鐨勯棶棰?/span>
          <input
            v-model.trim="queryText"
            type="search"
            placeholder="渚嬪锛氭垚缁╀负浠€涔堟彁浜や笉浜嗭紵鎬庝箞鍙戝竷閫夎锛熶负浠€涔堢湅涓嶅埌瀛︾敓锛?
            autocomplete="off"
            @keyup.enter="syncFiltersToUrl"
          />
        </label>
        <label class="help-control">
          <span>鎴戠殑瑙掕壊</span>
          <select v-model="selectedRole" @change="onFilterChange">
            <option v-for="role in roleOptions" :key="role.value" :value="role.value">
              {{ role.label }}
            </option>
          </select>
        </label>
        <label class="help-control">
          <span>涓氬姟鍒嗙被</span>
          <select v-model="selectedCategory" @change="onFilterChange">
            <option value="all">鍏ㄩ儴鍒嗙被</option>
            <option v-for="category in categoryOptions" :key="category.value" :value="category.value">
              {{ category.label }}锛坽{ category.count }}锛?
            </option>
          </select>
        </label>
        <button v-if="hasFilters" type="button" class="help-clear" @click="clearFilters">
          娓呴櫎绛涢€?
        </button>
      </section>

      <div v-if="invalidTopic" class="help-notice" role="alert">
        鍘熼摼鎺ユ寚鍚戠殑甯姪鏉＄洰涓嶅瓨鍦ㄦ垨宸茶皟鏁淬€傚凡杩斿洖鑷姪鏈嶅姟棣栭〉锛岃閲嶆柊鎼滅储銆?
      </div>

      <article v-if="currentEntry" class="help-article">
        <button type="button" class="help-back" @click="showOverview">鈫?杩斿洖鑷姪鏈嶅姟棣栭〉</button>

        <header class="help-article__header">
          <div class="help-badges">
            <span>{{ currentEntry.typeLabel }}</span>
            <span>{{ currentEntry.category }}</span>
            <span v-if="displayRoles.length">{{ displayRoles.join('銆?) }}</span>
          </div>
          <h2>{{ currentEntry.title }}</h2>
          <p>{{ currentEntry.summary }}</p>
          <div v-if="currentItem.entry || currentItem.route" class="help-entry">
            <div>
              <strong>浠庡摢閲岃繘鍏?/strong>
              <span>{{ currentItem.entry || '浠庡搴斾笟鍔℃ā鍧楄繘鍏? }}</span>
            </div>
            <button v-if="currentItem.route" type="button" @click="goRoute(currentItem.route)">
              鍓嶅線鍔炵悊椤甸潰
            </button>
          </div>
        </header>

        <section v-if="currentItem.prerequisites?.length" class="help-section">
          <h3>鎿嶄綔鍓嶅噯澶?/h3>
          <ul><li v-for="(item, index) in currentItem.prerequisites" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentEntry.type === 'card' && currentItem.steps?.length" class="help-section">
          <h3>鐓х潃鍋?/h3>
          <ol class="help-task-steps">
            <li v-for="(step, index) in currentItem.steps" :key="index">
              <span>{{ index + 1 }}</span>
              <div>{{ stringify(step) }}</div>
            </li>
          </ol>
        </section>

        <section v-else-if="currentEntry.type === 'flow' && currentItem.steps?.length" class="help-section">
          <h3>涓氬姟娴佽浆</h3>
          <ol class="help-flow">
            <li v-for="(step, index) in currentItem.steps" :key="index">
              <span class="help-flow__number">{{ index + 1 }}</span>
              <div>
                <strong>{{ step.name || stringify(step) }}</strong>
                <small v-if="step.who">{{ step.who }}</small>
                <p v-if="step.detail">{{ step.detail }}</p>
              </div>
            </li>
          </ol>
        </section>

        <section v-if="currentEntry.type === 'doc' && currentItem.points?.length" class="help-section">
          <h3>鍏抽敭瑕佺偣</h3>
          <ul><li v-for="(point, index) in currentItem.points" :key="index">{{ stringify(point) }}</li></ul>
        </section>

        <section v-if="currentItem.fields?.length" class="help-section">
          <h3>闇€瑕佸～鍐欐垨纭</h3>
          <ul><li v-for="(field, index) in currentItem.fields" :key="index">{{ stringify(field) }}</li></ul>
        </section>

        <section v-for="(section, index) in currentItem.sections || []" :key="index" class="help-section">
          <h3>{{ section.title || section.heading || `琛ュ厖璇存槑 ${index + 1}` }}</h3>
          <p v-if="section.body">{{ section.body }}</p>
          <ul v-if="section.items || section.list">
            <li v-for="(line, lineIndex) in section.items || section.list" :key="lineIndex">{{ stringify(line) }}</li>
          </ul>
        </section>

        <section v-if="currentItem.successCriteria?.length" class="help-section help-section--success">
          <h3>鎬庢牱鎵嶇畻鍔炴垚鍔?/h3>
          <ul><li v-for="(item, index) in currentItem.successCriteria" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.nextSteps?.length" class="help-section help-section--next">
          <h3>鍔炲畬浠ュ悗涓嬩竴姝?/h3>
          <ul><li v-for="(item, index) in currentItem.nextSteps" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.tips?.length" class="help-section help-section--tip">
          <h3>鎿嶄綔鎻愮ず</h3>
          <ul><li v-for="(tip, index) in currentItem.tips" :key="index">{{ stringify(tip) }}</li></ul>
        </section>

        <section v-if="currentItem.warnings?.length" class="help-section help-section--warning">
          <h3>閲嶈鎻愰啋</h3>
          <ul><li v-for="(warning, index) in currentItem.warnings" :key="index">{{ stringify(warning) }}</li></ul>
        </section>

        <section v-if="currentItem.faq?.length" class="help-section">
          <h3>甯歌闂</h3>
          <details v-for="(qa, index) in currentItem.faq" :key="index" class="help-faq">
            <summary>{{ qa.q || qa.question || stringify(qa) }}</summary>
            <p v-if="qa.a || qa.answer">{{ qa.a || qa.answer }}</p>
          </details>
        </section>

        <section v-if="currentItem.troubleshooting?.length" class="help-section">
          <h3>鍋氫笉浜嗘椂鎬庝箞鑷繁鎺掓煡</h3>
          <ol><li v-for="(item, index) in currentItem.troubleshooting" :key="index">{{ stringify(item) }}</li></ol>
        </section>

        <section v-if="currentItem.contactAdminWhen?.length" class="help-section help-section--admin">
          <h3>浠€涔堟儏鍐垫墠闇€瑕佹壘绠＄悊鍛?/h3>
          <ul><li v-for="(item, index) in currentItem.contactAdminWhen" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.related?.length" class="help-section">
          <h3>鐩稿叧鍏ュ彛</h3>
          <div class="help-related">
            <button
              v-for="(related, index) in currentItem.related"
              :key="index"
              type="button"
              @click="goRoute(related.route)"
            >
              {{ related.label || stringify(related) }} 鈫?
            </button>
          </div>
        </section>

        <section v-if="currentItem.embed || visualGallery.length" class="help-section help-section--embed">
          <h3>鍙鍖栬鏄?/h3>
          <p v-if="visualGallery.length" class="help-visual-intro">鍏堢敤鍥捐В蹇€熷畾浣嶇幆鑺傦紱闇€瑕佹煡鐪嬫楠ゃ€佽鑹插拰鎿嶄綔鍏ュ彛鏃讹紝鍐嶉槄璇讳笅鏂逛氦浜掑紡璇存槑銆?/p>
          <div v-if="visualGallery.length" class="help-visual-gallery" aria-label="娴佺▼鍥捐В">
            <a
              v-for="image in primaryVisuals"
              :key="image.src"
              class="help-visual-card"
              :class="{ 'is-primary': image.primary, 'is-mobile': image.mobile }"
              :href="image.src"
              target="_blank"
              rel="noopener noreferrer"
            >
              <img :src="image.src" :alt="image.title" loading="lazy" />
              <span>{{ image.title }}</span>
              <small>鐐瑰嚮鏌ョ湅澶у浘</small>
            </a>
          </div>
          <details v-if="archiveVisuals.length" class="help-visual-history">
            <summary>鏌ョ湅鍥捐В杩唬鐣欏瓨锛堜粎渚涜璁″洖婧級</summary>
            <div class="help-visual-gallery">
              <a
                v-for="image in archiveVisuals"
                :key="image.src"
                class="help-visual-card"
                :href="image.src"
                target="_blank"
                rel="noopener noreferrer"
              >
                <img :src="image.src" :alt="image.title" loading="lazy" />
                <span>{{ image.title }}</span>
                <small>鐐瑰嚮鏌ョ湅澶у浘</small>
              </a>
            </div>
          </details>
          <iframe
            v-if="currentItem.embed"
            :src="currentItem.embed"
            sandbox="allow-scripts"
            referrerpolicy="no-referrer"
            :title="currentItem.title"
          ></iframe>
        </section>

        <section class="help-feedback" aria-label="甯姪鏄惁瑙ｅ喅闂">
          <div>
            <strong>杩欑瘒甯姪瑙ｅ喅浣犵殑闂浜嗗悧锛?/strong>
            <small>浣犵殑閫夋嫨鍙敤浜庢敼杩涘府鍔╄川閲忋€?/small>
          </div>
          <div v-if="!currentFeedback" class="help-feedback__actions">
            <button type="button" @click="submitArticleFeedback('HELPFUL')">宸茶В鍐?/button>
            <button type="button" class="is-secondary" @click="submitArticleFeedback('NOT_HELPFUL')">娌¤В鍐?/button>
          </div>
          <span v-else class="help-feedback__done">宸茶褰曪紝璋㈣阿鍙嶉銆?/span>
        </section>

        <footer class="help-article__footer">
          <span>鏂囩珷缂栧彿锛歿{ currentEntry.id }}</span>
          <span v-if="!currentEntry.quality.isComplete">璇ユ潯鐩粛鏈夊厓鏁版嵁寰呮不鐞嗭紝涓嶅奖鍝嶅綋鍓嶉槄璇汇€?/span>
        </footer>
      </article>

      <template v-else>
        <section v-if="queryText || selectedCategory !== 'all'" class="help-results">
          <div class="help-section-heading">
            <div>
              <p class="help-eyebrow">鑷姪鎼滅储缁撴灉</p>
              <h2>鎵惧埌 {{ filteredEntries.length }} 椤瑰彲鎵ц甯姪</h2>
            </div>
          </div>
          <div v-if="filteredEntries.length" class="help-card-grid">
            <button
              v-for="entry in filteredEntries"
              :key="entry.id"
              type="button"
              class="help-card"
              @click="selectTopic(entry.id)"
            >
              <span>{{ entry.typeLabel }} 路 {{ entry.category }}</span>
              <strong>{{ entry.title }}</strong>
              <p>{{ entry.summary }}</p>
            </button>
          </div>
          <div v-else class="help-empty-state">
            <h3>娌℃湁鎵惧埌宸茬粡鏍搁獙鐨勭瓟妗?/h3>
            <p>鍙互鎹㈡垚鏇村叿浣撶殑涓氬姟鍔ㄤ綔鎴栭敊璇幇璞★紝渚嬪鈥滄垚缁╂彁浜も€濃€滈€€鍥炩€濃€滄暟鎹寖鍥粹€濃€?09鈥濄€傛病鏈夐€氳繃 verified-only 鍙戝竷闂ㄧ殑鏃х煡璇嗕笉浼氫负浜嗗噾绛旀閲嶆柊灞曠ず銆?/p>
            <button type="button" @click="clearFilters">杩斿洖鑷姪鏈嶅姟棣栭〉</button>
          </div>
        </section>

        <template v-else>
          <section class="help-intents" aria-label="鑷姪鏈嶅姟鍏ュ彛">
            <button
              v-for="intent in v3Home.intents"
              :key="intent.key"
              type="button"
              class="help-intent"
              :class="{ 'is-active': homeMode === intent.key }"
              @click="selectHomeMode(intent.key)"
            >
              <span>{{ intent.title }}</span>
              <strong>{{ intent.description }}</strong>
              <small>{{ intent.hint }}</small>
            </button>
          </section>

          <section v-if="homeMode === 'tasks'" class="help-section-block">
            <div class="help-section-heading">
              <div>
                <p class="help-eyebrow">鎴戣鍔炰竴浠朵簨</p>
                <h2>鎸夊綋鍓嶈鑹叉帹鑽愰珮棰戝姙鐞?/h2>
              </div>
              <p>褰撳墠鎸夆€渰{ activeRoleLabel }}鈥濇帹鑽愶紱姣忎竴椤归兘鏉ヨ嚜宸叉牳楠屾寮忕煡璇嗐€?/p>
            </div>
            <div class="help-card-grid">
              <button
                v-for="entry in priorityEntries"
                :key="entry.id"
                type="button"
                class="help-card"
                @click="selectTopic(entry.id)"
              >
                <span>{{ entry.typeLabel }} 路 {{ entry.category }}</span>
                <strong>{{ entry.title }}</strong>
                <p>{{ entry.summary }}</p>
              </button>
            </div>
          </section>

          <template v-else-if="homeMode === 'problems'">
            <section class="help-section-block">
              <div class="help-section-heading">
                <div>
                  <p class="help-eyebrow">鎴戦亣鍒伴棶棰?/p>
                  <h2>鍏堥€夋渶鍍忎綘褰撳墠鎯呭喌鐨勯棶棰?/h2>
                </div>
                <p>鐐瑰嚮鍚庣洿鎺ユ悳绱㈢浉鍏冲凡鏍搁獙绛旀锛屼笉瑕佹眰浣犲厛鐭ラ亾闂灞炰簬鍝釜妯″潡銆?/p>
              </div>
              <div class="help-question-grid">
                <button
                  v-for="question in v3Home.quickQuestions"
                  :key="question.label"
                  type="button"
                  class="help-question"
                  @click="applyQuickQuestion(question)"
                >
                  {{ question.label }}
                </button>
              </div>
            </section>

            <section class="help-section-block help-diagnosis">
              <div>
                <p class="help-eyebrow">閫氱敤鑷煡椤哄簭</p>
                <h2>鍏堣嚜宸辨帓鏌ワ紝鍐嶅喅瀹氭槸鍚﹂渶瑕佹壘绠＄悊鍛?/h2>
              </div>
              <ol>
                <li>纭褰撳墠瀛︽湡銆佹壒娆°€佸鐢熸垨涓氬姟鑼冨洿鏄惁姝ｇ‘銆?/li>
                <li>纭璐﹀彿褰撳墠瑙掕壊銆佹暟鎹寖鍥村拰璁板綍褰掑睘銆?/li>
                <li>纭涓氬姟鐘舵€佹槸鍚﹀厑璁稿綋鍓嶆搷浣滐紝鏄惁宸茬粡鎻愪氦銆佸彂甯冩垨褰掓。銆?/li>
                <li>纭鍓嶇疆鏁版嵁銆佸繀濉瓧娈靛拰鏉愭枡鏄惁榻愬叏銆?/li>
                <li>閬囧埌 403 / 409 / 鏄庣‘涓氬姟鎻愮ず鏃讹紝鍏堟寜甯姪涓殑瀵瑰簲鍘熷洜澶勭悊锛屼笉鍙嶅杩炵画鐐瑰嚮銆?/li>
                <li>鍙湁缁勭粐銆佽处鍙枫€佹潈闄愩€佹暟鎹寖鍥撮厤缃槑鏄鹃敊璇紝鎴栨寜甯姪鎺掓煡浠嶆棤娉曟仮澶嶆椂锛屽啀鑱旂郴瀛︽牎绠＄悊鍛樸€?/li>
              </ol>
            </section>
          </template>

          <section v-else-if="homeMode === 'journeys'" class="help-section-block">
            <div class="help-section-heading">
              <div>
                <p class="help-eyebrow">鏍稿績涓氬姟娴佺▼</p>
                <h2>鐪嬬幇鍦ㄥ湪鍝竴姝ワ紝涓嬩竴姝ヨ鍋氫粈涔?/h2>
              </div>
              <p>褰撳墠鍙睍绀哄凡缁忛€氳繃 verified-only 鍙戝竷闂ㄧ殑娴佺▼鑺傜偣锛涘皻鏈噸鏂伴獙鐪熺殑鍘嗗彶鑺傜偣涓嶄細娣疯繘鏉ャ€?/p>
            </div>
            <div class="help-journey-grid">
              <article v-for="journey in v3Home.journeys" :key="journey.key" class="help-journey">
                <header>
                  <div>
                    <strong>{{ journey.title }}</strong>
                    <span>宸叉牳楠?{{ journey.verifiedCount }} 涓妭鐐?/span>
                  </div>
                  <p>{{ journey.description }}</p>
                </header>
                <ol class="help-journey-steps">
                  <li v-for="(entry, index) in journey.entries" :key="entry.id">
                    <span>{{ index + 1 }}</span>
                    <button type="button" @click="selectTopic(entry.id)">
                      {{ entry.title }}
                    </button>
                  </li>
                </ol>
              </article>
            </div>
          </section>
        </template>
      </template>
    </div>
  </BasePortalLayout>
</template>

<script>
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import {
  HELP_ROLE_OPTIONS,
  getHelpCategories,
  getHelpEntry,
  getHelpOverview,
  getHelpSections,
  getV3HomeModel,
  resolveHelpRole,
  searchHelpCenter
} from '@/config/helpCenterModel'
import {
  formatHelpRate,
  helpMetricStatusLabel,
  loadHelpMetricsSummary,
  recordHelpMetric
} from '@/config/help/helpMetrics'
import { getAuthContext } from '@/security/auth/auth.context'
import { getHelpVisualGallery } from '@/config/help/helpVisualGallery'

export default {
  name: 'AdminHelpView',
  components: { BasePortalLayout },
  data() {
    const auth = getAuthContext()
    const requestedTopic = String(this.$route.query.topic || '')
    const defaultRole = resolveHelpRole(
      auth.currentRole || auth.primaryRole || (auth.roles && auth.roles[0]),
      auth.label
    )
    const requestedRole = String(this.$route.query.role || defaultRole || 'all')
    const selectedRole = HELP_ROLE_OPTIONS.some((role) => role.value === requestedRole) ? requestedRole : defaultRole
    return {
      auth,
      roleOptions: HELP_ROLE_OPTIONS,
      currentId: getHelpEntry(requestedTopic) ? requestedTopic : '',
      invalidTopic: Boolean(requestedTopic && !getHelpEntry(requestedTopic)),
      queryText: String(this.$route.query.q || ''),
      selectedRole,
      selectedCategory: String(this.$route.query.category || 'all'),
      homeMode: 'tasks',
      qualityMetrics: null,
      articleFeedback: {}
    }
  },
  computed: {
    brandTitle() {
      return `${this.auth.schoolName || '绠＄悊绔?} 路 绠＄悊绔痐
    },
    ctx() {
      return {
        tenantBrandConfig: { schoolName: this.auth.schoolName },
        currentRole: {
          roleType: this.auth.currentRole || this.auth.primaryRole || (this.auth.roles && this.auth.roles[0]) || 'SCHOOL_ADMIN',
          userName: this.auth.displayName
        }
      }
    },
    currentEntry() {
      return getHelpEntry(this.currentId)
    },
    currentItem() {
      return this.currentEntry?.item || {}
    },
    visualGallery() {
      return getHelpVisualGallery(this.currentId)
    },
    primaryVisuals() {
      return this.visualGallery.filter((image) => !image.archive)
    },
    archiveVisuals() {
      return this.visualGallery.filter((image) => image.archive)
    },
    currentFeedback() {
      return this.articleFeedback[this.currentId] || ''
    },
    displayRoles() {
      const roles = this.currentItem.roles || this.currentItem.role || []
      return Array.isArray(roles) ? roles : [roles].filter(Boolean)
    },
    overview() {
      return getHelpOverview(this.selectedRole)
    },
    categoryOptions() {
      return getHelpCategories(this.selectedRole)
    },
    visibleSections() {
      return getHelpSections(this.selectedRole, this.queryText, this.selectedCategory)
    },
    filteredEntries() {
      return searchHelpCenter(this.queryText, {
        role: this.selectedRole,
        category: this.selectedCategory,
        limit: 100
      })
    },
    v3Home() {
      return getV3HomeModel(this.selectedRole)
    },
    priorityEntries() {
      return this.v3Home.priorityTasks
    },
    hasFilters() {
      return Boolean(this.queryText || this.selectedCategory !== 'all' || this.selectedRole !== 'all')
    },
    activeRoleLabel() {
      return this.roleOptions.find((role) => role.value === this.selectedRole)?.label || '鍏ㄩ儴瑙掕壊'
    }
  },
  watch: {
    '$route.query.topic'(value) {
      const id = String(value || '')
      this.currentId = getHelpEntry(id) ? id : ''
      this.invalidTopic = Boolean(id && !getHelpEntry(id))
    }
  },
  mounted() {
    this.refreshQualityMetrics()
    if (this.currentEntry) this.trackArticleView(this.currentEntry, 'direct_link')
  },
  methods: {
    formatRate(value) {
      return formatHelpRate(value)
    },
    metricStatusLabel(value) {
      return helpMetricStatusLabel(value)
    },
    async refreshQualityMetrics() {
      this.qualityMetrics = await loadHelpMetricsSummary(30)
    },
    trackArticleView(entry, source = 'directory') {
      if (!entry) return
      void recordHelpMetric({
        eventType: 'ARTICLE_VIEW',
        articleId: entry.id,
        source,
        category: entry.category,
        roleGroup: this.selectedRole
      })
    },
    onMenu(item) {
      if (item?.path && item.path !== this.$route.path) this.$router.push(item.path)
    },
    selectTopic(id) {
      const entry = getHelpEntry(id)
      if (!entry) return
      this.currentId = id
      this.invalidTopic = false
      this.replaceQuery({ topic: id })
      this.trackArticleView(entry)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
    showOverview() {
      this.currentId = ''
      this.invalidTopic = false
      this.replaceQuery({ topic: undefined })
    },
    selectHomeMode(mode) {
      this.homeMode = mode
      this.currentId = ''
      this.invalidTopic = false
    },
    applyQuickQuestion(question) {
      this.queryText = String(question?.query || question?.label || '').trim()
      this.selectedCategory = 'all'
      this.syncFiltersToUrl({ source: 'quick_question' })
    },
    onFilterChange() {
      if (this.selectedCategory !== 'all' && !this.categoryOptions.some((item) => item.value === this.selectedCategory)) {
        this.selectedCategory = 'all'
      }
      this.showOverview()
      this.syncFiltersToUrl({ trackSearch: false })
    },
    clearFilters() {
      this.queryText = ''
      this.selectedRole = 'all'
      this.selectedCategory = 'all'
      this.currentId = ''
      this.invalidTopic = false
      this.homeMode = 'tasks'
      this.replaceQuery({ topic: undefined, q: undefined, role: undefined, category: undefined })
    },
    syncFiltersToUrl(options = {}) {
      this.currentId = ''
      this.invalidTopic = false
      this.replaceQuery({
        topic: undefined,
        q: this.queryText || undefined,
        role: this.selectedRole !== 'all' ? this.selectedRole : undefined,
        category: this.selectedCategory !== 'all' ? this.selectedCategory : undefined
      })
      if (options?.trackSearch !== false && this.queryText) {
        void recordHelpMetric({
          eventType: 'SEARCH',
          query: this.queryText,
          resultCount: this.filteredEntries.length,
          source: options?.source || 'search',
          category: this.selectedCategory,
          roleGroup: this.selectedRole
        })
      }
    },
    async submitArticleFeedback(eventType) {
      if (!this.currentEntry || this.currentFeedback) return
      const id = this.currentEntry.id
      const result = await recordHelpMetric({
        eventType,
        articleId: id,
        source: 'article',
        category: this.currentEntry.category,
        roleGroup: this.selectedRole
      })
      if (!result) return
      this.articleFeedback = { ...this.articleFeedback, [id]: eventType }
      void this.refreshQualityMetrics()
    },
    replaceQuery(patch) {
      const query = { ...this.$route.query, ...patch }
      Object.keys(query).forEach((key) => {
        if (query[key] === undefined || query[key] === null || query[key] === '') delete query[key]
      })
      this.$router.replace({ query }).catch(() => {})
    },
    goRoute(target) {
      if (typeof target === 'string' && target.startsWith('/')) this.$router.push(target)
    },
    isSectionOpen(section) {
      return section.items.some((entry) => entry.id === this.currentId) || section.key.endsWith('overview')
    },
    stringify(value) {
      if (typeof value === 'string') return value
      if (!value || typeof value !== 'object') return String(value || '')
      return value.label || value.name || value.title || value.detail || value.text || JSON.stringify(value)
    }
  }
}
</script>

<style scoped>
.help-nav { display: flex; flex-direction: column; gap: 8px; }
.help-nav button { font: inherit; }
.help-nav__home,
.help-nav__item { width: 100%; border: 0; text-align: left; cursor: pointer; color: var(--t2); background: transparent; }
.help-nav__home { display: flex; justify-content: space-between; align-items: center; padding: 10px 11px; border-radius: 10px; font-weight: 700; }
.help-nav__home small,
.help-nav__section summary small { color: var(--t3); font-weight: 600; }
.help-nav__home:hover,
.help-nav__home.is-active,
.help-nav__item:hover,
.help-nav__item.is-active { color: var(--brand); background: color-mix(in srgb, var(--brand) 9%, transparent); }
.help-nav__section { border-top: 1px solid var(--dv); padding-top: 7px; }
.help-nav__section summary { display: flex; justify-content: space-between; gap: 8px; padding: 7px 9px; cursor: pointer; color: var(--t1); font-size: 12px; font-weight: 800; }
.help-nav__item { padding: 8px 10px 8px 18px; border-radius: 9px; font-size: 12.5px; line-height: 1.45; }
.help-nav__empty { padding: 12px 10px; color: var(--t3); font-size: 12px; }
.help-shell { display: grid; gap: 18px; max-width: 1180px; margin: 0 auto; }
.help-hero { display: flex; justify-content: space-between; gap: 24px; padding: 26px; border: 1px solid var(--dv); border-radius: 20px; background: linear-gradient(135deg, color-mix(in srgb, var(--brand) 12%, white), white 62%); }
.help-hero h1 { margin: 3px 0 8px; font-size: 28px; color: var(--t1); }
.help-hero p { margin: 0; max-width: 680px; color: var(--t2); line-height: 1.7; }
.help-eyebrow { margin: 0; color: var(--brand); font-size: 12px; font-weight: 800; letter-spacing: .08em; }
.help-metrics { display: grid; grid-template-columns: repeat(3, minmax(76px, 1fr)); gap: 10px; margin: 0; min-width: 270px; }
.help-metrics div { padding: 13px; border-radius: 14px; background: rgba(255,255,255,.82); border: 1px solid rgba(255,255,255,.9); }
.help-metrics dt { color: var(--t3); font-size: 11px; }
.help-metrics dd { margin: 5px 0 0; color: var(--t1); font-size: 22px; font-weight: 800; }
.help-quality { padding: 18px; border: 1px solid var(--dv); border-radius: 16px; background: linear-gradient(135deg, #f7faff, white); }
.help-quality__heading { display: flex; justify-content: space-between; gap: 18px; align-items: end; margin-bottom: 14px; }
.help-quality__heading h2 { margin: 4px 0 0; color: var(--t1); font-size: 18px; }
.help-quality__heading > small { max-width: 520px; color: var(--t3); line-height: 1.55; }
.help-quality__metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0; }
.help-quality__metrics div { padding: 14px; border: 1px solid var(--dv); border-radius: 12px; background: white; }
.help-quality__metrics dt { color: var(--t3); font-size: 11px; }
.help-quality__metrics dd { margin: 5px 0; color: var(--t1); font-size: 22px; font-weight: 850; }
.help-quality__metrics small { color: var(--t3); line-height: 1.45; }
.help-controls { display: grid; grid-template-columns: minmax(300px, 1fr) minmax(160px, .35fr) minmax(180px, .4fr) auto; gap: 12px; align-items: end; padding: 16px; border: 1px solid var(--dv); border-radius: 16px; background: var(--c0); }
.help-control { display: grid; gap: 6px; color: var(--t2); font-size: 12px; font-weight: 700; }
.help-control input,
.help-control select { width: 100%; min-height: 40px; padding: 0 12px; border: 1px solid var(--dv); border-radius: 10px; color: var(--t1); background: white; font: inherit; outline: none; }
.help-control input:focus,
.help-control select:focus { border-color: var(--brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand) 14%, transparent); }
.help-clear { min-height: 40px; padding: 0 15px; border: 1px solid var(--dv); border-radius: 10px; background: white; color: var(--t2); cursor: pointer; }
.help-notice { padding: 12px 14px; border-radius: 12px; border: 1px solid #f4c66f; background: #fff8e6; color: #7a4d00; }
.help-article,
.help-section-block,
.help-results { padding: 26px; border: 1px solid var(--dv); border-radius: 18px; background: white; }
.help-intents { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; }
.help-intent { display: grid; gap: 8px; min-height: 128px; padding: 18px; border: 1px solid var(--dv); border-radius: 16px; background: white; text-align: left; cursor: pointer; }
.help-intent:hover,
.help-intent.is-active { border-color: color-mix(in srgb, var(--brand) 52%, var(--dv)); background: color-mix(in srgb, var(--brand) 6%, white); box-shadow: 0 10px 24px rgba(20,53,90,.07); }
.help-intent span { color: var(--brand); font-size: 17px; font-weight: 850; }
.help-intent strong { color: var(--t1); font-size: 13px; line-height: 1.6; }
.help-intent small { color: var(--t3); line-height: 1.5; }
.help-back { border: 0; padding: 0; background: transparent; color: var(--brand); font-weight: 700; cursor: pointer; }
.help-article__header { padding: 18px 0 22px; border-bottom: 1px solid var(--dv); }
.help-article__header h2 { margin: 12px 0 10px; color: var(--t1); font-size: 27px; line-height: 1.3; }
.help-article__header > p { margin: 0; max-width: 820px; color: var(--t2); line-height: 1.75; }
.help-badges { display: flex; flex-wrap: wrap; gap: 7px; }
.help-badges span { padding: 5px 9px; border-radius: 999px; background: color-mix(in srgb, var(--brand) 9%, white); color: var(--brand); font-size: 11px; font-weight: 700; }
.help-entry { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-top: 18px; padding: 14px; border-radius: 12px; background: var(--c1); }
.help-entry div { display: grid; gap: 4px; }
.help-entry strong { color: var(--t1); }
.help-entry span { color: var(--t2); font-size: 13px; }
.help-entry button,
.help-related button,
.help-empty-state button { border: 0; border-radius: 9px; padding: 9px 13px; background: var(--brand); color: white; font-weight: 700; cursor: pointer; }
.help-section { padding: 22px 0; border-bottom: 1px solid var(--dv); }
.help-section h3 { margin: 0 0 12px; color: var(--t1); font-size: 17px; }
.help-section p,
.help-section li { color: var(--t2); line-height: 1.75; }
.help-section ul,
.help-section ol { margin: 0; padding-left: 22px; }
.help-section--tip { margin-top: 18px; padding: 18px; border: 1px solid #b9ddff; border-radius: 13px; background: #f2f8ff; }
.help-section--warning { margin-top: 18px; padding: 18px; border: 1px solid #f6cf7d; border-radius: 13px; background: #fff9eb; }
.help-section--success { margin-top: 18px; padding: 18px; border: 1px solid #b7e4c7; border-radius: 13px; background: #f1fbf5; }
.help-section--next { margin-top: 18px; padding: 18px; border: 1px solid #c9d7ff; border-radius: 13px; background: #f5f7ff; }
.help-section--admin { margin-top: 18px; padding: 18px; border: 1px solid #e3d5f5; border-radius: 13px; background: #fbf8ff; }
.help-task-steps { display: grid; gap: 12px; padding: 0 !important; list-style: none; }
.help-task-steps li { display: grid; grid-template-columns: 30px 1fr; gap: 12px; align-items: start; }
.help-task-steps li > span,
.help-flow__number { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--brand); color: white; font-size: 12px; font-weight: 800; }
.help-flow { display: grid; gap: 10px; padding: 0 !important; list-style: none; }
.help-flow li { display: grid; grid-template-columns: 32px 1fr; gap: 12px; padding: 14px; border: 1px solid var(--dv); border-radius: 12px; }
.help-flow strong { color: var(--t1); }
.help-flow small { margin-left: 8px; color: var(--brand); }
.help-flow p { margin: 5px 0 0; }
.help-faq { padding: 12px 0; border-top: 1px solid var(--dv); }
.help-faq summary { cursor: pointer; color: var(--t1); font-weight: 700; }
.help-faq p { margin-bottom: 0; }
.help-related { display: flex; flex-wrap: wrap; gap: 9px; }
.help-visual-intro { margin: 0 0 12px; color: var(--t3); }
.help-visual-gallery { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0 0 16px; }
.help-visual-card { display: grid; gap: 7px; min-width: 0; padding: 10px; border: 1px solid var(--dv); border-radius: 12px; color: var(--t2); text-decoration: none; background: var(--c1); transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease; }
.help-visual-card:hover { border-color: var(--brand); box-shadow: 0 8px 20px color-mix(in srgb, var(--brand) 14%, transparent); transform: translateY(-1px); }
.help-visual-card.is-primary { grid-column: 1 / -1; }
.help-visual-card img { width: 100%; max-height: 430px; object-fit: contain; border-radius: 8px; background: white; }
.help-visual-card span { color: var(--t1); font-weight: 750; }
.help-visual-card small { color: var(--t3); }
.help-visual-history { margin: 0 0 16px; padding: 12px; border: 1px dashed var(--dv); border-radius: 12px; }
.help-visual-history summary { cursor: pointer; color: var(--t2); font-weight: 700; }
.help-visual-history .help-visual-gallery { margin: 12px 0 0; }
.help-section--embed iframe { width: 100%; min-height: 680px; border: 1px solid var(--dv); border-radius: 13px; background: white; }
.help-feedback { display: flex; justify-content: space-between; gap: 18px; align-items: center; margin-top: 20px; padding: 16px; border: 1px solid var(--dv); border-radius: 13px; background: var(--c1); }
.help-feedback > div:first-child { display: grid; gap: 4px; }
.help-feedback strong { color: var(--t1); }
.help-feedback small { color: var(--t3); }
.help-feedback__actions { display: flex; gap: 8px; }
.help-feedback__actions button { border: 0; border-radius: 9px; padding: 9px 14px; background: var(--brand); color: white; font-weight: 750; cursor: pointer; }
.help-feedback__actions button.is-secondary { border: 1px solid var(--dv); background: white; color: var(--t2); }
.help-feedback__done { color: var(--brand); font-size: 12px; font-weight: 800; }
.help-article__footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; padding-top: 18px; color: var(--t3); font-size: 11px; }
.help-section-heading { display: flex; justify-content: space-between; gap: 18px; align-items: end; margin-bottom: 18px; }
.help-section-heading h2 { margin: 5px 0 0; color: var(--t1); }
.help-section-heading > p { max-width: 430px; margin: 0; color: var(--t3); line-height: 1.6; }
.help-card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
.help-card { display: grid; gap: 9px; min-height: 150px; padding: 18px; border: 1px solid var(--dv); border-radius: 14px; background: white; text-align: left; cursor: pointer; transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease; }
.help-card:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--brand) 45%, var(--dv)); box-shadow: 0 10px 24px rgba(20,53,90,.08); }
.help-card span { color: var(--brand); font-size: 11px; font-weight: 800; }
.help-card strong { color: var(--t1); font-size: 16px; }
.help-card p { margin: 0; color: var(--t2); font-size: 13px; line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.help-question-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.help-question { min-height: 48px; padding: 11px 14px; border: 1px solid var(--dv); border-radius: 12px; background: var(--c1); color: var(--t1); text-align: left; font-weight: 750; cursor: pointer; }
.help-question:hover { border-color: var(--brand); color: var(--brand); background: color-mix(in srgb, var(--brand) 6%, white); }
.help-journey-grid { display: grid; gap: 14px; }
.help-journey { padding: 18px; border: 1px solid var(--dv); border-radius: 15px; background: linear-gradient(180deg, #fff, #fbfcff); }
.help-journey header { display: grid; gap: 7px; margin-bottom: 14px; }
.help-journey header > div { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.help-journey header strong { color: var(--t1); font-size: 17px; }
.help-journey header span { color: var(--brand); font-size: 11px; font-weight: 800; }
.help-journey header p { margin: 0; color: var(--t2); line-height: 1.65; }
.help-journey-steps { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
.help-journey-steps li { display: flex; align-items: center; gap: 7px; }
.help-journey-steps li > span { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: color-mix(in srgb, var(--brand) 12%, white); color: var(--brand); font-size: 10px; font-weight: 800; }
.help-journey-steps button { border: 1px solid var(--dv); border-radius: 999px; padding: 7px 10px; background: white; color: var(--t2); cursor: pointer; font: inherit; font-size: 12px; }
.help-journey-steps button:hover { border-color: var(--brand); color: var(--brand); }
.help-diagnosis { display: grid; grid-template-columns: .7fr 1fr; gap: 24px; background: linear-gradient(135deg, #f7faff, white); }
.help-diagnosis h2 { margin: 5px 0 0; color: var(--t1); }
.help-diagnosis ol { margin: 0; padding-left: 20px; }
.help-diagnosis li { padding: 5px 0; color: var(--t2); line-height: 1.6; }
.help-empty-state { padding: 50px 24px; text-align: center; color: var(--t2); }
.help-empty-state h3 { color: var(--t1); }
.help-empty-state p { max-width: 620px; margin: 0 auto 18px; line-height: 1.7; }
@media (max-width: 900px) {
  .help-hero { flex-direction: column; }
  .help-metrics { min-width: 0; }
  .help-quality__heading { align-items: flex-start; flex-direction: column; }
  .help-quality__metrics { grid-template-columns: 1fr; }
  .help-controls { grid-template-columns: 1fr 1fr; }
  .help-control--search { grid-column: 1 / -1; }
  .help-intents { grid-template-columns: 1fr; }
  .help-card-grid,
  .help-question-grid { grid-template-columns: 1fr; }
  .help-diagnosis { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .help-hero,
  .help-article,
  .help-section-block,
  .help-results { padding: 18px; border-radius: 14px; }
  .help-controls { grid-template-columns: 1fr; }
  .help-control--search { grid-column: auto; }
  .help-metrics { grid-template-columns: 1fr; }
  .help-entry,
  .help-feedback,
  .help-section-heading,
  .help-journey header > div { align-items: flex-start; flex-direction: column; }
  .help-visual-gallery { grid-template-columns: 1fr; }
  .help-visual-card.is-primary { grid-column: auto; }
  .help-visual-card img { max-height: 310px; }
  .help-section--embed iframe { min-height: 520px; }
}
</style>

