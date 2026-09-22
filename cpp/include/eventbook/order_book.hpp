#pragma once
#include <cstdint>
#include <map>
#include <optional>
#include <stdexcept>
#include <vector>

namespace eventbook {
enum class Side { Bid, Ask };
struct Level { int price_cents; int quantity; };
class OrderBook {
 public:
  void add(Side side, int price_cents, int quantity);
  void modify(Side side, int price_cents, int quantity);
  void cancel(Side side, int price_cents, int quantity);
  void trade(Side side, int price_cents, int quantity);
  std::optional<int> best_bid() const;
  std::optional<int> best_ask() const;
  std::optional<double> midpoint() const;
  std::optional<int> spread() const;
  std::vector<Level> depth(Side side, std::size_t n) const;
 private:
  std::map<int, int, std::greater<>> bids_;
  std::map<int, int> asks_;
  std::map<int, int, std::greater<>>& bid_levels();
  void validate_price_quantity(int price_cents, int quantity) const;
};
} // namespace eventbook
