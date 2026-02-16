"""
Artifact publishing and serialization.

This module handles:
1. Saving all training artifacts to disk
2. Creating artifact manifests
3. Loading artifacts for deployment
4. Artifact validation

Artifact types:
- Model (.pkl)
- Features (.csv)
- Configuration (.json)
- Metrics (.json)
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import shutil
import hashlib
import joblib


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ArtifactManifest:
    """Manifest of all published artifacts."""
    version: str
    created_at: str
    config_id: str
    
    # File paths (relative to artifacts directory)
    model_path: str
    features_path: str
    trading_config_path: str
    hyperparameters_path: str
    threshold_path: str
    fold_metrics_path: str
    aggregate_metrics_path: str
    regime_breakdown_path: str
    
    # Checksums for validation
    checksums: Dict[str, str]
    
    # Summary info
    summary: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArtifactManifest':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ArtifactPaths:
    """Paths to all artifact files."""
    base_dir: Path
    model_dir: Path
    features_dir: Path
    config_dir: Path
    metrics_dir: Path
    
    # Individual files
    model_file: Path
    features_file: Path
    trading_config_file: Path
    hyperparameters_file: Path
    threshold_file: Path
    fold_metrics_file: Path
    aggregate_metrics_file: Path
    regime_breakdown_file: Path
    manifest_file: Path
    
    @classmethod
    def from_base_dir(cls, base_dir: Union[str, Path]) -> 'ArtifactPaths':
        """Create paths from base directory."""
        base = Path(base_dir)
        
        return cls(
            base_dir=base,
            model_dir=base / 'model',
            features_dir=base / 'features',
            config_dir=base / 'config',
            metrics_dir=base / 'metrics',
            model_file=base / 'model' / 'short_entry_model.pkl',
            features_file=base / 'features' / 'selected_features.csv',
            trading_config_file=base / 'config' / 'trading_config.json',
            hyperparameters_file=base / 'config' / 'hyperparameters.json',
            threshold_file=base / 'config' / 'threshold.json',
            fold_metrics_file=base / 'metrics' / 'fold_metrics.json',
            aggregate_metrics_file=base / 'metrics' / 'aggregate_metrics.json',
            regime_breakdown_file=base / 'metrics' / 'regime_breakdown.json',
            manifest_file=base / 'manifest.json'
        )
    
    def create_directories(self) -> None:
        """Create all artifact directories."""
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)


# =============================================================================
# JSON UTILITIES
# =============================================================================

class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""
    
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif pd.isna(obj):
            return None
        return super().default(obj)


def save_json(data: Any, filepath: Union[str, Path], indent: int = 2) -> None:
    """
    Save data to JSON file with numpy support.
    
    Args:
        data: Data to save
        filepath: Path to output file
        indent: JSON indentation
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, cls=NumpyEncoder, indent=indent)


def load_json(filepath: Union[str, Path]) -> Any:
    """
    Load data from JSON file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Loaded data
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# =============================================================================
# CHECKSUM UTILITIES
# =============================================================================

def compute_file_checksum(filepath: Union[str, Path]) -> str:
    """
    Compute MD5 checksum of a file.
    
    Args:
        filepath: Path to file
        
    Returns:
        Hex digest of MD5 hash
    """
    hash_md5 = hashlib.md5()
    
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    
    return hash_md5.hexdigest()


def verify_checksum(filepath: Union[str, Path], expected: str) -> bool:
    """
    Verify file checksum matches expected.
    
    Args:
        filepath: Path to file
        expected: Expected checksum
        
    Returns:
        True if matches
    """
    actual = compute_file_checksum(filepath)
    return actual == expected


# =============================================================================
# ARTIFACT SAVING
# =============================================================================

def save_model_artifact(
    model: Any,
    filepath: Union[str, Path]
) -> str:
    """
    Save model to pickle file.
    
    Args:
        model: Model object to save (TrainedModel or raw model)
        filepath: Path to output file
        
    Returns:
        Path to saved file
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # If TrainedModel, extract the data
    if hasattr(model, 'model'):
        save_dict = {
            'model': model.model,
            'feature_names': model.feature_names,
            'hyperparameters': model.hyperparameters,
            'is_calibrated': model.is_calibrated,
            'calibration_method': model.calibration_method,
            'training_rows': getattr(model, 'training_rows', 0),
            'training_class_balance': getattr(model, 'training_class_balance', None)
        }
    else:
        save_dict = {'model': model}
    
    joblib.dump(save_dict, path)
    
    return str(path)


