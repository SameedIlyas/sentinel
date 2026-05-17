/**
 * Clinic Basic — Spanish overlay.
 *
 * Two sources of keys, both intentional:
 *  1. (A1) PRD.v2.md §6.8.2.b — five locked training-status banner keys.
 *     Translations are drafts pending healthcare-reviewer sign-off.
 *  2. (R2 + HEALTH-2) Projected product-role labels and Spanish parity
 *     for the canonical role.* keys.
 *
 * This file is NOT yet wired into resolveDict — the i18n provider does
 * not currently switch locales. It is shipped so the translations are
 * version-controlled before the bilingual provider lands. Lookups fall
 * through to `clinic_basic` (English) for anything missing so the surface
 * degrades gracefully — never to a raw enum key.
 */

import type { TierDict } from './types';

export const clinic_basic_es: TierDict = {
  // ── (A1) Training-status banner copy — PRD.v2.md §6.8.2.b ──────────
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

  // ── (R2) Projected product role ────────────────────────────────────
  'clinic.role.admin': 'Propietario de la práctica',
  'clinic.role.staff': 'Personal',

  // ── (R2) Canonical role labels — Spanish parity with clinic_basic ──
  'role.system_admin': 'Administrador Sentinel',
  'role.admin': 'Propietario de la práctica',
  'role.cmio': 'Clínico principal',
  'role.data_scientist': 'Responsable de IA',
  'role.compliance_officer': 'Gerente de oficina',
  'role.clinical_user': 'Clínico',
  'role.analyst': 'Revisor',
  'role.viewer': 'Observador',
};
