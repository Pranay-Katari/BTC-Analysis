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
    eth_price: float
    sol_price: float

    def engine_line(self) -> str:
        return (
            f"{self.elapsed_seconds},{self.yes_bid_c},{self.yes_ask_c},"
            f"{self.btc_price},{self.target_price},{self.volume},"
            f"{self.eth_price},{self.sol_price}\n"
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
    eth_velocity: float
    sol_velocity: float
    simulated_above_pct: float
    probability_gap_pct: float
    terminal_median: float
    terminal_p10: float
    terminal_p90: float
    reversal_probability_pct: float
    regime: str
    decision: str
    position: str
    cross_asset_state: str
    model_confidence: str

    @classmethod
    def from_csv(cls, line: str) -> "Analytics":
        fields = line.strip().split(",")
        if len(fields) != 25:
            raise ValueError(f"unexpected analytics response: {line!r}")
        numbers = [float(value) for value in fields[:20]]
        return cls(*numbers, *fields[20:])


def point(event: LiveEvent, analytics: Analytics) -> dict:
    return {**asdict(event), **asdict(analytics)}
