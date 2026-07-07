import unittest

from engine import process_commands
import json

class TestInventoryReservationEngine(unittest.TestCase):

    def test_spec_example(self):
        commands = [
            {"commandId": "c1", "type": "add_stock", "sku": "P1", "quantity": 10},
            {"commandId": "c2", "type": "reserve", "orderId": "O100", "sku": "P1", "quantity": 4},
            {"commandId": "c3", "type": "reserve", "orderId": "O200", "sku": "P1", "quantity": 8},
            {"commandId": "c4", "type": "add_stock", "sku": "P1", "quantity": 5},
            {"commandId": "c5", "type": "reserve", "orderId": "O200", "sku": "P1", "quantity": 8},
            {"commandId": "c6", "type": "ship", "orderId": "O100", "sku": "P1", "quantity": 3},
            {"commandId": "c7", "type": "release", "orderId": "O200", "sku": "P1", "quantity": 2},
            {"commandId": "c8", "type": "ship", "orderId": "O100", "sku": "P1", "quantity": 2},
            {"commandId": "c9", "type": "add_stock", "sku": "P2", "quantity": 7},
            {"commandId": "c10", "type": "reserve", "orderId": "O300", "sku": "P2", "quantity": 5},
            {"commandId": "c10", "type": "reserve", "orderId": "O300", "sku": "P2", "quantity": 5},
        ]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], ["c3", "c8", "c10"])
        self.assertEqual(
            result["summaries"],
            [
                {"sku": "P1", "onHand": 12, "reserved": 7, "available": 5, "shipped": 3},
                {"sku": "P2", "onHand": 7, "reserved": 5, "available": 2, "shipped": 0},
            ],
        )
        # print(json.dumps(result, indent=2))

    def test_duplicate_command_id_only_first_applies(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 5},
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 100},
        ]
        result = process_commands(commands)
        self.assertEqual(result["summaries"][0]["onHand"], 5)
        self.assertEqual(result["failedCommands"], ["a1"])
        # print(json.dumps(result, indent=2))

    def test_reserve_fails_without_enough_available(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 5},
            {"commandId": "a2", "type": "reserve", "orderId": "O1", "sku": "X", "quantity": 6},
        ]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], ["a2"])
        self.assertEqual(result["summaries"][0]["reserved"], 0)
        # print(json.dumps(result, indent=2))

    def test_release_fails_if_order_has_no_reservation(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 5},
            {"commandId": "a2", "type": "release", "orderId": "O1", "sku": "X", "quantity": 1},
        ]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], ["a2"])

    def test_ship_reduces_on_hand_and_reserved(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 10},
            {"commandId": "a2", "type": "reserve", "orderId": "O1", "sku": "X", "quantity": 4},
            {"commandId": "a3", "type": "ship", "orderId": "O1", "sku": "X", "quantity": 4},
        ]
        result = process_commands(commands)
        summary = result["summaries"][0]
        self.assertEqual(summary["onHand"], 6)
        self.assertEqual(summary["reserved"], 0)
        self.assertEqual(summary["shipped"], 4)
        self.assertEqual(summary["available"], 6)
        # print(json.dumps(result, indent=2))

    def test_case_insensitive_type(self):
        commands = [
            {"commandId": "a1", "type": "ADD_STOCK", "sku": "X", "quantity": 5},
            {"commandId": "a2", "type": "Reserve", "orderId": "O1", "sku": "X", "quantity": 2},
        ]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], [])
        self.assertEqual(result["summaries"][0]["reserved"], 2)
        # print(json.dumps(result, indent=2))

    def test_quantity_must_be_positive(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 0},
            {"commandId": "a2", "type": "add_stock", "sku": "X", "quantity": -3},
        ]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], ["a1", "a2"])
        self.assertEqual(result["summaries"], [])  # no successful commands for sku
        # print(json.dumps(result, indent=2))

    def test_missing_order_id_on_reserve(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 5},
            {"commandId": "a2", "type": "reserve", "sku": "X", "quantity": 2},
        ]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], ["a2"])

    def test_blank_sku_fails(self):
        commands = [{"commandId": "a1", "type": "add_stock", "sku": "  ", "quantity": 5}]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], ["a1"])
        self.assertEqual(result["summaries"], [])

    def test_unknown_type_fails(self):
        commands = [{"commandId": "a1", "type": "cancel", "sku": "X", "quantity": 5}]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], ["a1"])

    def test_summaries_sorted_by_sku(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "Z", "quantity": 5},
            {"commandId": "a2", "type": "add_stock", "sku": "A", "quantity": 5},
        ]
        result = process_commands(commands)
        self.assertEqual([s["sku"] for s in result["summaries"]], ["A", "Z"])

    def test_release_partial_then_ship_remaining(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 10},
            {"commandId": "a2", "type": "reserve", "orderId": "O1", "sku": "X", "quantity": 6},
            {"commandId": "a3", "type": "release", "orderId": "O1", "sku": "X", "quantity": 2},
            {"commandId": "a4", "type": "ship", "orderId": "O1", "sku": "X", "quantity": 4},
        ]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], [])
        summary = result["summaries"][0]
        self.assertEqual(summary["onHand"], 6)
        self.assertEqual(summary["reserved"], 0)
        self.assertEqual(summary["shipped"], 4)

    def test_two_orders_same_sku_independent_reservations(self):
        commands = [
            {"commandId": "a1", "type": "add_stock", "sku": "X", "quantity": 10},
            {"commandId": "a2", "type": "reserve", "orderId": "O1", "sku": "X", "quantity": 3},
            {"commandId": "a3", "type": "reserve", "orderId": "O2", "sku": "X", "quantity": 3},
            # O2 only has 3 reserved; trying to ship 4 against O2 must fail,
            # even though total reserved (6) would technically cover it.
            {"commandId": "a4", "type": "ship", "orderId": "O2", "sku": "X", "quantity": 4},
        ]
        result = process_commands(commands)
        self.assertEqual(result["failedCommands"], ["a4"])
        summary = result["summaries"][0]
        self.assertEqual(summary["reserved"], 6)
        self.assertEqual(summary["shipped"], 0)

if __name__ == "__main__":
    unittest.main()