#!/usr/bin/env python3
"""
Test MLP Inference
Test trained MLP model on flow data.

Usage:
    python3 testing/test_mlp_inference.py --model models/mlp_engine.pkl
    python3 testing/test_mlp_inference.py --model models/mlp_engine.pkl --data data/testing_output/flow_records_labeled.csv
"""
import sys
import argparse
from pathlib import Path
import json

# Add app to path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / 'app'))

try:
    import pandas as pd
    import numpy as np
    from sklearn.metrics import classification_report, confusion_matrix
    PANDAS_AVAILABLE = True
except ImportError:
    print("ERROR: pandas and scikit-learn required")
    print("Install with: pip install pandas scikit-learn")
    sys.exit(1)

from minifw_ai.utils.mlp_engine import MLPThreatDetector
from minifw_ai.collector_flow import FlowStats, build_feature_vector_24


def create_flow_from_record(record: dict) -> FlowStats:
    """Create FlowStats object from CSV record."""
    flow = FlowStats(
        client_ip=str(record.get('client_ip', '0.0.0.0')),
        dst_ip=str(record.get('dst_ip', '0.0.0.0')),
        dst_port=int(record.get('dst_port', 0)),
        proto=str(record.get('proto', 'tcp'))
    )
    
    # Set timing
    if 'timestamp' in record:
        flow.first_seen = float(record['timestamp'])
    if 'duration' in record:
        flow.last_seen = flow.first_seen + float(record['duration'])
    
    # Set counters
    if 'packets' in record:
        flow.pkt_count = int(record['packets'])
    if 'bytes' in record:
        flow.bytes_sent = int(record['bytes'])
    
    # Set domain info
    if 'domain' in record and record['domain']:
        flow.domain = str(record['domain'])
    if 'sni' in record and record['sni']:
        flow.sni = str(record['sni'])
        flow.tls_seen = True
    
    return flow


def test_single_inference(detector: MLPThreatDetector):
    """Test single flow inference."""
    print("\n[TEST 1] Single Flow Inference")
    print("=" * 60)
    
    # Create a test flow (suspicious pattern)
    flow = FlowStats(
        client_ip="192.168.1.100",
        dst_ip="8.8.8.8",
        dst_port=443,
        proto="tcp"
    )
    
    # Simulate suspicious behavior
    flow.pkt_count = 500
    flow.bytes_sent = 50000
    flow.domain = "slot-gacor.xyz"
    flow.sni = "slot-gacor.xyz"
    flow.tls_seen = True
    
    # Inference
    is_threat, proba = detector.is_suspicious(flow, return_probability=True)
    
    print(f"\nTest Flow:")
    print(f"  Client: {flow.client_ip}")
    print(f"  Destination: {flow.dst_ip}:{flow.dst_port}")
    print(f"  Domain: {flow.domain}")
    print(f"  Packets: {flow.pkt_count}")
    
    print(f"\nMLP Inference:")
    print(f"  Threat: {is_threat}")
    print(f"  Probability: {proba:.4f}")
    
    if is_threat:
        print("  ✓ DETECTED as threat")
    else:
        print("  ✗ Classified as normal")


