/**
 * Banner helper for ClinicAiTool model-training status (PRD.v2.md §6.8.2.b).
 *
 * Pure function — given a tool record and whether the practice has a
 * BAA covering training use, returns the locked i18n key to render, or
 * `null` if no banner should appear. The five keys are the verbatim
 * set frozen in PRD.v2.md §6.8.2.b.
 *
 * Keep this file self-contained and free of React imports so it is
 * trivially unit-testable.
 */

export type TrainingStatus =
  | 'unknown'
  | 'no_training'
  | 'trains_on_customer_data'
  | 'opt_out_available';

export type PracticeOptOutState =
  | 'not_applicable'
  | 'required_not_set'
  | 'required_and_set'
  | 'verified';

export interface TrainingStatusFields {
  model_training_status: TrainingStatus;
  practice_opt_out_state: PracticeOptOutState;
}

export const TRAINING_BANNER_KEYS = {
  warningNoBaa: 'clinic.tools.training_status.warning_no_baa',
  warningBaaPresent: 'clinic.tools.training_status.warning_baa_present',
  optOutRequired: 'clinic.tools.training_status.opt_out_required',
  optOutVerified: 'clinic.tools.training_status.opt_out_verified',
  unknown: 'clinic.tools.training_status.unknown',
} as const;

export type TrainingBannerKey =
  (typeof TRAINING_BANNER_KEYS)[keyof typeof TRAINING_BANNER_KEYS];

/**
 * Map a tool's training-status fields to the appropriate banner i18n key.
 *
 * Returns ``null`` when no banner should render (no_training case).
 * Matrix follows the table in PRD.v2.md §6.8.2.b verbatim.
 */
export function trainingBannerKey(
  tool: TrainingStatusFields,
  baaSigned: boolean,
): TrainingBannerKey | null {
  const status = tool.model_training_status;
  const optOut = tool.practice_opt_out_state;

  if (status === 'no_training') return null;
  if (status === 'unknown') return TRAINING_BANNER_KEYS.unknown;

  if (status === 'trains_on_customer_data') {
    if (baaSigned) return TRAINING_BANNER_KEYS.warningBaaPresent;
    // not_applicable / required_not_set / required_and_set without BAA →
    // the strongest warning per PRD.v2.md §6.8.2.b row 1.
    return TRAINING_BANNER_KEYS.warningNoBaa;
  }

  if (status === 'opt_out_available') {
    if (optOut === 'verified') return TRAINING_BANNER_KEYS.optOutVerified;
    if (optOut === 'required_not_set')
      return TRAINING_BANNER_KEYS.optOutRequired;
    if (optOut === 'required_and_set')
      return TRAINING_BANNER_KEYS.optOutRequired;
    // not_applicable + opt_out_available is a weird combo (vendor offers
    // but practice marked N/A) — surface the unknown / muted banner so
    // the practice admin investigates.
    return TRAINING_BANNER_KEYS.unknown;
  }

  return null;
}
