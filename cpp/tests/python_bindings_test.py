import _eventbook_core as core


book = core.OrderBook()
book.add(core.Side.BID, 51, 4)
book.add(core.Side.ASK, 53, 6)

assert book.best_bid() == 51
assert book.best_ask() == 53
assert book.spread() == 2
assert book.depth(core.Side.BID, 1)[0].quantity == 4
