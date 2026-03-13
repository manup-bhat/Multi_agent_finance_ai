"""
Algo ID Tracker — SEBI Generic Algo Registration & Tagging
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint (Correction #10):
  SEBI requires all algorithmic strategies to be registered with the broker
  and each order tagged with the appropriate Algo ID.

SEBI Algo Rules (April 2026):
  - Every algo strategy must be registered with broker → broker registers with NSE/BSE
  - Orders placed by registered algos must include the Algo ID tag
  - "White-box" registration for algos with OPS > 1 OR position > threshold
  - Unique Algo ID per strategy per exchange segment
  - Audit trail: all algo-tagged orders must be queryable by SEBI

This module:
  1. Registry of strategy → AlgoID mappings
  2. Order tagging: attach Algo ID to any order dict
  3. Registration status tracking (PENDING / REGISTERED / REJECTED)
  4. Full order audit log keyed by Algo ID
"""
from __future__ import annotations

import datetime
import uuid
import structlog
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = structlog.get_logger(__name__)


class AlgoStatus(str, Enum):
    PENDING    = "PENDING"       # Submitted, awaiting broker confirmation
    REGISTERED = "REGISTERED"   # Confirmed by broker / NSE
    REJECTED   = "REJECTED"     # Rejected by broker / NSE
    SUSPENDED  = "SUSPENDED"    # Temporarily suspended by regulator


@dataclass
class AlgoRegistration:
    """One registered algo strategy."""
    algo_id:       str                   # Broker-assigned ID (or UUID for local tracking)
    strategy_name: str
    segment:       str                   # NSE_EQ / NSE_FO / NSE_CDS
    description:   str
    registered_at: Optional[datetime.datetime]
    status:        AlgoStatus
    registered_by: str                   # Broker name
    order_count:   int  = 0


@dataclass
class TaggedOrder:
    """Order with Algo ID attached for SEBI compliance."""
    order_id:      str
    algo_id:       str
    strategy_name: str
    ticker:        str
    segment:       str
    order_type:    str      # MARKET / LIMIT / SL / SL-M
    direction:     str      # BUY / SELL
    quantity:      int
    price:         float
    timestamp:     datetime.datetime
    metadata:      dict = field(default_factory=dict)


class AlgoIDTracker:
    """
    Registry and order-tagging system for SEBI algo compliance.

    Usage:
        tracker = AlgoIDTracker()
        tracker.register(
            strategy_name="MeanReversionRSI_BB",
            segment="NSE_FO",
            description="RSI + Bollinger Bands mean reversion for Bank Nifty",
            broker="ICICI_DIRECT",
        )
        tagged = tracker.tag_order(
            strategy_name="MeanReversionRSI_BB",
            raw_order={"ticker": "BANKNIFTY", "qty": 25, "price": 46000, ...}
        )
    """

    def __init__(self):
        self._registry:    dict[str, AlgoRegistration] = {}    # strategy_name → AlgoReg
        self._order_log:   list[TaggedOrder]            = []
        self._id_map:      dict[str, str]               = {}   # algo_id → strategy_name
        logger.info("algo_id_tracker.init")

    def register(
        self,
        strategy_name: str,
        segment: str = "NSE_FO",
        description: str = "",
        broker: str = "SELF",
        algo_id: Optional[str] = None,
        status: AlgoStatus = AlgoStatus.REGISTERED,
    ) -> AlgoRegistration:
        """
        Register an algorithmic strategy.

        Args:
            strategy_name: Unique human-readable strategy name
            segment:       NSE market segment
            description:   Plain-text description for SEBI
            broker:        Broker name (for production, use actual broker code)
            algo_id:       Optional broker-assigned ID (auto-generated UUID if None)
            status:        Registration status (default REGISTERED for dev)

        Returns:
            AlgoRegistration
        """
        if strategy_name in self._registry:
            logger.warning("algo_id_tracker.already_registered", strategy=strategy_name)
            return self._registry[strategy_name]

        effective_id = algo_id or f"ALGO_{uuid.uuid4().hex[:8].upper()}"
        reg = AlgoRegistration(
            algo_id=effective_id,
            strategy_name=strategy_name,
            segment=segment,
            description=description,
            registered_at=datetime.datetime.utcnow(),
            status=status,
            registered_by=broker,
        )
        self._registry[strategy_name] = reg
        self._id_map[effective_id]    = strategy_name

        logger.info(
            "algo_id_tracker.registered",
            strategy=strategy_name, algo_id=effective_id,
            segment=segment, status=status,
        )
        return reg

    def get_algo_id(self, strategy_name: str) -> Optional[str]:
        """Return the Algo ID for a strategy, or None if not registered."""
        reg = self._registry.get(strategy_name)
        return reg.algo_id if reg else None

    def tag_order(
        self,
        strategy_name: str,
        raw_order: dict,
    ) -> TaggedOrder:
        """
        Tag a raw order dict with the strategy's Algo ID.

        Args:
            strategy_name: The strategy placing the order
            raw_order:     Dict with keys: ticker, qty, price, order_type, direction, segment

        Returns:
            TaggedOrder (must be submitted to broker with .algo_id attached)

        Raises:
            KeyError: If strategy is not registered
        """
        if strategy_name not in self._registry:
            raise KeyError(
                f"Strategy '{strategy_name}' not registered. "
                "Call register() before placing orders."
            )
        reg = self._registry[strategy_name]

        if reg.status not in (AlgoStatus.REGISTERED,):
            logger.warning(
                "algo_id_tracker.non_registered_order",
                strategy=strategy_name, status=reg.status,
            )

        tagged = TaggedOrder(
            order_id=f"ORD_{uuid.uuid4().hex[:10].upper()}",
            algo_id=reg.algo_id,
            strategy_name=strategy_name,
            ticker=raw_order.get("ticker", "UNKNOWN"),
            segment=raw_order.get("segment", reg.segment),
            order_type=raw_order.get("order_type", "MARKET"),
            direction=raw_order.get("direction", "BUY"),
            quantity=int(raw_order.get("qty", 0)),
            price=float(raw_order.get("price", 0.0)),
            timestamp=datetime.datetime.utcnow(),
            metadata=raw_order,
        )
        reg.order_count += 1
        self._order_log.append(tagged)

        logger.info(
            "algo_id_tracker.order_tagged",
            algo_id=reg.algo_id, ticker=tagged.ticker,
            direction=tagged.direction, qty=tagged.quantity,
        )
        return tagged

    def get_registration(self, strategy_name: str) -> Optional[AlgoRegistration]:
        return self._registry.get(strategy_name)

    def is_registered(self, strategy_name: str) -> bool:
        reg = self._registry.get(strategy_name)
        return reg is not None and reg.status == AlgoStatus.REGISTERED

    def get_order_log(self, algo_id: Optional[str] = None) -> list[TaggedOrder]:
        """Return all tagged orders, optionally filtered by algo_id."""
        if algo_id:
            return [o for o in self._order_log if o.algo_id == algo_id]
        return list(self._order_log)

    def list_strategies(self) -> list[str]:
        return list(self._registry.keys())
