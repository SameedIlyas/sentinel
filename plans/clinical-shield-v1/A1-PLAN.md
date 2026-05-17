# A1-PLAN.md — Workstream A1: AI Tools Model Training Status

> Phase-specific executable plan for workstream A1 of `plans/clinical-shield-v1.md`. Authored by `planner` agent under adversarial-review constraints (HEALTH-2, HEALTH-5, HEALTH-6).
> Tier A (see clinical-shield-v1.md). Independent PR. Safe to merge to `main` without rebasing onto any other v1.0 work.

## Overview

A1 adds the **Model Training Status** + **Practice Opt-Out State** auditable schema to `clinic_ai_tools` (`policy_engine/models/clinic.py:52-98`), surfaces it through the tools API (`policy_engine/routes/clinic/tools.py:39-77`), wires a new `clinic.tool.trains_on_data` alert type into the translator (`policy_engine/services/clinic_alert_translator.py`), adds a "Tools that train on your data" line in the monthly compliance PDF (`policy_engine/services/clinic_pdf_report.py:75-237`), and renders the BAA-aware bilingual banner on the dashboard (`dashboard/src/pages/clinic/ToolList.tsx`, `ToolEditor.tsx`). All five locked PRD i18n keys (PRD.v2.md §6.8.2.b) ship in English + Spanish.

## Requirements (from PRD.v2.md §6.8.2 + adversarial-review findings HEALTH-2/5/6)

- Five new columns on `clinic_ai_tools` per PRD.v2.md §6.8.2.a.
- `model_training_status` enum: `unknown | no_training | trains_on_customer_data | opt_out_available`.
- `practice_opt_out_state` enum: `not_applicable | required_not_set | required_and_set | verified` (HEALTH-5 split).
- `opt_out_verified_at` (DateTime nullable), `opt_out_verified_by_user_id` (FK `users.id` ON DELETE SET NULL, nullable), `model_training_status_evidence` (String(2000) nullable).
- Alembic migration **018** (head is `017` per `alembic/versions/2024_02_24_0000-017_*.py`) with working `downgrade()` + backfill (`'unknown'` / `'not_applicable'`).
- Pydantic schemas updated in `ToolCreate`, `ToolUpdate`, `ToolResponse`; only **Admin** product-role can set `practice_opt_out_state == 'verified'` (HEALTH-5 / PRD.v2.md §6.8.2.a).
- New alert type `clinic.tool.trains_on_data` with **idempotency window: one alert per `(org_id, tool_id)` per 30 days** (PRD.v2.md §6.8.2.c).
- Monthly PDF gains a "Tools that train on your data" row in the "Tools registry" section (`policy_engine/services/clinic_pdf_report.py:223-227`).
- Dashboard banner rendered per the four locked conditions (PRD.v2.md §6.8.2.b); five i18n keys in `clinic_basic.ts`, `clinic_standard.ts`, `clinic_multi_site.ts` + new Spanish overlays (`*.es.ts`).
- TDD: RED → GREEN → REFACTOR. Coverage ≥ 85% on touched modules.

## Implementation steps

### Phase 1 — schema + migration

1. **Add enums to model** — `policy_engine/models/clinic.py:49`. Define `ClinicAiToolModelTrainingStatus` (UNKNOWN, NO_TRAINING, TRAINS_ON_CUSTOMER_DATA, OPT_OUT_AVAILABLE) and `ClinicAiToolPracticeOptOutState` (NOT_APPLICABLE, REQUIRED_NOT_SET, REQUIRED_AND_SET, VERIFIED) as `str, enum.Enum`. Test: `tests/clinic/test_routes_tools.py::test_enums_exposed`.
2. **Add five columns to `ClinicAiTool`** — `policy_engine/models/clinic.py:98`. NOT NULL defaults for the two enums; nullable for the other three. Test: `tests/clinic/test_models_clinic_training.py::test_default_values`.
3. **Write Alembic migration 018** — see verbatim file content below. Test: `tests/migrations/test_018_round_trip.py`.

### Phase 2 — API + validation

