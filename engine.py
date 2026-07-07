"""Inventory Reservation Engine. See README.md for design/approach notes."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import json

VALID_TYPES = {"add_stock", "reserve", "release", "ship"}
ORDER_REQUIRED_TYPES = {"reserve", "release", "ship"}

class InsufficientInventoryError(Exception):
    """Raised when a reserve would exceed currently available inventory."""

class InsufficientReservationError(Exception):
    """Raised when a release/ship exceeds what's reserved for that order+sku."""

@dataclass 
class SkuState:
    sku: str
    on_hand: int = 0
    reserved: int = 0
    shipped: int = 0
    # orderId -> qty currently reserved for this sku by that order
    reservations: Dict[str, int] = field(default_factory=dict)

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved

    def add_stock(self, qty: int) -> None:
        self.on_hand += qty

    def reserve(self, order_id: str, qty: int) -> None:
        if qty > self.available:
            raise InsufficientInventoryError(
                f"{self.sku}: cannot reserve {qty}, only {self.available} available"
            )
        self.reserved += qty
        self.reservations[order_id] = self.reservations.get(order_id, 0) + qty

    def release(self, order_id: str, qty: int) -> None:
        held = self.reservations.get(order_id, 0)
        if qty > held:
            raise InsufficientReservationError(
                f"{self.sku}: order {order_id} has {held} reserved, cannot release {qty}"
            )
        self.reserved -= qty
        self._shrink_reservation(order_id, qty)

    def ship(self, order_id: str, qty: int) -> None:
        held = self.reservations.get(order_id, 0)
        if qty > held:
            raise InsufficientReservationError(
                f"{self.sku}: order {order_id} has {held} reserved, cannot ship {qty}"
            )
        # ship reduces on_hand too, not just reserved (see README assumptions)
        self.reserved -= qty
        self.on_hand -= qty
        self.shipped += qty
        self._shrink_reservation(order_id, qty)

    def _shrink_reservation(self, order_id: str, qty: int) -> None:
        remaining = self.reservations.get(order_id, 0) - qty
        if remaining <= 0:
            self.reservations.pop(order_id, None)
        else:
            self.reservations[order_id] = remaining

    def to_summary(self) -> dict:
        return {
            "sku": self.sku,
            "onHand": self.on_hand,
            "reserved": self.reserved,
            "available": self.available,
            "shipped": self.shipped,
        }

def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")

def _validate_shape(cmd: dict) -> Optional[str]:
    """Structural validation only. Returns a failure reason, or None if OK."""
    if _is_blank(cmd.get("commandId")):
        return "missing commandId"

    raw_type = cmd.get("type")
    if _is_blank(raw_type):
        return "missing type"
    ctype = raw_type.strip().lower()
    if ctype not in VALID_TYPES:
        return f"unknown type '{raw_type}'"

    if _is_blank(cmd.get("sku")):
        return "missing sku"

    qty = cmd.get("quantity")
    if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty <= 0:
        return "quantity must be a positive number"

    if ctype in ORDER_REQUIRED_TYPES and _is_blank(cmd.get("orderId")):
        return "missing orderId"

    return None

def process_commands(commands: List[dict]) -> dict:
    skus: Dict[str, SkuState] = {}
    touched: Set[str] = set()
    seen_ids: Set[str] = set()
    failed: List[str] = []

    for cmd in commands:
        command_id = cmd.get("commandId")

        if _validate_shape(cmd) is not None:
            if not _is_blank(command_id):
                failed.append(command_id)
            continue

        if command_id in seen_ids:
            failed.append(command_id)
            continue
        seen_ids.add(command_id)

        ctype = cmd["type"].strip().lower()
        sku_name = cmd["sku"]
        qty = cmd["quantity"]
        order_id = cmd.get("orderId")

        state = skus.setdefault(sku_name, SkuState(sku=sku_name))

        try:
            if ctype == "add_stock":
                state.add_stock(qty)
            elif ctype == "reserve":
                state.reserve(order_id, qty)
            elif ctype == "release":
                state.release(order_id, qty)
            elif ctype == "ship":
                state.ship(order_id, qty)
        except (InsufficientInventoryError, InsufficientReservationError):
            failed.append(command_id)
            continue

        touched.add(sku_name)

    summaries = [skus[sku].to_summary() for sku in sorted(touched)]
    return {"summaries": summaries, "failedCommands": failed}

if __name__ == "__main__":
    example_commands = [
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
    print(json.dumps(process_commands(example_commands), indent=2))