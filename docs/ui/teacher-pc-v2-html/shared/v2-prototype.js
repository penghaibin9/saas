(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
  window.V2Prototype={
    setTheme(theme){document.body.dataset.theme=theme||'academy';localStorage.setItem('teacher-pc-v2-theme',theme||'academy')},
    setState(state){
      $$('[data-prototype-state]').forEach(el=>el.classList.toggle('active',el.dataset.prototypeState===state));
      $$('[data-state-button]').forEach(el=>el.classList.toggle('active',el.dataset.stateButton===state));
    }
  };
  document.body.dataset.theme=localStorage.getItem('teacher-pc-v2-theme')||'academy';
  document.addEventListener('click',e=>{
    const theme=e.target.closest('[data-theme-value]'); if(theme) V2Prototype.setTheme(theme.dataset.themeValue);
    const state=e.target.closest('[data-state-button]'); if(state) V2Prototype.setState(state.dataset.stateButton);
    const tab=e.target.closest('[data-tab]'); if(tab){
      const scope=tab.closest('[data-tab-scope]')||document;
      $$('[data-tab]',scope).forEach(x=>x.classList.remove('active'));tab.classList.add('active');
      $$('[data-tab-panel]',scope).forEach(x=>x.hidden=x.dataset.tabPanel!==tab.dataset.tab);
    }
  });
})();
