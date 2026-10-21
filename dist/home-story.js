/* A single animation owns desktop wheel motion. Native touch, keyboard and nested
   scrollers keep their normal behavior. Section changes use actual page distance. */
(() => {
  const desktop = matchMedia('(min-width:1100px) and (min-height:680px)');
  const reduced = matchMedia('(prefers-reduced-motion:reduce)');
  const screens = [...document.querySelectorAll('.hero,.story-screen')];
  const hero = document.querySelector('.hero-copy');
  const headings = [...document.querySelectorAll('.story-screen .section-heading,.river-heading')];
  const visualOffsets = new WeakMap();
  let anchors = [], frame = 0, visualFrame = 0;
  let position = scrollY, target = scrollY, velocity = 0, lastFrame = 0;
  let committed = false, direction = 0, lastWheel = -Infinity;
  const clamp = (n,min,max) => Math.max(min,Math.min(max,n));
  const enabled = () => desktop.matches && !reduced.matches;
  const maxScroll = () => Math.max(0,document.documentElement.scrollHeight-innerHeight);

  function measure() {
    anchors = screens.flatMap(screen => {
      const top = screen.getBoundingClientRect().top + scrollY;
      // Tall sections must be readable to their bottom before the next transition.
      return screen.offsetHeight > innerHeight + 4 ? [top,top+screen.offsetHeight-innerHeight] : [top];
    }).filter((value,i,array) => !i || value-array[i-1]>4);
  }

  function paint() {
    visualFrame = 0;
    if (!enabled()) {
      [hero,...headings].forEach(el => { el.style.removeProperty('transform');el.style.removeProperty('opacity'); });
      headings.forEach(el=>visualOffsets.set(el,0));
      return;
    }
    const leave = clamp(scrollY/innerHeight,0,1);
    hero.style.transform = `translate3d(0,${-leave*44}px,0)`;
    hero.style.opacity = String(1-leave*.8);
    headings.forEach(el => {
      const top=el.getBoundingClientRect().top-(visualOffsets.get(el)||0);
      const entrance = clamp((innerHeight-top)/(innerHeight*.6),0,1);
      const offset=(1-entrance)*24;
      visualOffsets.set(el,offset);
      el.style.transform = `translate3d(0,${offset}px,0)`;
      el.style.opacity = String(.35+entrance*.65);
    });
  }

  function cancel() {
    cancelAnimationFrame(frame);frame=0;velocity=0;committed=false;
    target=position=scrollY;
  }

  function animate(time) {
    const dt = clamp((time-lastFrame)/1000,0,1/30);
    lastFrame=time;
    // Analytic critically damped spring: continuous velocity as the wheel target
    // changes, independent of display refresh rate. No CSS snap or smooth-scroll.
    const omega=12.5, offset=position-target, decay=Math.exp(-omega*dt);
    const impulse=velocity+omega*offset;
    position=target+(offset+impulse*dt)*decay;
    velocity=(velocity-omega*impulse*dt)*decay;
    window.scrollTo({top:position,behavior:'instant'});
    if (Math.abs(position-target)<.5 && Math.abs(velocity)<4) {
      window.scrollTo({top:target,behavior:'instant'});position=target;velocity=0;frame=0;
      return;
    }
    frame=requestAnimationFrame(animate);
  }

  function start() {
    if (frame) return;
    position=scrollY;lastFrame=performance.now();frame=requestAnimationFrame(animate);
  }

  function nestedScroll(event,delta) {
    for (let el=event.target instanceof Element?event.target:null;el && el!==document.body;el=el.parentElement) {
      if (el.matches('select,input,textarea,dialog,[role="dialog"],[role="listbox"]')) return true;
      const style=getComputedStyle(el);
      if (/(auto|scroll)/.test(style.overflowY) && el.scrollHeight>el.clientHeight+1) {
        // The river's list intentionally contains its own wheel motion at the edges.
        if (style.overscrollBehaviorY==='contain' || (delta>0?el.scrollTop+el.clientHeight<el.scrollHeight-1:el.scrollTop>0)) return true;
      }
    }
    return false;
  }

  window.addEventListener('wheel',event => {
    if (!enabled() || event.ctrlKey || event.metaKey || event.shiftKey || !event.deltaY || Math.abs(event.deltaX)>Math.abs(event.deltaY)) return;
    if (document.body.style.overflow==='hidden' || nestedScroll(event,event.deltaY)) { cancel();return; }
    if (!event.cancelable) { cancel();return; }
    const now=performance.now(), nextDirection=Math.sign(event.deltaY);
    const idle=now-lastWheel>180;
    lastWheel=now;
    event.preventDefault();
    if (committed && direction===nextDirection && (frame || !idle)) return;
    if (nextDirection!==direction || (!frame && idle)) { cancel();direction=nextDirection; }
    committed=false;
    const delta=event.deltaY*(event.deltaMode===1?20:event.deltaMode===2?innerHeight:1);
    target=clamp(target+delta,0,maxScroll());
    // Commit once 30% of the distance from this boundary has been traversed.
    // Input is absorbed until this gesture settles, so momentum cannot skip a screen.
    const from=direction>0?anchors.findLast(value=>value<=position+2):anchors.find(value=>value>=position-2);
    const to=direction>0?anchors.find(value=>value>(from??Infinity)+4):anchors.findLast(value=>value<(from??-Infinity)-4);
    if (from!==undefined && to!==undefined && (target-from)/(to-from)>=.3) {
      target=to;committed=true;
    }
    start();
  },{passive:false});

  window.addEventListener('scroll',() => {
    if (!frame) target=position=scrollY;
    if (!visualFrame) visualFrame=requestAnimationFrame(paint);
  },{passive:true});
  window.addEventListener('keydown',event => {
    if (['ArrowDown','ArrowUp','PageDown','PageUp','Home','End',' '].includes(event.key)) cancel();
  });
  window.addEventListener('pointerdown',cancel,{passive:true});
  window.addEventListener('touchstart',cancel,{passive:true});
  document.querySelectorAll('a[href^="#"]').forEach(link => link.addEventListener('click',event => {
    const id=link.getAttribute('href').slice(1),section=document.getElementById(id);
    if (!enabled() || !section || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button) return;
    event.preventDefault();cancel();measure();
    target=clamp(section.getBoundingClientRect().top+scrollY,0,maxScroll());
    committed=true;start();history.pushState(null,'','#'+id);
  }));
  const refresh=() => { cancel();measure();paint(); };
  new ResizeObserver(measure).observe(document.querySelector('main'));
  window.addEventListener('resize',refresh,{passive:true});
  window.addEventListener('pagehide',cancel);
  window.addEventListener('popstate',cancel);
  window.addEventListener('hashchange',cancel);
  document.addEventListener('visibilitychange',() => { if(document.hidden) cancel(); });
  desktop.addEventListener('change',refresh);reduced.addEventListener('change',refresh);
  measure();paint();
})();
