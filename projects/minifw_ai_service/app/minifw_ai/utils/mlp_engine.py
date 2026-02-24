"""
MLP Engine for MiniFW-AI
Flow-based threat detection using Multi-Layer Perceptron classifier.

This module provides:
- MLPThreatDetector class for inference
- Model loading and caching
- Feature normalization using StandardScaler
- Threat probability scoring
"""

from __future__ import annotations
import os
import pickle
from pathlib import Path
from typing import Optional, Tuple
import logging

try:
    import numpy as np
    import pandas as pd
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    np = None
    pd = None
    MLPClassifier = None
    StandardScaler = None

# Try to import FlowStats and build_feature_vector_24
try:
    from ..collector_flow import FlowStats, build_feature_vector_24
except ImportError:
    # Fallback for testing
    FlowStats = None
    build_feature_vector_24 = None


logger = logging.getLogger(__name__)

# CRITICAL: Feature names in exact order
# Must match training data columns
FEATURE_NAMES = [
    "duration_sec",
    "pkt_count_total",
    "bytes_total",
    "bytes_per_sec",
    "pkts_per_sec",
    "avg_pkt_size",
    "pkt_size_std",
    "inbound_outbound_ratio",
    "max_burst_pkts_1s",
    "max_burst_bytes_1s",
    "interarrival_mean_ms",
    "interarrival_std_ms",
    "interarrival_p95_ms",
    "small_pkt_ratio",
    "tls_seen",
    "tls_handshake_time_ms",
    "ja3_hash_bucket",
    "sni_len",
    "alpn_h2",
    "cert_self_signed_suspect",
    "dns_seen",
    "fqdn_len",
    "subdomain_depth",
    "domain_repeat_5min",
]


