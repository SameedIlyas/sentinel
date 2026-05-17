import { describe, it, expect } from 'vitest';
import {
  trainingBannerKey,
  TRAINING_BANNER_KEYS,
} from '../trainingBanner';

describe('trainingBannerKey', () => {
  it('returns null when vendor does not train on data', () => {
    expect(
      trainingBannerKey(
        { model_training_status: 'no_training', practice_opt_out_state: 'not_applicable' },
        false,
      ),
    ).toBeNull();
  });

  it('returns the warning_no_baa key when training + no BAA', () => {
    expect(
      trainingBannerKey(
        {
          model_training_status: 'trains_on_customer_data',
          practice_opt_out_state: 'not_applicable',
        },
        false,
      ),
    ).toBe(TRAINING_BANNER_KEYS.warningNoBaa);
  });

  it('returns the warning_baa_present key when training + BAA', () => {
    expect(
      trainingBannerKey(
        {
          model_training_status: 'trains_on_customer_data',
          practice_opt_out_state: 'not_applicable',
        },
        true,
      ),
    ).toBe(TRAINING_BANNER_KEYS.warningBaaPresent);
  });

  it('returns opt_out_required when opt_out available + not set', () => {
    expect(
      trainingBannerKey(
        {
          model_training_status: 'opt_out_available',
          practice_opt_out_state: 'required_not_set',
        },
        false,
      ),
    ).toBe(TRAINING_BANNER_KEYS.optOutRequired);
  });

  it('returns opt_out_verified when opt_out + verified', () => {
    expect(
      trainingBannerKey(
        {
          model_training_status: 'opt_out_available',
          practice_opt_out_state: 'verified',
        },
        false,
      ),
    ).toBe(TRAINING_BANNER_KEYS.optOutVerified);
  });

  it('returns unknown when training status is unknown', () => {
    expect(
      trainingBannerKey(
        { model_training_status: 'unknown', practice_opt_out_state: 'not_applicable' },
        false,
      ),
    ).toBe(TRAINING_BANNER_KEYS.unknown);
  });
});
