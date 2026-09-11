-- HEATSHIELD Supabase schema.
-- Run this in your Supabase project's SQL editor (Database > SQL Editor)
-- after creating the project. Requires Supabase Auth to already be
-- enabled (it is, by default).

-- ============================================================
-- Reference: the 48 operational wards (id/name only - the real
-- geometry lives in the FastAPI backend's geojson, not duplicated here)
-- ============================================================
create table if not exists wards (
  ward_id text primary key,
  ward_name text not null
);

-- Real ward id/name pairs, extracted directly from
-- frontend/public/wards_ahmedabad.geojson (sourcewardcode/sourcewardname)
-- - this table existing with no data was the actual bug: profiles,
-- dependents, corporate_accounts, and interventions all have a foreign
-- key on ward_id, so signing up with any ward selected failed with
-- "Database error saving new user" (the trigger's insert hit an FK
-- violation against this empty table, aborting the whole signup).
insert into wards (ward_id, ward_name) values
  ('12', 'Naroda'),
  ('8', 'Thaltej'),
  ('46', 'Lambha'),
  ('26', 'Bapu Nagar'),
  ('48', 'Ramol Hathijan'),
  ('11', 'Sardar Nagar'),
  ('14', 'Kuber Nagar'),
  ('23', 'Thakkarbapa Nagar'),
  ('13', 'Saijpur Bogha'),
  ('27', 'Saraspur-Rakhiyal'),
  ('22', 'India colony'),
  ('2', 'Chandlodiya'),
  ('1', 'Gota'),
  ('7', 'Ghatlodia'),
  ('19', 'Bodakdev'),
  ('3', 'Chandkheda'),
  ('33', 'Sarkhej'),
  ('34', 'Maktampura'),
  ('20', 'Jodhpur'),
  ('32', 'Vejalpur'),
  ('31', 'Vasna'),
  ('30', 'Paldi'),
  ('18', 'Navrangpura'),
  ('9', 'Naranpura'),
  ('6', 'New Wadaj'),
  ('10', 'S. P. Stadium'),
  ('5', 'Ranip'),
  ('4', 'Sabarmati'),
  ('16', 'Shahibag'),
  ('15', 'Asarwa'),
  ('21', 'Dariyapur'),
  ('35', 'Baherampura'),
  ('47', 'Vatva'),
  ('37', 'Mani Nagar'),
  ('45', 'Isanpur'),
  ('39', 'Amraiwadi'),
  ('40', 'Odhav'),
  ('41', 'Vastral'),
  ('42', 'Indrapuri'),
  ('25', 'Virat Nagar'),
  ('44', 'Khokhra'),
  ('17', 'Shahpur'),
  ('29', 'Jamalpur'),
  ('28', 'Khadia'),
  ('36', 'Danilimda'),
  ('38', 'Gomtipur'),
  ('43', 'Bhaipura Hatkeshwar'),
  ('24', 'Nikol')
on conflict (ward_id) do update set ward_name = excluded.ward_name;

-- ============================================================
-- Individual accounts
-- ============================================================
-- CREATE TYPE has no IF NOT EXISTS in Postgres - this guard is what
-- makes the whole file safe to re-run (needed the first time this bit
-- someone: re-running after adding the trigger at the bottom failed
-- with "type already exists" on this exact line).
do $$ begin
  create type relationship_type as enum (
    'self', 'parent', 'grandparent', 'child', 'spouse', 'sibling', 'other'
  );
exception when duplicate_object then null;
end $$;

create table if not exists profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  full_name text not null,
  phone text,
  preferred_language text not null default 'en' check (preferred_language in ('en', 'hi', 'gu')),
  ward_id text references wards (ward_id),
  age int check (age >= 0 and age <= 120),
  is_outdoor_worker boolean not null default false,
  created_at timestamptz not null default now()
);

alter table profiles enable row level security;

drop policy if exists "individuals read their own profile" on profiles;

create policy "individuals read their own profile"
  on profiles for select
  using (auth.uid() = id);

drop policy if exists "individuals update their own profile" on profiles;

create policy "individuals update their own profile"
  on profiles for update
  using (auth.uid() = id);

drop policy if exists "individuals insert their own profile" on profiles;

create policy "individuals insert their own profile"
  on profiles for insert
  with check (auth.uid() = id);

-- Dependent circle: the reason for this table existing at all is the
-- explicit ask - "a dependent circle for every profile where I could
-- add my grandmother's age too, so I get those alerts as well."
create table if not exists dependents (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references profiles (id) on delete cascade,
  full_name text not null,
  relationship relationship_type not null,
  age int not null check (age >= 0 and age <= 120),
  ward_id text references wards (ward_id), -- nullable: defaults to the profile's own ward if not set
  is_outdoor_worker boolean not null default false,
  created_at timestamptz not null default now()
);

alter table dependents enable row level security;

drop policy if exists "individuals manage their own dependents" on dependents;

create policy "individuals manage their own dependents"
  on dependents for all
  using (auth.uid() = profile_id)
  with check (auth.uid() = profile_id);

