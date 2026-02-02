#!/usr/bin/env python3
"""
MLP Training Pipeline for MiniFW-AI
Train Multi-Layer Perceptron classifier on labeled flow data.

Usage:
    python3 scripts/train_mlp.py --data data/testing_output/flow_records_labeled.csv
    python3 scripts/train_mlp.py --data data/training/*.csv --output models/mlp_model.pkl
"""
import sys
import argparse
import pickle
from pathlib import Path
from datetime import datetime
import json

try:
    import pandas as pd
    import numpy as np
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPClassifier
    from sklearn.metrics import (
        classification_report,
        confusion_matrix,
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        roc_auc_score
    )
    DEPS_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: Missing required dependencies: {e}")
    print("\nInstall with:")
    print("  pip install scikit-learn pandas numpy")
    sys.exit(1)


# Feature names (must match build_feature_vector_24)
FEATURE_NAMES = [
    # Basic flow (8)
    "duration_sec", "pkt_count_total", "bytes_total", "bytes_per_sec",
    "pkts_per_sec", "avg_pkt_size", "pkt_size_std", "inbound_outbound_ratio",
    # Burst & periodicity (6)
    "max_burst_pkts_1s", "max_burst_bytes_1s", "interarrival_mean_ms",
    "interarrival_std_ms", "interarrival_p95_ms", "small_pkt_ratio",
    # TLS (6)
    "tls_seen", "tls_handshake_time_ms", "ja3_hash_bucket", "sni_len",
    "alpn_h2", "cert_self_signed_suspect",
    # DNS (4)
    "dns_seen", "fqdn_len", "subdomain_depth", "domain_repeat_5min"
]


