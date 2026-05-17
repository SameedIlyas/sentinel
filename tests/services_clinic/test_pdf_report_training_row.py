"""PDF compliance report renders the 'Tools that train on your data' row.

PRD.v2.md §6.8.2.c — the monthly clinic compliance PDF must surface a
count of tools whose vendor trains on customer prompts in the Tools
registry section.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from policy_engine.models.clinic import (
    ClinicAiToolModelTrainingStatus,
)
from policy_engine.services.clinic_pdf_report import _collect, _render_html


pytestmark = pytest.mark.clinic


def test_collect_counts_trains_on_customer_data(db_session, clinic_org) -> None:
    """_collect aggregates the count of trains_on_customer_data tools."""
    from tests.factories.clinic import make_clinic_tool

    make_clinic_tool(
        db_session,
        clinic_org,
        name="GPT4 free",
        model_training_status=ClinicAiToolModelTrainingStatus.TRAINS_ON_CUSTOMER_DATA,
    )
    make_clinic_tool(
        db_session,
        clinic_org,
        name="Nuance DAX",
        model_training_status=ClinicAiToolModelTrainingStatus.NO_TRAINING,
    )
    period_start = datetime.utcnow() - timedelta(days=30)
    period_end = datetime.utcnow()
    data = _collect(db_session, clinic_org, period_start, period_end)
    assert data.tools_trains_on_customer_data == 1


def test_render_html_includes_training_row(db_session, clinic_org) -> None:
    """The rendered HTML PDF body contains the training-status row."""
    from tests.factories.clinic import make_clinic_tool

    make_clinic_tool(
        db_session,
        clinic_org,
        name="GPT4 free",
        model_training_status=ClinicAiToolModelTrainingStatus.TRAINS_ON_CUSTOMER_DATA,
    )
    period_start = datetime.utcnow() - timedelta(days=30)
    period_end = datetime.utcnow()
    data = _collect(db_session, clinic_org, period_start, period_end)
    html = _render_html(data)
    assert "Tools that train on your data" in html
    # Count value must surface in the kv row.
    assert ">1<" in html or 'class="v">1<' in html


def test_render_html_row_present_with_zero_count(db_session, clinic_org) -> None:
    """Row renders even when the count is zero so compliance officers see the
    field exists (avoids 'missing because zero' confusion)."""
    period_start = datetime.utcnow() - timedelta(days=30)
    period_end = datetime.utcnow()
    data = _collect(db_session, clinic_org, period_start, period_end)
    html = _render_html(data)
    assert "Tools that train on your data" in html
    assert data.tools_trains_on_customer_data == 0
