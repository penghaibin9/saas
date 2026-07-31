(function () {
  'use strict';

  const ICON_FROM = '../../shared/icons.svg#';
  const ICON_TO = '../shared/icons.svg#';
  const ROUTES = new Map([
    ['学工工作台', '/admin/student-affairs/dashboard'],
    ['学生主档', '/admin/student/list'],
    ['班级与辅导员', '/admin/campus-service/classes'],
    ['数字迎新', '/admin/orientation'],
    ['请假销假', '/admin/student-affairs/leave'],
    ['宿舍与公寓', '/admin/student-affairs/dorm/exception'],
    ['风险预警与处置', '/admin/student-affairs/risk'],
    ['困难认定', '/admin/student-affairs/aid'],
    ['奖助勤贷补', '/admin/student-affairs/funding'],
    ['违纪处分', '/admin/student-affairs/discipline'],
    ['谈心谈话与家校协同', '/admin/student-affairs/talk'],
    ['心理关注', '/admin/student-affairs/mental'],
    ['活动与第二课堂', '/admin/student-affairs/activity'],
    ['统计与档案', '/admin/student-affairs/stats']
  ]);
  const openerByOverlay = new WeakMap();

  function queryAll(root, selector) {
    const items = [];
    if (root instanceof Element && root.matches(selector)) items.push(root);
    if (root.querySelectorAll) items.push(...root.querySelectorAll(selector));
    return items;
  }

  function patchIcons(root) {
    queryAll(root, 'use[href]').forEach((use) => {
      const href = use.getAttribute('href') || '';
      if (href.startsWith(ICON_FROM)) {
        use.setAttribute('href', `${ICON_TO}${href.slice(ICON_FROM.length)}`);
      }
    });
  }

  function patchButtons(root) {
    queryAll(root, 'button:not([type])').forEach((button) => {
      button.setAttribute('type', 'button');
    });
  }

  function patchSideLinks(root) {
    queryAll(root, '.v2-side-nav a').forEach((link) => {
      const label = (link.textContent || '').trim();
      const route = ROUTES.get(label);
      if (!route) return;
      link.setAttribute('href', route);
      link.dataset.productionRoute = route;
    });
  }

  function patchDialogs(root) {
    queryAll(root, '.v2-drawer-backdrop[id], .v2-modal-backdrop[id]').forEach((overlay) => {
      const dialog = overlay.querySelector('[role="dialog"]');
      if (!dialog) return;
      if (!dialog.hasAttribute('tabindex')) dialog.setAttribute('tabindex', '-1');
      const title = dialog.querySelector('h1, h2, h3');
      if (!title) return;
      if (!title.id) title.id = `${overlay.id}-title`;
      dialog.setAttribute('aria-labelledby', title.id);
    });
  }

  function patch(root) {
    patchIcons(root);
    patchButtons(root);
    patchSideLinks(root);
    patchDialogs(root);
  }

  function openOverlays() {
    return [...document.querySelectorAll('.v2-drawer-backdrop.open, .v2-modal-backdrop.open')];
  }

  function topOverlay() {
    const items = openOverlays();
    return items[items.length - 1] || null;
  }

  function focusableElements(overlay) {
    if (!overlay) return [];
    return [...overlay.querySelectorAll([
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ].join(','))].filter((element) => {
      if (!(element instanceof HTMLElement)) return false;
      if (element.hidden || element.getAttribute('aria-hidden') === 'true') return false;
      return element.getClientRects().length > 0;
    });
  }

  function focusDialog(overlay) {
    if (!overlay || !overlay.classList.contains('open')) return;
    const dialog = overlay.querySelector('[role="dialog"]');
    if (!dialog) return;
    const [first] = focusableElements(overlay);
    (first || dialog).focus({ preventScroll: true });
  }

  function restoreFocus(overlay) {
    const opener = overlay ? openerByOverlay.get(overlay) : null;
    if (opener instanceof HTMLElement && opener.isConnected) {
      opener.focus({ preventScroll: true });
    }
  }

  function closeOverlay(overlay) {
    if (!overlay) return;
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    restoreFocus(overlay);
  }

  const observer = new MutationObserver((records) => {
    records.forEach((record) => {
      record.addedNodes.forEach((node) => {
        if (node instanceof Element) patch(node);
      });
    });
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
  patch(document);

  document.addEventListener('click', (event) => {
    const opener = event.target.closest?.('[data-open]');
    if (opener) {
      const overlay = document.getElementById(opener.dataset.open || '');
      if (overlay) {
        openerByOverlay.set(overlay, opener);
        queueMicrotask(() => focusDialog(overlay));
      }
      return;
    }

    const closer = event.target.closest?.('[data-close]');
    if (closer) {
      const overlay = closer.closest('.v2-drawer-backdrop, .v2-modal-backdrop');
      if (overlay) queueMicrotask(() => restoreFocus(overlay));
      return;
    }

    const overlay = event.target.closest?.('.v2-drawer-backdrop.open, .v2-modal-backdrop.open');
    if (overlay && event.target === overlay) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeOverlay(overlay);
    }
  }, true);

  document.addEventListener('keydown', (event) => {
    const overlay = topOverlay();
    if (!overlay) return;

    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeOverlay(overlay);
      return;
    }

    if (event.key !== 'Tab') return;
    const focusable = focusableElements(overlay);
    if (!focusable.length) {
      event.preventDefault();
      focusDialog(overlay);
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || !overlay.contains(active))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }, true);
})();
