"""
optimizer_utils.py - Utilities for multiprocessing in optimizer
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
import pickle

def evaluate_config_worker(args_tuple):
    """Worker function for multiprocessing - must be at module level."""
    config, seed, pickled_data_info = args_tuple
    
    # Unpickle the data
    data_info = pickle.loads(pickled_data_info)
    
    # Set seed
    np.random.seed(seed)
    
    # Call the actual evaluation function directly (no optimizer instance)
    result = evaluate_config_direct(
        config=config,
        features_df=data_info['features_df'],
        train_indices=data_info['train_indices'],
        test_indices=data_info['test_indices'],
        tp_label_cache=data_info['tp_label_cache'],
        feature_selection_mode=data_info['feature_selection_mode'],
        min_features=data_info['min_features'],
        max_features=data_info['max_features'],
        sl_fixed=data_info['sl_fixed'],
        volume_ratio_fixed=data_info['volume_ratio_fixed'],
        lower_wick_fixed=data_info['lower_wick_fixed'],
        max_bars_fixed=data_info['max_bars_fixed'],
        threshold_values=data_info['threshold_values'],
        seed=seed
    )
    
    return result

def evaluate_config_direct(
    config: Dict[str, Any],
    features_df: pd.DataFrame,
    train_indices: np.ndarray,
    test_indices: np.ndarray,
    tp_label_cache: Dict[int, np.ndarray],
    feature_selection_mode: str,
    min_features: int,
    max_features: int,
    sl_fixed: int,
    volume_ratio_fixed: float,
    lower_wick_fixed: float,
    max_bars_fixed: int,
    threshold_values: list,
    seed: int
) -> Dict[str, Any]:
    """Evaluate a configuration directly without optimizer instance."""
    
    try:
        # 1. Get or compute labels for this TP
        from labels import TripleBarrierLabeler
        
        tp_pips = config['tp_pips']
        bb_position = config['bb_position']
        rsi_value = config['rsi_value']
        
        if tp_pips in tp_label_cache:
            labels = tp_label_cache[tp_pips]
        else:
            labeler = TripleBarrierLabeler(
                tp_pips=tp_pips,
                sl_pips=sl_fixed,
                max_bars=max_bars_fixed,
                pip_factor=0.0001
            )
            
            labels = labeler.label_short_entries(
                features_df,
                entry_price_col='next_bar_open'
            )
            
            labels = labels.iloc[:-(labeler.max_bars + 1)].values
            tp_label_cache[tp_pips] = labels
        
        # 2. Get signal indices
        mask = (
            (features_df['bb_position'].iloc[:len(labels)] > bb_position) &
            (features_df['rsi_value'].iloc[:len(labels)] > rsi_value) &
            (features_df['volume_ratio'].iloc[:len(labels)] > volume_ratio_fixed) &
            (features_df['lower_wick'].iloc[:len(labels)] > lower_wick_fixed)
        )
        
        signal_indices = np.where(mask)[0]
        
        if len(signal_indices) < 200:
            return None
        
        # 3. Feature selection (simplified - correlation-based)
        # Get all potential numeric features
        non_feature_columns = {
            'timestamp', 'pair', 'dummy', 'open', 'high', 'low', 'close', 'volume',
            'next_bar_open', 'bb_position', 'rsi_value', 'volume_ratio', 'lower_wick',
            'time', 'date', 'hour', 'minute', 'day', 'month', 'year'
        }
        
        all_columns = set(features_df.columns)
        potential_features = [col for col in all_columns if col not in non_feature_columns]
        numeric_cols = features_df[potential_features].select_dtypes(include=[np.number]).columns.tolist()
        
        if not numeric_cols:
            return None
        
        # Simple correlation-based selection
        X = features_df[numeric_cols].iloc[signal_indices].values
        y = labels[signal_indices]
        
        correlations = []
        for i in range(X.shape[1]):
            corr = np.corrcoef(X[:, i], y)[0, 1]
            if np.isnan(corr):
                corr = 0
            correlations.append((numeric_cols[i], abs(corr)))
        
        correlations.sort(key=lambda x: x[1], reverse=True)
        n_features = min(max_features, max(min_features, len(correlations)))
        selected_features = [col for col, _ in correlations[:n_features]]
        
        # 4. Train/test split
        X = features_df[selected_features].iloc[:len(labels)].values
        y = labels
        
        train_mask = np.isin(signal_indices, train_indices)
        test_mask = np.isin(signal_indices, test_indices)
        
        X_train = X[signal_indices[train_mask]]
        y_train = y[signal_indices[train_mask]]
        X_test = X[signal_indices[test_mask]]
        y_test = y[signal_indices[test_mask]]
        
        if len(X_train) < 100 or len(X_test) < 50:
            return None
        
        # 5. Train model
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced',
            random_state=seed,
            n_jobs=1
        )
        
        model.fit(X_train, y_train)
        
        # 6. Predict and find best threshold - FIXED!
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        
        # Find optimal threshold
        from sklearn.metrics import f1_score, precision_score, recall_score
        best_score = -1
        best_threshold = 0.5
        best_metrics = {}
        
        # Make sure threshold_values is defined
        if not threshold_values:
            threshold_values = [0.4, 0.41, 0.42, 0.43, 0.44, 0.45, 0.46, 0.47, 0.48, 0.49, 0.50]
        
        # Debug counter
        thresholds_tested = 0
        
        for threshold in threshold_values:
            y_pred = (y_pred_proba >= threshold).astype(int)
            
            # Skip if no positive predictions or all predictions are positive
            if y_pred.sum() == 0 or y_pred.sum() == len(y_pred):
                continue
                
            thresholds_tested += 1
            
            f1 = f1_score(y_test, y_pred, zero_division=0)
            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            
            # FIXED SCORE FORMULA: Emphasize precision
            score = (f1 * 0.3) + (precision * 0.5) + (recall * 0.2)
            
            if score > best_score:
                best_score = score
                best_threshold = threshold
                best_metrics = {'f1': f1, 'precision': precision, 'recall': recall}
        
        # If no threshold worked (all gave invalid predictions)
        if best_score == -1:
            # Use threshold that gives ~30% positive rate
            sorted_proba = np.sort(y_pred_proba)
            idx = int(len(sorted_proba) * 0.7)  # 30% positive rate
            if idx < len(sorted_proba):
                best_threshold = sorted_proba[idx]
            else:
                best_threshold = 0.5
            
            y_pred = (y_pred_proba >= best_threshold).astype(int)
            best_metrics = {
                'f1': f1_score(y_test, y_pred, zero_division=0),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0)
            }
        
        # 7. Calculate AUC-PR
        from sklearn.metrics import precision_recall_curve, auc, accuracy_score
        precision_curve, recall_curve, _ = precision_recall_curve(y_test, y_pred_proba)
        auc_pr = auc(recall_curve, precision_curve)
        
        # 8. Final predictions with best threshold
        y_pred = (y_pred_proba >= best_threshold).astype(int)
        accuracy = accuracy_score(y_test, y_pred)
        
        # 9. Calculate composite score - UPDATED!
        signal_bars = len(signal_indices)
        positive_rate = y_train.mean()
        
        # NEW SCORE FORMULA: Emphasize precision even more
        # Precision is most important for trading (avoid false signals)
        score = (
            auc_pr * 0.30 +           # Model discrimination ability
            best_metrics['f1'] * 0.20 +      # Balance
            best_metrics['precision'] * 0.40 + # MOST IMPORTANT: Signal quality
            best_metrics['recall'] * 0.10     # Less important
        )
        
        # Bonus for good AUC-PR relative to baseline
        if auc_pr > positive_rate * 1.5:
            score *= 1.2
        elif auc_pr > positive_rate * 1.2:
            score *= 1.1
        
        # Penalize too few signals
        if signal_bars < 300:
            score *= 0.7
        elif signal_bars < 500:
            score *= 0.9
        
        score = min(max(score, 0), 1)
        
        # 10. One-line result display
        emoji = "🟢" if score > 0.7 else "🟡" if score > 0.6 else "⚪"
        print(f"{emoji} TP={tp_pips} BB={bb_position:.2f} RSI={rsi_value} "
              f"Th={best_threshold:.2f} | "
              f"F1={best_metrics['f1']:.3f} P={best_metrics['precision']:.3f} "
              f"R={best_metrics['recall']:.3f} AP={auc_pr:.3f} S={signal_bars:4d}")
        
        # 11. Create result dictionary
        result = {
            'config_key': config['config_key'],
            'tp_pips': tp_pips,
            'bb_position': bb_position,
            'rsi_value': rsi_value,
            'sl_pips': sl_fixed,
            'volume_ratio': volume_ratio_fixed,
            'lower_wick': lower_wick_fixed,
            'max_bars': max_bars_fixed,
            'threshold': best_threshold,
            'optimal_threshold': best_threshold,
            'signal_filter': 'all',
            'signal_bars': signal_bars,
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'train_positive_rate': positive_rate,
            'test_positive_rate': y_test.mean(),
            'selected_features': selected_features,
            'selected_features_count': len(selected_features),
            'feature_selection_mode': feature_selection_mode,
            'score': score,
            'auc_pr': auc_pr,
            'f1_score': best_metrics['f1'],
            'precision': best_metrics['precision'],
            'recall': best_metrics['recall'],
            'accuracy': accuracy,
            'model': model if score > 0.7 else None,
        }
        
        return result
        
    except Exception as e:
        print(f"❌ Worker error for {config.get('config_key', 'unknown')}: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return None