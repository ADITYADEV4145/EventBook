#include "eventbook/order_book.hpp"
#include <functional>
namespace eventbook {
void OrderBook::validate_price_quantity(int p, int q) const { if (p < 0 || p > 100 || q <= 0) throw std::invalid_argument("price must be 0..100 and quantity positive"); }
void OrderBook::add(Side s,int p,int q) { validate_price_quantity(p,q); if(s==Side::Bid) bids_[p] += q; else asks_[p] += q; }
void OrderBook::modify(Side s,int p,int q) { validate_price_quantity(p,q); if(s==Side::Bid) { if(!bids_.contains(p)) throw std::invalid_argument("modify missing level"); bids_[p]=q; } else { if(!asks_.contains(p)) throw std::invalid_argument("modify missing level"); asks_[p]=q; } }
void OrderBook::cancel(Side s,int p,int q) { validate_price_quantity(p,q); if(s==Side::Bid) { auto it=bids_.find(p); if(it==bids_.end()||it->second<q) throw std::invalid_argument("cancel exceeds level"); if((it->second-=q)==0)bids_.erase(it); } else { auto it=asks_.find(p); if(it==asks_.end()||it->second<q) throw std::invalid_argument("cancel exceeds level"); if((it->second-=q)==0)asks_.erase(it); } }
void OrderBook::trade(Side s,int p,int q) { cancel(s,p,q); }
std::optional<int> OrderBook::best_bid() const { return bids_.empty()?std::nullopt:std::optional<int>(bids_.begin()->first); }
std::optional<int> OrderBook::best_ask() const { return asks_.empty()?std::nullopt:std::optional<int>(asks_.begin()->first); }
std::optional<double> OrderBook::midpoint() const { auto b=best_bid(),a=best_ask(); return b&&a?std::optional<double>(((*b)+(*a))/2.0):std::nullopt; }
std::optional<int> OrderBook::spread() const { auto b=best_bid(),a=best_ask(); return b&&a?std::optional<int>((*a)-(*b)):std::nullopt; }
std::vector<Level> OrderBook::depth(Side s,std::size_t n) const { std::vector<Level> r; if(s==Side::Bid) for(auto [p,q]:bids_){if(r.size()==n)break;r.push_back({p,q});} else for(auto [p,q]:asks_){if(r.size()==n)break;r.push_back({p,q});} return r; }
} // namespace eventbook
