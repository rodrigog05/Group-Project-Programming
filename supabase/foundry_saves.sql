create table if not exists public.foundry_saves (
    user_id uuid primary key references auth.users(id) on delete cascade,
    revision bigint not null check (revision > 0),
    snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object')
);

alter table public.foundry_saves enable row level security;

revoke all on public.foundry_saves from public, anon, authenticated;
grant select, insert on public.foundry_saves to authenticated;
grant update (revision, snapshot) on public.foundry_saves to authenticated;

create policy "Read own save" on public.foundry_saves
    for select to authenticated using ((select auth.uid()) = user_id);

create policy "Create own save" on public.foundry_saves
    for insert to authenticated with check ((select auth.uid()) = user_id);

create policy "Update own save" on public.foundry_saves
    for update to authenticated using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);
