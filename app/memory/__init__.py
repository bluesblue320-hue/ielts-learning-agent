"""Phase 6 hierarchical learning memory read models.

L0 = existing normalized PostgreSQL rows (never duplicated); L1/L2/L3 are
derived read models over them. No new tables, no synthetic memory ids, no
provider calls, no mutations.
"""
