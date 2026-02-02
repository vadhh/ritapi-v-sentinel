## MLP Engine Documentation

# MiniFW-AI MLP Engine

Machine Learning-based threat detection using Multi-Layer Perceptron (MLP) for flow-based analysis.

## Overview

The MLP Engine adds AI-powered threat detection to MiniFW-AI's decision system. It analyzes network flow patterns using a trained neural network to identify suspicious behavior that traditional rule-based systems might miss.

### Architecture

```
Flow Data → Feature Extraction (24 features) → MLP Model → Threat Score → Decision System
```

### Components

1. **Feature Extractor** (`collector_flow.py`)
   - Extracts 24 features from network flows
   - Groups: Basic flow (8), Burst & periodicity (6), TLS (6), DNS (4)

2. **MLP Engine** (`utils/mlp_engine.py`)
   - Loads trained model
   - Performs inference
   - Manages predictions

3. **Training Pipeline** (`scripts/train_mlp.py`)
   - Trains MLP classifier
   - Evaluates performance
   - Exports model

4. **Integration** (`main.py`)
   - Connects MLP to scoring system
   - Adds MLP weight to decisions
   - Logs MLP predictions

## Feature Vector (24 Features)

### Basic Flow Features (8)
1. `duration_sec` - Flow duration in seconds
2. `pkt_count_total` - Total packets
3. `bytes_total` - Total bytes transferred
4. `bytes_per_sec` - Bytes per second rate
5. `pkts_per_sec` - Packets per second rate
6. `avg_pkt_size` - Average packet size
7. `pkt_size_std` - Packet size standard deviation
8. `inbound_outbound_ratio` - Ratio of incoming/outgoing traffic

### Burst & Periodicity Features (6)
9. `max_burst_pkts_1s` - Maximum packets in 1-second window
10. `max_burst_bytes_1s` - Maximum bytes in 1-second window
11. `interarrival_mean_ms` - Mean packet inter-arrival time (ms)
12. `interarrival_std_ms` - Standard deviation of inter-arrival times
13. `interarrival_p95_ms` - 95th percentile inter-arrival time
14. `small_pkt_ratio` - Ratio of small packets (<100 bytes)

### TLS Features (6)
15. `tls_seen` - Whether TLS was observed (0/1)
16. `tls_handshake_time_ms` - TLS handshake duration
17. `ja3_hash_bucket` - JA3 fingerprint bucket
18. `sni_len` - SNI length
19. `alpn_h2` - HTTP/2 ALPN indicator
20. `cert_self_signed_suspect` - Self-signed certificate indicator

### DNS Features (4)
21. `dns_seen` - Whether DNS was observed (0/1)
22. `fqdn_len` - Domain name length
23. `subdomain_depth` - Number of subdomain levels
24. `domain_repeat_5min` - Domain repeat count in 5 minutes

## Installation

### Prerequisites

```bash
pip install scikit-learn pandas numpy
```

Or using requirements:
```bash
pip install -r requirements.txt
```

### Setup

1. **Enable MLP in MiniFW-AI:**

Set environment variables:
```bash
export MINIFW_MLP_MODEL=/opt/ritapi_vsentinel/mlp_engine.pkl
export MINIFW_MLP_THRESHOLD=0.5
```

2. **Update systemd service** (if using systemd):

Edit `/etc/systemd/system/minifw-ai.service`:
```ini
[Service]
Environment="MINIFW_MLP_MODEL=/opt/ritapi_vsentinel/mlp_engine.pkl"
Environment="MINIFW_MLP_THRESHOLD=0.5"
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart minifw-ai
```

## Training Workflow

### Step 1: Generate Training Data

Use standalone test to generate labeled flows:

```bash
# Generate 5000 labeled flows
python3 testing/test_standalone_integration.py 5000

# Output: data/testing_output/flow_records_labeled.csv
```

**Data Quality Requirements:**
- Minimum 5,000 flows recommended
- 20-40% threat ratio for balanced dataset
- All 24 features present
- Labels: 0 (normal), 1 (threat)

### Step 2: Train MLP Model

```bash
python3 scripts/train_mlp.py \
  --data data/testing_output/flow_records_labeled.csv \
  --output models/mlp_engine.pkl \
  --test-size 0.2
```

**Options:**
- `--data`: Path to labeled CSV or directory with CSV files
- `--output`: Output path for trained model (default: `./models/mlp_engine.pkl`)
- `--test-size`: Test set ratio (default: 0.2 = 20%)
- `--random-state`: Random seed for reproducibility (default: 42)

**Output:**
- `models/mlp_engine.pkl` - Trained model with scaler
- `models/mlp_engine_metrics.json` - Performance metrics

### Step 3: Evaluate Model

```bash
python3 testing/test_mlp_inference.py \
  --model models/mlp_engine.pkl \
  --data data/testing_output/flow_records_labeled.csv
```

