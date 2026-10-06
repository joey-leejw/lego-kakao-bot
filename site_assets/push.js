// 알림 구독 버튼 + 방문/클릭 기록 (Supabase)
(function () {
  const C = window.LD_CONFIG || {};
  const TOPICS = [
    ['kr_deal', '🏷️ 국내 할인'], ['new_release', '🆕 신제품'],
    ['kr_news', '🇰🇷 국내 소식'], ['global_news', '🌍 해외 소식'],
  ];
  const ua = navigator.userAgent;
  const isIOS = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isAndroid = /Android/i.test(ua);
  const isKakao = /KAKAOTALK/i.test(ua);
  const inApp = isKakao || /NAVER\(inapp|Instagram|FBAN|FBAV|Line\/|DaumApps|everytimeApp|; wv\)/i.test(ua)
    || (isIOS && /CriOS|FxiOS|EdgiOS|Whale/i.test(ua)); // 아이폰은 Safari에서만 알림 가능
  const standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const params = new URLSearchParams(location.search);
  let src0 = null; try { src0 = sessionStorage.getItem('ld_src'); } catch (_) {}
  const src = (params.get('src') || src0 || (standalone ? 'pwa' : (document.referrer.includes('blog.naver') ? 'blog' : 'direct'))).slice(0, 40);
  try { if (!src0) sessionStorage.setItem('ld_src', src); } catch (_) {}
  const platform = isIOS ? 'ios' : isAndroid ? 'android' : 'desktop';

  // ---------- Supabase 호출 ----------
  function sbHeaders() {
    const h = { apikey: C.sbKey, 'Content-Type': 'application/json', Prefer: 'return=minimal' };
    if ((C.sbKey || '').startsWith('eyJ')) h.Authorization = 'Bearer ' + C.sbKey;
    return h;
  }
  function sb(path, body, keepalive) {
    if (!C.sbUrl || !C.sbKey) return Promise.resolve();
    return fetch(C.sbUrl + '/rest/v1/' + path, { method: 'POST', headers: sbHeaders(), body: JSON.stringify(body), keepalive: !!keepalive });
  }
  function log(kind, extra) {
    sb('events', Object.assign({ kind, src, page: location.pathname.slice(-120) }, extra || {}), true).catch(() => {});
  }

  // 방문 기록 + 기사 클릭 기록
  log('view');
  document.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('a.t, a.orig');
    if (!a) return;
    const card = a.closest('.card, .source');
    log('article', { target: a.href.slice(0, 2000), section: card ? (card.id || 'source') : null });
  });

  // ---------- 알림 구독 UI ----------
  const box = document.getElementById('push');
  if (!box || !C.vapid) return;
  const KEY_TOPICS = 'ld_topics';
  const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY_TOPICS)) || null; } catch (_) { return null; } })();

  function urlB64ToUint8(b64) {
    const pad = '='.repeat((4 - (b64.length % 4)) % 4);
    const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }
  function iosVersion() {
    const m = ua.match(/OS (\d+)_(\d+)/);
    return m ? parseFloat(m[1] + '.' + m[2]) : 0;
  }
  function topicChecks(selected) {
    const sel = selected || TOPICS.map((t) => t[0]);
    return '<div class="topics">' + TOPICS.map(([k, label]) =>
      `<label><input type="checkbox" value="${k}" ${sel.includes(k) ? 'checked' : ''}> ${label}</label>`).join('') + '</div>';
  }
  function chosen() {
    const v = [...box.querySelectorAll('.topics input:checked')].map((i) => i.value);
    return v.length ? v : TOPICS.map((t) => t[0]);
  }
  function render(html) { box.innerHTML = html; box.hidden = false; }
  const head = '<b>🔔 매일 12시, 레고 소식을 알림으로</b>';

  async function register() {
    return navigator.serviceWorker.register('sw.js');
  }

  async function subscribe() {
    const btn = box.querySelector('button.go');
    if (btn) { btn.disabled = true; btn.textContent = '설정 중…'; }
    try {
      const reg = await register();
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') return show();
      let sub = await reg.pushManager.getSubscription();
      if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8(C.vapid) });
      const j = sub.toJSON();
      const topics = chosen();
      const r = await sb('rpc/subscribe_push', {
        p_endpoint: j.endpoint, p_p256dh: j.keys.p256dh, p_auth: j.keys.auth,
        p_topics: topics, p_platform: platform, p_source: src, p_user_agent: ua.slice(0, 300),
      });
      if (r && !r.ok) throw new Error('save failed ' + r.status);
      try { localStorage.setItem(KEY_TOPICS, JSON.stringify(topics)); } catch (_) {}
      log('subscribe');
      show();
    } catch (err) {
      render(`${head}<p class="warn">알림 설정에 실패했어요. 잠시 후 다시 시도해 주세요.</p><button class="go">다시 시도</button>`);
      box.querySelector('button.go').onclick = subscribe;
    }
  }

  async function unsubscribe() {
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg && (await reg.pushManager.getSubscription());
    if (sub) {
      await sb('rpc/unsubscribe_push', { p_endpoint: sub.endpoint }).catch(() => {});
      await sub.unsubscribe();
    }
    log('unsubscribe');
    show();
  }

  function openExternal() {
    const url = location.href.split('#')[0];
    if (isKakao) { location.href = 'kakaotalk://web/openExternal?url=' + encodeURIComponent(url); return; }
    if (isAndroid) { location.href = 'intent://' + url.replace(/^https?:\/\//, '') + '#Intent;scheme=https;package=com.android.chrome;end'; return; }
    copyLink();
  }
  function copyLink() {
    const url = location.href.split('#')[0].split('?')[0];
    (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(
      () => alertInline('주소를 복사했어요. Safari를 열고 주소창에 붙여넣어 주세요.'),
      () => alertInline('주소: ' + url));
  }
  function alertInline(msg) {
    let p = box.querySelector('.note');
    if (!p) { p = document.createElement('p'); p.className = 'note'; box.appendChild(p); }
    p.textContent = msg;
  }

  async function show() {
    // 1) 카톡·네이버 등 앱 안의 브라우저
    if (inApp) {
      render(`${head}<p>지금 보고 계신 앱 안의 브라우저에서는 알림을 켤 수 없어요.
        ${isIOS ? '<b>Safari</b>로' : '<b>크롬</b>으로'} 열어 주세요.</p>
        <button class="go">${isIOS && !isKakao ? '주소 복사하기' : (isIOS ? 'Safari로 열기' : '크롬으로 열기')}</button>
        ${isIOS ? '<p class="hint">안 열리면: 화면 오른쪽 아래 <b>⋯</b> 또는 <b>공유</b> → <b>Safari로 열기</b></p>' : ''}`);
      box.querySelector('button.go').onclick = isIOS && !isKakao ? copyLink : openExternal;
      return;
    }
    // 2) 아이폰: 홈 화면에 추가해야 알림 가능 (iOS 16.4+)
    if (isIOS && !standalone) {
      if (iosVersion() && iosVersion() < 16.4) {
        render(`${head}<p class="warn">아이폰 알림은 iOS 16.4 이상에서만 돼요. 설정 → 일반 → 소프트웨어 업데이트 후 이용해 주세요.</p>`);
        return;
      }
      render(`${head}<p>아이폰은 <b>홈 화면에 추가</b>한 뒤 알림을 켤 수 있어요. (최초 1회)</p>
        <ol class="steps"><li>Safari 아래쪽 <b>공유 버튼</b>(□↑)을 눌러요</li>
        <li><b>홈 화면에 추가</b>를 눌러요</li>
        <li>홈 화면에 생긴 아이콘으로 열고 <b>알림 받기</b>를 눌러요</li></ol>`);
      return;
    }
    // 3) 지원 안 하는 브라우저
    if (!supported) {
      render(`${head}<p class="warn">이 브라우저는 알림을 지원하지 않아요. 크롬이나 Safari에서 열어 주세요.</p>`);
      return;
    }
    // 4) 알림 차단됨
    if (Notification.permission === 'denied') {
      render(`${head}<p class="warn">알림이 차단돼 있어요. 주소창 왼쪽 <b>자물쇠(🔒) → 알림 허용</b>으로 바꾼 뒤 새로고침해 주세요.</p>`);
      return;
    }
    // 5) 이미 구독 중인지 확인
    let sub = null;
    try {
      const reg = await navigator.serviceWorker.getRegistration();
      sub = reg && (await reg.pushManager.getSubscription());
    } catch (_) {}
    document.documentElement.classList.toggle('ld-sub', !!(sub && Notification.permission === 'granted'));
    if (sub && Notification.permission === 'granted') {
      render(`<b>✅ 매일 12시 알림을 받고 있어요</b>
        <details><summary>받을 소식 바꾸기 · 알림 끄기</summary>${topicChecks(saved)}
        <div class="row"><button class="go">저장</button><button class="off">알림 끄기</button></div></details>`);
      box.querySelector('button.go').onclick = subscribe;
      box.querySelector('button.off').onclick = unsubscribe;
      return;
    }
    // 6) 처음 방문
    render(`${head}<p>할인 시작·마감, 신제품 공개를 놓치지 마세요. 무료예요.</p>${topicChecks(saved)}
      <button class="go">🔔 알림 받기</button>`);
    box.querySelector('button.go').onclick = subscribe;
  }

  if (supported) register().catch(() => {});
  show();
})();
