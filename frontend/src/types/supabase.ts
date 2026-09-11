// Hand-written types mirroring supabase/schema.sql. Not generated -
// keep in sync by hand if the schema changes (or run `supabase gen
// types typescript` once a project exists and replace this file).
import type { CorporateOrgType, RiskGroup } from '@/types/domain'

export interface ProfileRow {
  id: string
  full_name: string
  phone: string | null
  preferred_language: 'en' | 'hi' | 'gu'
  ward_id: string | null
  age: number | null
  is_outdoor_worker: boolean
  created_at: string
}

export type RelationshipType =
  | 'self' | 'parent' | 'grandparent' | 'child' | 'spouse' | 'sibling' | 'other'

export interface DependentRow {
  id: string
  profile_id: string
  full_name: string
  relationship: RelationshipType
  age: number
  ward_id: string | null
  is_outdoor_worker: boolean
  created_at: string
}

export interface CorporateAccountRow {
  id: string
  org_name: string
  org_type: CorporateOrgType
  contact_name: string
  contact_phone: string | null
  ward_id: string | null
  created_at: string
}

export type AlertStatus = 'draft' | 'queued'

export interface AlertLogRow {
  id: string
  sent_by: string
  ward_ids: string[]
  target_groups: RiskGroup[]
  message_en: string
  message_hi: string | null
  message_gu: string | null
  status: AlertStatus
  created_at: string
}

export type InterventionStatus = 'recommended' | 'acknowledged' | 'in_progress' | 'completed'

export interface InterventionRow {
  id: string
  ward_id: string
  action_type: string
  status: InterventionStatus
  acknowledged_by: string | null
  acknowledged_at: string | null
  completed_at: string | null
  notes: string | null
  created_at: string
}
