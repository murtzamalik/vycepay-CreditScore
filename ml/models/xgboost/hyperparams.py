"""Default hyperparameters and search space for XGBoost credit scoring model.

The defaults are tuned for binary classification of serious delinquency
(90+ DPD within 12 months) on imbalanced datasets typical of credit scoring.
"""

from typing import Any

# Default hyperparameters for production XGBoost model.
# scale_pos_weight is set assuming ~5% positive (delinquent) rate;
# adjust based on actual class imbalance in training data.
DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "gamma": 0.1,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "scale_pos_weight": 19.0,  # ~5% positive rate -> (1 - 0.05) / 0.05
    "random_state": 42,
    "n_jobs": -1,
    "early_stopping_rounds": 50,
    "tree_method": "hist",
}

# Hyperparameter search space for Optuna / RandomizedSearchCV.
# Each value is a tuple of (distribution_type, *args) for flexibility.
SEARCH_SPACE: dict[str, tuple[str, ...]] = {
    "max_depth": ("int", "3", "10"),
    "learning_rate": ("log_uniform", "0.005", "0.3"),
    "n_estimators": ("int", "200", "1500"),
    "min_child_weight": ("int", "1", "20"),
    "subsample": ("uniform", "0.6", "1.0"),
    "colsample_bytree": ("uniform", "0.5", "1.0"),
    "gamma": ("uniform", "0.0", "0.5"),
    "reg_alpha": ("log_uniform", "0.001", "10.0"),
    "reg_lambda": ("log_uniform", "0.001", "10.0"),
    "scale_pos_weight": ("uniform", "1.0", "30.0"),
}

# Six core VyceScore features in canonical order.
CORE_FEATURES: list[str] = [
    "cblri",
    "utdi",
    "scfv",
    "ddc_ratio",
    "niq_score",
    "gos_index",
]

# Performance targets for model acceptance.
PERFORMANCE_TARGETS: dict[str, float] = {
    "auc_roc": 0.75,
    "precision_at_1000": 0.30,
    "calibration_error": 0.05,
}
