(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
  const storage={
    get(key){try{return window.localStorage.getItem(key)}catch(_){return null}},
    set(key,value){try{window.localStorage.setItem(key,value)}catch(_){/* local file / sandbox preview may deny storage */}}
  };
  window.V2Prototype={
    setTheme(theme){const value=theme||'academy';document.body.dataset.theme=value;storage.set('teacher-pc-v2-theme',value)},
    setState(state){
      $$('[data-prototype-state]').forEach(el=>el.classList.toggle('active',el.dataset.prototypeState===state));
      $$('[data-state-button]').forEach(el=>el.classList.toggle('active',el.dataset.stateButton===state));
    },
    open(id){const el=document.getElementById(id);if(el){el.classList.add('open');el.setAttribute('aria-hidden','false')}},
    close(id){const el=document.getElementById(id);if(el){el.classList.remove('open');el.setAttribute('aria-hidden','true')}}
  };
  document.body.dataset.theme=storage.get('teacher-pc-v2-theme')||'academy';
  document.addEventListener('click',e=>{
    const theme=e.target.closest('[data-theme-value]'); if(theme) V2Prototype.setTheme(theme.dataset.themeValue);
    const state=e.target.closest('[data-state-button]'); if(state) V2Prototype.setState(state.dataset.stateButton);
    const tab=e.target.closest('[data-tab]'); if(tab){
      const scope=tab.closest('[data-tab-scope]')||document;
      $$('[data-tab]',scope).forEach(x=>x.classList.remove('active'));tab.classList.add('active');
      $$('[data-tab-panel]',scope).forEach(x=>x.hidden=x.dataset.tabPanel!==tab.dataset.tab);
    }
    const open=e.target.closest('[data-open]'); if(open) V2Prototype.open(open.dataset.open);
    const close=e.target.closest('[data-close]'); if(close) V2Prototype.close(close.dataset.close);
    if(e.target.classList.contains('v2-modal-backdrop') && e.target.id) V2Prototype.close(e.target.id);
  });
  document.addEventListener('keydown',e=>{if(e.key==='Escape')$$('.v2-modal-backdrop.open').forEach(el=>V2Prototype.close(el.id))});
})();
