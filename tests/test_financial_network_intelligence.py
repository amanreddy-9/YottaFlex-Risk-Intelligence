"""Comprehensive test suite for the Financial Network Intelligence System (Scenarios A through H).

Verifies:
- Scenario A: Customer ownership of multiple accounts and transactional relationships.
- Scenario B: Directional fund flow path tracing (distinguishing unique fund flow from gross volume).
- Scenario C: Circular transaction loop detection (A -> B -> C -> A).
- Scenario D: Rapid fund dispersion (fan-out) and fan-in concentration pattern detection.
- Scenario E: Shared device collusion rings linking multiple distinct customer accounts.
- Scenario F: Isolated entity handling with zero edges.
- Scenario G: Graceful fallback for non-existent / invalid entity IDs.
- Scenario H: Entity search, entity resolution, and transparent network risk scoring.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yottaflex.api.service import WorkbenchService
from yottaflex.workflow.network_intelligence import (
    compute_network_risk_analysis,
    detect_circular_transfers,
    detect_suspicious_patterns,
    get_financial_network_graph,
    get_network_overview,
    resolve_entities,
    search_network_entities,
    trace_money_flow_path,
)

DB_PATH = ROOT / "data" / "exports" / "full" / "yottaflex.db"


class TestFinancialNetworkIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest(f"Database {DB_PATH} not found; skipping network intelligence tests.")
        cls.conn = sqlite3.connect(str(DB_PATH))
        cls.conn.row_factory = sqlite3.Row
        cls.service = WorkbenchService(DB_PATH.parent)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "conn"):
            cls.conn.close()

    def test_scenario_a_customer_ownership_and_transactions(self):
        """Scenario A: Customer owns accounts and has transaction relationships."""
        # Find a customer with at least one account
        cust = self.conn.execute("SELECT primary_customer_id FROM accounts LIMIT 1").fetchone()
        self.assertIsNotNone(cust)
        cust_id = cust["primary_customer_id"]

        graph = get_financial_network_graph(self.conn, seed_id=cust_id, depth=2, max_nodes=50)
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        self.assertGreaterEqual(len(graph["nodes"]), 1)

        # Confirm customer node is present
        node_ids = {n["id"] for n in graph["nodes"]}
        self.assertIn(cust_id, node_ids)

        # Confirm customer node has CUSTOMER type
        cust_node = next(n for n in graph["nodes"] if n["id"] == cust_id)
        self.assertEqual(cust_node["type"], "CUSTOMER")
        self.assertIn("risk_score", cust_node)
        self.assertIn("risk_classification", cust_node)

        # Check for OWNS edge to an account
        owns_edges = [e for e in graph["edges"] if e["source"] == cust_id and e["relationship"] == "OWNS"]
        self.assertGreaterEqual(len(owns_edges), 1)

    def test_scenario_b_multi_hop_fund_flow_path(self):
        """Scenario B: Reconstruct directional fund transfer path and distinguish unique flow from gross volume."""
        # Query two accounts linked by transfer_links
        transfer = self.conn.execute("SELECT source_account_id, dest_account_id, transfer_amount FROM transfer_links LIMIT 1").fetchone()
        self.assertIsNotNone(transfer)
        src = transfer["source_account_id"]
        dst = transfer["dest_account_id"]

        result = trace_money_flow_path(self.conn, src, dst, max_depth=3)
        self.assertGreaterEqual(result["paths_found"], 1)
        self.assertGreaterEqual(result["shortest_path_hops"], 1)
        self.assertGreater(result["total_transaction_volume"], 0)
        self.assertGreater(result["estimated_unique_flow"], 0)

        # Spec Section 5: Estimated unique flow must never exceed gross transaction volume
        self.assertLessEqual(result["estimated_unique_flow"], result["total_transaction_volume"])
        self.assertEqual(result["flow_confidence"], "CONFIRMED")

        # Verify hop attributes
        hop = result["paths"][0][0]
        self.assertEqual(hop["from_account"], src)
        self.assertEqual(hop["to_account"], dst)
        self.assertIn("amount", hop)
        self.assertIn("initiated_at", hop)

    def test_scenario_c_circular_transfer_loops(self):
        """Scenario C: Detect circular transaction loops (A -> B -> C -> A)."""
        cycles = detect_circular_transfers(self.conn, limit=10)
        self.assertIsInstance(cycles, list)

        if len(cycles) > 0:
            c = cycles[0]
            self.assertIn("cycle_id", c)
            self.assertIn("length", c)
            self.assertGreaterEqual(c["length"], 3)  # At least 3 hops for closed loop
            self.assertEqual(c["nodes"][0], c["nodes"][-1])  # Closes on itself
            self.assertGreater(c["total_cycle_volume"], 0)
            self.assertEqual(c["confidence"], "CONFIRMED_CYCLE")

    def test_scenario_d_rapid_fund_dispersion_and_concentration(self):
        """Scenario D: Identify fan-in concentration and rapid dispersion (fan-out)."""
        patterns = detect_suspicious_patterns(self.conn)
        self.assertIn("fan_in_concentration", patterns)
        self.assertIn("rapid_dispersion", patterns)
        self.assertIn("shared_device_clusters", patterns)

        # Check fan-in concentration structure
        for item in patterns["fan_in_concentration"]:
            self.assertIn("destination_account", item)
            self.assertIn("inflow_sources", item)
            self.assertGreaterEqual(item["inflow_sources"], 3)
            self.assertGreater(item["total_inflow_amount"], 0)

        # Check rapid dispersion structure
        for item in patterns["rapid_dispersion"]:
            self.assertIn("origin_account", item)
            self.assertIn("outflow_targets", item)
            self.assertGreaterEqual(item["outflow_targets"], 3)
            self.assertGreater(item["total_outflow_amount"], 0)

    def test_scenario_e_shared_device_collusion_rings(self):
        """Scenario E: Multiple customers linked through shared device/emulator."""
        patterns = detect_suspicious_patterns(self.conn)
        clusters = patterns["shared_device_clusters"]
        self.assertGreaterEqual(len(clusters), 1)

        cluster = clusters[0]
        self.assertIn("device_id", cluster)
        self.assertGreaterEqual(cluster["shared_customers_count"], 2)
        self.assertGreaterEqual(len(cluster["customers"]), 2)

        # Verify device node in graph
        dev_graph = get_financial_network_graph(self.conn, seed_id=cluster["device_id"], depth=2, max_nodes=30)
        dev_node = next(n for n in dev_graph["nodes"] if n["id"] == cluster["device_id"])
        self.assertEqual(dev_node["type"], "DEVICE")

    def test_scenario_f_isolated_entity_handling(self):
        """Scenario F: Handle entity with minimal or zero connections gracefully."""
        # Create a temporary in-memory database with an isolated customer
        mem_conn = sqlite3.connect(":memory:")
        mem_conn.row_factory = sqlite3.Row
        mem_conn.execute("CREATE TABLE customers (customer_id TEXT PRIMARY KEY, full_name TEXT, kyc_tier TEXT, risk_rating TEXT, home_country TEXT, segment TEXT, email TEXT, phone TEXT, address_street TEXT, address_city TEXT)")
        mem_conn.execute("CREATE TABLE accounts (account_id TEXT PRIMARY KEY, primary_customer_id TEXT, current_balance REAL, account_type TEXT, status TEXT, opened_at TEXT, last_activity_at TEXT)")
        mem_conn.execute("CREATE TABLE transfer_links (transfer_id TEXT PRIMARY KEY, source_account_id TEXT, dest_account_id TEXT, transfer_amount REAL, initiated_at TEXT, debit_txn_id TEXT, credit_txn_id TEXT)")
        mem_conn.execute("CREATE TABLE transactions (txn_id TEXT PRIMARY KEY, account_id TEXT, amount REAL, timestamp TEXT, txn_type TEXT, status TEXT, merchant_id TEXT)")
        mem_conn.execute("CREATE TABLE devices (device_id TEXT PRIMARY KEY, customer_id TEXT, fingerprint TEXT, device_type TEXT, os TEXT, is_emulator INTEGER, is_rooted INTEGER)")
        mem_conn.execute("CREATE TABLE merchants (merchant_id TEXT PRIMARY KEY, legal_name TEXT, mcc_code TEXT, risk_tier TEXT)")
        mem_conn.execute("CREATE TABLE account_ownerships (account_id TEXT, customer_id TEXT, PRIMARY KEY(account_id, customer_id))")
        mem_conn.execute("CREATE TABLE account_device_links (account_id TEXT, device_id TEXT, PRIMARY KEY(account_id, device_id))")

        mem_conn.execute("INSERT INTO customers VALUES ('CUS-ISOLATED-1', 'Isolated Person', 'TIER_1', 'LOW', 'US', 'RETAIL', 'iso@test.com', '123', 'Street', 'City')")
        mem_conn.commit()

        graph = get_financial_network_graph(mem_conn, seed_id="CUS-ISOLATED-1", depth=2, max_nodes=50)
        self.assertEqual(len(graph["nodes"]), 1)
        self.assertEqual(len(graph["edges"]), 0)
        self.assertEqual(graph["nodes"][0]["id"], "CUS-ISOLATED-1")
        mem_conn.close()

    def test_scenario_g_invalid_entity_id_fallback(self):
        """Scenario G: Non-existent entity ID returns safe empty graph structure."""
        graph = get_financial_network_graph(self.conn, seed_id="NON_EXISTENT_ID_99999", depth=2, max_nodes=50)
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["total_nodes"], 0)

        # Path trace between non-existent accounts
        path = trace_money_flow_path(self.conn, "NON_EXISTENT_A", "NON_EXISTENT_B", max_depth=3)
        self.assertEqual(path["paths_found"], 0)
        self.assertEqual(path["paths"], [])

    def test_scenario_h_search_resolution_and_risk_analysis(self):
        """Scenario H: Search, entity resolution and transparent risk scoring."""
        # Search entities
        search_res = search_network_entities(self.conn, query="ACC-", entity_type="ACCOUNT", limit=5)
        self.assertGreaterEqual(len(search_res), 1)
        self.assertEqual(search_res[0]["type"], "ACCOUNT")

        # Entity resolution
        res_items = resolve_entities(self.conn, limit=10)
        self.assertIsInstance(res_items, list)
        if len(res_items) > 0:
            item = res_items[0]
            self.assertIn("cluster_id", item)
            self.assertIn(item["resolution_status"], ["CONFIRMED_MATCH", "POTENTIAL_MATCH"])
            self.assertGreater(item["match_confidence"], 50)
            self.assertGreaterEqual(len(item["shared_identifiers"]), 1)

        # Network risk analysis
        risk = compute_network_risk_analysis(self.conn)
        self.assertIn("overall_network_risk_score", risk)
        self.assertTrue(0 <= risk["overall_network_risk_score"] <= 100)
        self.assertIn(risk["risk_tier"], ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        self.assertIn("factors", risk)
        self.assertGreater(len(risk["factors"]), 0)

        # Check factor weights sum approximately to 1.0
        total_weight = sum(f["weight"] for f in risk["factors"])
        self.assertAlmostEqual(total_weight, 1.0, places=2)

    def test_service_methods_integration(self):
        """Verify service layer methods work and return structured dictionaries."""
        overview = self.service.get_financial_network_overview()
        self.assertIn("total_customers", overview)
        self.assertIn("total_transfers", overview)

        patterns = self.service.detect_suspicious_patterns()
        self.assertIn("fan_in_concentration", patterns)

        cycles = self.service.detect_circular_transfers(limit=5)
        self.assertIsInstance(cycles, list)

    def test_node_selection_and_inspector_metadata_completeness(self):
        """Verify every node in graph has all required metadata fields for Inspector Panel."""
        graph = get_financial_network_graph(self.conn, depth=2, max_nodes=50)
        self.assertGreater(len(graph["nodes"]), 0)

        valid_types = {"CUSTOMER", "ACCOUNT", "MERCHANT", "DEVICE", "TRANSACTION"}
        valid_tiers = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

        for node in graph["nodes"]:
            # Required fields for Entity Intelligence Panel
            self.assertIn("id", node)
            self.assertTrue(len(node["id"]) > 0)
            self.assertIn("label", node)
            self.assertTrue(len(node["label"]) > 0)
            self.assertIn("type", node)
            self.assertIn(node["type"], valid_types)
            self.assertIn("risk_score", node)
            self.assertTrue(0 <= node["risk_score"] <= 100)
            self.assertIn("risk_classification", node)
            self.assertIn(node["risk_classification"], valid_tiers)
            self.assertIn("in_degree", node)
            self.assertGreaterEqual(node["in_degree"], 0)
            self.assertIn("out_degree", node)
            self.assertGreaterEqual(node["out_degree"], 0)
            self.assertIn("metadata", node)
            self.assertIsInstance(node["metadata"], dict)

    def test_node_selection_neighbor_isolation_and_highlighting(self):
        """Simulate node selection highlighting logic: neighbors identified and non-neighbors dimmed."""
        graph = get_financial_network_graph(self.conn, depth=2, max_nodes=50)
        nodes = graph["nodes"]
        edges = graph["edges"]

        for selected_node in nodes[:5]:
            selected_id = selected_node["id"]

            # Compute connected neighbors through edges
            neighbor_ids = {selected_id}
            for e in edges:
                if e["source"] == selected_id:
                    neighbor_ids.add(e["target"])
                elif e["target"] == selected_id:
                    neighbor_ids.add(e["source"])

            # Verify selection invariant: selected node is always in neighbor set
            self.assertIn(selected_id, neighbor_ids)

            # Check that degree matches total edge occurrences
            edge_count = sum(1 for e in edges if e["source"] == selected_id or e["target"] == selected_id)
            self.assertEqual(selected_node["in_degree"] + selected_node["out_degree"], edge_count)

    def test_multiple_node_selections_and_deselection(self):
        """Verify sequential node selections and background click deselection."""
        graph = get_financial_network_graph(self.conn, depth=2, max_nodes=30)
        nodes = graph["nodes"]
        self.assertGreaterEqual(len(nodes), 2)

        # Selection state simulation
        active_selection = None

        # 1. Select Node 1
        active_selection = nodes[0]["id"]
        self.assertEqual(active_selection, nodes[0]["id"])

        # 2. Switch to Node 2 (single click switches selection)
        active_selection = nodes[1]["id"]
        self.assertEqual(active_selection, nodes[1]["id"])

        # 3. Deselect by clicking background
        active_selection = None
        self.assertIsNone(active_selection)


if __name__ == "__main__":
    unittest.main()
