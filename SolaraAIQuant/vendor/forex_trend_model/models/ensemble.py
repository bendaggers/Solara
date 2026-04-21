"""
Ensemble Model: XGBoost + LightGBM + CatBoost
Soft-voting ensemble. SAQ vendored copy — training helpers removed.
LightGBM TypeError fix applied: catches both AttributeError and TypeError in predict_proba.
"""

import numpy as np
import pandas as pd
import joblib
import logging
from pathlib import Path
from sklearn.metrics import balanced_accuracy_score

logger = logging.getLogger(__name__)

LABEL_MAP     = {-1: 0, 0: 1, 1: 2}
LABEL_INVERSE = {0: -1, 1: 0, 2: 1}


def _remap(y):
    return np.vectorize(LABEL_MAP.get)(y)

def _unremap(y):
    return np.vectorize(LABEL_INVERSE.get)(y)


class XGBoostTrendModel:

    DEFAULT_PARAMS = {
        'n_estimators': 500, 'max_depth': 6, 'learning_rate': 0.05,
        'subsample': 0.8, 'colsample_bytree': 0.8, 'min_child_weight': 5,
        'gamma': 0.1, 'reg_alpha': 0.1, 'reg_lambda': 1.0,
        'random_state': 42, 'n_jobs': -1, 'verbosity': 0,
    }

    def __init__(self, params: dict = None):
        self.params       = {**self.DEFAULT_PARAMS, **(params or {})}
        self.model        = None
        self.feature_cols = None
        self.is_fitted    = False

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return _unremap(self.model.predict(X[self.feature_cols]))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        data = X[self.feature_cols]
        try:
            return self.model.predict_proba(data)
        except Exception:
            pass
        try:
            import xgboost as _xgb
            dmatrix = _xgb.DMatrix(data.values)
            raw = self.model.get_booster().predict(dmatrix)
            n = len(data)
            return raw.reshape(n, raw.size // n)
        except Exception:
            pass
        logger.warning("XGBoostTrendModel: all prediction tiers failed — returning uniform probs.")
        return np.full((len(data), 3), 1.0 / 3.0)


class LightGBMTrendModel:

    DEFAULT_PARAMS = {
        'n_estimators': 500, 'max_depth': 6, 'learning_rate': 0.05,
        'num_leaves': 31, 'min_child_samples': 20, 'reg_alpha': 0.1,
        'reg_lambda': 0.1, 'class_weight': 'balanced', 'random_state': 42,
        'n_jobs': -1, 'verbose': -1,
    }

    def __init__(self, params: dict = None):
        self.params       = {**self.DEFAULT_PARAMS, **(params or {})}
        self.model        = None
        self.feature_cols = None
        self.is_fitted    = False

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return _unremap(self.model.predict(X[self.feature_cols]))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        data = X[self.feature_cols]
        try:
            return self.model.predict_proba(data)
        except (AttributeError, TypeError):
            # LightGBM joblib deserialization: internal predict pointer can be
            # None → TypeError. Use booster_ directly; shape guard for single rows.
            try:
                raw = self.model.booster_.predict(
                    data.values if hasattr(data, 'values') else data
                )
                if raw.ndim == 1:
                    raw = raw.reshape(1, -1)
                return raw
            except Exception:
                return self.model.predict_proba(data.values)


class CatBoostTrendModel:

    DEFAULT_PARAMS = {
        'iterations': 500, 'depth': 6, 'learning_rate': 0.05,
        'l2_leaf_reg': 3.0, 'bagging_temperature': 1.0, 'random_strength': 1.0,
        'auto_class_weights': 'Balanced', 'random_seed': 42, 'thread_count': -1,
        'verbose': False, 'loss_function': 'MultiClass',
    }

    def __init__(self, params: dict = None, cat_features: list = None):
        self.params       = {**self.DEFAULT_PARAMS, **(params or {})}
        self.cat_features = cat_features or ['pair_encoded']
        self.model        = None
        self.feature_cols = None
        self.is_fitted    = False

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return _unremap(self.model.predict(X[self.feature_cols]).flatten())

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        data = X[self.feature_cols]
        try:
            return self.model.predict_proba(data)
        except Exception:
            pass
        try:
            return self.model.predict(data, prediction_type='Probability')
        except Exception:
            pass
        try:
            from catboost import CatBoost, Pool
            cat_idx = [i for i, c in enumerate(self.feature_cols) if c in self.cat_features]
            pool = Pool(data.values, cat_features=cat_idx if cat_idx else None)
            return np.array(CatBoost.predict(self.model, pool, prediction_type='Probability'))
        except Exception:
            pass
        logger.warning(
            "CatBoostTrendModel: all prediction tiers failed — returning uniform probs."
        )
        return np.full((len(data), 3), 1.0 / 3.0)


class TrendEnsemble:
    """Soft-voting ensemble of XGBoost + LightGBM + CatBoost."""

    def __init__(
        self,
        lgb_params=None, xgb_params=None, cat_params=None,
        weights=None, use_xgb=True, use_lgb=True, use_cat=True,
        cat_features=None,
    ):
        self.use_xgb      = use_xgb
        self.use_lgb      = use_lgb
        self.use_cat      = use_cat
        self.weights      = weights
        self.feature_cols = None
        self.is_fitted    = False
        self.models       = {}

        if use_lgb:
            self.models['lgbm'] = LightGBMTrendModel(lgb_params)
        if use_xgb:
            try:
                self.models['xgb'] = XGBoostTrendModel(xgb_params)
            except ImportError as e:
                logger.warning(f"XGBoost unavailable: {e}. Skipping.")
                self.use_xgb = False
        if use_cat:
            try:
                self.models['cat'] = CatBoostTrendModel(cat_params, cat_features)
            except ImportError as e:
                logger.warning(f"CatBoost unavailable: {e}. Skipping.")
                self.use_cat = False

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self._check_fitted()
        probs_list, weights_used = [], []
        for i, (name, m) in enumerate(self.models.items()):
            try:
                probs_list.append(m.predict_proba(X))
                weights_used.append(
                    self.weights[i] if (self.weights and i < len(self.weights)) else 1.0
                )
            except Exception as exc:
                logger.warning(f"TrendEnsemble: member '{name}' failed ({exc}) — skipping")
        if not probs_list:
            raise RuntimeError("TrendEnsemble: all member models failed during predict_proba")
        if len(probs_list) == 1:
            return probs_list[0]
        w = np.array(weights_used) / np.sum(weights_used)
        return sum(wi * p for wi, p in zip(w, probs_list))

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return _unremap(np.argmax(self.predict_proba(X), axis=1))

    def _check_fitted(self):
        if not self.is_fitted:
            raise RuntimeError("Ensemble not fitted. Call .fit() first.")

    def save(self, path) -> None:
        joblib.dump(self, Path(path))

    @classmethod
    def load(cls, path) -> 'TrendEnsemble':
        return joblib.load(Path(path))
