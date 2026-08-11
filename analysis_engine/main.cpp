#include "replay/analytics_engine.hpp"

#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

namespace {

vector<string> split_csv(const string& line) {
  vector<string> fields;
  stringstream input(line);
  string field;

  while (getline(input, field, ',')) {
    fields.push_back(field);
  }

  return fields;
}

void send_metrics(const replay::Metrics& metrics) {
  cout << fixed << setprecision(6) << metrics.timestamp << ','
       << metrics.yes_price << ',' << metrics.no_price << ','
       << metrics.contract_velocity << ',' << metrics.btc_velocity << ','
       << metrics.contract_acceleration << ',' << metrics.btc_acceleration << ','
       << metrics.volatility_bps << ',' << metrics.path_efficiency << ','
       << metrics.margin_pct << ',' << metrics.spread_cents << ','
       << metrics.cumulative_pnl_cents << ',' << metrics.regime << ','
       << metrics.decision << ',' << metrics.position << '\n'
       << flush;
}

}  // namespace

int main() {
  replay::AnalyticsEngine engine;
  string line;

  // Python sends one market update per line and reads one response per line.
  while (getline(cin, line)) {
    if (line == "reset") {
      engine.reset();
      cout << "reset\n" << flush;
      continue;
    }

    const auto fields = split_csv(line);
    if (fields.size() != 6) {
      cerr << "expected timestamp,yes_bid,yes_ask,btc,target,volume\n";
      continue;
    }

    try {
      const replay::Event tick{
          stod(fields[0]), stod(fields[1]), stod(fields[2]),
          stod(fields[3]), stod(fields[4]), stod(fields[5])};
      send_metrics(engine.process(tick));
    } catch (const exception& error) {
      cerr << error.what() << '\n';
    }
  }

  return 0;
}
