// Roles for the account/profile menu's scope switcher. Same underlying
// data, different scoped views per role - see
// components/layout/ProfileMenu.tsx. Labels live in the i18n locale
// files ("roles.*"), not here.
export type Role = 'nodal_officer' | 'ward_officer' | 'hospital' | 'employer'

export type CorporateOrgType = 'city_admin' | 'hospital' | 'school' | 'primary_health_centre'

// Mirrors alerts_log.target_groups in supabase/schema.sql - kept even
// though the current frontend no longer writes new alerts, since the
// column and any existing rows still use this shape.
export type RiskGroup = 'elderly' | 'outdoor_workers' | 'children' | 'general'

export type AccountKind = 'individual' | 'corporate'
