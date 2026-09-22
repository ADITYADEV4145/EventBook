#include "eventbook/order_book.hpp"
#include <cassert>
using namespace eventbook;
int main() { OrderBook b; b.add(Side::Bid, 45, 10); b.add(Side::Ask, 49, 8); assert(b.best_bid()==45 && b.best_ask()==49 && b.spread()==4); b.trade(Side::Ask,49,3); assert(b.depth(Side::Ask,1)[0].quantity==5); bool thrown=false; try { b.cancel(Side::Bid,45,11); } catch(...) { thrown=true; } assert(thrown); }
