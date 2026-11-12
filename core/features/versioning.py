"""Feature configuration, method IDs and implementation versions.

These identifiers are part of the feature contract. Any change to a formula,
parameter convention or implementation must change the relevant version.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from core.features.config import FeatureConfig
from core.features.types import (
    METHOD_LIQUIDITY_UNSUPPORTED,
    METHOD_MOMENTUM_TS_MOM_V1,
    METHOD_PHASE_HEURISTIC_V1,
    METHOD_STRUCTURE_SWING_BOS_V1,
    METHOD_TREND_DRIFT_V1,
    METHOD_TREND_MARKET_STRUCTURE_V1,
    METHOD_VOLATILITY_RANGE_EXPANSION_V1,
    PackId,
)

FEATURE_SCHEMA_VERSION = "p3_feature_v1"
FEATURE_CONFIG_VERSION = 1

# Existing indicator families. This stage adds series, not new families.
INDICATOR_IMPLEMENTATION_VERSIONS: dict[str, str] = {
    "sma": "sma_v1",
    "ema_fast": "ema_v1",
    "ema_slow": "ema_v1",
    "wma": "wma_v1",
    "hma": "hma_v1",
    "dema": "dema_v1",
    "tema": "tema_v1",
    "atr": "atr_v1",
    "rsi": "rsi_v1",
    "macd": "macd_v1",
    "macd_signal": "macd_v1",
    "macd_histogram": "macd_v1",
    "bb_upper": "bollinger_v1",
    "bb_middle": "bollinger_v1",
    "bb_lower": "bollinger_v1",
    "adx": "adx_v1",
    "plus_di": "adx_v1",
    "minus_di": "adx_v1",
    "relative_volume": "relative_volume_v1",
}

# Existing view method IDs. These are part of feature configuration identity.
FEATURE_METHOD_IDS: dict[str, str] = {
    "trend": str(METHOD_TREND_MARKET_STRUCTURE_V1),
    "trend_reserved": str(METHOD_TREND_DRIFT_V1),
    "momentum": str(METHOD_MOMENTUM_TS_MOM_V1),
    "volatility": str(METHOD_VOLATILITY_RANGE_EXPANSION_V1),
    "phase": str(METHOD_PHASE_HEURISTIC_V1),
    "liquidity": str(METHOD_LIQUIDITY_UNSUPPORTED),
    "structure_bos": str(METHOD_STRUCTURE_SWING_BOS_V1),
}

INDICATOR_METHOD_IDS: dict[str, str] = {
    "sma": "sma_v1",
    "ema_fast": "ema_v1",
    "ema_slow": "ema_v1",
    "wma": "wma_v1",
    "hma": "hma_v1",
    "dema": "dema_v1",
    "tema": "tema_v1",
    "atr": "atr_v1",
    "rsi": "rsi_v1",
    "macd": "macd_v1",
    "macd_signal": "macd_v1",
    "macd_histogram": "macd_v1",
    "bb_upper": "bollinger_v1",
    "bb_middle": "bollinger_v1",
    "bb_lower": "bollinger_v1",
    "adx": "adx_v1",
    "plus_di": "adx_v1",
    "minus_di": "adx_v1",
    "relative_volume": "relative_volume_v1",
}


@dataclass(frozen=True)
class FeatureProvenance:
    """Traceability metadata carried by a FeatureContext."""

    schema_version: str
    config_version: int
    config_hash: str
    schema_hash: str
    pack_ids: tuple[str, ...]
    method_ids: Mapping[str, str]
    indicator_versions: Mapping[str, str]
    indicator_parameters: Mapping[str, Mapping[str, object]]
    timeframe: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method_ids", MappingProxyType(dict(self.method_ids)))
        object.__setattr__(
            self, "indicator_versions", MappingProxyType(dict(self.indicator_versions))
        )
        object.__setattr__(
            self,
            "indicator_parameters",
            MappingProxyType(
                {
                    key: MappingProxyType(dict(value))
                    for key, value in self.indicator_parameters.items()
                }
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "config_version": self.config_version,
            "config_hash": self.config_hash,
            "schema_hash": self.schema_hash,
            "pack_ids": list(self.pack_ids),
            "method_ids": dict(self.method_ids),
            "indicator_versions": dict(self.indicator_versions),
            "indicator_parameters": {
                key: dict(value) for key, value in self.indicator_parameters.items()
            },
            "timeframe": self.timeframe,
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _canonical(payload: Any) -> str:
    return json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))


def feature_config_hash(config: FeatureConfig) -> str:
    """Deterministic hash of all feature configuration values and versions."""
    payload = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "config_version": FEATURE_CONFIG_VERSION,
        "config": asdict(config),
        "indicator_versions": INDICATOR_IMPLEMENTATION_VERSIONS,
        "indicator_method_ids": INDICATOR_METHOD_IDS,
        "feature_method_ids": FEATURE_METHOD_IDS,
    }
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def feature_schema_hash(
    *,
    pack_ids: Sequence[PackId | str],
    config: FeatureConfig,
    timeframe: str,
    indicator_versions: Mapping[str, str] | None = None,
    method_ids: Mapping[str, str] | None = None,
) -> str:
    """Hash actual pack/method/config/implementation identity, not only pack IDs."""
    versions = dict(indicator_versions or INDICATOR_IMPLEMENTATION_VERSIONS)
    methods = dict(method_ids or FEATURE_METHOD_IDS)
    payload = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "config_version": FEATURE_CONFIG_VERSION,
        "packs": sorted(str(item) for item in pack_ids),
        "methods": methods,
        "indicator_versions": versions,
        "indicator_method_ids": INDICATOR_METHOD_IDS,
        "config_hash": feature_config_hash(config),
        "timeframe": timeframe.upper(),
    }
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def indicator_parameters(config: FeatureConfig) -> dict[str, dict[str, object]]:
    i = config.indicators
    return {
        "sma": {"length": i.sma_period},
        "ema_fast": {"length": i.ema_fast_period},
        "ema_slow": {"length": i.ema_slow_period},
        "wma": {"length": i.wma_period},
        "hma": {"length": i.hma_period},
        "dema": {"length": i.dema_period},
        "tema": {"length": i.tema_period},
        "atr": {"length": i.atr_period},
        "rsi": {"length": i.rsi_period},
        "macd": {"fast": i.macd_fast_period, "slow": i.macd_slow_period, "signal": i.macd_signal_period},
        "macd_signal": {"fast": i.macd_fast_period, "slow": i.macd_slow_period, "signal": i.macd_signal_period},
        "macd_histogram": {"fast": i.macd_fast_period, "slow": i.macd_slow_period, "signal": i.macd_signal_period},
        "bb_upper": {"length": i.bollinger_period, "std": i.bollinger_std},
        "bb_middle": {"length": i.bollinger_period, "std": i.bollinger_std},
        "bb_lower": {"length": i.bollinger_period, "std": i.bollinger_std},
        "adx": {"length": i.adx_period},
        "plus_di": {"length": i.adx_period},
        "minus_di": {"length": i.adx_period},
        "relative_volume": {"length": i.relative_volume_period},
    }


def feature_provenance(
    *,
    pack_ids: Sequence[PackId | str],
    config: FeatureConfig,
    timeframe: str,
    indicator_versions: Mapping[str, str] | None = None,
    method_ids: Mapping[str, str] | None = None,
) -> FeatureProvenance:
    versions = dict(indicator_versions or INDICATOR_IMPLEMENTATION_VERSIONS)
    methods = dict(method_ids or FEATURE_METHOD_IDS)
    return FeatureProvenance(
        schema_version=FEATURE_SCHEMA_VERSION,
        config_version=FEATURE_CONFIG_VERSION,
        config_hash=feature_config_hash(config),
        schema_hash=feature_schema_hash(
            pack_ids=pack_ids,
            config=config,
            timeframe=timeframe,
            indicator_versions=versions,
            method_ids=methods,
        ),
        pack_ids=tuple(str(item) for item in pack_ids),
        method_ids=methods,
        indicator_versions=versions,
        indicator_parameters=indicator_parameters(config),
        timeframe=timeframe.upper(),
    )