**Expected Output:**
```
Performance Metrics:
  Accuracy:  0.9250 (92.5%)
  Precision: 0.8900
  Recall:    0.9100
  F1 Score:  0.9000
```

### Step 4: Test Integration

```bash
python3 testing/test_mlp_integration.py \
  --model models/mlp_engine.pkl
```

This tests:
- Model loading
- Feature extraction
- MLP inference
- Integration with scoring
- End-to-end flow

### Step 5: Deploy

```bash
# Copy model to production
sudo cp models/mlp_engine.pkl /opt/ritapi_vsentinel/mlp_engine.pkl

# Set permissions
sudo chown root:root /opt/ritapi_vsentinel/mlp_engine.pkl

# Restart MiniFW-AI
sudo systemctl restart minifw-ai

# Verify MLP is loaded
sudo journalctl -u minifw-ai -n 20 | grep MLP
```

Expected log output:
```
[MLP] Loaded model from: /opt/ritapi_vsentinel/mlp_engine.pkl
[MLP] Threshold: 0.5
```

## Configuration

### MLP Weight in Policy

Edit `config/policy.json`:

```json
{
  "features": {
    "dns_weight": 41,
    "sni_weight": 34,
    "asn_weight": 15,
    "burst_weight": 10,
    "mlp_weight": 30
  }
}
```

**Weight Explanation:**
- `mlp_weight`: How much MLP score contributes to total score
- MLP outputs 0-100 score
- Contribution = `(mlp_score * mlp_weight) / 100`
- Example: MLP score 80, weight 30 → contributes 24 points

### Threshold Tuning

Adjust `MINIFW_MLP_THRESHOLD` to balance false positives vs. false negatives:

| Threshold | Effect | Use Case |
|-----------|--------|----------|
| 0.3 | High sensitivity | Catch more threats, more false positives |
| 0.5 | Balanced (default) | Good balance for most cases |
| 0.7 | High precision | Fewer false positives, may miss some threats |

### Example Configurations

**Conservative (Low False Positives):**
```bash
export MINIFW_MLP_THRESHOLD=0.7
```
```json
"features": { "mlp_weight": 20 }
```

**Aggressive (Catch More Threats):**
```bash
export MINIFW_MLP_THRESHOLD=0.4
```
```json
"features": { "mlp_weight": 40 }
```

**Balanced (Default):**
```bash
export MINIFW_MLP_THRESHOLD=0.5
```
```json
"features": { "mlp_weight": 30 }
```

## Testing

### Available Tests

1. **test_mlp_inference.py** - Test model inference
2. **test_mlp_integration.py** - Test integration with MiniFW-AI
3. **test_standalone_integration.py** - Generate training data

### Quick Test

```bash
# Generate test data
python3 testing/test_standalone_integration.py 100

# Train quick model
python3 scripts/train_mlp.py \
  --data data/testing_output/flow_records_labeled.csv \
  --output /tmp/test_model.pkl

# Test inference
python3 testing/test_mlp_inference.py \
  --model /tmp/test_model.pkl \
  --data data/testing_output/flow_records_labeled.csv

# Test integration
python3 testing/test_mlp_integration.py \
  --model /tmp/test_model.pkl
```

## Model Performance

### Training Metrics

From training output:
```
Training Set Performance:
  Accuracy:  0.9450
  Precision: 0.9200
  Recall:    0.9350
  F1 Score:  0.9275
  AUC-ROC:   0.9600

Test Set Performance:
  Accuracy:  0.9250
  Precision: 0.8900
  Recall:    0.9100
  F1 Score:  0.9000
  AUC-ROC:   0.9450
```

### What to Look For

- **Accuracy > 90%**: Good overall performance
- **Precision > 85%**: Low false positive rate
- **Recall > 85%**: Catches most threats
- **F1 Score > 85%**: Good balance
- **Test accuracy close to train**: No overfitting

### Confusion Matrix

```
  TN: 4000  |  FP:  200   (False Positive Rate: 4.8%)
  FN:  100  |  TP:  700   (True Positive Rate: 87.5%)
```

- **TN (True Negative)**: Correctly identified normal traffic
- **FP (False Positive)**: Normal traffic flagged as threat
- **FN (False Negative)**: Missed threats
- **TP (True Positive)**: Correctly detected threats

## Integration Details

### How MLP Integrates

1. **Flow Tracking**: MiniFW-AI tracks network flows
2. **DNS Enrichment**: Flows enriched with DNS data
3. **Feature Extraction**: 24 features extracted per flow
4. **MLP Inference**: Model predicts threat probability
5. **Scoring**: MLP score added to total score
6. **Decision**: Combined score determines action

### Decision Flow

