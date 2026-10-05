-- ============================================================
-- 레고 데일리: Supabase 초기 설정 (SQL Editor에 전체 붙여넣고 Run 한 번)
-- 여러 번 실행해도 안전하도록 작성됨
-- ============================================================

-- 1) 웹푸시 구독자
create table if not exists public.push_subscribers (
  id            uuid primary key default gen_random_uuid(),
  endpoint      text not null unique,
  p256dh        text not null,
  auth          text not null,
  topics        text[] not null default array['kr_deal','new_release','kr_news','global_news'],
  platform      text,             -- android / ios / desktop
  source        text,             -- 처음 들어온 경로: blog / kakao / direct ...
  user_agent    text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
alter table public.push_subscribers enable row level security;
-- 정책(policy)을 하나도 만들지 않음 → 웹페이지(공개 키)로는 읽기·쓰기 불가.
-- 등록/해지는 아래 함수로만, 목록 조회·발송은 관리자 키(GitHub Actions)로만.

-- 2) 방문·클릭 기록 (어디서 왔는지, 어떤 기사를 눌렀는지 → 수익화 분석용)
create table if not exists public.events (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  kind        text not null,      -- view(페이지 방문) / article(기사 클릭) / subscribe / unsubscribe
  src         text,               -- push / kakao / blog / pwa / direct
  page        text,
  target      text,               -- 클릭한 기사 주소
  section     text                -- kr_deal-0 같은 카드 위치
);
alter table public.events enable row level security;
drop policy if exists "anyone can insert events" on public.events;
create policy "anyone can insert events" on public.events
  for insert to anon, authenticated
  with check (
    kind in ('view','article','subscribe','unsubscribe')
    and char_length(coalesce(src,''))     <= 40
    and char_length(coalesce(page,''))    <= 300
    and char_length(coalesce(target,''))  <= 2000
    and char_length(coalesce(section,'')) <= 40
  );
create index if not exists events_created_at_idx on public.events (created_at);

-- 권한 명시: 구독자 표는 공개 키로 접근 불가, 기록 표는 '쓰기만' 가능
revoke all on public.push_subscribers from anon, authenticated;
revoke all on public.events from anon, authenticated;
grant insert on public.events to anon, authenticated;

-- 3) 구독 등록/수정 함수 (웹페이지에서 호출)
create or replace function public.subscribe_push(
  p_endpoint text, p_p256dh text, p_auth text,
  p_topics text[] default null, p_platform text default null,
  p_source text default null, p_user_agent text default null
) returns void
language plpgsql security definer set search_path = public as $$
declare
  allowed text[] := array['kr_deal','new_release','kr_news','global_news'];
  t text[] := coalesce(p_topics, allowed);
begin
  if p_endpoint !~ '^https://' or char_length(p_endpoint) > 1000
     or char_length(p_p256dh) > 200 or char_length(p_auth) > 100 then
    raise exception 'invalid subscription';
  end if;
  if not (t <@ allowed) or cardinality(t) = 0 then
    raise exception 'invalid topics';
  end if;
  insert into push_subscribers (endpoint, p256dh, auth, topics, platform, source, user_agent)
  values (p_endpoint, p_p256dh, p_auth, t, left(p_platform, 20), left(p_source, 40), left(p_user_agent, 300))
  on conflict (endpoint) do update
    set p256dh = excluded.p256dh, auth = excluded.auth, topics = excluded.topics,
        platform = excluded.platform, updated_at = now();
end $$;

-- 4) 구독 해지 함수
create or replace function public.unsubscribe_push(p_endpoint text) returns void
language sql security definer set search_path = public as $$
  delete from push_subscribers where endpoint = p_endpoint;
$$;

revoke all on function public.subscribe_push(text,text,text,text[],text,text,text) from public;
revoke all on function public.unsubscribe_push(text) from public;
grant execute on function public.subscribe_push(text,text,text,text[],text,text,text) to anon, authenticated;
grant execute on function public.unsubscribe_push(text) to anon, authenticated;

-- 5) 한눈에 보는 통계 (Table Editor에서 views → daily_stats)
create or replace view public.daily_stats with (security_invoker = on) as
select
  d::date as day,
  (select count(*) from push_subscribers where created_at::date <= d) as total_subscribers,
  (select count(*) from push_subscribers where created_at::date = d)  as new_subscribers,
  (select count(*) from events where kind='view' and created_at::date = d)                  as views,
  (select count(*) from events where kind='view' and src='push' and created_at::date = d)   as views_from_push,
  (select count(*) from events where kind='view' and src='blog' and created_at::date = d)   as views_from_blog,
  (select count(*) from events where kind='article' and created_at::date = d)               as article_clicks
from generate_series(current_date - 29, current_date, interval '1 day') as d
order by day desc;
revoke all on public.daily_stats from anon, authenticated;
