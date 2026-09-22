#include "eventbook/order_book.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

PYBIND11_MODULE(_eventbook_core, module) {
  module.doc() = "EventBook C++20 order-book primitives.";

  py::enum_<eventbook::Side>(module, "Side")
      .value("BID", eventbook::Side::Bid)
      .value("ASK", eventbook::Side::Ask);

  py::class_<eventbook::Level>(module, "BookLevel")
      .def_readonly("price_cents", &eventbook::Level::price_cents)
      .def_readonly("quantity", &eventbook::Level::quantity);

  py::class_<eventbook::OrderBook>(module, "OrderBook")
      .def(py::init<>())
      .def("add", &eventbook::OrderBook::add)
      .def("modify", &eventbook::OrderBook::modify)
      .def("cancel", &eventbook::OrderBook::cancel)
      .def("trade", &eventbook::OrderBook::trade)
      .def("best_bid", &eventbook::OrderBook::best_bid)
      .def("best_ask", &eventbook::OrderBook::best_ask)
      .def("midpoint", &eventbook::OrderBook::midpoint)
      .def("spread", &eventbook::OrderBook::spread)
      .def("depth", &eventbook::OrderBook::depth);
}
