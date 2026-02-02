# MLP Engine Quick Start

Fast track guide to get MLP threat detection working in MiniFW-AI.

## Prerequisites

```bash
pip install scikit-learn pandas numpy
```

## Quick Setup (5 Steps)

### 1. Generate Training Data

```bash
# Generate 5000 labeled flows (takes ~30 seconds)
python3 testing/test_standalone_integration.py 5000
```

Output: `data/testing_output/flow_records_labeled.csv`

### 2. Train MLP Model

```bash
# Create models directory
mkdir -p models

# Train model (takes ~1-2 minutes)
python3 scripts/train_mlp.py \
  --data data/testing_output/flow_records_labeled.csv \
  --output models/mlp_engine.pkl
```

Output: `models/mlp_engine.pkl`

### 3. Test Model

```bash
# Test inference
python3 testing/test_mlp_inference.py \
  --model models/mlp_engine.pkl \
  --data data/testing_output/flow_records_labeled.csv
```

Expected: Accuracy > 90%

### 4. Test Integration

```bash
# Test integration with MiniFW-AI
python3 testing/test_mlp_integration.py \
  --model models/mlp_engine.pkl
```

Expected: All 5 tests pass

### 5. Deploy

```bash
# Copy to production location
sudo mkdir -p /opt/ritapi_vsentinel
sudo cp models/mlp_engine.pkl /opt/ritapi_vsentinel/mlp_engine.pkl

# Set environment variable
export MINIFW_MLP_MODEL=/opt/ritapi_vsentinel/mlp_engine.pkl
export MINIFW_MLP_THRESHOLD=0.5

# Restart MiniFW-AI
sudo systemctl restart minifw-ai

# Verify MLP loaded
sudo journalctl -u minifw-ai -n 20 | grep MLP
```

Expected output:
```
[MLP] Loaded model from: /opt/ritapi_vsentinel/mlp_engine.pkl
[MLP] Threshold: 0.5
```

## Verify It's Working

### Check Logs

```bash
# Watch for MLP decisions
sudo journalctl -u minifw-ai -f | grep mlp_threat
```

### Check Flow Records

```bash
# View recent flow records with MLP predictions
tail -f /opt/minifw_ai/logs/flow_records.jsonl | jq '.mlp_proba'
```

### Test with Simulation

```bash
# Simulate traffic
python3 scripts/simulate_attack.py

# Check if MLP detects it
sudo journalctl -u minifw-ai -n 50 | grep -E "(mlp_threat|BLOCK)"
```

## Configuration

### Adjust Sensitivity

Edit environment variable for threshold:

```bash
# More sensitive (catch more threats, more false positives)
export MINIFW_MLP_THRESHOLD=0.4

# Less sensitive (fewer false positives, may miss threats)
export MINIFW_MLP_THRESHOLD=0.6

# Balanced (default)
export MINIFW_MLP_THRESHOLD=0.5
```

### Adjust Weight

Edit `config/policy.json`:

```json
{
  "features": {
    "mlp_weight": 30  // 20-40 recommended
  }
}
```

## Common Issues

### "Model file not found"

```bash
# Check path
ls -lh /opt/ritapi_vsentinel/mlp_engine.pkl

# If missing, copy it
sudo cp models/mlp_engine.pkl /opt/ritapi_vsentinel/mlp_engine.pkl
```

### "scikit-learn not installed"

```bash
pip install scikit-learn pandas numpy
```

### "MLP not loading in MiniFW-AI"

```bash
# Check environment variable is set
echo $MINIFW_MLP_MODEL

# Set it if missing
export MINIFW_MLP_MODEL=/opt/ritapi_vsentinel/mlp_engine.pkl

# Add to systemd service
sudo nano /etc/systemd/system/minifw-ai.service
# Add: Environment="MINIFW_MLP_MODEL=/opt/ritapi_vsentinel/mlp_engine.pkl"

sudo systemctl daemon-reload
sudo systemctl restart minifw-ai
```

### Too Many False Positives

```bash
# Increase threshold
export MINIFW_MLP_THRESHOLD=0.6

# OR decrease weight
# Edit config/policy.json: "mlp_weight": 20
```

### Missing Threats

```bash
# Decrease threshold
export MINIFW_MLP_THRESHOLD=0.4

# OR increase weight  
# Edit config/policy.json: "mlp_weight": 40
```

## Testing Commands Reference

```bash
# Generate training data
python3 testing/test_standalone_integration.py 5000

# Train model
python3 scripts/train_mlp.py --data data/testing_output/flow_records_labeled.csv --output models/mlp_engine.pkl

# Test inference
python3 testing/test_mlp_inference.py --model models/mlp_engine.pkl --data data/testing_output/flow_records_labeled.csv

# Test integration
python3 testing/test_mlp_integration.py --model models/mlp_engine.pkl

# Simulate traffic for testing
python3 scripts/simulate_attack.py
python3 scripts/real_traffic_simulator.py
```

## Performance Benchmarks

On typical hardware:
- Training 5000 samples: ~1-2 minutes
- Inference per flow: ~1-2 ms
- Batch inference (100 flows): ~10-20 ms

## Next Steps

After basic setup:
1. Collect real traffic for retraining
2. Monitor false positive rate
3. Tune threshold and weight
4. Set up periodic retraining

See full documentation: `docs/MLP_ENGINE.md`

---

**Quick Tip**: Start with default settings (threshold=0.5, weight=30) and adjust based on observed performance.
