from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class LiveEvent:
    elapsed_seconds: int
    timestamp_utc: str
    yes_bid_c: float
    yes_ask_c: float
    btc_price: float
    target_price: float
    volume: float

    def engine_line(self) -> str:
        return (
            f"{self.elapsed_seconds},{self.yes_bid_c},{self.yes_ask_c},"
            f"{self.btc_price},{self.target_price},{self.volume}\n"
        )


@dataclass(slots=True)
class Analytics:
    elapsed_seconds: float
    yes_price: float
    no_price: float
    contract_velocity: float
    btc_velocity: float
    contract_acceleration: float
    btc_acceleration: float
    volatility_bps: float
    path_efficiency: float
    margin_pct: float
    spread_cents: float
    cumulative_pnl_cents: float
    regime: str
    decision: str
    position: str

    @classmethod
    def from_csv(cls, line: str) -> "Analytics":
        fields = line.strip().split(",")
        if len(fields) != 15:
            raise ValueError(f"unexpected analytics response: {line!r}")
        numbers = [float(value) for value in fields[:12]]
        return cls(*numbers, *fields[12:])


def point(event: LiveEvent, analytics: Analytics) -> dict:
    return {**asdict(event), **asdict(analytics)}
