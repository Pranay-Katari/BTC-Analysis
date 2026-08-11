#include "replay/analytics_engine.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>

using namespace std;

namespace replay {
namespace {

double midpoint(const Event& event) {
  return (event.yes_bid + event.yes_ask) / 2.0;
}

double velocity(const Event& current, const Event& previous,
                double current_value, double previous_value) {
  const double seconds = current.timestamp - previous.timestamp;
  return seconds > 0 ? (current_value - previous_value) / seconds : 0;
}

double volatility_bps(const deque<Event>& window) {
  if (window.size() < 3) return 0;
  vector<double> returns;
  for (size_t i = 1; i < window.size(); ++i) {
    if (window[i - 1].btc_price > 0) {
      returns.push_back(
          log(window[i].btc_price / window[i - 1].btc_price) * 10000.0);
    }
  }
  const double mean =
      accumulate(returns.begin(), returns.end(), 0.0) / returns.size();
  double variance = 0;
  for (const double value : returns) variance += pow(value - mean, 2);
  return sqrt(variance / returns.size());
}

double path_efficiency(const deque<Event>& window) {
  if (window.size() < 2) return 0;
  double travelled = 0;
  for (size_t i = 1; i < window.size(); ++i) {
    travelled += abs(midpoint(window[i]) - midpoint(window[i - 1]));
  }
  return travelled > 0
             ? abs(midpoint(window.back()) - midpoint(window.front())) /
                   travelled
             : 0;
}

}  // namespace

Metrics AnalyticsEngine::process(const Event& event) {
  window_.push_back(event);
  while (!window_.empty() && event.timestamp - window_.front().timestamp > 60) {
    window_.pop_front();
  }

  const Event& reference = window_.size() > 3 ? window_[window_.size() - 4]
                                               : window_.front();
  const double yes = midpoint(event);
  const double contract_velocity =
      velocity(event, reference, yes, midpoint(reference));
  const double btc_velocity =
      velocity(event, reference, event.btc_price, reference.btc_price);
  const double step = event.timestamp - previous_timestamp_;
  const double contract_acceleration =
      step > 0 ? (contract_velocity - previous_contract_velocity_) / step : 0;
  const double btc_acceleration =
      step > 0 ? (btc_velocity - previous_btc_velocity_) / step : 0;
  previous_contract_velocity_ = contract_velocity;
  previous_btc_velocity_ = btc_velocity;
  previous_timestamp_ = event.timestamp;
  const double vol = volatility_bps(window_);
  const string regime =
      window_.size() < 10 ? "warming-up" : vol < 0.08 ? "quiet" :
      vol < 0.30 ? "normal" : "active";
  const string consensus = yes >= 50 ? "yes" : "no";
  const double consensus_price = max(yes, 100.0 - yes);
  const bool agreement =
      (consensus == "yes" && contract_velocity > 0 && btc_velocity > 0) ||
      (consensus == "no" && contract_velocity < 0 && btc_velocity < 0);

  string decision = "observe";
  if (position_ == "flat" && window_.size() >= 10 &&
      consensus_price >= 85 && agreement) {
    position_ = consensus;
    entry_price_ = consensus_price;
    decision = "paper-entry";
  } else if (position_ != "flat") {
    const double held_price = position_ == "yes" ? yes : 100.0 - yes;
    const bool expired = event.timestamp >= 900;
    if (held_price < 70 || expired) {
      const double settlement = expired
                                    ? ((event.btc_price >= event.target_price) ==
                                               (position_ == "yes")
                                           ? 100.0
                                           : 0.0)
                                    : held_price;
      cumulative_pnl_cents_ += settlement - entry_price_;
      position_ = "flat";
      decision = "paper-exit";
    } else {
      decision = "hold";
    }
  }

  return Metrics{
      .timestamp = event.timestamp,
      .yes_price = yes,
      .no_price = 100.0 - yes,
      .contract_velocity = contract_velocity,
      .btc_velocity = btc_velocity,
      .contract_acceleration = contract_acceleration,
      .btc_acceleration = btc_acceleration,
      .volatility_bps = vol,
      .path_efficiency = path_efficiency(window_),
      .margin_pct = event.target_price > 0
                        ? (event.btc_price - event.target_price) /
                              event.target_price * 100.0
                        : 0,
      .spread_cents = max(0.0, event.yes_ask - event.yes_bid),
      .cumulative_pnl_cents = cumulative_pnl_cents_,
      .regime = regime,
      .decision = decision,
      .position = position_,
  };
}

void AnalyticsEngine::reset() {
  window_.clear();
  position_ = "flat";
  entry_price_ = 0;
  cumulative_pnl_cents_ = 0;
  previous_contract_velocity_ = 0;
  previous_btc_velocity_ = 0;
  previous_timestamp_ = 0;
}

}  // namespace replay
