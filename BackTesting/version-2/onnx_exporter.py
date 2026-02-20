"""
ONNX Model Exporter for Solara Trading System.

This script exports the trained model to ONNX format
for native execution in MetaTrader 5.

Requirements:
    pip install onnx onnxmltools skl2onnx onnxruntime

Usage:
    python onnx_exporter.py artifacts/ output/
"""

import sys
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

# ONNX conversion libraries
try:
    import onnx
    from onnx import helper, TensorProto
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    print("⚠️  ONNX libraries not installed. Run:")
    print("    pip install onnx onnxruntime")

# LightGBM to ONNX
try:
    import onnxmltools
    from onnxmltools.convert import convert_lightgbm
    from onnxmltools.convert.common.data_types import FloatTensorType
    LIGHTGBM_ONNX_AVAILABLE = True
except ImportError:
    LIGHTGBM_ONNX_AVAILABLE = False

# Sklearn to ONNX
try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType as SklearnFloatTensorType
    SKLEARN_ONNX_AVAILABLE = True
except ImportError:
    SKLEARN_ONNX_AVAILABLE = False


class ONNXExporter:
    """
    Exports trained Solara model to ONNX format for MT5.
    """
    
    def __init__(self, artifacts_dir: str):
        """
        Load model and artifacts.
        
        Args:
            artifacts_dir: Path to artifacts folder
        """
        self.artifacts_dir = Path(artifacts_dir)
        
        # Load model
        model_path = self.artifacts_dir / "model" / "short_entry_model.pkl"
        self.trained_model = joblib.load(model_path)
        
        # Extract the actual model (might be wrapped in calibration)
        self.model = self._extract_base_model()
        self.model_type = type(self.model).__name__
        
        # Load features
        features_path = self.artifacts_dir / "features" / "selected_features.csv"
        features_df = pd.read_csv(features_path)
        self.feature_names = features_df['feature_name'].tolist()
        self.n_features = len(self.feature_names)
        
        # Load config
        config_path = self.artifacts_dir / "config" / "trading_config.json"
        with open(config_path) as f:
            self.config = json.load(f)
        
        threshold_path = self.artifacts_dir / "config" / "threshold.json"
        with open(threshold_path) as f:
            self.threshold = json.load(f)
        
        print(f"✅ Loaded model: {self.model_type}")
        print(f"   Features: {self.n_features}")
        print(f"   Feature names: {self.feature_names}")
    
    def _extract_base_model(self):
        """Extract the base model from calibration wrapper."""
        model = self.trained_model.model
        
        # Handle CalibratedClassifierCV
        if hasattr(model, 'calibrated_classifiers_'):
            # Get the first calibrated classifier's base estimator
            return model.calibrated_classifiers_[0].estimator
        elif hasattr(model, 'estimator'):
            return model.estimator
        else:
            return model
    
    def export_to_onnx(self, output_dir: str) -> str:
        """
        Export model to ONNX format.
        
        Args:
            output_dir: Directory to save ONNX model
            
        Returns:
            Path to saved ONNX model
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        onnx_path = output_path / "solara_model.onnx"
        
        # Determine model type and export
        if 'LGBMClassifier' in self.model_type or 'LightGBM' in self.model_type:
            self._export_lightgbm(onnx_path)
        elif 'GradientBoosting' in self.model_type:
            self._export_sklearn(onnx_path)
        elif 'RandomForest' in self.model_type:
            self._export_sklearn(onnx_path)
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
        
        # Validate the exported model
        self._validate_onnx(onnx_path)
        
        # Save metadata for MT5
        self._save_mt5_metadata(output_path)
        
        return str(onnx_path)
    
    def _export_lightgbm(self, onnx_path: Path):
        """Export LightGBM model to ONNX."""
        if not LIGHTGBM_ONNX_AVAILABLE:
            raise ImportError("onnxmltools not installed. Run: pip install onnxmltools")
        
        print(f"📦 Exporting LightGBM model to ONNX...")
        
        # Define input type
        initial_type = [('features', FloatTensorType([None, self.n_features]))]
        
        # Convert to ONNX
        onnx_model = convert_lightgbm(
            self.model,
            initial_types=initial_type,
            target_opset=12
        )
        
        # Save
        onnxmltools.utils.save_model(onnx_model, str(onnx_path))
        
        print(f"✅ Saved to: {onnx_path}")
    
    def _export_sklearn(self, onnx_path: Path):
        """Export sklearn model to ONNX."""
        if not SKLEARN_ONNX_AVAILABLE:
            raise ImportError("skl2onnx not installed. Run: pip install skl2onnx")
        
        print(f"📦 Exporting sklearn model to ONNX...")
        
        # Define input type
        initial_type = [('features', SklearnFloatTensorType([None, self.n_features]))]
        
        # Convert to ONNX
        onnx_model = convert_sklearn(
            self.model,
            initial_types=initial_type,
            target_opset=12
        )
        
        # Save
        with open(onnx_path, 'wb') as f:
            f.write(onnx_model.SerializeToString())
        
        print(f"✅ Saved to: {onnx_path}")
    
    def _validate_onnx(self, onnx_path: Path):
        """Validate exported ONNX model."""
        print(f"🔍 Validating ONNX model...")
        
        # Load and check
        onnx_model = onnx.load(str(onnx_path))
        onnx.checker.check_model(onnx_model)
        
        # Test inference
        session = ort.InferenceSession(str(onnx_path))
        
        # Create dummy input
        dummy_input = np.random.randn(1, self.n_features).astype(np.float32)
        
        # Get input/output names
        input_name = session.get_inputs()[0].name
        output_names = [o.name for o in session.get_outputs()]
        
        # Run inference
        outputs = session.run(output_names, {input_name: dummy_input})
        
        print(f"   Input name: {input_name}")
        print(f"   Input shape: (batch, {self.n_features})")
        print(f"   Output names: {output_names}")
        print(f"   Test inference: ✅ Passed")
        
        # Compare with original model
        self._compare_predictions(session, input_name)
    
    def _compare_predictions(self, session, input_name: str):
        """Compare ONNX predictions with original model."""
        print(f"🔍 Comparing ONNX vs original predictions...")
        
        # Create test data
        np.random.seed(42)
        test_data = np.random.randn(10, self.n_features).astype(np.float32)
        
        # Original model predictions
        original_proba = self.model.predict_proba(test_data)[:, 1]
        
        # ONNX predictions
        onnx_outputs = session.run(None, {input_name: test_data})
        
        # Find probability output
        onnx_proba = None
        for output in onnx_outputs:
            if len(output.shape) == 2 and output.shape[1] == 2:
                onnx_proba = output[:, 1]
                break
            elif len(output.shape) == 1 and len(output) == len(test_data):
                # Some models output just the positive class probability
                onnx_proba = output
                break
        
        if onnx_proba is None:
            print("   ⚠️  Could not extract probabilities from ONNX output")
            return
        
        # Compare
        max_diff = np.max(np.abs(original_proba - onnx_proba))
        mean_diff = np.mean(np.abs(original_proba - onnx_proba))
        
        print(f"   Max difference: {max_diff:.6f}")
        print(f"   Mean difference: {mean_diff:.6f}")
        
        if max_diff < 0.01:
            print(f"   ✅ Predictions match!")
        else:
            print(f"   ⚠️  Predictions differ (may be due to floating point)")
    
    def _save_mt5_metadata(self, output_dir: Path):
        """Save metadata needed by MT5 EA."""
        metadata = {
            'model_type': self.model_type,
            'n_features': self.n_features,
            'feature_names': self.feature_names,
            'feature_order': {name: i for i, name in enumerate(self.feature_names)},
            'bb_threshold': self.config['bb_threshold'],
            'rsi_threshold': self.config['rsi_threshold'],
            'tp_pips': self.config['tp_pips'],
            'sl_pips': self.config['sl_pips'],
            'max_holding_bars': self.config['max_holding_bars'],
            'probability_threshold': self.threshold['probability_threshold']
        }
        
        # Save as JSON
        metadata_path = output_dir / "model_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Saved metadata to: {metadata_path}")
        
        # Save feature info as MQL5 include file
        self._save_mql5_constants(output_dir, metadata)
    
    def _save_mql5_constants(self, output_dir: Path, metadata: Dict):
        """Generate MQL5 header file with model constants."""
        mql5_path = output_dir / "SolaraModelConstants.mqh"
        
        content = f'''//+------------------------------------------------------------------+
//| SolaraModelConstants.mqh - Auto-generated model constants         |
//| DO NOT EDIT - Generated by onnx_exporter.py                       |
//+------------------------------------------------------------------+

#ifndef SOLARA_MODEL_CONSTANTS_MQH
#define SOLARA_MODEL_CONSTANTS_MQH

//--- Model Configuration
#define MODEL_FEATURES       {metadata['n_features']}
#define BB_THRESHOLD         {metadata['bb_threshold']}
#define RSI_THRESHOLD        {metadata['rsi_threshold']}
#define TP_PIPS              {metadata['tp_pips']}
#define SL_PIPS              {metadata['sl_pips']}
#define MAX_HOLDING_BARS     {metadata['max_holding_bars']}
#define PROBABILITY_THRESHOLD {metadata['probability_threshold']}

//--- Feature Indices (order matters!)
'''
        
        # Add feature indices
        for i, name in enumerate(metadata['feature_names']):
            const_name = f"FEATURE_{name.upper()}"
            content += f"#define {const_name} {i}\n"
        
        content += f'''
//--- Feature Names Array
string FeatureNames[MODEL_FEATURES] = {{
'''
        for i, name in enumerate(metadata['feature_names']):
            comma = ',' if i < len(metadata['feature_names']) - 1 else ''
            content += f'    "{name}"{comma}\n'
        
        content += '''};

#endif // SOLARA_MODEL_CONSTANTS_MQH
'''
        
        with open(mql5_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Saved MQL5 constants to: {mql5_path}")


def main():
    """Main export function."""
    if len(sys.argv) < 3:
        print("Usage: python onnx_exporter.py <artifacts_dir> <output_dir>")
        print("\nExample:")
        print("  python onnx_exporter.py artifacts/ onnx_output/")
        sys.exit(1)
    
    artifacts_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not ONNX_AVAILABLE:
        print("\n❌ ONNX libraries not installed!")
        print("Run: pip install onnx onnxruntime onnxmltools skl2onnx")
        sys.exit(1)
    
    # Export
    exporter = ONNXExporter(artifacts_dir)
    onnx_path = exporter.export_to_onnx(output_dir)
    
    print(f"\n{'='*60}")
    print(f"✅ ONNX EXPORT COMPLETE")
    print(f"{'='*60}")
    print(f"Model: {onnx_path}")
    print(f"\nCopy these files to your MT5 installation:")
    print(f"  1. solara_model.onnx → MQL5/Files/")
    print(f"  2. SolaraModelConstants.mqh → MQL5/Include/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