-- ============================================================
-- Corporate accounts (admin / hospital / school / primary health centre)
-- ============================================================
do $$ begin
  create type corporate_org_type as enum (
    'city_admin', 'hospital', 'school', 'primary_health_centre'
  );
exception when duplicate_object then null;
end $$;

create table if not exists corporate_accounts (
  id uuid primary key references auth.users (id) on delete cascade,
  org_name text not null,
  org_type corporate_org_type not null,
  contact_name text not null,
  contact_phone text,
  ward_id text references wards (ward_id),
  created_at timestamptz not null default now()
);

alter table corporate_accounts enable row level security;

drop policy if exists "corporate accounts read their own record" on corporate_accounts;

create policy "corporate accounts read their own record"
  on corporate_accounts for select
  using (auth.uid() = id);

drop policy if exists "corporate accounts update their own record" on corporate_accounts;

create policy "corporate accounts update their own record"
  on corporate_accounts for update
  using (auth.uid() = id);

drop policy if exists "corporate accounts insert their own record" on corporate_accounts;

create policy "corporate accounts insert their own record"
  on corporate_accounts for insert
  with check (auth.uid() = id);

-- ============================================================
-- Auto-create the profile/corporate_account row on signup.
--
-- Why this exists: supabase.auth.signUp() does NOT grant an active
-- session until the email is confirmed (Supabase's default project
-- setting). A client-side insert into profiles/corporate_accounts
-- immediately after signUp() then fails RLS - auth.uid() is null
-- because there's no session yet, regardless of whether confirmation
-- is on or off in a given project. A trigger on auth.users fires at
-- insert time and runs as the function owner (security definer),
-- which bypasses RLS - so this works correctly no matter how email
-- confirmation is configured. The client passes every form field as
-- signUp() metadata (options.data) instead of a follow-up insert.
-- ============================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  meta jsonb := new.raw_user_meta_data;
  kind text := meta ->> 'account_kind';
begin
  if kind = 'corporate' then
    insert into public.corporate_accounts (
      id, org_name, org_type, contact_name, contact_phone, ward_id
    )
    values (
      new.id,
      coalesce(meta ->> 'org_name', ''),
      coalesce((meta ->> 'org_type')::corporate_org_type, 'hospital'),
      coalesce(meta ->> 'contact_name', ''),
      meta ->> 'contact_phone',
      nullif(meta ->> 'ward_id', '')
    )
    on conflict (id) do nothing;
  else
    insert into public.profiles (
      id, full_name, phone, preferred_language, ward_id, age, is_outdoor_worker
    )
    values (
      new.id,
      coalesce(meta ->> 'full_name', ''),
      meta ->> 'phone',
      coalesce(meta ->> 'preferred_language', 'en'),
      nullif(meta ->> 'ward_id', ''),
      nullif(meta ->> 'age', '')::int,
      coalesce((meta ->> 'is_outdoor_worker')::boolean, false)
    )
    on conflict (id) do nothing;
  end if;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================
-- Alerts / advisories log
-- ============================================================
-- Real audit record of what was composed and targeted - the actual
-- SMS/WhatsApp delivery integration is deliberately not built yet (see
-- conversation history: alerts come after frontend+backend are final).
-- status stays 'queued' until that integration exists; never fake
-- 'delivered'.
do $$ begin
  create type alert_target_group as enum (
    'elderly', 'outdoor_workers', 'children', 'general'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type alert_status as enum ('draft', 'queued');
exception when duplicate_object then null;
end $$;

create table if not exists alerts_log (
  id uuid primary key default gen_random_uuid(),
  sent_by uuid not null references auth.users (id),
  ward_ids text[] not null,
  target_groups alert_target_group[] not null,
  message_en text not null,
  message_hi text,
  message_gu text,
  status alert_status not null default 'draft',
  created_at timestamptz not null default now()
);

alter table alerts_log enable row level security;

drop policy if exists "corporate accounts manage alerts they sent" on alerts_log;

create policy "corporate accounts manage alerts they sent"
  on alerts_log for all
  using (auth.uid() = sent_by)
  with check (auth.uid() = sent_by);

-- ============================================================
-- Interventions (recommended actions per ward, with tracking)
-- ============================================================
do $$ begin
  create type intervention_status as enum (
    'recommended', 'acknowledged', 'in_progress', 'completed'
  );
exception when duplicate_object then null;
end $$;

create table if not exists interventions (
  id uuid primary key default gen_random_uuid(),
  ward_id text not null references wards (ward_id),
  action_type text not null,
  status intervention_status not null default 'recommended',
  acknowledged_by uuid references auth.users (id),
  acknowledged_at timestamptz,
  completed_at timestamptz,
  notes text,
  created_at timestamptz not null default now()
);

alter table interventions enable row level security;

drop policy if exists "authenticated users read interventions" on interventions;

create policy "authenticated users read interventions"
  on interventions for select
  using (auth.role() = 'authenticated');

drop policy if exists "authenticated users update interventions" on interventions;

create policy "authenticated users update interventions"
  on interventions for update
  using (auth.role() = 'authenticated');

drop policy if exists "authenticated users create interventions" on interventions;

create policy "authenticated users create interventions"
  on interventions for insert
  with check (auth.role() = 'authenticated');