class MLPThreatDetector:
    """
    MLP-based threat detector for network flows.

    Uses a trained MLPClassifier to detect suspicious flows based on
    24 extracted features from flow statistics.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        threshold: float = 0.5,
        enable_caching: bool = True,
    ):
        """
        Initialize MLP Threat Detector.

        Args:
            model_path: Path to trained model (.pkl or .joblib)
            threshold: Probability threshold for threat classification (0.0-1.0)
            enable_caching: Enable in-memory model caching
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn is required for MLP engine. "
                "Install with: pip install scikit-learn"
            )

        self.threshold = threshold
        self.enable_caching = enable_caching

        # Model and scaler
        self.model: Optional[MLPClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.model_loaded = False

        # Default model path
        if model_path is None:
            model_path = os.getenv(
                "MINIFW_MLP_MODEL", "/opt/ritapi_vsentinel/mlp_engine.joblib"
            )

        self.model_path = Path(model_path)

        # Feature metadata
        self.feature_names = [
            # Basic flow (8)
            "duration_sec",
            "pkt_count_total",
            "bytes_total",
            "bytes_per_sec",
            "pkts_per_sec",
            "avg_pkt_size",
            "pkt_size_std",
            "inbound_outbound_ratio",
            # Burst & periodicity (6)
            "max_burst_pkts_1s",
            "max_burst_bytes_1s",
            "interarrival_mean_ms",
            "interarrival_std_ms",
            "interarrival_p95_ms",
            "small_pkt_ratio",
            # TLS (6)
            "tls_seen",
            "tls_handshake_time_ms",
            "ja3_hash_bucket",
            "sni_len",
            "alpn_h2",
            "cert_self_signed_suspect",
            # DNS (4)
            "dns_seen",
            "fqdn_len",
            "subdomain_depth",
            "domain_repeat_5min",
        ]

        # Stats
        self.total_inferences = 0
        self.total_threats_detected = 0

        # Try to load model if path exists
        if self.model_path.exists():
            try:
                self.load_model(str(self.model_path))
            except Exception as e:
                logger.warning(f"Failed to auto-load model from {model_path}: {e}")

    def load_model(self, model_path: str) -> bool:
        """
        Load trained MLP model and scaler from file.

        Args:
            model_path: Path to pickled model file

        Returns:
            True if loaded successfully

        Raises:
            FileNotFoundError: If model file doesn't exist
            Exception: If model loading fails
        """
        path = Path(model_path)

        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        logger.info(f"Loading MLP model from: {model_path}")

        try:
            with path.open("rb") as f:
                model_data = pickle.load(f)

            # Support both dict format and direct model format
            if isinstance(model_data, dict):
                self.model = model_data.get("model")
                self.scaler = model_data.get("scaler")

                # Log metadata if available
                if "metadata" in model_data:
                    metadata = model_data["metadata"]
                    logger.info(
                        f"Model trained on: {metadata.get('trained_at', 'unknown')}"
                    )
                    logger.info(
                        f"Training samples: {metadata.get('n_samples', 'unknown')}"
                    )
                    logger.info(
                        f"Model accuracy: {metadata.get('accuracy', 'unknown')}"
                    )
            else:
                # Assume it's just the model
                self.model = model_data
                self.scaler = None
                logger.warning("No scaler found in model file, using raw features")

            if self.model is None:
                raise ValueError("Model is None after loading")

            self.model_loaded = True
            self.model_path = path

            logger.info("✓ MLP model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def is_suspicious(
        self, flow: "FlowStats", return_probability: bool = False
    ) -> bool | Tuple[bool, float]:
        """
        Detect if a flow is suspicious using MLP inference.

        Args:
            flow: FlowStats object to analyze
            return_probability: If True, also return threat probability

        Returns:
            If return_probability=False: bool (True if suspicious)
            If return_probability=True: (bool, float) - (is_suspicious, probability)
        """
        if not self.model_loaded:
            logger.warning("MLP model not loaded, returning False")
            return (False, 0.0) if return_probability else False

        try:
            # Extract features
            features = build_feature_vector_24(flow)

            # CRITICAL FIX: Use DataFrame with explicit feature names
            # This prevents feature misalignment warnings and ensures
            # features are in the correct order
            X = pd.DataFrame([features], columns=FEATURE_NAMES)

            # Normalize if scaler available
            if self.scaler is not None:
                X_scaled = self.scaler.transform(X)
            else:
                X_scaled = X.values

            # Predict probability
            proba = self.model.predict_proba(X_scaled)[0]
            threat_proba = proba[1] if len(proba) > 1 else proba[0]

            # Update stats
            self.total_inferences += 1

            # Threshold decision
            is_threat = threat_proba >= self.threshold

            if is_threat:
                self.total_threats_detected += 1

            if return_probability:
                return (is_threat, float(threat_proba))
            else:
                return is_threat

        except Exception as e:
            logger.error(f"MLP inference error: {e}")
            return (False, 0.0) if return_probability else False

    def predict_proba(self, flow: "FlowStats") -> float:
        """
        Get threat probability for a flow (0.0 - 1.0).

        Args:
            flow: FlowStats object to analyze

        Returns:
            Threat probability (0.0 = safe, 1.0 = threat)
        """
        _, proba = self.is_suspicious(flow, return_probability=True)
        return proba

    def batch_predict(self, flows: list["FlowStats"]) -> list[Tuple[bool, float]]:
        """
        Batch prediction for multiple flows (more efficient).

        Args:
            flows: List of FlowStats objects

        Returns:
            List of (is_suspicious, probability) tuples
        """
        if not self.model_loaded:
            logger.warning("MLP model not loaded")
            return [(False, 0.0)] * len(flows)

        try:
            # Extract all features
            features_list = [build_feature_vector_24(flow) for flow in flows]

            # CRITICAL FIX: Use DataFrame with explicit feature names
            X = pd.DataFrame(features_list, columns=FEATURE_NAMES)

            # Normalize
            if self.scaler is not None:
                X_scaled = self.scaler.transform(X)
            else:
                X_scaled = X.values

            # Batch predict
            probas = self.model.predict_proba(X_scaled)
            threat_probas = probas[:, 1] if probas.shape[1] > 1 else probas[:, 0]

            # Update stats
            self.total_inferences += len(flows)

            # Apply threshold
            results = []
            for proba in threat_probas:
                is_threat = proba >= self.threshold
                if is_threat:
                    self.total_threats_detected += 1
                results.append((is_threat, float(proba)))

            return results

        except Exception as e:
            logger.error(f"Batch prediction error: {e}")
            return [(False, 0.0)] * len(flows)

    def get_feature_importance(self) -> dict[str, float]:
        """
        Get feature importance from the model (if available).

        Returns:
            Dict mapping feature names to importance scores
        """
        if not self.model_loaded:
            return {}

        # MLPClassifier doesn't have built-in feature_importances_
        # We could implement permutation importance here if needed
        # For now, return empty dict
        return {}

    def get_stats(self) -> dict:
        """
        Get detector statistics.

        Returns:
            Dict with inference statistics
        """
        threat_rate = 0.0
        if self.total_inferences > 0:
            threat_rate = self.total_threats_detected / self.total_inferences

        return {
            "model_loaded": self.model_loaded,
            "model_path": str(self.model_path) if self.model_path else None,
            "threshold": self.threshold,
            "total_inferences": self.total_inferences,
            "total_threats_detected": self.total_threats_detected,
            "threat_rate": threat_rate,
            "has_scaler": self.scaler is not None,
        }

    def reset_stats(self):
        """Reset inference statistics."""
        self.total_inferences = 0
        self.total_threats_detected = 0


# Singleton instance for easy import
_detector_instance: Optional[MLPThreatDetector] = None


def get_mlp_detector(
    model_path: Optional[str] = None, threshold: float = 0.5, force_reload: bool = False
) -> MLPThreatDetector:
    """
    Get singleton MLP detector instance.

    Args:
        model_path: Path to model file (only used on first call or force_reload)
        threshold: Threat probability threshold
        force_reload: Force reload of detector

    Returns:
        MLPThreatDetector instance
    """
    global _detector_instance

    if _detector_instance is None or force_reload:
        _detector_instance = MLPThreatDetector(
            model_path=model_path, threshold=threshold
        )

    return _detector_instance
