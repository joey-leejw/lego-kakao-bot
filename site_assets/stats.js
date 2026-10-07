// 브릭소리 통계 대시보드 (stats.html 전용). 허락된 이메일로 로그인해야 숫자가 보임.
(function () {
  const C = window.LD_CONFIG || {};
  const app = document.getElementById('app');
  const SRC = { push: '웹 알림', kakao: '카톡', blog: '블로그 글 배너', blog_widget: '블로그 위젯',
    blog_weekly: '블로그 주간 글', pwa: '홈 화면 앱', direct: '직접 방문' };
  const TOPIC = { kr_deal: '국내 할인', new_release: '신제품', kr_news: '국내 소식', global_news: '해외 소식' };
  const PLATFORM = { android: '안드로이드', ios: '아이폰', desktop: 'PC' };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (n) => Number(n || 0).toLocaleString('ko-KR');
  const md = (d) => { const p = String(d).split('-'); return `${+p[1]}/${+p[2]}`; };

  if (!window.supabase || !C.sbUrl || !C.sbKey) {
    app.innerHTML = '<p class="empty">Supabase 설정이 없어 통계를 불러올 수 없어요.</p>';
    return;
  }
  const client = window.supabase.createClient(C.sbUrl, C.sbKey);
  let days = 30;

  // ---------- 로그인 ----------
  function loginView(msg) {
    app.innerHTML = `<section class="box st-login"><h2>관리자 로그인</h2>
      <p>등록된 이메일을 입력하면 로그인 링크를 보내드려요.</p>
      <label for="em">이메일</label><input id="em" type="email" autocomplete="email" placeholder="you@example.com">
      <button id="go" type="button">로그인 링크 받기</button><p class="st-msg">${esc(msg || '')}</p></section>`;
    document.getElementById('go').onclick = async () => {
      const email = document.getElementById('em').value.trim();
      const out = app.querySelector('.st-msg');
      if (!email) { out.textContent = '이메일을 입력해 주세요.'; return; }
      out.textContent = '보내는 중…';
      const { error } = await client.auth.signInWithOtp({
        email, options: { shouldCreateUser: false, emailRedirectTo: location.origin + location.pathname },
      });
      out.textContent = error ? `보내지 못했어요: ${error.message}` : '메일함을 확인해 주세요. 링크를 누르면 이 페이지로 돌아와요.';
    };
  }

  async function start() {
    const { data } = await client.auth.getSession();
    if (!data.session) return loginView();
    load();
  }
  client.auth.onAuthStateChange((ev) => { if (ev === 'SIGNED_IN') load(); });

  // ---------- 데이터 ----------
  async function load() {
    app.innerHTML = '<p class="empty">불러오는 중…</p>';
    const { data, error } = await client.rpc('admin_stats', { p_days: days });
    if (error) {
      const who = (await client.auth.getUser()).data.user;
      app.innerHTML = `<p class="empty">통계를 볼 수 없어요 (${esc(error.message)})${who ? ` · 로그인: ${esc(who.email)}` : ''}</p>
        <button class="st-out" type="button">로그아웃</button>`;
      app.querySelector('.st-out').onclick = () => client.auth.signOut().then(() => loginView());
      return;
    }
    render(data);
  }

  // ---------- 그리기 ----------
  const tip = document.createElement('div');
  tip.className = 'st-tip'; tip.hidden = true; document.body.appendChild(tip);
  function bindTips(root) {
    root.querySelectorAll('[data-tip]').forEach((el) => {
      el.addEventListener('mousemove', (e) => {
        tip.innerHTML = el.dataset.tip; tip.hidden = false;
        tip.style.left = Math.min(e.clientX + 12, innerWidth - tip.offsetWidth - 8) + 'px';
        tip.style.top = (e.clientY - tip.offsetHeight - 10) + 'px';
      });
      el.addEventListener('mouseleave', () => { tip.hidden = true; });
    });
  }

  // 막대 그래프 (한 가지 값, 날짜별)
  function bars(rows, key, color, label) {
    const W = innerWidth < 640 ? 420 : 760, H = 200, P = { l: 30, r: 6, t: 10, b: 22 };
    const max = Math.max(2, Math.ceil(Math.max(...rows.map((r) => r[key])) / 2) * 2);
    const step = (W - P.l - P.r) / rows.length;
    const bw = Math.max(2, Math.min(18, step - 2));
    const y = (v) => P.t + (H - P.t - P.b) * (1 - v / max);
    const ticks = [0, Math.round(max / 2), max];
    let s = ticks.map((t) => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(t)}" y2="${y(t)}" class="grid"/>
      <text x="${P.l - 6}" y="${y(t) + 4}" class="ax" text-anchor="end">${fmt(t)}</text>`).join('');
    const every = Math.ceil(rows.length / 8);
    rows.forEach((r, i) => {
      const x = P.l + i * step + (step - bw) / 2, v = r[key], h = (H - P.t - P.b) * v / max;
      if (v > 0) s += `<path d="M${x},${y(0)} v${-Math.max(h - 4, 0)} q0,-4 4,-4 h${bw - 8 > 0 ? bw - 8 : 0} q4,0 4,4 v${Math.max(h - 4, 0)} z" fill="${color}"/>`;
      s += `<rect x="${P.l + i * step}" y="${P.t}" width="${step}" height="${H - P.t - P.b}" fill="transparent" data-tip="<b>${md(r.day)}</b> ${label} ${fmt(v)}"/>`;
      if ((i % every === 0 && rows.length - 1 - i >= every / 2) || i === rows.length - 1) s += `<text x="${P.l + i * step + step / 2}" y="${H - 6}" class="ax" text-anchor="middle">${md(r.day)}</text>`;
    });
    return `<svg viewBox="0 0 ${W} ${H}" class="st-svg" role="img" aria-label="${esc(label)} 날짜별">${s}</svg>`;
  }

  // 꺾은선 그래프 (한 가지 값) + 표시선
  function line(rows, vals, color, label, unit, mark) {
    const W = 420, H = 200, P = { l: 44, r: 12, t: 14, b: 22 };
    const raw = Math.max(1e-9, ...vals.map((v) => v || 0)) * 1.1;
    const max = unit === '%' ? Math.ceil(raw * 20) / 20 : Math.max(2, Math.ceil(raw / 2) * 2);
    const step = (W - P.l - P.r) / Math.max(1, rows.length - 1);
    const x = (i) => P.l + i * step, y = (v) => P.t + (H - P.t - P.b) * (1 - v / max);
    const f = (v) => unit === '%' ? `${(v * 100).toFixed(1)}%` : fmt(v);
    let s = [0, max / 2, max].map((t) => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(t)}" y2="${y(t)}" class="grid"/>
      <text x="${P.l - 6}" y="${y(t) + 4}" class="ax" text-anchor="end">${f(t)}</text>`).join('');
    if (mark) {
      const mi = rows.findIndex((r) => r.day >= mark.day);
      if (mi >= 0) s += `<line x1="${x(mi)}" x2="${x(mi)}" y1="${P.t}" y2="${H - P.b}" class="mark"/>
        <text x="${x(mi) > W * 0.7 ? x(mi) - 4 : x(mi) + 4}" y="${P.t + 10}" class="ax" text-anchor="${x(mi) > W * 0.7 ? 'end' : 'start'}">${esc(mark.label)}</text>`;
    }
    const pts = vals.map((v, i) => v == null ? null : [x(i), y(v)]);
    let d = '', pen = false;
    pts.forEach((p) => { if (!p) { pen = false; return; } d += (pen ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1); pen = true; });
    s += `<path d="${d}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    const every = Math.ceil(rows.length / 6);
    rows.forEach((r, i) => {
      if (pts[i]) s += `<circle cx="${pts[i][0]}" cy="${pts[i][1]}" r="${rows.length > 40 ? 0 : 3}" fill="${color}" stroke="var(--surface)" stroke-width="2"/>`;
      s += `<rect x="${x(i) - step / 2}" y="${P.t}" width="${step}" height="${H - P.t - P.b}" fill="transparent" data-tip="<b>${md(r.day)}</b> ${label} ${vals[i] == null ? '-' : f(vals[i])}"/>`;
      if ((i % every === 0 && rows.length - 1 - i >= every / 2) || i === rows.length - 1) s += `<text x="${x(i)}" y="${H - 6}" class="ax" text-anchor="middle">${md(r.day)}</text>`;
    });
    return `<svg viewBox="0 0 ${W} ${H}" class="st-svg" role="img" aria-label="${esc(label)} 날짜별">${s}</svg>`;
  }

  // 가로 막대 목록 (항목별 크기)
  function hbars(items, color, unit) {
    if (!items || !items.length) return '<p class="empty">아직 데이터가 없어요.</p>';
    const max = Math.max(1, ...items.map((i) => i.n));
    return '<div class="hb">' + items.map((i) => `<div class="hb-row" data-tip="<b>${esc(i.label)}</b> ${fmt(i.n)}${unit || ''}">
      <span class="hb-l">${esc(i.label)}</span><span class="hb-t"><i style="width:${Math.max(2, 100 * i.n / max)}%;background:${color}"></i></span>
      <span class="hb-n">${fmt(i.n)}</span></div>`).join('') + '</div>';
  }

  function tile(cls, title, value, sub) {
    return `<div class="stat ${cls}"><b>${title}</b><strong>${value}</strong><small>${sub}</small></div>`;
  }

  function render(d) {
    const rows = d.daily || [];
    const sum = (k) => rows.reduce((a, r) => a + (r[k] || 0), 0);
    const views = sum('views'), clicks = sum('clicks'), newSubs = sum('new_subs');
    const visitors = d.visitors_total || 0;
    const ctr = views ? clicks / views : 0;
    const today = rows[rows.length - 1] || {};
    const ctrs = rows.map((r) => r.views ? r.clicks / r.views : null);
    const c2 = '2026-10-06';
    const avg = (arr) => { const v = arr.filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
    const before = avg(rows.filter((r) => r.day < c2).map((r) => r.views ? r.clicks / r.views : null));
    const after = avg(rows.filter((r) => r.day >= c2).map((r) => r.views ? r.clicks / r.views : null));
    const pct = (v) => v == null ? '-' : (v * 100).toFixed(1) + '%';
    const srcItems = (d.by_src || []).map((r) => ({ label: SRC[r.src] || r.src, n: r.visitors || r.views }));
    const S = window.LD_SOURCES || { items: [], days: 0 };

    app.innerHTML = `
      <div class="st-bar"><div class="st-range" role="group" aria-label="기간">
        ${[7, 30, 90].map((n) => `<button type="button" data-d="${n}" class="${n === days ? 'on' : ''}">${n}일</button>`).join('')}
      </div><button class="st-out" type="button">로그아웃</button></div>
      <div class="stats st-tiles">
        ${tile('s-news', '방문자', fmt(visitors), `오늘 ${fmt(today.visitors)} · 페이지뷰 ${fmt(views)}`)}
        ${tile('s-deal', '소식 클릭', fmt(clicks), `클릭률 ${pct(ctr)}`)}
        ${tile('s-new', '알림 구독자', fmt(d.subs_total), `기간 중 새로 ${fmt(newSubs)}`)}
        ${tile('s-soon', 'C2 전후 클릭률', `${pct(after)}`, `바꾸기 전 ${pct(before)}`)}
      </div>
      <section class="box st-card"><div class="box-h"><h2>날짜별 방문자</h2><span class="n">최근 ${days}일</span></div>
        <div class="st-pad">${bars(rows, 'visitors', 'var(--news-fg)', '방문자')}
        <details><summary>표로 보기</summary><table class="st-table"><thead><tr><th>날짜</th><th>방문자</th><th>페이지뷰</th><th>클릭</th><th>새 구독</th><th>해지</th></tr></thead><tbody>
        ${rows.slice().reverse().map((r) => `<tr><td>${md(r.day)}</td><td>${fmt(r.visitors)}</td><td>${fmt(r.views)}</td><td>${fmt(r.clicks)}</td><td>${fmt(r.new_subs)}</td><td>${fmt(r.unsubs)}</td></tr>`).join('')}
        </tbody></table></details></div></section>
      <div class="st-grid">
        <section class="box st-card"><div class="box-h"><h2>알림 구독자 수</h2><span class="n">누적</span></div>
          <div class="st-pad">${line(rows, rows.map((r) => r.total_subs), 'var(--new-fg)', '구독자', '')}</div></section>
        <section class="box st-card"><div class="box-h"><h2>클릭률</h2><span class="n">클릭 ÷ 페이지뷰</span></div>
          <div class="st-pad">${line(rows, ctrs, 'var(--deal-fg)', '클릭률', '%', { day: c2, label: 'C2 적용' })}</div></section>
        <section class="box st-card"><div class="box-h"><h2>들어온 경로</h2><span class="n">방문자</span></div>
          <div class="st-pad">${hbars(srcItems, 'var(--news-fg)', '명')}</div></section>
        <section class="box st-card"><div class="box-h"><h2>구독자 관심 분야</h2><span class="n">중복 선택</span></div>
          <div class="st-pad">${hbars((d.subs_by_topic || []).map((r) => ({ label: TOPIC[r.topic] || r.topic, n: r.n })), 'var(--new-fg)', '명')}</div></section>
        <section class="box st-card"><div class="box-h"><h2>구독 경로 · 기기</h2><span class="n">전체 기간</span></div>
          <div class="st-pad"><p class="st-sub">처음 들어온 경로</p>${hbars((d.subs_by_src || []).map((r) => ({ label: SRC[r.src] || r.src, n: r.n })), 'var(--new-fg)', '명')}
          <p class="st-sub">기기</p>${hbars((d.subs_by_platform || []).map((r) => ({ label: PLATFORM[r.platform] || r.platform, n: r.n })), 'var(--cal-fg)', '명')}</div></section>
        <section class="box st-card"><div class="box-h"><h2>출처별 채택</h2><span class="n">최근 ${S.days}일 실린 소식</span></div>
          <div class="st-pad">${hbars(S.items.map((r) => ({ label: r.source, n: r.n })), 'var(--deal-fg)', '건')}</div></section>
      </div>
      <section class="box st-card"><div class="box-h"><h2>많이 눌린 소식 TOP 10</h2><span class="n">최근 7일</span></div>
        ${(d.top_clicks || []).length ? '<ol class="st-top">' + d.top_clicks.map((r) => {
          const u = String(r.target || '');
          const name = (S.titles || {})[u] || u.replace(/^https?:\/\/(www\.)?/, '').slice(0, 70);
          return `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(name)}</a><span>${fmt(r.n)}회</span></li>`;
        }).join('') + '</ol>' : '<p class="empty">아직 클릭 기록이 없어요.</p>'}</section>
      <p class="st-note">방문자는 브라우저 기준이에요(같은 사람이 휴대폰·PC로 오면 2명). 이 페이지 방문은 집계하지 않아요.</p>`;
    app.querySelectorAll('.st-range button').forEach((b) => { b.onclick = () => { days = +b.dataset.d; load(); }; });
    app.querySelector('.st-out').onclick = () => client.auth.signOut().then(() => loginView('로그아웃했어요.'));
    bindTips(app);
  }

  start();
})();
