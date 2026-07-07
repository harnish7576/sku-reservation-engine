INVENTORY RESERVATION ENGINE
=============================

HOW TO RUN
----------
No dependencies beyond the Python standard library

Run source code:
    python3 engine.py

Run tests:
    python3 -m unittest test_engine.py -v

Use directly:
    from engine import process_commands
    result = process_commands(commands)
    # result = {"summaries": [...], "failedCommands": [...]}


DESIGN
------
SkuState (dataclass) owns all state for one SKU: on_hand, reserved,
shipped, and a per-order reservation ledger (orderId -> qty). Its
methods (add_stock, reserve, release, ship) enforce their own
invariants and raise a domain exception if invalid, so reserved can
never change without the ledger changing with it. available is a
property derived from on_hand and reserved, never stored separately.

process_commands is a thin loop: validate shape, check commandId
against a seen set for dedup, dispatch to the matching SkuState
method, catch domain exceptions as failures. No inventory logic lives
in the loop itself


ASSUMPTIONS
-----------
- ship reduces on_hand, not just reserved. Confirmed against the
  worked example: P1 gets 10 + 5 = 15 units added, but expected final
  onHand is 12 -- exactly 15 minus the 3 shipped in c6.

- Reservations are tracked per (orderId, sku). An order can only
  release/ship up to what it individually holds, even if the SKU's
  total reserved count is higher. See
  test_two_orders_same_sku_independent_reservations

- Any type outside add_stock/reserve/release/ship fails the command

- quantity must be a positive number. Zero, negative, non-numeric,
  and bool values are all rejected before any state mutation.

- A command with a blank/missing commandId is excluded from state
  mutation but only added to failedCommands if the id itself exists
  (nothing meaningful to report otherwise).

- Failed commands never partially mutate state -- all validation
  happens before or is caught immediately after a SkuState method
  runs.


DESIGN TRADEOFFS
-----------------
- Domain objects over a flat counters dict: costs a bit more code,
  buys protection against reserved and the per-order ledger drifting
  out of sync.

- Exceptions over (success, reason) tuples: keeps the mutation code
  readable and makes a missed failure check loud instead of silent.

- Dedup checked before domain validation: a duplicate commandId fails
  even if the underlying command would have succeeded (matches c10 in
  the spec example)


EXTRAS
----------------------------
- Concurrency: lock per SKU (not global, not per-order), since
  reserve validation reads/writes shared SKU-level counters.

- Persistence: append validated commands to a durable log before
  mutating state; replay from last snapshot on restart. Existing
  commandId dedup makes replay idempotent for free

- API: keep process_commands/SkuState free of I/O; an HTTP layer
  translates request -> command, takes the SKU lock, calls the
  domain function, persists, responds.

- Audit/replay: store the full command list including failures.
  State is a fold over that list, so "state at time T" is a filter +
  replay, not a separate mechanism.