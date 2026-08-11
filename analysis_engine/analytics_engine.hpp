#pragma once

#include <deque>
#include <string>

namespace replay {

struct Event {
  double timestamp = 0;
  double yes_bid = 0;
  double yes_ask = 0;
  double btc_price = 0;
  double target_price = 0;
  double volume = 0;
};

struct Metrics {
  double timestamp = 0;
  double yes_price = 0;
  double no_price = 0;
  double contract_velocity = 0;
  double btc_velocity = 0;
  double contract_acceleration = 0;
  double btc_acceleration = 0;
  double volatility_bps = 0;
  double path_efficiency = 0;
  double margin_pct = 0;
  double spread_cents = 0;
  double cumulative_pnl_cents = 0;
  std::string regime = "warming-up";
  std::string decision = "observe";
  std::string position = "flat";
};

class AnalyticsEngine {
 public:
  Metrics process(const Event& event);
  void reset();

 private:
  std::deque<Event> window_;
  std::string position_ = "flat";
  double entry_price_ = 0;
  double cumulative_pnl_cents_ = 0;
  double previous_contract_velocity_ = 0;
  double previous_btc_velocity_ = 0;
  double previous_timestamp_ = 0;
};

}  // namespace replay
