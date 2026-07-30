(function () {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const storage = {
    get(key) {
      try { return window.localStorage.getItem(key); } catch (_) { return null; }
    },
    set(key, value) {
      try { window.localStorage.setItem(key, value); } catch (_) { /* file:// previews may deny storage */ }
    }
  };

  const ACADEMIC_MODULES = [
    ['dashboard', '教务看板', '/admin/academic-affairs', '../dashboard/index.html'],
    ['terms', '学年学期', '/admin/academic-affairs/terms', '../terms-calendar/term-list.html'],
    ['calendar', '校历节次', '/admin/academic-affairs/calendar', '../terms-calendar/calendar-events.html'],
    ['roster', '学籍管理', '/admin/academic-affairs/roster', '../roster/roster-list.html'],
    ['registration', '注册管理', '/admin/academic-affairs/registration', '../registration/registration-batches.html'],
    ['major-split', '专业分流', '/admin/academic-affairs/major-split', ''],
    ['status-changes', '学籍异动', '/admin/academic-affairs/status-changes', '../status-changes/status-change-ledger.html'],
    ['orgs', '学院专业班级', '/admin/academic-affairs/orgs', '../orgs/org-college.html'],
    ['programs', '培养方案', '/admin/academic-affairs/programs', '../programs/program-authoring.html'],
    ['courses', '课程库', '/admin/academic-affairs/courses', '../courses/course-list.html'],
    ['teaching-plan', '教学计划', '/admin/academic-affairs/programs', '../programs/program-practice-plan.html'],
    ['teaching-tasks', '教学任务', '/admin/academic-affairs/teaching-tasks', '../teaching-tasks/task-workbench.html'],
    ['scheduling', '排课管理', '/admin/academic-affairs/scheduling', ''],
    ['schedule', '课表管理', '/admin/academic-affairs/schedule', '../schedule/schedule-batches.html'],
    ['schedule-change', '调停课', '/admin/academic-affairs/schedule-change', '../schedule-change/schedule-change-ledger.html'],
    ['attendance', '课堂考勤', '/admin/academic-affairs/attendance-stats', ''],
    ['selection', '选课管理', '/admin/academic-affairs/selection', '../selection/selection-batches.html'],
    ['exam', '考务管理', '/admin/academic-affairs/exam', '../exam/exam-batches.html'],
    ['makeup', '补考重修缓考免修', '/admin/academic-affairs/makeup', ''],
    ['grades', '成绩管理', '/admin/academic-affairs/grade-overview', '../grades/grade-overview.html'],
    ['grade-review', '成绩审核发布更正', '/admin/academic-affairs/grade-college-review', '../grades/grade-college-review.html'],
    ['warnings', '学业预警', '/admin/academic-affairs/warnings', ''],
    ['graduation', '毕业资格审核', '/admin/academic-affairs/graduation', ''],
    ['textbooks', '教材管理', '/admin/academic-affairs/textbooks', ''],
    ['resources', '教学资源', '/admin/academic-affairs/classrooms', ''],
    ['evaluation', '教学评价', '/admin/academic-affairs/evaluation', ''],
    ['quality', '教学质量', '/admin/academic-affairs/quality', ''],
    ['archive', '教务归档', '/admin/academic-affairs/archive', ''],
    ['stats', '教务统计', '/admin/academic-affairs/stats', '']
  ].map(([key, label, route, prototype]) => ({ key, label, route, prototype }));

  function currentAcademicModule() {
    const path = String(window.location.pathname || '').replace(/\\/g, '/');
    const file = path.split('/').pop() || '';
    if (path.includes('/dashboard/')) return 'dashboard';
    if (path.includes('/terms-calendar/')) {
      return /^(calendar-|time-)/.test(file) ? 'calendar' : 'terms';
    }
    if (path.includes('/roster/')) return 'roster';
    if (path.includes('/registration/')) return 'registration';
    if (path.includes('/status-changes/')) return 'status-changes';
    if (path.includes('/orgs/')) return 'orgs';
    if (path.includes('/programs/')) return 'programs';
    if (path.includes('/courses/')) return 'courses';
    if (path.includes('/teaching-tasks/')) return 'teaching-tasks';
    if (path.includes('/schedule-change/')) return 'schedule-change';
    if (path.includes('/schedule/')) return 'schedule';
    if (path.includes('/selection/')) return 'selection';
    if (path.includes('/exam/')) return 'exam';
    if (path.includes('/grades/')) {
      return /grade-(audit|change|college-review|publish|recheck)/.test(file) ? 'grade-review' : 'grades';
    }
    return 'dashboard';
  }

  function showPrototypeToast(message) {
    let toast = $('.v2-prototype-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'v2-prototype-toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('is-visible');
    window.clearTimeout(showPrototypeToast._timer);
    showPrototypeToast._timer = window.setTimeout(() => toast.classList.remove('is-visible'), 3200);
  }

  function renderAcademicNavigation() {
    const sidebar = $('.v2-sidebar');
    if (!sidebar || !window.location.pathname.includes('/academic-affairs/')) return;

    const activeKey = currentAcademicModule();
    const active = ACADEMIC_MODULES.find(item => item.key === activeKey) || ACADEMIC_MODULES[0];
    const collapsed = storage.get('teacher-pc-v2-sidebar-collapsed') === '1';

    sidebar.classList.toggle('is-collapsed', collapsed);
    sidebar.innerHTML = `
      <div class="v2-side-heading">
        <div class="v2-side-heading-copy">
          <h1 class="v2-side-title">教务中心</h1>
          <p class="v2-side-sub">真实二级模块 · 与 navPlan 顺序一致</p>
        </div>
        <button type="button" class="v2-side-collapse-btn" data-v2-sidebar-toggle aria-label="${collapsed ? '展开左侧菜单' : '收起左侧菜单'}" aria-expanded="${collapsed ? 'false' : 'true'}">${collapsed ? '›' : '‹'}</button>
      </div>
      <label class="v2-side-search-wrap">
        <span class="v2-visually-hidden">搜索二级模块</span>
        <input class="v2-side-search" type="search" placeholder="搜索二级模块" autocomplete="off" data-v2-side-search />
      </label>
      <nav class="v2-side-nav v2-side-nav--direct" aria-label="教务中心二级模块">
        ${ACADEMIC_MODULES.map((item, index) => {
          const available = Boolean(item.prototype);
          return `<a
            class="${item.key === activeKey ? 'active' : ''}${available ? '' : ' is-prototype-pending'}"
            ${available ? `href="${item.prototype}"` : 'href="#"'}
            data-v2-module-key="${item.key}"
            data-v2-module-label="${item.label}"
            data-v2-route="${item.route}"
            ${available ? '' : 'data-v2-prototype-pending="true"'}
            title="${item.label} · ${item.route}${available ? '' : ' · 原型待覆盖'}"
            ${item.key === activeKey ? 'aria-current="page"' : ''}
          ><span class="v2-nav-index" aria-hidden="true">${String(index + 1).padStart(2, '0')}</span><span class="v2-nav-label">${item.label}</span>${available ? '' : '<span class="v2-nav-badge">原型待覆盖</span>'}</a>`;
        }).join('')}
      </nav>
      <div class="v2-side-search-empty" data-v2-side-empty hidden>没有匹配的二级模块</div>
    `;

    const layout = $('.v2-layout');
    if (layout) layout.classList.toggle('is-sidebar-collapsed', collapsed);

    const nav = $('.v2-side-nav', sidebar);
    const savedScroll = Number(storage.get('teacher-pc-v2-sidebar-scroll') || 0);
    if (nav && savedScroll > 0) nav.scrollTop = savedScroll;

    const breadcrumb = $('.v2-breadcrumb');
    const tertiary = (window.V2_PAGE && window.V2_PAGE.title) || document.title.replace(/\s*V2\s*$/i, '') || '当前功能';
    if (breadcrumb) {
      breadcrumb.innerHTML = `<span>教务中心</span><span aria-hidden="true">/</span><span>${active.label}</span><span aria-hidden="true">/</span><strong>${tertiary}</strong>`;
      breadcrumb.setAttribute('aria-label', '面包屑');
    }
  }

  function bindAcademicNavigation() {
    const sidebar = $('.v2-sidebar');
    if (!sidebar || !window.location.pathname.includes('/academic-affairs/')) return;

    if (sidebar.dataset.v2NavBound === '1') return;
    sidebar.dataset.v2NavBound = '1';

    const nav = $('.v2-side-nav', sidebar);
    const search = $('[data-v2-side-search]', sidebar);
    const empty = $('[data-v2-side-empty]', sidebar);

    if (search && nav) {
      search.addEventListener('input', () => {
        const query = search.value.trim().toLowerCase();
        let visible = 0;
        $$('a[data-v2-module-label]', nav).forEach(link => {
          const haystack = `${link.dataset.v2ModuleLabel} ${link.dataset.v2Route}`.toLowerCase();
          const matched = !query || haystack.includes(query);
          link.hidden = !matched;
          if (matched) visible += 1;
        });
        if (empty) empty.hidden = visible > 0;
      });
      search.addEventListener('keydown', event => {
        if (event.key !== 'Enter') return;
        const first = $$('a[data-v2-module-label]', nav).find(link => !link.hidden);
        if (first) { event.preventDefault(); first.click(); }
      });
    }

    sidebar.addEventListener('click', event => {
      const toggle = event.target.closest('[data-v2-sidebar-toggle]');
      if (toggle) {
        const nextCollapsed = !sidebar.classList.contains('is-collapsed');
        sidebar.classList.toggle('is-collapsed', nextCollapsed);
        const layout = $('.v2-layout');
        if (layout) layout.classList.toggle('is-sidebar-collapsed', nextCollapsed);
        toggle.textContent = nextCollapsed ? '›' : '‹';
        toggle.setAttribute('aria-expanded', nextCollapsed ? 'false' : 'true');
        toggle.setAttribute('aria-label', nextCollapsed ? '展开左侧菜单' : '收起左侧菜单');
        storage.set('teacher-pc-v2-sidebar-collapsed', nextCollapsed ? '1' : '0');
        return;
      }

      const pending = event.target.closest('[data-v2-prototype-pending]');
      if (pending) {
        event.preventDefault();
        showPrototypeToast(`${pending.dataset.v2ModuleLabel}：生产路由为 ${pending.dataset.v2Route}，当前尚未制作独立高保真 HTML，不伪装为已覆盖。`);
      }
    });

    if (nav) {
      nav.addEventListener('scroll', () => storage.set('teacher-pc-v2-sidebar-scroll', String(nav.scrollTop)), { passive: true });
    }
  }

  function enhanceGenericSidebar() {
    const sidebar = $('.v2-sidebar');
    if (!sidebar || window.location.pathname.includes('/academic-affairs/')) return;
    if (sidebar.dataset.v2GenericEnhanced === '1') return;
    sidebar.dataset.v2GenericEnhanced = '1';

    const title = $('.v2-side-title', sidebar);
    const subtitle = $('.v2-side-sub', sidebar);
    const nav = $('.v2-side-nav', sidebar);
    if (!nav) return;

    const heading = document.createElement('div');
    heading.className = 'v2-side-heading';
    const copy = document.createElement('div');
    copy.className = 'v2-side-heading-copy';
    if (title) copy.appendChild(title);
    if (subtitle) copy.appendChild(subtitle);
    heading.appendChild(copy);

    const collapsed = storage.get('teacher-pc-v2-generic-sidebar-collapsed') === '1';
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'v2-side-collapse-btn';
    toggle.dataset.v2SidebarToggle = '';
    toggle.textContent = collapsed ? '›' : '‹';
    toggle.setAttribute('aria-label', collapsed ? '展开左侧菜单' : '收起左侧菜单');
    toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    heading.appendChild(toggle);
    sidebar.insertBefore(heading, nav);

    const oldCollapse = $('.v2-collapse', sidebar);
    if (oldCollapse) oldCollapse.remove();

    const searchWrap = document.createElement('label');
    searchWrap.className = 'v2-side-search-wrap';
    searchWrap.innerHTML = '<span class="v2-visually-hidden">搜索当前中心模块</span><input class="v2-side-search" type="search" placeholder="搜索当前中心模块" autocomplete="off" data-v2-side-search />';
    sidebar.insertBefore(searchWrap, nav);

    $$('a', nav).forEach((link, index) => {
      const labelNode = $('span', link);
      const label = (labelNode ? labelNode.textContent : link.textContent || '').trim();
      if (labelNode) labelNode.classList.add('v2-nav-label');
      link.dataset.v2ModuleLabel = label;
      link.title = label;
      link.setAttribute('data-v2-generic-module', String(index + 1));
    });

    const empty = document.createElement('div');
    empty.className = 'v2-side-search-empty';
    empty.dataset.v2SideEmpty = '';
    empty.hidden = true;
    empty.textContent = '没有匹配的模块';
    sidebar.appendChild(empty);

    const layout = $('.v2-layout');
    sidebar.classList.toggle('is-collapsed', collapsed);
    if (layout) layout.classList.toggle('is-sidebar-collapsed', collapsed);

    const savedScroll = Number(storage.get('teacher-pc-v2-generic-sidebar-scroll') || 0);
    if (savedScroll > 0) nav.scrollTop = savedScroll;

    const search = $('[data-v2-side-search]', sidebar);
    search.addEventListener('input', () => {
      const query = search.value.trim().toLowerCase();
      let visible = 0;
      $$('a[data-v2-module-label]', nav).forEach(link => {
        const matched = !query || link.dataset.v2ModuleLabel.toLowerCase().includes(query);
        link.hidden = !matched;
        if (matched) visible += 1;
      });
      empty.hidden = visible > 0;
    });
    search.addEventListener('keydown', event => {
      if (event.key !== 'Enter') return;
      const first = $$('a[data-v2-module-label]', nav).find(link => !link.hidden);
      if (first) { event.preventDefault(); first.click(); }
    });

    toggle.addEventListener('click', () => {
      const nextCollapsed = !sidebar.classList.contains('is-collapsed');
      sidebar.classList.toggle('is-collapsed', nextCollapsed);
      if (layout) layout.classList.toggle('is-sidebar-collapsed', nextCollapsed);
      toggle.textContent = nextCollapsed ? '›' : '‹';
      toggle.setAttribute('aria-expanded', nextCollapsed ? 'false' : 'true');
      toggle.setAttribute('aria-label', nextCollapsed ? '展开左侧菜单' : '收起左侧菜单');
      storage.set('teacher-pc-v2-generic-sidebar-collapsed', nextCollapsed ? '1' : '0');
    });
    nav.addEventListener('scroll', () => storage.set('teacher-pc-v2-generic-sidebar-scroll', String(nav.scrollTop)), { passive: true });
  }

  function enhanceExamTabs() {
    if (!window.location.pathname.includes('/academic-affairs/exam/')) return;
    const targets = {
      '考试批次': 'exam-batches.html',
      '考试课程': 'exam-courses.html',
      '自动排考': 'exam-auto-arrange.html',
      '冲突处理': 'exam-conflicts.html',
      '考场与座位': 'exam-rooms-seats.html',
      '监考与巡考': 'exam-invigilators.html',
      '发布前核验': 'exam-publish-precheck.html',
      '异常记录': 'exam-incidents.html',
      '考务统计': 'exam-stats.html',
      '考务归档': 'exam-archive.html'
    };
    $$('.v2-workspace-tabs .v2-workspace-tab').forEach(tab => {
      const label = (tab.textContent || '').trim();
      const href = targets[label];
      if (!href || tab.tagName === 'A') return;
      const link = document.createElement('a');
      link.className = tab.className;
      link.href = href;
      link.textContent = label;
      if (tab.classList.contains('active')) link.setAttribute('aria-current', 'page');
      tab.replaceWith(link);
    });
  }

  function enhanceSharedStates() {
    $$('[data-state-button="unauthorized"]').forEach(button => {
      if (/只读/.test(button.textContent || '')) button.textContent = '403 / 只读';
      button.title = '预览无权限或只读边界；生产权限以后端裁决为准';
    });
    $$('.v2-workspace-tabs').forEach(tabs => {
      tabs.setAttribute('role', 'tablist');
      tabs.setAttribute('aria-label', '三级功能');
      $$('.v2-workspace-tab', tabs).forEach(tab => {
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-selected', tab.classList.contains('active') ? 'true' : 'false');
        tab.setAttribute('tabindex', tab.classList.contains('active') ? '0' : '-1');
      });
    });
  }

  window.V2Prototype = {
    setTheme(theme) {
      const value = theme || 'academy';
      document.body.dataset.theme = value;
      storage.set('teacher-pc-v2-theme', value);
    },
    setState(state) {
      $$('[data-prototype-state]').forEach(el => el.classList.toggle('active', el.dataset.prototypeState === state));
      $$('[data-state-button]').forEach(el => el.classList.toggle('active', el.dataset.stateButton === state));
    },
    open(id) {
      const el = document.getElementById(id);
      if (el) { el.classList.add('open'); el.setAttribute('aria-hidden', 'false'); }
    },
    close(id) {
      const el = document.getElementById(id);
      if (el) { el.classList.remove('open'); el.setAttribute('aria-hidden', 'true'); }
    }
  };

  function initEnhancements() {
    document.body.dataset.theme = storage.get('teacher-pc-v2-theme') || 'academy';
    renderAcademicNavigation();
    bindAcademicNavigation();
    enhanceGenericSidebar();
    enhanceExamTabs();
    enhanceSharedStates();
  }

  initEnhancements();
  if (!$('.v2-sidebar')) {
    const observer = new MutationObserver(() => {
      if (!$('.v2-sidebar')) return;
      observer.disconnect();
      initEnhancements();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    window.addEventListener('v2:page-ready', initEnhancements, { once: true });
  }

  document.addEventListener('click', event => {
    const theme = event.target.closest('[data-theme-value]');
    if (theme) window.V2Prototype.setTheme(theme.dataset.themeValue);

    const state = event.target.closest('[data-state-button]');
    if (state) window.V2Prototype.setState(state.dataset.stateButton);

    const tab = event.target.closest('[data-tab]');
    if (tab) {
      const scope = tab.closest('[data-tab-scope]') || document;
      $$('[data-tab]', scope).forEach(item => item.classList.remove('active'));
      tab.classList.add('active');
      $$('[data-tab-panel]', scope).forEach(panel => { panel.hidden = panel.dataset.tabPanel !== tab.dataset.tab; });
    }

    const open = event.target.closest('[data-open]');
    if (open) window.V2Prototype.open(open.dataset.open);
    const close = event.target.closest('[data-close]');
    if (close) window.V2Prototype.close(close.dataset.close);
    if (event.target.classList.contains('v2-modal-backdrop') && event.target.id) window.V2Prototype.close(event.target.id);
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') $$('.v2-modal-backdrop.open,.v2-drawer-backdrop.open').forEach(el => window.V2Prototype.close(el.id));
  });
})();
