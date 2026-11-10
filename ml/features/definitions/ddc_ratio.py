"""Digital Documentation Compliance (DDC) Ratio.

Measures the rate at which an entity completes required operational
tasks and documentation through digital channels. High DDC indicates
operational discipline — timely filings, complete records, responsive
to compliance requests — which correlates with creditworthiness.

Expected range: 0.0 - 1.0 (completion ratio).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(df: pd.DataFrame) -> pd.Series:
    """Compute the DDC Ratio for each entity.

    Args:
        df: DataFrame with one row per entity, expected columns:
            - ``tasks_completed``: number of required operational /
              compliance tasks completed in the last 12 months.
            - ``tasks_assigned``: total tasks assigned in the same period.
            - ``avg_completion_days``: average days to complete a task.
            - ``tasks_overdue``: number of tasks completed past deadline.

    Returns:
        pd.Series with DDC Ratio values in [0, 1], indexed like the input.

    Implementation notes (stub):
        1. Base ratio = tasks_completed / tasks_assigned.
        2. Penalize for overdue tasks (timeliness factor).
        3. Penalize for slow average completion time.
        4. Floor at 0.0 if no tasks were assigned (no signal).
    """
    completed = df["tasks_completed"].values.astype(float)
    assigned = df["tasks_assigned"].values.astype(float)
    avg_days = df["avg_completion_days"].values.astype(float)
    overdue = df["tasks_overdue"].values.astype(float)

    # Base completion ratio
    assigned_safe = np.where(assigned > 0, assigned, 1.0)
    base_ratio = np.clip(completed / assigned_safe, 0.0, 1.0)

    # Timeliness factor: penalize overdue tasks
    overdue_ratio = np.where(completed > 0, overdue / completed, 0.0)
    timeliness = 1.0 - np.clip(overdue_ratio, 0.0, 1.0)

    # Speed factor: sigmoid around 7-day benchmark
    speed = 1.0 / (1.0 + np.exp(0.3 * (avg_days - 7.0)))

    # No-signal gate: if no tasks assigned, DDC is undefined -> 0
    has_tasks = (assigned > 0).astype(float)

    # Composite DDC
    ddc = (0.5 * base_ratio + 0.3 * timeliness + 0.2 * speed) * has_tasks
    ddc = np.clip(ddc, 0.0, 1.0)

    return pd.Series(ddc, index=df.index, name="ddc_ratio")
