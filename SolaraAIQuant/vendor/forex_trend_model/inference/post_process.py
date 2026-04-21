"""Post-processing and decision logic for raw model probability outputs."""

import numpy as np
import logging

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    'min_confidence': 0.45,
    'min_margin': 0.15,
    'switch_threshold': 0.55,
    'ood_zscore': 4.0,
}


def compute_entropy_confidence(probs_dict: dict) -> float:
    p = np.array([probs_dict['down'], probs_dict['sideways'], probs_dict['up']])
    entropy = -np.sum(p * np.log(p + 1e-10))
    return float(np.clip(1 - entropy / np.log(3), 0, 1))


def compute_trend_strength(probs_dict: dict) -> float:
    return float(abs(probs_dict['up'] - probs_dict['down']))


def compute_regime_tag(probs_dict: dict, confidence: float, atr_pct: float = None) -> str:
    directional = probs_dict['up'] + probs_dict['down']
    if confidence < 0.3:
        return 'low_confidence'
    if atr_pct is not None and atr_pct > 1.5:
        return 'volatile'
    if directional > 0.6:
        return 'trending'
    return 'ranging'


def check_ood(features: dict, training_stats: dict, threshold: float = 4.0):
    ood_features = []
    for col, val in features.items():
        if col not in training_stats:
            continue
        stats = training_stats[col]
        std = stats.get('std', 1)
        if std < 1e-10:
            continue
        if abs(val - stats.get('mean', 0)) / std > threshold:
            ood_features.append(col)
    return len(ood_features) > 0, ood_features


def post_process_prediction(
    probs_dict: dict,
    prior_state: str,
    thresholds: dict = None,
    features: dict = None,
    training_stats: dict = None,
    atr_pct: float = None,
):
    thresholds = thresholds or DEFAULT_THRESHOLDS
    confidence = compute_entropy_confidence(probs_dict)
    strength   = compute_trend_strength(probs_dict)

    ood_flag, ood_features = False, []
    if features is not None and training_stats is not None:
        ood_flag, ood_features = check_ood(features, training_stats, threshold=thresholds['ood_zscore'])

    regime_tag = compute_regime_tag(probs_dict, confidence, atr_pct)

    if ood_flag:
        return ('sideways', False, 'ood_detected', confidence, strength, regime_tag, True, ood_features)
    if confidence < thresholds['min_confidence']:
        return ('sideways', False, 'low_confidence', confidence, strength, regime_tag, False, ood_features)

    best_class = max(probs_dict, key=probs_dict.get)
    best_prob  = probs_dict[best_class]
    sorted_probs = sorted(probs_dict.values(), reverse=True)
    margin = sorted_probs[0] - sorted_probs[1]
    class_map = {'up': 'uptrend', 'down': 'downtrend', 'sideways': 'sideways'}
    best_class_name = class_map.get(best_class, best_class)

    if margin < thresholds['min_margin']:
        return ('sideways', True, 'insufficient_margin', confidence, strength, regime_tag, False, ood_features)
    if best_class_name != prior_state and best_prob < thresholds['switch_threshold']:
        return (prior_state, True, 'hysteresis', confidence, strength, regime_tag, False, ood_features)

    return (best_class_name, True, 'strong_signal', confidence, strength, regime_tag, False, ood_features)
