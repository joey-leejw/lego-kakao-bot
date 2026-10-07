-- ============================================================
-- 브릭소리 통계 대시보드 설정 (SQL Editor에 전체 붙여넣고 Run 한 번)
-- 여러 번 실행해도 안전함. setup.sql 을 먼저 실행한 상태여야 함.
-- ============================================================

-- 1) 방문자 구분용 익명 번호(브라우저마다 무작위 값, 개인정보 아님)
alter table public.events add column if not exists vid text;
drop policy if exists "anyone can insert events" on public.events;
create policy "anyone can insert events" on public.events
  for insert to anon, authenticated
  with check (
    kind in ('view','article','subscribe','unsubscribe')
    and char_length(coalesce(src,''))     <= 40
    and char_length(coalesce(page,''))    <= 300
    and char_length(coalesce(target,''))  <= 2000
    and char_length(coalesce(section,'')) <= 40
    and char_length(coalesce(vid,''))     <= 40
  );

-- 2) 통계를 볼 수 있는 이메일 목록 (공개 키로는 읽기·쓰기 불가)
create table if not exists public.admins (email text primary key);
alter table public.admins enable row level security;
revoke all on public.admins from anon, authenticated;
insert into public.admins (email) values ('coolabtype@gmail.com') on conflict do nothing;

-- 3) 통계 함수: 허락된 이메일로 로그인했거나, GitHub Actions(관리자 키)일 때만 결과를 줌
create or replace function public.admin_stats(p_days int default 30)
returns json
language plpgsql security definer set search_path = public as $$
declare
  claims json := coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::json;
  me text := lower(coalesce(claims->>'email', ''));
  is_service boolean := coalesce(claims->>'role', '') = 'service_role';
  d0 date := (now() at time zone 'Asia/Seoul')::date - greatest(least(p_days, 180), 1) + 1;
  result json;
begin
  if not is_service and not exists (select 1 from admins where lower(email) = me and me <> '') then
    raise exception 'not allowed';
  end if;

  with ev as (
    select (created_at at time zone 'Asia/Seoul')::date as day, kind, coalesce(nullif(src, ''), 'direct') as src,
           vid, target, section
    from events where created_at >= (d0::timestamp at time zone 'Asia/Seoul')
  ),
  days as (select generate_series(d0, (now() at time zone 'Asia/Seoul')::date, interval '1 day')::date as day),
  subs as (select (created_at at time zone 'Asia/Seoul')::date as day, source, topics, platform from push_subscribers)
  select json_build_object(
    'from', d0,
    'today', (now() at time zone 'Asia/Seoul')::date,
    'daily', (select json_agg(json_build_object(
        'day', d.day,
        'views', (select count(*) from ev where ev.day = d.day and kind = 'view'),
        'visitors', (select count(distinct vid) from ev where ev.day = d.day and kind = 'view'),
        'clicks', (select count(*) from ev where ev.day = d.day and kind = 'article'),
        'new_subs', (select count(*) from subs where subs.day = d.day),
        'total_subs', (select count(*) from subs where subs.day <= d.day),
        'unsubs', (select count(*) from ev where ev.day = d.day and kind = 'unsubscribe')
      ) order by d.day) from days d),
    'by_src', (select json_agg(r) from (
        select src, count(*) as views, count(distinct vid) as visitors
        from ev where kind = 'view' group by src order by count(*) desc) r),
    'visitors_total', (select count(distinct vid) from ev where kind = 'view'),
    'subs_total', (select count(*) from push_subscribers),
    'subs_by_topic', (select json_agg(r) from (
        select t as topic, count(*) as n from push_subscribers, unnest(topics) t group by t order by n desc) r),
    'subs_by_src', (select json_agg(r) from (
        select coalesce(nullif(source, ''), 'direct') as src, count(*) as n
        from push_subscribers group by 1 order by n desc) r),
    'subs_by_platform', (select json_agg(r) from (
        select coalesce(platform, '?') as platform, count(*) as n from push_subscribers group by 1 order by n desc) r),
    'top_clicks', (select json_agg(r) from (
        select target, max(section) as section, count(*) as n
        from ev where kind = 'article' and day >= (now() at time zone 'Asia/Seoul')::date - 6
        group by target order by n desc limit 10) r)
  ) into result;
  return result;
end $$;

revoke all on function public.admin_stats(int) from public, anon;
grant execute on function public.admin_stats(int) to authenticated, service_role;
