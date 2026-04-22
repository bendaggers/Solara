"""TrendPrediction dataclass — output schema for a single bar prediction."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


@dataclass
class TrendPrediction:
    predicted_class: str
    prob_up: float
    prob_sideways: float
    prob_down: float
    trend_strength: float
    trend_confidence: float
    regime_tag: str
    model_valid: bool
    ood_flag: bool
    reason: str
    timestamp: datetime
    pair: str
    timeframe: str
    model_version: str
    ood_features: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        if isinstance(d['timestamp'], datetime):
            d['timestamp'] = d['timestamp'].isoformat()
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def is_tradeable(self) -> bool:
        return self.model_valid and not self.ood_flag and self.predicted_class != 'sideways'

    def __repr__(self) -> str:
        return (
            f"TrendPrediction({self.pair}/{self.timeframe} @ {self.timestamp} | "
            f"class={self.predicted_class} | "
            f"up={self.prob_up:.2f}/side={self.prob_sideways:.2f}/down={self.prob_down:.2f} | "
            f"conf={self.trend_confidence:.2f} | valid={self.model_valid} | reason={self.reason})"
        )