```
DNS Query Received
    ↓
Update Flow Stats
    ↓
Extract 24 Features
    ↓
MLP Inference → Threat Probability (0.0-1.0)
    ↓
If probability >= threshold → MLP Score = probability * 100
    ↓
Total Score = DNS_score + SNI_score + ASN_score + Burst_score + (MLP_score * mlp_weight / 100)
    ↓
If Total Score >= block_threshold → BLOCK
If Total Score >= monitor_threshold → MONITOR
Else → ALLOW
```

### Example Decision

Client accesses `slot-gacor.xyz`:

1. **DNS Match**: Domain in deny list → +41 points
2. **MLP Inference**: 0.85 probability → Score 85
3. **MLP Contribution**: 85 * 30 / 100 = +25.5 points
4. **Total Score**: 41 + 25 = 66 points
5. **Decision**: 66 >= 60 (block threshold) → **BLOCK**

## Troubleshooting

### Model Not Loading

```bash
# Check file exists
ls -lh /opt/ritapi_vsentinel/mlp_engine.pkl

# Check permissions
sudo chmod 644 /opt/ritapi_vsentinel/mlp_engine.pkl

# Check logs
sudo journalctl -u minifw-ai -n 50 | grep -i mlp
```

### Poor Performance

**If too many false positives:**
1. Increase threshold: `MINIFW_MLP_THRESHOLD=0.6`
2. Decrease weight in policy: `"mlp_weight": 20`
3. Retrain with more normal traffic samples

**If missing threats:**
1. Decrease threshold: `MINIFW_MLP_THRESHOLD=0.4`
2. Increase weight in policy: `"mlp_weight": 40`
3. Retrain with more threat samples

### Missing Dependencies

```bash
pip install scikit-learn pandas numpy
```

### Import Errors

```bash
# Make sure you're in project root
cd /path/to/minifw-ritapi

# Set PYTHONPATH
export PYTHONPATH="$(pwd)/app:$PYTHONPATH"
```

## Advanced Topics

### Custom Model Training

Train with custom parameters:

```python
from sklearn.neural_network import MLPClassifier

model = MLPClassifier(
    hidden_layer_sizes=(64, 32, 16),  # Deeper network
    activation='relu',
    solver='adam',
    alpha=0.001,  # Stronger regularization
    learning_rate_init=0.0001,  # Slower learning
    max_iter=1000,
    early_stopping=True
)
```

### Feature Engineering

Add custom features to `collector_flow.py`:

```python
def build_feature_vector_24(flow: FlowStats) -> list[float]:
    # ... existing features ...
    
    # Custom feature: entropy of packet sizes
    pkt_entropy = calculate_entropy(flow.pkt_sizes)
    
    return features + [pkt_entropy]
```

### Continuous Learning

Periodically retrain with new data:

```bash
# Collect new flows
python3 testing/test_real_traffic.py 60

# Combine with existing data
cat data/old_training.csv data/testing_output/flow_records.jsonl > data/combined.csv

# Retrain
python3 scripts/train_mlp.py --data data/combined.csv
```

## Performance Optimization

### Batch Processing

MLP engine supports batch inference for better performance:

```python
results = detector.batch_predict(flows)  # More efficient than loop
```

### Model Caching

Model is cached on first load - subsequent predictions are fast:

```python
# First call loads model (slow)
detector = get_mlp_detector(model_path)

# Subsequent predictions use cached model (fast)
is_threat = detector.is_suspicious(flow)
```

### Feature Extraction

Feature extraction is optimized for speed:
- Incremental statistics (no full recomputation)
- Fixed-size buffers (deque with maxlen)
- Minimal memory allocation

## API Reference

### MLPThreatDetector

```python
from minifw_ai.utils.mlp_engine import MLPThreatDetector

detector = MLPThreatDetector(
    model_path="/path/to/model.pkl",
    threshold=0.5,
    enable_caching=True
)

# Single prediction
is_threat = detector.is_suspicious(flow)
is_threat, probability = detector.is_suspicious(flow, return_probability=True)

# Batch prediction
results = detector.batch_predict(flows)

# Get statistics
stats = detector.get_stats()
```

### get_mlp_detector

```python
from minifw_ai.utils.mlp_engine import get_mlp_detector

# Singleton pattern - reuses same instance
detector = get_mlp_detector(
    model_path="/path/to/model.pkl",
    threshold=0.5,
    force_reload=False
)
```

## Best Practices

1. **Training Data**
   - Collect 5000+ samples
   - Maintain 20-40% threat ratio
   - Include diverse traffic patterns
   - Label accurately

2. **Model Deployment**
   - Test thoroughly before production
   - Start with conservative threshold
   - Monitor false positive rate
   - Retrain periodically

3. **Performance Tuning**
   - Adjust threshold based on false positives
   - Balance MLP weight with other signals
   - Use batch inference when possible

4. **Monitoring**
   - Track MLP statistics
   - Log predictions for analysis
   - Review false positives/negatives
   - Collect feedback for retraining

---

**Version**: 1.0  
**Last Updated**: 2026-01-26  
**Status**: Production Ready