def save_features_artifact(
    features: List[str],
    importances: Dict[str, float],
    filepath: Union[str, Path]
) -> str:
    """
    Save features to CSV file.
    
    Args:
        features: List of feature names
        importances: Dictionary of feature importances
        filepath: Path to output file
        
    Returns:
        Path to saved file
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    df = pd.DataFrame([
        {
            'feature_name': feat,
            'rank': i + 1,
            'importance': importances.get(feat, 0.0)
        }
        for i, feat in enumerate(features)
    ])
    
    df.to_csv(path, index=False)
    
    return str(path)


def save_trading_config_artifact(
    config: Dict[str, Any],
    filepath: Union[str, Path]
) -> str:
    """
    Save trading configuration to JSON.
    
    Args:
        config: Configuration dictionary
        filepath: Path to output file
        
    Returns:
        Path to saved file
    """
    save_json(config, filepath)
    return str(filepath)


def save_hyperparameters_artifact(
    hyperparameters: Dict[str, Any],
    model_type: str,
    filepath: Union[str, Path]
) -> str:
    """
    Save hyperparameters to JSON.
    
    Args:
        hyperparameters: Hyperparameter dictionary
        model_type: Type of model
        filepath: Path to output file
        
    Returns:
        Path to saved file
    """
    data = {
        'model_type': model_type,
        **hyperparameters
    }
    
    save_json(data, filepath)
    return str(filepath)


def save_threshold_artifact(
    threshold: float,
    optimization_method: str,
    min_trades_constraint: int,
    filepath: Union[str, Path]
) -> str:
    """
    Save threshold configuration to JSON.
    
    Args:
        threshold: Probability threshold
        optimization_method: Method used for optimization
        min_trades_constraint: Minimum trades constraint
        filepath: Path to output file
        
    Returns:
        Path to saved file
    """
    data = {
        'probability_threshold': threshold,
        'optimization_method': optimization_method,
        'threshold_range': [0.50, 0.90],
        'threshold_step': 0.01,
        'min_trades_constraint': min_trades_constraint
    }
    
    save_json(data, filepath)
    return str(filepath)


def save_fold_metrics_artifact(
    fold_results: List[Dict[str, Any]],
    filepath: Union[str, Path]
) -> str:
    """
    Save per-fold metrics to JSON.
    
    Args:
        fold_results: List of fold result dictionaries
        filepath: Path to output file
        
    Returns:
        Path to saved file
    """
    data = {'folds': fold_results}
    save_json(data, filepath)
    return str(filepath)


def save_aggregate_metrics_artifact(
    metrics: Dict[str, Any],
    filepath: Union[str, Path]
) -> str:
    """
    Save aggregate metrics to JSON.
    
    Args:
        metrics: Aggregate metrics dictionary
        filepath: Path to output file
        
    Returns:
        Path to saved file
    """
    save_json(metrics, filepath)
    return str(filepath)


def save_regime_breakdown_artifact(
    breakdown: Dict[str, Dict[str, float]],
    recommendation: str,
    filepath: Union[str, Path]
) -> str:
    """
    Save regime breakdown to JSON.
    
    Args:
        breakdown: Regime breakdown dictionary
        recommendation: Trading recommendation
        filepath: Path to output file
        
    Returns:
        Path to saved file
    """
    data = {
        'breakdown': breakdown,
        'recommendation': recommendation
    }
    
    save_json(data, filepath)
    return str(filepath)


# =============================================================================
# COMPLETE ARTIFACT PUBLISHING
# =============================================================================

def publish_artifacts(
    final_model: Any,  # FinalModel
    best_config: Any,  # BestConfiguration
    fold_results: List[Dict[str, Any]],
    output_dir: Union[str, Path],
    version: str = "1.0.0"
) -> ArtifactManifest:
    """
    Publish all training artifacts to disk.
    
    This is the main entry point for artifact publishing.
    
    Args:
        final_model: The final trained model
        best_config: The best configuration selected
        fold_results: List of fold result dictionaries
        output_dir: Base directory for artifacts
        version: Version string for the artifacts
        
    Returns:
        ArtifactManifest with all file paths and checksums
    """
    paths = ArtifactPaths.from_base_dir(output_dir)
    paths.create_directories()
    
    saved_files = {}
    
    # 1. Save model
    save_model_artifact(
        model=final_model.trained_model,
        filepath=paths.model_file
    )
    saved_files['model'] = paths.model_file
    
    # 2. Save features
    save_features_artifact(
        features=final_model.features,
        importances=final_model.feature_importances,
        filepath=paths.features_file
    )
    saved_files['features'] = paths.features_file
    
    # 3. Save trading config
    trading_config = {
        'config_id': final_model.config.config_id,
        'bb_threshold': final_model.config.bb_threshold,
        'rsi_threshold': final_model.config.rsi_threshold,
        'tp_pips': final_model.config.tp_pips,
        'sl_pips': final_model.config.sl_pips,
        'max_holding_bars': final_model.config.max_holding_bars,
        'direction': 'SHORT'
    }
    save_trading_config_artifact(
        config=trading_config,
        filepath=paths.trading_config_file
    )
    saved_files['trading_config'] = paths.trading_config_file
    
    # 4. Save hyperparameters
    save_hyperparameters_artifact(
        hyperparameters=final_model.hyperparameters,
        model_type='GradientBoostingClassifier',
        filepath=paths.hyperparameters_file
    )
    saved_files['hyperparameters'] = paths.hyperparameters_file
    
    # 5. Save threshold
    save_threshold_artifact(
        threshold=final_model.threshold,
        optimization_method='ev_maximization',
        min_trades_constraint=30,
        filepath=paths.threshold_file
    )
    saved_files['threshold'] = paths.threshold_file
    
    # 6. Save fold metrics
    save_fold_metrics_artifact(
        fold_results=fold_results,
        filepath=paths.fold_metrics_file
    )
    saved_files['fold_metrics'] = paths.fold_metrics_file
    
    # 7. Save aggregate metrics
    aggregate_metrics = {
        'precision': {
            'mean': final_model.expected_precision,
            'std': best_config.aggregate_metrics.precision_std if best_config.aggregate_metrics else 0
        },
        'recall': {
            'mean': best_config.aggregate_metrics.recall_mean if best_config.aggregate_metrics else 0,
            'std': best_config.aggregate_metrics.recall_std if best_config.aggregate_metrics else 0
        },
        'f1_score': {
            'mean': best_config.aggregate_metrics.f1_mean if best_config.aggregate_metrics else 0,
            'std': best_config.aggregate_metrics.f1_std if best_config.aggregate_metrics else 0
        },
        'auc_pr': {
            'mean': best_config.aggregate_metrics.auc_pr_mean if best_config.aggregate_metrics else 0,
            'std': best_config.aggregate_metrics.auc_pr_std if best_config.aggregate_metrics else 0
        },
        'expected_value': {
            'mean': final_model.expected_ev,
            'std': best_config.aggregate_metrics.ev_std if best_config.aggregate_metrics else 0
        },
        'total_trades': best_config.aggregate_metrics.total_trades if best_config.aggregate_metrics else 0,
        'n_folds': best_config.aggregate_metrics.n_folds if best_config.aggregate_metrics else 0,
        'total_training_rows': final_model.total_training_rows,
        'total_calibration_rows': final_model.total_calibration_rows
    }
    save_aggregate_metrics_artifact(
        metrics=aggregate_metrics,
        filepath=paths.aggregate_metrics_file
    )
    saved_files['aggregate_metrics'] = paths.aggregate_metrics_file
    
    # 8. Save regime breakdown
    save_regime_breakdown_artifact(
        breakdown=final_model.regime_breakdown,
        recommendation=final_model.regime_recommendation,
        filepath=paths.regime_breakdown_file
    )
    saved_files['regime_breakdown'] = paths.regime_breakdown_file
    
    # Compute checksums
    checksums = {}
    for name, filepath in saved_files.items():
        checksums[name] = compute_file_checksum(filepath)
    
    # Create manifest
    manifest = ArtifactManifest(
        version=version,
        created_at=datetime.now().isoformat(),
        config_id=final_model.config.config_id,
        model_path=str(paths.model_file.relative_to(paths.base_dir)),
        features_path=str(paths.features_file.relative_to(paths.base_dir)),
        trading_config_path=str(paths.trading_config_file.relative_to(paths.base_dir)),
        hyperparameters_path=str(paths.hyperparameters_file.relative_to(paths.base_dir)),
        threshold_path=str(paths.threshold_file.relative_to(paths.base_dir)),
        fold_metrics_path=str(paths.fold_metrics_file.relative_to(paths.base_dir)),
        aggregate_metrics_path=str(paths.aggregate_metrics_file.relative_to(paths.base_dir)),
        regime_breakdown_path=str(paths.regime_breakdown_file.relative_to(paths.base_dir)),
        checksums=checksums,
        summary={
            'n_features': len(final_model.features),
            'threshold': final_model.threshold,
            'expected_precision': final_model.expected_precision,
            'expected_ev': final_model.expected_ev,
            'training_rows': final_model.total_training_rows
        }
    )
    
    # Save manifest
    save_json(manifest.to_dict(), paths.manifest_file)
    
    return manifest


# =============================================================================
# ARTIFACT LOADING
# =============================================================================

def load_manifest(artifacts_dir: Union[str, Path]) -> ArtifactManifest:
    """
    Load artifact manifest from directory.
    
    Args:
        artifacts_dir: Path to artifacts directory
        
    Returns:
        ArtifactManifest
    """
    paths = ArtifactPaths.from_base_dir(artifacts_dir)
    data = load_json(paths.manifest_file)
    return ArtifactManifest.from_dict(data)


def load_model(artifacts_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Load trained model from artifacts.
    
    Args:
        artifacts_dir: Path to artifacts directory
        
    Returns:
        Dictionary with model and metadata
    """
    paths = ArtifactPaths.from_base_dir(artifacts_dir)
    return joblib.load(paths.model_file)


