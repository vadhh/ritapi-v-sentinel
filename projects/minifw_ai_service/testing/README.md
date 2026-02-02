# MiniFW-AI Testing Suite

This directory contains all test scripts for the MiniFW-AI Flow Collector system.

## Test Scripts

### 1. test_flow_collector.py
**Real Traffic Testing - Requires Root Access**

Tests flow collection from actual network traffic using conntrack.

```bash
# Run from project root
sudo python3 testing/test_flow_collector.py [duration_seconds]

# Example: collect for 60 seconds
sudo python3 testing/test_flow_collector.py 60
```

**Features:**
- Collects real network flows via conntrack
- Enriches with DNS data from dnsmasq
- Extracts 24-feature vectors
- Exports to `./data/flow_records.jsonl`

**Prerequisites:**
- Must run as root (conntrack access)
- dnsmasq should be running with logging enabled

---

### 2. test_flow_collector_simulated.py
**Simulated Flow Generation - No Root Required**

Generates synthetic flow data for development and testing without requiring network access.

```bash
# Run from project root
python3 testing/test_flow_collector_simulated.py [flow_count]

# Example: generate 100 flows
python3 testing/test_flow_collector_simulated.py 100
```

**Features:**
- Generates realistic flow patterns (web, streaming, bot, gaming)
- No root access required
- Creates labeled data for training
- Outputs to `./data/testing_output/`

**Use Cases:**
- Development without gateway setup
- Quick feature extraction testing
- Initial dataset generation

---

### 3. test_real_traffic.py
**Full Integration Test - Requires Root**

Runs MiniFW-AI with flow collection enabled on real network traffic.

```bash
# Run from project root
sudo python3 testing/test_real_traffic.py [duration_minutes]

# Example: run for 5 minutes
sudo python3 testing/test_real_traffic.py 5
```

**Features:**
- Full MiniFW-AI + Flow Collector integration
- Real-time event logging
- Flow record export
- Progress monitoring

**Prerequisites:**
- Root access
- dnsmasq running and logging
- Active network traffic through gateway

**Outputs:**
- `./data/testing_output/events.jsonl` - MiniFW-AI events
- `./data/testing_output/flow_records.jsonl` - Flow records

---

### 4. test_standalone_integration.py
**Standalone Integration Test - No Gateway Required**

Simulates full MiniFW-AI decision logic with synthetic data on any computer.

```bash
# Run from project root
python3 testing/test_standalone_integration.py [flow_count]

# Example: generate 500 flows
python3 testing/test_standalone_integration.py 500
```

**Features:**
- Complete flow + decision pipeline simulation
- Generates labeled data (normal/threat)
- MiniFW-AI action simulation (allow/monitor/block)
- Quality metrics and statistics
- No dependencies on network infrastructure

**Outputs:**
- `./data/testing_output/flow_records.jsonl` - Raw flow data
- `./data/testing_output/flow_records_labeled.csv` - Labeled CSV for training

**Best For:**
- Development on laptops/workstations
- Testing decision logic
- Generating training datasets
- Pre-deployment validation

---

## Output Directory Structure

All test outputs go to `./data/testing_output/`:

```
data/
└── testing_output/
    ├── events.jsonl              # MiniFW-AI events (from test_real_traffic.py)
    ├── flow_records.jsonl        # Raw flow records
    ├── flow_records_labeled.csv  # CSV with labels for training
    └── features.csv              # Feature matrix only
```

## Running Tests

### Quick Start (No Root)
```bash
# From project root
python3 testing/test_standalone_integration.py 1000
```

### With Real Traffic (Root Required)
```bash
# From project root
sudo python3 testing/test_real_traffic.py 10
```

### Development Mode
```bash
# From project root
python3 testing/test_flow_collector_simulated.py 200
```

## Test Flow

1. **Development**: Use `test_flow_collector_simulated.py` or `test_standalone_integration.py`
2. **Pre-deployment**: Use `test_flow_collector.py` on test gateway
3. **Production Testing**: Use `test_real_traffic.py` with monitoring

## Data Quality Checks

The standalone test provides quality metrics:
- ✓ Threat/Normal balance (20-40% threats recommended)
- ✓ Data volume (500+ flows minimum, 1000+ excellent)
- ✓ Feature completeness
- ✓ Label distribution

## Next Steps After Testing

1. **Review Generated Data**
   ```bash
   cat ./data/testing_output/flow_records_labeled.csv | head -20
   ```

2. **Train MLP Model**
   ```bash
   python3 scripts/train_mlp.py --data ./data/testing_output/flow_records_labeled.csv
   ```

3. **Test Inference**
   ```bash
   python3 scripts/test_inference.py --model mlp_model.joblib
   ```

## Troubleshooting

### Permission Denied
- Make sure you're in project root directory
- For real traffic tests, use `sudo`

### No Data Collected
- Check dnsmasq is running: `systemctl status dnsmasq`
- Verify dnsmasq logging: `tail -f /var/log/dnsmasq.log`
- Ensure network traffic is flowing

### Import Errors
- Verify you're running from project root
- Check `app/minifw_ai/` directory exists
- All imports are relative to project root

## Notes

- All tests now use relative paths from project root
- No hardcoded `/tmp/` or `/opt/` paths
- Output always goes to `./data/testing_output/`
- Tests can be run from anywhere as long as you're in project root