4. **Extend Pydantic schemas** — `policy_engine/routes/clinic/tools.py:39-77`. Add `@field_validator('practice_opt_out_state')` requiring `current_user.role in (admin, system_admin)` when value is `verified`. Test: `tests/clinic/test_routes_tools.py::test_staff_cannot_mark_verified`.
5. **Persist verification provenance** — in `create_tool` + `update_tool`, on a `verified` write set `tool.opt_out_verified_at = datetime.utcnow()` and `tool.opt_out_verified_by_user_id = current_user.id`. Test: `test_verified_state_stamps_provenance`.
6. **Idempotent alert dispatch** — helper `_maybe_emit_trains_on_data_alert(db, org_id, tool)`: INSERT into `alerts` with `alert_type='clinic.tool.trains_on_data'`, `organization_id=org_id`. Suppress if existing row in last 30 days. Test: `test_alert_emitted_once_in_30d_window` (use freezegun for the post-window flip).

### Phase 3 — translator + PDF

7. **Translator entry** — add `clinic.tool.trains_on_data` mapping. Title: `"Tool may train on your data"`; description: `"Heads-up: {tool} uses entered prompts to train its public models. Move it to a Sentinel-approved tool if you handle PHI in it."` Next-step: `"Move PHI workflows off this tool, or sign a BAA with the vendor that permits training use."` Test: `tests/services_clinic/test_alert_translator_training.py`.
8. **PDF report row** — `policy_engine/services/clinic_pdf_report.py`. Add `tools_trains_on_customer_data: int` to `ReportData`. In `_collect`: `tool_q.filter(ClinicAiTool.model_training_status == 'trains_on_customer_data').count()`. In `_render_html`, add KV row `<div class="kv"><span class="k">Tools that train on your data</span><span class="v">{data.tools_trains_on_customer_data}</span></div>` inside the "Tools registry" section. Test: `tests/services_clinic/test_pdf_report_training_row.py`.

### Phase 4 — dashboard

9. **Extend Tool TS interface + add banner helper** — `dashboard/src/pages/clinic/ToolList.tsx:13-23`. Add five fields to `interface Tool`. Add `function trainingBannerKey(tool, baaSigned): string | null` returning one of the five locked keys per PRD.v2.md §6.8.2.b. Pull `baaSigned` from the org's `useAuth()` context.
10. **Render banner in ToolList rows** — wrap each `<TableRow>` in a `<React.Fragment>` and append a second row whose cell spans all columns and renders `<MuiAlert severity="warning">{t(trainingBannerKey(tool, baaSigned))}</MuiAlert>` when the helper returns non-null.
11. **Add fields + live banner to ToolEditor** — `dashboard/src/pages/clinic/ToolEditor.tsx`. Three new form controls (two `<TextField select>`, one multiline). Disable the `verified` option when `productRole !== 'admin'`. Live banner above the form preview-renders the current state.

### Phase 5 — i18n

12. **Add five locked English keys** to `clinic_basic.ts`, `clinic_standard.ts`, `clinic_multi_site.ts`, and `enterprise.ts` (fallback). Verbatim copy is in §i18n keys below.
13. **Create Spanish overlays** — `clinic_basic.es.ts`, `clinic_standard.es.ts`, `clinic_multi_site.es.ts`. Strings drafted below; `healthcare-reviewer` sign-off required before merge.

### Phase 6 — verification