def load_features(artifacts_dir: Union[str, Path]) -> pd.DataFrame:
    """
    Load selected features from artifacts.
    
    Args:
        artifacts_dir: Path to artifacts directory
        
    Returns:
        DataFrame with features
    """
    paths = ArtifactPaths.from_base_dir(artifacts_dir)
    return pd.read_csv(paths.features_file)


def load_trading_config(artifacts_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Load trading configuration from artifacts.
    
    Args:
        artifacts_dir: Path to artifacts directory
        
    Returns:
        Trading configuration dictionary
    """
    paths = ArtifactPaths.from_base_dir(artifacts_dir)
    return load_json(paths.trading_config_file)


def load_threshold(artifacts_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Load threshold configuration from artifacts.
    
    Args:
        artifacts_dir: Path to artifacts directory
        
    Returns:
        Threshold configuration dictionary
    """
    paths = ArtifactPaths.from_base_dir(artifacts_dir)
    return load_json(paths.threshold_file)


def load_all_artifacts(artifacts_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Load all artifacts from directory.
    
    Args:
        artifacts_dir: Path to artifacts directory
        
    Returns:
        Dictionary with all artifacts
    """
    paths = ArtifactPaths.from_base_dir(artifacts_dir)
    
    return {
        'manifest': load_json(paths.manifest_file),
        'model': joblib.load(paths.model_file),
        'features': pd.read_csv(paths.features_file),
        'trading_config': load_json(paths.trading_config_file),
        'hyperparameters': load_json(paths.hyperparameters_file),
        'threshold': load_json(paths.threshold_file),
        'fold_metrics': load_json(paths.fold_metrics_file),
        'aggregate_metrics': load_json(paths.aggregate_metrics_file),
        'regime_breakdown': load_json(paths.regime_breakdown_file)
    }


# =============================================================================
# ARTIFACT VALIDATION
# =============================================================================

def validate_artifacts(artifacts_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Validate all artifacts in directory.
    
    Checks:
    - All files exist
    - Checksums match
    - Files are readable
    
    Args:
        artifacts_dir: Path to artifacts directory
        
    Returns:
        Validation report dictionary
    """
    paths = ArtifactPaths.from_base_dir(artifacts_dir)
    
    report = {
        'is_valid': True,
        'files': {},
        'issues': []
    }
    
    # Check manifest exists
    if not paths.manifest_file.exists():
        report['is_valid'] = False
        report['issues'].append("Manifest file not found")
        return report
    
    # Load manifest
    try:
        manifest = load_manifest(artifacts_dir)
    except Exception as e:
        report['is_valid'] = False
        report['issues'].append(f"Failed to load manifest: {e}")
        return report
    
    # Check each file
    files_to_check = [
        ('model', paths.model_file),
        ('features', paths.features_file),
        ('trading_config', paths.trading_config_file),
        ('hyperparameters', paths.hyperparameters_file),
        ('threshold', paths.threshold_file),
        ('fold_metrics', paths.fold_metrics_file),
        ('aggregate_metrics', paths.aggregate_metrics_file),
        ('regime_breakdown', paths.regime_breakdown_file)
    ]
    
    for name, filepath in files_to_check:
        file_report = {
            'exists': filepath.exists(),
            'checksum_valid': False,
            'readable': False
        }
        
        if not filepath.exists():
            report['is_valid'] = False
            report['issues'].append(f"File not found: {name}")
        else:
            # Check checksum
            if name in manifest.checksums:
                file_report['checksum_valid'] = verify_checksum(
                    filepath, 
                    manifest.checksums[name]
                )
                if not file_report['checksum_valid']:
                    report['is_valid'] = False
                    report['issues'].append(f"Checksum mismatch: {name}")
            
            # Check readable
            try:
                if name == 'model':
                    joblib.load(filepath)
                elif name == 'features':
                    pd.read_csv(filepath)
                else:
                    load_json(filepath)
                file_report['readable'] = True
            except Exception as e:
                report['is_valid'] = False
                report['issues'].append(f"Cannot read {name}: {e}")
        
        report['files'][name] = file_report
    
    return report


def verify_model_compatibility(
    artifacts_dir: Union[str, Path],
    required_features: List[str]
) -> Dict[str, Any]:
    """
    Verify model is compatible with given features.
    
    Args:
        artifacts_dir: Path to artifacts directory
        required_features: Features that must be present
        
    Returns:
        Compatibility report dictionary
    """
    report = {
        'is_compatible': True,
        'issues': [],
        'model_features': [],
        'missing_features': [],
        'extra_features': []
    }
    
    try:
        features_df = load_features(artifacts_dir)
        model_features = features_df['feature_name'].tolist()
        report['model_features'] = model_features
    except Exception as e:
        report['is_compatible'] = False
        report['issues'].append(f"Cannot load features: {e}")
        return report
    
    required_set = set(required_features)
    model_set = set(model_features)
    
    missing = required_set - model_set
    extra = model_set - required_set
    
    report['missing_features'] = list(missing)
    report['extra_features'] = list(extra)
    
    if missing:
        report['is_compatible'] = False
        report['issues'].append(f"Missing {len(missing)} required features")
    
    return report


# =============================================================================
# ARTIFACT MANAGEMENT
# =============================================================================

def copy_artifacts(
    source_dir: Union[str, Path],
    dest_dir: Union[str, Path]
) -> None:
    """
    Copy all artifacts to new directory.
    
    Args:
        source_dir: Source artifacts directory
        dest_dir: Destination directory
    """
    source = Path(source_dir)
    dest = Path(dest_dir)
    
    if dest.exists():
        shutil.rmtree(dest)
    
    shutil.copytree(source, dest)


def archive_artifacts(
    artifacts_dir: Union[str, Path],
    archive_path: Union[str, Path],
    format: str = 'zip'
) -> str:
    """
    Create archive of artifacts.
    
    Args:
        artifacts_dir: Path to artifacts directory
        archive_path: Path for output archive (without extension)
        format: Archive format ('zip', 'tar', 'gztar')
        
    Returns:
        Path to created archive
    """
    return shutil.make_archive(
        str(archive_path),
        format,
        str(artifacts_dir)
    )


def get_artifact_summary(artifacts_dir: Union[str, Path]) -> str:
    """
    Generate human-readable summary of artifacts.
    
    Args:
        artifacts_dir: Path to artifacts directory
        
    Returns:
        Summary string
    """
    try:
        manifest = load_manifest(artifacts_dir)
    except Exception as e:
        return f"Cannot load artifacts: {e}"
    
    lines = [
        "=" * 60,
        "ARTIFACT SUMMARY",
        "=" * 60,
        f"Version: {manifest.version}",
        f"Created: {manifest.created_at}",
        f"Config ID: {manifest.config_id}",
        "",
        "Files:",
        f"  Model:          {manifest.model_path}",
        f"  Features:       {manifest.features_path}",
        f"  Trading Config: {manifest.trading_config_path}",
        f"  Hyperparams:    {manifest.hyperparameters_path}",
        f"  Threshold:      {manifest.threshold_path}",
        f"  Fold Metrics:   {manifest.fold_metrics_path}",
        f"  Agg Metrics:    {manifest.aggregate_metrics_path}",
        f"  Regime:         {manifest.regime_breakdown_path}",
        "",
        "Summary:",
        f"  Features:       {manifest.summary.get('n_features', 'N/A')}",
        f"  Threshold:      {manifest.summary.get('threshold', 'N/A')}",
        f"  Precision:      {manifest.summary.get('expected_precision', 'N/A')}",
        f"  Expected Value: {manifest.summary.get('expected_ev', 'N/A')}",
        f"  Training Rows:  {manifest.summary.get('training_rows', 'N/A')}",
        "=" * 60
    ]
    
    return "\n".join(lines)


# =============================================================================
# DEPLOYMENT UTILITIES
# =============================================================================

def prepare_for_deployment(
    artifacts_dir: Union[str, Path],
    deployment_dir: Union[str, Path],
    include_metrics: bool = False
) -> Dict[str, str]:
    """
    Prepare minimal artifacts for deployment.
    
    Only copies essential files:
    - Model
    - Features
    - Trading config
    - Threshold
    
    Args:
        artifacts_dir: Source artifacts directory
        deployment_dir: Deployment target directory
        include_metrics: Include metrics files
        
    Returns:
        Dictionary of copied files
    """
    source_paths = ArtifactPaths.from_base_dir(artifacts_dir)
    dest_paths = ArtifactPaths.from_base_dir(deployment_dir)
    dest_paths.create_directories()
    
    copied = {}
    
    # Essential files
    essential = [
        ('model', source_paths.model_file, dest_paths.model_file),
        ('features', source_paths.features_file, dest_paths.features_file),
        ('trading_config', source_paths.trading_config_file, dest_paths.trading_config_file),
        ('threshold', source_paths.threshold_file, dest_paths.threshold_file),
        ('hyperparameters', source_paths.hyperparameters_file, dest_paths.hyperparameters_file)
    ]
    
    for name, src, dst in essential:
        if src.exists():
            shutil.copy2(src, dst)
            copied[name] = str(dst)
    
    # Optional metrics
    if include_metrics:
        metrics = [
            ('aggregate_metrics', source_paths.aggregate_metrics_file, dest_paths.aggregate_metrics_file),
            ('regime_breakdown', source_paths.regime_breakdown_file, dest_paths.regime_breakdown_file)
        ]
        
        for name, src, dst in metrics:
            if src.exists():
                shutil.copy2(src, dst)
                copied[name] = str(dst)
    
    # Create deployment manifest
    deployment_manifest = {
        'source_version': load_manifest(artifacts_dir).version,
        'deployed_at': datetime.now().isoformat(),
        'files': list(copied.keys())
    }
    
    save_json(deployment_manifest, dest_paths.base_dir / 'deployment_manifest.json')
    
    return copied
