-- =====================================================================
-- Sushi Planner — schemat bazy dla Supabase
-- Wklej całość w Supabase → SQL Editor → Run.
-- =====================================================================

create table if not exists workspaces (
  id         uuid primary key default gen_random_uuid(),
  name       text not null default 'Mój lokal',
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists members (
  workspace_id uuid references workspaces(id) on delete cascade,
  user_id      uuid references auth.users(id) on delete cascade,
  role         text not null default 'chef' check (role in ('owner','chef','viewer')),
  primary key (workspace_id, user_id)
);

alter table workspaces enable row level security;
alter table members    enable row level security;

-- Każdy widzi wyłącznie workspace, do którego należy.
drop policy if exists "read own workspace" on workspaces;
create policy "read own workspace" on workspaces for select
  using (exists (
    select 1 from members m
    where m.workspace_id = workspaces.id and m.user_id = auth.uid()
  ));

-- Zapisywać mogą właściciel i kucharz; viewer tylko czyta.
drop policy if exists "write own workspace" on workspaces;
create policy "write own workspace" on workspaces for update
  using (exists (
    select 1 from members m
    where m.workspace_id = workspaces.id
      and m.user_id = auth.uid()
      and m.role in ('owner','chef')
  ));

drop policy if exists "read members" on members;
create policy "read members" on members for select using (user_id = auth.uid());

-- Pierwsze logowanie: zakłada workspace i czyni użytkownika właścicielem.
create or replace function bootstrap_workspace() returns uuid
language plpgsql security definer as $$
declare wid uuid;
begin
  select workspace_id into wid from members where user_id = auth.uid() limit 1;
  if wid is null then
    insert into workspaces(name) values ('Mój lokal') returning id into wid;
    insert into members(workspace_id, user_id, role) values (wid, auth.uid(), 'owner');
  end if;
  return wid;
end $$;


-- =====================================================================
-- DOPISYWANIE KUCHARZY
-- ---------------------------------------------------------------------
-- 1. Kucharz zakłada konto w aplikacji (zakładka Ustawienia → Zaloguj).
--    Przy pierwszym logowaniu dostanie WŁASNY, pusty workspace.
-- 2. Ty przenosisz go do swojego. W Supabase → SQL Editor:
--
--      -- podejrzyj id użytkowników i workspace'ów:
--      select u.id, u.email, m.workspace_id, m.role
--      from auth.users u left join members m on m.user_id = u.id;
--
--      -- przepnij kucharza do Twojego workspace:
--      delete from members where user_id = '<UUID_KUCHARZA>';
--      insert into members (workspace_id, user_id, role)
--      values ('<UUID_TWOJEGO_WORKSPACE>', '<UUID_KUCHARZA>', 'chef');
--
--    Rola 'viewer' = tylko podgląd receptur i gramatur, bez edycji.
-- =====================================================================
