from pathlib import Path

path = Path('frontend/src/layouts/BasePortalLayout.vue')
text = path.read_text(encoding='utf-8')
old = '''        <div class="bpl-thdots" title="主题皮肤 themePreference">
          <span
            v-for="t in themeOptions"
            :key="t.key"
            class="bpl-thdot"
            :class="['bpl-thdot--' + t.key, { 'is-on': theme === t.key }]"
            :title="t.label"
            @click="setTheme(t.key)"
          />
        </div>'''
new = '''        <div class="bpl-thdots" role="group" aria-label="界面主题">
          <button
            v-for="t in themeOptions"
            :key="t.key"
            type="button"
            class="bpl-thdot"
            :class="['bpl-thdot--' + t.key, { 'is-on': theme === t.key }]"
            :title="t.label"
            :aria-label="`切换到${t.label}主题`"
            :aria-pressed="theme === t.key"
            @click="setTheme(t.key)"
          />
        </div>'''
if old in text:
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
elif new not in text:
    raise SystemExit('theme-control block does not match the audited baseline')
