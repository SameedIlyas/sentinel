/**
 * Zod schema for the User object cached in localStorage (CRIT-011).
 *
 * The localStorage `user` key historically returned whatever
 * ``JSON.parse(localStorage.getItem('user'))`` evaluated to. An
 * attacker who could write to localStorage (XSS via any third-party
 * extension, dev-tools console, supply-chain compromise of one of the
 * dashboard's many dependencies) could therefore force a UserRole
 * upgrade purely on the client side.
 *
 * The fix:
 *
 * 1. Parse the cached entry through ``UserSchema.safeParse``. On any
 *    schema failure, clear the entry and return null — never return a
 *    half-validated object.
 * 2. Re-derive role/tier from the server's ``validateToken`` response
 *    on every auth-context boot. The cached values are advisory; the
 *    server response is authoritative.
 *
 * The remaining attack surface — JWT in localStorage — is documented as
 * a separate follow-up (move to HttpOnly cookies).
 */
import { z } from 'zod';

// Enum of acceptable role strings. Mirrors the Python UserRole enum.
// Keep this literal-string list in sync with policy_engine/models/user.py.
export const UserRoleSchema = z.enum([
  'system_admin',
  'admin',
  'cmio',
  'data_scientist',
  'compliance_officer',
  'clinical_user',
  'analyst',
  'viewer',
]);

export const TierKeySchema = z.enum([
  'enterprise',
  'clinic_basic',
  'clinic_standard',
  'clinic_multi_site',
]);

/**
 * Strict validator for any object claimed to be a cached ``User``. The
 * fields exactly mirror the runtime User interface in types/index.ts —
 * add fields here when the User shape grows.
 */
export const UserSchema = z.object({
  id: z.string().min(1),
  username: z.string().min(1),
  email: z.string().email().or(z.string().min(1)),
  role: UserRoleSchema,
  full_name: z.string().optional(),
  is_active: z.boolean(),
  organization_id: z.string().optional(),
  tier: TierKeySchema.optional(),
  created_at: z.string().min(1),
  updated_at: z.string().optional(),
  last_login: z.string().optional(),
});

export type ValidatedUser = z.infer<typeof UserSchema>;

/**
 * Validate an arbitrary value (typically ``JSON.parse(localStorage.user)``)
 * and return the validated User, or ``null`` if the value does not match
 * the schema.
 */
export function parseUser(raw: unknown): ValidatedUser | null {
  const result = UserSchema.safeParse(raw);
  if (!result.success) return null;
  return result.data;
}
