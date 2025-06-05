# defense_module.py
import os
import random
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import IsolationForest

class DefenseModule:
    def __init__(self):
        self.model_path = "data/anomaly_detector.pkl"
        self.vectorizer_path = "data/vectorizer.pkl"
        self.threshold = 0.5  # anomaly threshold to flag attack
        self.signature_keywords = set([
            "system prompt", "internal", "instructions", "config", "bypass",
            "developer settings", "constructed", "hidden", "initialization",
            "secret", "role", "token", "authentication", "access denied"
        ])

        self.benign_samples = [
            "what's the weather today?",
            "tell me a joke",
            "play some music",
            "open google.com",
            "generate an image of a cat",
            "show me today's news",
            "tell me something interesting",
            "what's the time now",
            "who is the president of USA",
            "open youtube.com"
        ]
        self.suspicious_samples = []

        # Load or create vectorizer and model
        if os.path.exists(self.model_path) and os.path.exists(self.vectorizer_path):
            self.vectorizer = joblib.load(self.vectorizer_path)
            self.model = joblib.load(self.model_path)
        else:
            self.vectorizer = TfidfVectorizer()
            X = self.vectorizer.fit_transform(self.benign_samples)
            self.model = IsolationForest(contamination=0.1, random_state=42)
            self.model.fit(X)
            joblib.dump(self.vectorizer, self.vectorizer_path)
            joblib.dump(self.model, self.model_path)

        # Parameters for incremental retraining
        self.retrain_batch_size = 20
        self.min_samples_to_retrain = 50

    def _contains_signature(self, query):
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.signature_keywords)

    def is_attack(self, query):
        # Signature-based detection (immediate high confidence if matched)
        if self._contains_signature(query):
            return True, 1.0

        # Behavioral detection (anomaly score)
        vector = self.vectorizer.transform([query])
        prediction = self.model.predict(vector)[0]  # -1 = anomaly, 1 = normal
        score = self.model.decision_function(vector)[0]  # higher = normal, lower = anomaly

        # Normalize anomaly score to [0, 1]
        # IsolationForest scores can be negative, so normalize by min/max
        normalized_score = (1.0 - score) / 2
        normalized_score = max(0.0, min(1.0, normalized_score))

        is_anomaly = (prediction == -1) and (normalized_score >= self.threshold)

        return is_anomaly, normalized_score

    def defend(self, query):
        is_threat, anomaly_score = self.is_attack(query)

        if is_threat:
            # Block suspicious query
            return "Access denied. I cannot disclose internal configuration.", True, anomaly_score
        else:
            # Allow benign query (no info leaked here, just None)
            return None, False, anomaly_score

    def improve_defense(self, reward, query, leak_occurred):
        """
        Reinforce defense model based on reward and feedback.

        reward: float (higher is better)
        query: str (the query attempted)
        leak_occurred: bool (True if defense failed and info leaked)
        """

        # Adjust threshold adaptively
        if leak_occurred:
            # Make defense more sensitive by lowering threshold (detect more anomalies)
            self.threshold = max(0.1, self.threshold - 0.02)
            # Add query to suspicious samples for retraining
            self.suspicious_samples.append(query)
        else:
            # Relax threshold a bit (allow some flexibility)
            self.threshold = min(0.9, self.threshold + 0.01)
            # Add to benign samples for retraining
            self.benign_samples.append(query)

        # Periodic retraining with collected samples
        total_samples = len(self.benign_samples) + len(self.suspicious_samples)
        if total_samples >= self.min_samples_to_retrain:
            self._retrain_model()

    def _retrain_model(self):
        """
        Retrain the IsolationForest model on updated benign + suspicious samples.
        Suspicious samples are removed or used as anomalies.
        """
        print(f"[DefenseModule] Retraining model with {len(self.benign_samples)} benign and {len(self.suspicious_samples)} suspicious samples...")

        # Label benign as normal (1), suspicious as anomalies (-1)
        combined_samples = self.benign_samples + self.suspicious_samples
        labels = np.array([1]*len(self.benign_samples) + [-1]*len(self.suspicious_samples))

        # Fit vectorizer on combined samples for better coverage
        self.vectorizer = TfidfVectorizer()
        X = self.vectorizer.fit_transform(combined_samples)

        # IsolationForest doesn't use labels, but we can set contamination ~ fraction of suspicious
        contamination = max(0.05, len(self.suspicious_samples) / max(len(combined_samples), 1))
        self.model = IsolationForest(contamination=contamination, random_state=42)
        self.model.fit(X)

        # Save updated model and vectorizer
        joblib.dump(self.vectorizer, self.vectorizer_path)
        joblib.dump(self.model, self.model_path)

        # Clear suspicious samples to avoid overfitting on stale data
        self.suspicious_samples.clear()

        print(f"[DefenseModule] Retraining done. Threshold: {self.threshold:.3f}")

