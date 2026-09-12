-- Apply once in Supabase SQL editor before enabling WhatsApp preferences.
-- Existing profile RLS restricts these preferences to the account owner.
alter table public.profiles add column if not exists whatsapp_opt_in boolean not null default false;
alter table public.profiles add column if not exists whatsapp_opt_in_at timestamptz;

create or replace function public.track_whatsapp_consent()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.whatsapp_opt_in and (not old.whatsapp_opt_in or new.phone is distinct from old.phone) then
    new.whatsapp_opt_in_at := now();
  elsif not new.whatsapp_opt_in then
    new.whatsapp_opt_in_at := null;
  else
    new.whatsapp_opt_in_at := old.whatsapp_opt_in_at;
  end if;
  return new;
end;
$$;
drop trigger if exists track_whatsapp_consent on public.profiles;
create trigger track_whatsapp_consent before update on public.profiles
for each row execute function public.track_whatsapp_consent();
