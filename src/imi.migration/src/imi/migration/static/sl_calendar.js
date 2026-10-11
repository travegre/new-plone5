/* Slovenian date picker: display DD.MM.YYYY, submit unchanged ISO dates. */
(function () {
  'use strict';
  var months = ['januar','februar','marec','april','maj','junij','julij','avgust','september','oktober','november','december'];
  var weekdays = ['Po','To','Sr','Če','Pe','So','Ne'];
  var active = null;
  var calendarCounter = 0;
  function pad(n) { return String(n).padStart(2, '0'); }
  function iso(d) { return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()); }
  function display(s) { var m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(s || ''); return m ? m[3]+'.'+m[2]+'.'+m[1] : ''; }
  function parse(s) {
    var m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})\.?$/.exec((s || '').trim());
    if (!m) return null;
    var y=+m[3], mo=+m[2], day=+m[1], d=new Date(y,mo-1,day);
    return d.getFullYear()===y && d.getMonth()===mo-1 && d.getDate()===day ? d : null;
  }
  function close() { if(active) { active.remove(); active=null; } }
  function position(panel, anchor) {
    var rect=anchor.getBoundingClientRect(), width=270, height=305;
    var left=Math.max(8,Math.min(rect.left,window.innerWidth-width-8));
    var top=rect.bottom+5;
    if(top+height>window.innerHeight && rect.top>height)top=rect.top-height-5;
    panel.style.left=left+'px';panel.style.top=Math.max(8,top)+'px';
  }
  function render(panel, input, original, year, month) {
    panel.textContent = '';
    var head=document.createElement('div'); head.className='imi-calendar-head';
    function nav(label, delta) {
      var b=document.createElement('button'); b.type='button'; b.textContent=label;
      b.addEventListener('click',function(){ var d=new Date(year,month+delta,1);render(panel,input,original,d.getFullYear(),d.getMonth()); });
      head.appendChild(b);
    }
    nav('‹',-1);
    var caption=document.createElement('span');caption.className='imi-calendar-caption';
    var monthLabel=document.createElement('strong');monthLabel.textContent=months[month];caption.appendChild(monthLabel);
    var yearSelect=document.createElement('select');yearSelect.className='imi-calendar-year';yearSelect.setAttribute('aria-label','Leto');
    for(var y=year-20;y<=year+20;y++){
      var option=document.createElement('option');option.value=String(y);option.textContent=String(y);
      if(y===year)option.selected=true;
      yearSelect.appendChild(option);
    }
    yearSelect.addEventListener('change',function(e){e.stopPropagation();render(panel,input,original,+yearSelect.value,month);});
    caption.appendChild(yearSelect);head.appendChild(caption);
    nav('›',1);panel.appendChild(head);
    var grid=document.createElement('div');grid.className='imi-calendar-grid';
    weekdays.forEach(function(w){var c=document.createElement('span');c.className='imi-calendar-weekday';c.textContent=w;grid.appendChild(c);});
    var first=(new Date(year,month,1).getDay()+6)%7;
    for(var i=0;i<first;i++)grid.appendChild(document.createElement('span'));
    var length=new Date(year,month+1,0).getDate();
    for(var day=1;day<=length;day++){
      (function(day){
        var d=new Date(year,month,day), b=document.createElement('button');b.type='button';b.textContent=day;
        var today=iso(new Date());
        if(iso(d)===(original.value || today))b.className='imi-calendar-selected';
        if((original.min && iso(d)<original.min)||(original.max && iso(d)>original.max))b.disabled=true;
        b.addEventListener('click',function(){
          original.value=iso(d);input.value=display(original.value);input.setCustomValidity('');
          original.dispatchEvent(new Event('input',{bubbles:true}));
          original.dispatchEvent(new Event('change',{bubbles:true}));
          input.dispatchEvent(new Event('change',{bubbles:true}));close();
        });grid.appendChild(b);
      })(day);
    }
    panel.appendChild(grid);
  }
  function enhance(original) {
    if(original.dataset.imiCalendar || original.disabled)return;
    original.dataset.imiCalendar='1';
    original.dataset.imiCalendarId='imi-date-'+(++calendarCounter);
    var wrapper=document.createElement('span');wrapper.className='imi-date-wrapper';
    var input=document.createElement('input');input.type='text';input.className=(original.className || '')+' imi-date-display';
    input.placeholder='DD.MM.LLLL';input.setAttribute('aria-label',original.getAttribute('aria-label') || 'Datum (DD.MM.LLLL)');
    input.autocomplete='off';input.value=display(original.value);input.required=original.required;
    var button=document.createElement('button');button.type='button';button.className='imi-date-trigger';button.textContent='▦';button.title='Odpri koledar';button.setAttribute('aria-label','Odpri koledar');
    original.parentNode.insertBefore(wrapper,original);wrapper.appendChild(input);wrapper.appendChild(button);
    wrapper.appendChild(original);original.classList.add('imi-date-original');original.tabIndex=-1;original.required=false;
    function sync() {
      var raw=input.value.trim();
      if(!raw){original.value='';input.setCustomValidity(input.required?'Vnesite datum.':'');return;}
      var d=parse(raw), value=d && iso(d);
      if(!value || (original.min && value<original.min)||(original.max && value>original.max)){
        original.value='';input.setCustomValidity('Vnesite veljaven datum v obliki DD.MM.LLLL.');return;
      }
      original.value=value;input.setCustomValidity('');
    }
    input.addEventListener('input',sync);
    input.addEventListener('blur',function(){sync();if(original.value)input.value=display(original.value);});
    original.addEventListener('change',function(){input.value=display(original.value);input.setCustomValidity('');});
    button.addEventListener('click',function(e){
      e.stopPropagation();if(active && active.dataset.owner===original.dataset.imiCalendarId){close();return;}close();
      var panel=document.createElement('div');panel.className='imi-calendar-popup';panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Izbira datuma');
      panel.dataset.owner=original.dataset.imiCalendarId;
      document.body.appendChild(panel);active=panel;
      position(panel,button);
      // Keep calendar navigation clicks from triggering document or Plone handlers.
      panel.addEventListener('click',function(event){event.stopPropagation();});
      panel.addEventListener('mousedown',function(event){event.stopPropagation();});
      var d=parse(input.value) || (original.value && parse(display(original.value))) || new Date();
      render(panel,input,original,d.getFullYear(),d.getMonth());
    });
    if(original.form)original.form.addEventListener('submit',function(e){
      sync();if(!input.checkValidity()){e.preventDefault();input.reportValidity();}
    });
  }
  document.addEventListener('click',function(e){
    if(active && !active.contains(e.target) && !e.target.closest('.imi-date-trigger'))close();
  });
  document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
  window.addEventListener('resize',close);
  window.addEventListener('scroll',close,true);
  function init(){document.querySelectorAll('input[type="date"]:not([data-imi-calendar])').forEach(enhance);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
  new MutationObserver(function(){init();}).observe(document.documentElement,{childList:true,subtree:true});
})();