14. `pytest tests/clinic tests/services_clinic --cov-fail-under=85`.
15. `npx vitest run src/pages/clinic/__tests__ src/i18n/__tests__`.
16. `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.
17. `bandit -r policy_engine/routes/clinic policy_engine/models/clinic.py policy_engine/services/clinic_pdf_report.py` + `npx tsc --noEmit`.

## Alembic migration 018 — verbatim

File: `alembic/versions/2026_05_17_0000-018_clinic_model_training_status.py`

```python
"""Clinic AI Tools — Model Training Status + Practice Opt-Out State.

PRD.v2.md §6.8.2.a. HEALTH-5 split: vendor capability (model_training_status)
distinguished from practice configuration (practice_opt_out_state) with
provenance fields for the verified state.

Revision ID: 018
Revises: 017
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "clinic_ai_tools" not in set(inspector.get_table_names()):
        return
    existing = {c["name"] for c in inspector.get_columns("clinic_ai_tools")}

    with op.batch_alter_table("clinic_ai_tools") as batch_op:
        if "model_training_status" not in existing:
            batch_op.add_column(sa.Column(
                "model_training_status", sa.String(),
                nullable=False, server_default="unknown"))
        if "practice_opt_out_state" not in existing:
            batch_op.add_column(sa.Column(
                "practice_opt_out_state", sa.String(),
                nullable=False, server_default="not_applicable"))
        if "opt_out_verified_at" not in existing:
            batch_op.add_column(sa.Column(
                "opt_out_verified_at", sa.DateTime(), nullable=True))
        if "opt_out_verified_by_user_id" not in existing:
            batch_op.add_column(sa.Column(
                "opt_out_verified_by_user_id", sa.String(),
                sa.ForeignKey("users.id", ondelete="SET NULL",
                              name="fk_clinic_ai_tools_opt_out_verified_by"),
                nullable=True))
        if "model_training_status_evidence" not in existing:
            batch_op.add_column(sa.Column(
                "model_training_status_evidence", sa.String(length=2000),
                nullable=True))

    op.execute(
        "UPDATE clinic_ai_tools SET model_training_status='unknown' "
        "WHERE model_training_status IS NULL"
    )
    op.execute(
        "UPDATE clinic_ai_tools SET practice_opt_out_state='not_applicable' "
        "WHERE practice_opt_out_state IS NULL"
    )

    # Drop server_default so application code owns the value going forward
    # (matches migration 016 idiom).
    with op.batch_alter_table("clinic_ai_tools") as batch_op:
        batch_op.alter_column("model_training_status", server_default=None)
        batch_op.alter_column("practice_opt_out_state", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "clinic_ai_tools" not in set(inspector.get_table_names()):
        return
    existing = {c["name"] for c in inspector.get_columns("clinic_ai_tools")}
    with op.batch_alter_table("clinic_ai_tools") as batch_op:
        for col in (
            "model_training_status_evidence",
            "opt_out_verified_by_user_id",
            "opt_out_verified_at",
            "practice_opt_out_state",
            "model_training_status",
        ):
            if col in existing:
                batch_op.drop_column(col)
```

## Pydantic schema additions

In `policy_engine/routes/clinic/tools.py:39-77`:

```python
from policy_engine.models.clinic import (
    ClinicAiToolModelTrainingStatus,
    ClinicAiToolPracticeOptOutState,
)
from pydantic import field_validator, ValidationInfo

_VERIFIED = ClinicAiToolPracticeOptOutState.VERIFIED


class ToolCreate(BaseModel):
    # ... existing fields ...
    model_training_status: ClinicAiToolModelTrainingStatus = ClinicAiToolModelTrainingStatus.UNKNOWN
    practice_opt_out_state: ClinicAiToolPracticeOptOutState = ClinicAiToolPracticeOptOutState.NOT_APPLICABLE
    model_training_status_evidence: Optional[str] = Field(None, max_length=2000)

    @field_validator("practice_opt_out_state")
    @classmethod
    def _admin_only_verified(cls, v, info: ValidationInfo):
        user = (info.context or {}).get("current_user")
        if v == _VERIFIED and user is not None and getattr(user, "role", None) not in ("admin", "system_admin"):
            raise ValueError("only Admin may mark opt-out verified")
        return v


class ToolUpdate(BaseModel):
    # same fields Optional + same validator

class ToolResponse(BaseModel):
    # ... existing fields ...
    model_training_status: str
    practice_opt_out_state: str
    opt_out_verified_at: Optional[datetime]
    opt_out_verified_by_user_id: Optional[str]
    model_training_status_evidence: Optional[str]
```

Routes call `ToolCreate.model_validate(payload, context={"current_user": current_user})`.

## Dashboard JSX-pseudo diffs

`ToolList.tsx` row body:

```tsx
{tools.map((tool) => (
  <React.Fragment key={tool.id}>
    <TableRow hover>{/* existing 7 cells */}</TableRow>
    {trainingBannerKey(tool, org.baaSigned) && (
      <TableRow>
        <TableCell colSpan={7} sx={{ p: 0, borderBottom: 0 }}>
          <MuiAlert
            severity={tool.model_training_status === 'trains_on_customer_data' ? 'warning' : 'info'}
            sx={{ borderRadius: 0 }}
          >
            {t(trainingBannerKey(tool, org.baaSigned)!,
               { date: tool.opt_out_verified_at, user: tool.opt_out_verified_by_user_id })}
          </MuiAlert>
        </TableCell>
      </TableRow>
    )}
  </React.Fragment>
))}
```

`ToolEditor.tsx` after the existing fields:

```tsx
<TextField select label={t('clinic.tools.field.model_training_status')}
  value={form.model_training_status} onChange={(e) => set('model_training_status', e.target.value)}>
  <MenuItem value="unknown">Not confirmed yet</MenuItem>
  <MenuItem value="no_training">Vendor does NOT train on prompts</MenuItem>
  <MenuItem value="trains_on_customer_data">Vendor trains on customer prompts</MenuItem>
  <MenuItem value="opt_out_available">Opt-out available from vendor</MenuItem>
</TextField>
<TextField select label={t('clinic.tools.field.practice_opt_out_state')}
  value={form.practice_opt_out_state} onChange={(e) => set('practice_opt_out_state', e.target.value)}>
  <MenuItem value="not_applicable">Not applicable</MenuItem>
  <MenuItem value="required_not_set">Required but NOT set in vendor account</MenuItem>
  <MenuItem value="required_and_set">Set in vendor account, not yet verified</MenuItem>
  <MenuItem value="verified" disabled={productRole !== 'admin'}>Verified by Admin</MenuItem>
</TextField>
<TextField multiline rows={2} label={t('clinic.tools.field.model_training_status_evidence')}
  value={form.model_training_status_evidence}
  onChange={(e) => set('model_training_status_evidence', e.target.value)} />
{trainingBannerKey(form, org.baaSigned) && (
  <MuiAlert severity="warning">{t(trainingBannerKey(form, org.baaSigned)!)}</MuiAlert>
)}
```

## Locked i18n keys (verbatim from PRD.v2.md §6.8.2.b)

**English** (`clinic_basic.ts`, `clinic_standard.ts`, `clinic_multi_site.ts`):

```ts
'clinic.tools.training_status.warning_no_baa':
  'This tool may train its models on what you type here. Treat anything entered as disclosed outside your practice. Do not enter patient information unless your written BAA with the vendor explicitly permits training use — most BAAs do not.',
'clinic.tools.training_status.warning_baa_present':
  "This tool's vendor trains on prompts, but your BAA permits this use. Patient information is still handled under the BAA's terms — confirm with your compliance lead before entering new categories of PHI.",
'clinic.tools.training_status.opt_out_required':
  "This tool trains on prompts unless you turn it off in the vendor's settings. Confirm the opt-out is set, then mark this tool as Verified in Sentinel.",
'clinic.tools.training_status.opt_out_verified':
  'Opt-out verified on {date} by {user}.',
'clinic.tools.training_status.unknown':
  'Status not yet confirmed — assign to a practice admin to investigate.',
```

**Spanish** (`clinic_basic.es.ts` etc., draft — `healthcare-reviewer` sign-off required):

```ts
'clinic.tools.training_status.warning_no_baa':
  'Esta herramienta puede entrenar sus modelos con lo que escriba aquí. Trate todo lo ingresado como divulgado fuera de su consultorio. No ingrese información de pacientes a menos que su BAA por escrito con el proveedor permita explícitamente el uso para entrenamiento — la mayoría de los BAA no lo hacen.',
'clinic.tools.training_status.warning_baa_present':
  'El proveedor de esta herramienta entrena con los mensajes, pero su BAA permite este uso. La información del paciente sigue gestionada bajo los términos del BAA — confirme con su responsable de cumplimiento antes de ingresar nuevas categorías de PHI.',
'clinic.tools.training_status.opt_out_required':
  'Esta herramienta entrena con los mensajes a menos que lo desactive en la configuración del proveedor. Confirme que la exclusión esté activa y luego marque la herramienta como Verificada en Sentinel.',
'clinic.tools.training_status.opt_out_verified':
  'Exclusión verificada el {date} por {user}.',
'clinic.tools.training_status.unknown':
  'Estado aún no confirmado — asigne a un administrador del consultorio para investigar.',
```

## Test plan

| Test file | New/Update | Key assertions |
|---|---|---|
| `tests/clinic/test_routes_tools.py` | update | `test_create_with_training_status_201`; `test_staff_cannot_mark_verified`; `test_admin_marks_verified_stamps_provenance`; `test_alert_emitted_once_in_30d_window`; `test_alert_emitted_after_window` (freezegun) |
| `tests/clinic/test_models_clinic_training.py` | new | enum default values; FK ON DELETE SET NULL semantics |
| `tests/migrations/test_018_round_trip.py` | new | `upgrade head → downgrade -1 → upgrade head`; column presence after each step; pre-existing row backfilled to `'unknown'` |
| `tests/services_clinic/test_alert_translator_training.py` | new | `translate_alert(tier='clinic_basic', alert_type='clinic.tool.trains_on_data')` returns title + verbatim description |
| `tests/services_clinic/test_pdf_report_training_row.py` | new | seed one `trains_on_customer_data` tool + one without; assert HTML contains `'Tools that train on your data'` and count = 1 |
| `dashboard/src/pages/clinic/__tests__/ToolList.test.tsx` | new | banner row renders when status is `trains_on_customer_data` + no BAA; suppressed when status is `no_training` |
| `dashboard/src/pages/clinic/__tests__/ToolEditor.test.tsx` | new | `verified` option disabled for staff productRole; live banner reflects form state |
| `dashboard/src/i18n/__tests__/keys.test.ts` | update | all 5 keys exist in en + es for the three clinic dicts |

## Verification commands

```bash
# Python
pytest tests/clinic tests/services_clinic -x --cov=policy_engine/models/clinic \
       --cov=policy_engine/routes/clinic/tools --cov=policy_engine/services/clinic_alert_translator \
       --cov=policy_engine/services/clinic_pdf_report --cov-fail-under=85 --cov-report=term-missing
# Migration round-trip
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
pytest tests/migrations/test_018_round_trip.py -x
# Static
bandit -r policy_engine/routes/clinic policy_engine/models/clinic.py policy_engine/services/clinic_pdf_report.py
ruff check policy_engine/ && black --check policy_engine/
# Frontend
cd dashboard && npx tsc --noEmit
npx vitest run src/pages/clinic/__tests__ src/i18n/__tests__
```

## PR template body

```markdown
## A1 — AI Tools Registry: Model Training Status

Implements PRD.v2.md §6.8.2 + plans/clinical-shield-v1.md §A1.

### What ships
- Two new enum columns on `clinic_ai_tools`: `model_training_status` + `practice_opt_out_state` (HEALTH-5 split).
- Provenance: `opt_out_verified_at`, `opt_out_verified_by_user_id`, `model_training_status_evidence`.
- Alembic migration 018 with round-trip-tested downgrade.
- Pydantic schemas updated; Admin-only validator on the `verified` state.
- New alert `clinic.tool.trains_on_data` with 30-day idempotency window.
- Monthly PDF row "Tools that train on your data".
- Dashboard banner + editor controls; five locked keys, en + es.

### Out of scope
R1, R2, A2, A3 — see plans/clinical-shield-v1.md.

### Tier
A. Safe to merge to `main` independently.

### Test plan
- [ ] pytest with --cov-fail-under=85
- [ ] alembic upgrade head && downgrade -1 && upgrade head
- [ ] tsc + vitest
- [ ] bandit clean
- [ ] Manual: create tool with trains_on_customer_data, observe banner + one alert; flip back-and-forth in 30d → still one alert
- [ ] Manual: staff user attempts `verified` → 422

### Reviewers
- `database-reviewer` — migration reversibility
- `python-reviewer` — schemas + alert idempotency
- `typescript-reviewer` — banner helper logic
- `healthcare-reviewer` — Spanish copy sign-off + HEALTH-2/5/6 closeout
- `code-reviewer` — final
```