def load_training_data(data_path: str) -> tuple:
    """
    Load and prepare training data from CSV.
    
    Args:
        data_path: Path to CSV file or directory with CSV files
        
    Returns:
        (X, y, df) - Features, labels, and original dataframe
    """
    path = Path(data_path)
    
    print(f"[1/6] Loading data from: {path}")
    
    if path.is_file():
        df = pd.read_csv(path)
        print(f"  ✓ Loaded {len(df)} records from file")
    elif path.is_dir():
        # Load all CSV files from directory
        csv_files = list(path.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {path}")
        
        print(f"  Found {len(csv_files)} CSV files")
        dfs = [pd.read_csv(f) for f in csv_files]
        df = pd.concat(dfs, ignore_index=True)
        print(f"  ✓ Loaded {len(df)} records from {len(csv_files)} files")
    else:
        raise FileNotFoundError(f"Data path not found: {data_path}")
    
    # Check for required columns
    if 'label' not in df.columns:
        raise ValueError("CSV must have 'label' column (0=normal, 1=threat)")
    
    # Check if features exist
    missing_features = [f for f in FEATURE_NAMES if f not in df.columns]
    if missing_features:
        raise ValueError(f"Missing feature columns: {missing_features}")
    
    # Extract features and labels
    # CRITICAL: Keep as DataFrame to preserve feature names for scaler
    X = df[FEATURE_NAMES].copy()
    y = df['label'].values
    
    # Handle NaN/inf values
    X = X.replace([np.inf, -np.inf], [1e6, -1e6])
    X = X.fillna(0.0)
    
    print(f"\n  Dataset shape: {X.shape}")
    print(f"  Features: {len(FEATURE_NAMES)}")
    print(f"  Samples: {len(X)}")
    
    return X, y, df


def analyze_dataset(X, y):
    """Print dataset statistics."""
    print("\n[2/6] Dataset Analysis")
    print("=" * 60)
    
    # Class distribution
    unique, counts = np.unique(y, return_counts=True)
    total = len(y)
    
    print(f"\nClass Distribution:")
    for label, count in zip(unique, counts):
        label_name = "Threat" if label == 1 else "Normal"
        percentage = (count / total) * 100
        print(f"  {label_name} ({label}): {count:5d} ({percentage:5.1f}%)")
    
    # Check balance
    threat_ratio = counts[1] / total if len(counts) > 1 else 0
    print(f"\nThreat Ratio: {threat_ratio:.2%}")
    
    if threat_ratio < 0.15 or threat_ratio > 0.45:
        print("  ⚠ WARNING: Imbalanced dataset!")
        print("    Recommended: 20-40% threats for best results")
    else:
        print("  ✓ Good class balance")
    
    # Feature statistics (handle both DataFrame and array)
    X_values = X.values if hasattr(X, 'values') else X
    
    print(f"\nFeature Statistics:")
    print(f"  Mean: {X_values.mean():.2f}")
    print(f"  Std:  {X_values.std():.2f}")
    print(f"  Min:  {X_values.min():.2f}")
    print(f"  Max:  {X_values.max():.2f}")
    
    # Check for zero variance features
    feature_stds = X_values.std(axis=0)
    zero_var = np.sum(feature_stds == 0)
    if zero_var > 0:
        print(f"\n  ⚠ WARNING: {zero_var} features have zero variance")


def train_mlp_model(X_train, y_train, X_test, y_test) -> tuple:
    """
    Train MLP classifier.
    
    Args:
        X_train: Training features (DataFrame or array)
        y_train: Training labels
        X_test: Test features (DataFrame or array)
        y_test: Test labels
    
    Returns:
        (model, scaler, metrics)
    """
    print("\n[3/6] Training MLP Classifier")
    print("=" * 60)
    
    # Normalize features
    # CRITICAL: scaler.fit_transform() preserves DataFrame feature names
    print("\nNormalizing features with StandardScaler...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Initialize MLP
    print("\nMLP Configuration:")
    print("  Architecture: Input(24) -> Dense(32) -> Dense(16) -> Output(2)")
    print("  Activation: ReLU")
    print("  Solver: Adam")
    print("  Max iterations: 500")
    
    model = MLPClassifier(
        hidden_layer_sizes=(32, 16),
        activation='relu',
        solver='adam',
        alpha=0.0001,
        batch_size='auto',
        learning_rate='adaptive',
        learning_rate_init=0.001,
        max_iter=500,
        random_state=42,
        verbose=True,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=10
    )
    
    # Train
    print("\nTraining model...")
    model.fit(X_train_scaled, y_train)
    
    print(f"\n✓ Training completed")
    print(f"  Iterations: {model.n_iter_}")
    print(f"  Final loss: {model.loss_:.4f}")
    
    # Evaluate
    print("\n[4/6] Model Evaluation")
    print("=" * 60)
    
    y_pred_train = model.predict(X_train_scaled)
    y_pred_test = model.predict(X_test_scaled)
    
    y_proba_train = model.predict_proba(X_train_scaled)[:, 1]
    y_proba_test = model.predict_proba(X_test_scaled)[:, 1]
    
    # Metrics
    metrics = {
        'train': {
            'accuracy': accuracy_score(y_train, y_pred_train),
            'precision': precision_score(y_train, y_pred_train, zero_division=0),
            'recall': recall_score(y_train, y_pred_train, zero_division=0),
            'f1': f1_score(y_train, y_pred_train, zero_division=0),
            'auc': roc_auc_score(y_train, y_proba_train) if len(np.unique(y_train)) > 1 else 0.0
        },
        'test': {
            'accuracy': accuracy_score(y_test, y_pred_test),
            'precision': precision_score(y_test, y_pred_test, zero_division=0),
            'recall': recall_score(y_test, y_pred_test, zero_division=0),
            'f1': f1_score(y_test, y_pred_test, zero_division=0),
            'auc': roc_auc_score(y_test, y_proba_test) if len(np.unique(y_test)) > 1 else 0.0
        }
    }
    
    print("\nTraining Set Performance:")
    print(f"  Accuracy:  {metrics['train']['accuracy']:.4f}")
    print(f"  Precision: {metrics['train']['precision']:.4f}")
    print(f"  Recall:    {metrics['train']['recall']:.4f}")
    print(f"  F1 Score:  {metrics['train']['f1']:.4f}")
    print(f"  AUC-ROC:   {metrics['train']['auc']:.4f}")
    
    print("\nTest Set Performance:")
    print(f"  Accuracy:  {metrics['test']['accuracy']:.4f}")
    print(f"  Precision: {metrics['test']['precision']:.4f}")
    print(f"  Recall:    {metrics['test']['recall']:.4f}")
    print(f"  F1 Score:  {metrics['test']['f1']:.4f}")
    print(f"  AUC-ROC:   {metrics['test']['auc']:.4f}")
    
    # Confusion matrix
    print("\nConfusion Matrix (Test Set):")
    cm = confusion_matrix(y_test, y_pred_test)
    print(f"  TN: {cm[0,0]:5d}  |  FP: {cm[0,1]:5d}")
    print(f"  FN: {cm[1,0]:5d}  |  TP: {cm[1,1]:5d}")
    
    # Classification report
    print("\nDetailed Classification Report (Test Set):")
    print(classification_report(y_test, y_pred_test, target_names=['Normal', 'Threat']))
    
    return model, scaler, metrics


def save_model(
    model: MLPClassifier,
    scaler: StandardScaler,
    metrics: dict,
    output_path: str,
    metadata: dict
):
    """Save trained model with metadata."""
    print(f"\n[5/6] Saving Model")
    print("=" * 60)
    
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Prepare model package
    model_package = {
        'model': model,
        'scaler': scaler,
        'metadata': {
            'trained_at': datetime.now().isoformat(),
            'n_samples': metadata['n_samples'],
            'n_features': len(FEATURE_NAMES),
            'feature_names': FEATURE_NAMES,
            'accuracy': metrics['test']['accuracy'],
            'precision': metrics['test']['precision'],
            'recall': metrics['test']['recall'],
            'f1_score': metrics['test']['f1'],
            'auc_roc': metrics['test']['auc'],
            'class_distribution': metadata['class_distribution'],
            'model_type': 'MLPClassifier',
            'hidden_layers': model.hidden_layer_sizes,
            'iterations': model.n_iter_,
        }
    }
    
    # Save with pickle
    with output.open('wb') as f:
        pickle.dump(model_package, f)
    
    print(f"\n✓ Model saved to: {output}")
    print(f"  File size: {output.stat().st_size / 1024:.1f} KB")
    
    # Save metrics as JSON for easy viewing
    metrics_file = output.parent / f"{output.stem}_metrics.json"
    with metrics_file.open('w') as f:
        json.dump({
            'train': metrics['train'],
            'test': metrics['test'],
            'metadata': model_package['metadata']
        }, f, indent=2)
    
    print(f"✓ Metrics saved to: {metrics_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Train MLP classifier for MiniFW-AI flow-based threat detection"
    )
    parser.add_argument(
        '--data',
        required=True,
        help='Path to labeled CSV file or directory with CSV files'
    )
    parser.add_argument(
        '--output',
        default='./models/mlp_engine.pkl',
        help='Output path for trained model (default: ./models/mlp_engine.pkl)'
    )
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.2,
        help='Test set size (default: 0.2 = 20%%)'
    )
    parser.add_argument(
        '--random-state',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MiniFW-AI MLP Training Pipeline")
    print("=" * 60)
    print()
    
    try:
        # Load data
        X, y, df = load_training_data(args.data)
        
        # Analyze
        analyze_dataset(X, y)
        
        # Train/test split
        print(f"\nSplitting data: {(1-args.test_size)*100:.0f}% train, {args.test_size*100:.0f}% test")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=args.test_size,
            random_state=args.random_state,
            stratify=y
        )
        
        print(f"  Train: {len(X_train)} samples")
        print(f"  Test:  {len(X_test)} samples")
        
        # Train
        model, scaler, metrics = train_mlp_model(X_train, y_train, X_test, y_test)
        
        # Save
        unique, counts = np.unique(y, return_counts=True)
        metadata = {
            'n_samples': len(X),
            'class_distribution': {
                'normal': int(counts[0]),
                'threat': int(counts[1]) if len(counts) > 1 else 0
            }
        }
        
        save_model(model, scaler, metrics, args.output, metadata)
        
        # Final summary
        print("\n[6/6] Training Complete!")
        print("=" * 60)
        print(f"\n✓ Model ready for deployment")
        print(f"\nTo use this model:")
        print(f"  1. Copy to production: cp {args.output} /opt/ritapi_vsentinel/mlp_engine.pkl")
        print(f"  2. Set environment: export MINIFW_MLP_MODEL=/opt/ritapi_vsentinel/mlp_engine.pkl")
        print(f"  3. Restart MiniFW-AI: sudo systemctl restart minifw-ai")
        print()
        print(f"Test accuracy: {metrics['test']['accuracy']:.2%}")
        print(f"Precision: {metrics['test']['precision']:.2%}")
        print(f"Recall: {metrics['test']['recall']:.2%}")
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