def test_batch_inference(detector: MLPThreatDetector, data_path: str):
    """Test batch inference on dataset."""
    print("\n[TEST 2] Batch Inference on Dataset")
    print("=" * 60)
    
    # Load data
    print(f"\nLoading data from: {data_path}")
    df = pd.read_csv(data_path)
    print(f"✓ Loaded {len(df)} records")
    
    # Create FlowStats objects
    print("\nConverting to FlowStats objects...")
    flows = []
    for idx, row in df.iterrows():
        flow = create_flow_from_record(row.to_dict())
        flows.append(flow)
    
    print(f"✓ Created {len(flows)} flow objects")
    
    # Batch predict
    print("\nRunning batch inference...")
    results = detector.batch_predict(flows)
    
    # Analyze results
    predictions = [is_threat for is_threat, _ in results]
    probabilities = [proba for _, proba in results]
    
    threat_count = sum(predictions)
    print(f"\n✓ Inference complete")
    print(f"  Total flows: {len(flows)}")
    print(f"  Detected threats: {threat_count}")
    print(f"  Threat rate: {threat_count/len(flows)*100:.1f}%")
    
    # If labels available, evaluate accuracy
    if 'label' in df.columns:
        print("\n[TEST 3] Model Accuracy Evaluation")
        print("=" * 60)
        
        y_true = df['label'].values
        y_pred = np.array(predictions, dtype=int)
        
        # Metrics
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        print(f"\nPerformance Metrics:")
        print(f"  Accuracy:  {accuracy:.4f} ({accuracy*100:.1f}%)")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall:    {recall:.4f}")
        print(f"  F1 Score:  {f1:.4f}")
        
        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        print(f"\nConfusion Matrix:")
        print(f"  TN: {cm[0,0]:5d}  |  FP: {cm[0,1]:5d}")
        print(f"  FN: {cm[1,0]:5d}  |  TP: {cm[1,1]:5d}")
        
        # Classification report
        print(f"\nDetailed Report:")
        print(classification_report(y_true, y_pred, target_names=['Normal', 'Threat']))
        
        # Sample predictions
        print("\n[TEST 4] Sample Predictions")
        print("=" * 60)
        
        # Show some correct and incorrect predictions
        print("\nCorrect Threat Detections (first 5):")
        correct_threats = df[(y_true == 1) & (y_pred == 1)].head(5)
        for idx, row in correct_threats.iterrows():
            print(f"  {row.get('client_ip', 'N/A'):15s} -> {row.get('domain', 'N/A'):30s} [P={probabilities[idx]:.3f}]")
        
        print("\nMissed Threats (first 5):")
        missed_threats = df[(y_true == 1) & (y_pred == 0)].head(5)
        for idx, row in missed_threats.iterrows():
            print(f"  {row.get('client_ip', 'N/A'):15s} -> {row.get('domain', 'N/A'):30s} [P={probabilities[idx]:.3f}]")
        
        print("\nFalse Positives (first 5):")
        false_positives = df[(y_true == 0) & (y_pred == 1)].head(5)
        for idx, row in false_positives.iterrows():
            print(f"  {row.get('client_ip', 'N/A'):15s} -> {row.get('domain', 'N/A'):30s} [P={probabilities[idx]:.3f}]")


def test_model_info(detector: MLPThreatDetector):
    """Display model information."""
    print("\n[MODEL INFO]")
    print("=" * 60)
    
    stats = detector.get_stats()
    
    print(f"\nModel Status:")
    print(f"  Loaded: {stats['model_loaded']}")
    print(f"  Path: {stats['model_path']}")
    print(f"  Threshold: {stats['threshold']}")
    print(f"  Has Scaler: {stats['has_scaler']}")
    
    print(f"\nInference Statistics:")
    print(f"  Total inferences: {stats['total_inferences']}")
    print(f"  Threats detected: {stats['total_threats_detected']}")
    print(f"  Threat rate: {stats['threat_rate']*100:.1f}%")


def main():
    parser = argparse.ArgumentParser(
        description="Test MLP inference on flow data"
    )
    parser.add_argument(
        '--model',
        required=True,
        help='Path to trained MLP model (.pkl file)'
    )
    parser.add_argument(
        '--data',
        help='Path to test CSV data (optional, for batch testing)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.5,
        help='Threat probability threshold (default: 0.5)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MiniFW-AI MLP Inference Test")
    print("=" * 60)
    
    try:
        # Load model
        print(f"\nLoading MLP model from: {args.model}")
        detector = MLPThreatDetector(
            model_path=args.model,
            threshold=args.threshold
        )
        
        if not detector.model_loaded:
            print("❌ Failed to load model")
            sys.exit(1)
        
        print("✓ Model loaded successfully")
        
        # Test single inference
        test_single_inference(detector)
        
        # Test batch inference if data provided
        if args.data:
            test_batch_inference(detector, args.data)
        
        # Model info
        test_model_info(detector)
        
        print("\n" + "=" * 60)
        print("✓ All tests completed!")
        print("=" * 60)
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
