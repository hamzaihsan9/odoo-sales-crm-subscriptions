#!/usr/bin/env python3
"""
Interactive Odoo 17 Sales & Recurring Subscription Billing Web Simulator.
Provides a high-fidelity Odoo 17 Community UI experience running on port 8069.
Enables real-time testing of Quotation margin calculation, discount guardrails,
automatic subscription generation, MRR/ARR analytics, and cron invoicing.
"""

import os
import http.server
import socketserver
import json
import urllib.parse
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

PORT = 8069

# In-Memory State Store simulating Odoo ORM Models
STATE = {
    "quotations": [
        {
            "id": "S00042",
            "partner": "Acme Enterprise Corp",
            "tier": "enterprise",
            "is_subscription": True,
            "billing_cycle": "monthly",
            "state": "draft",
            "discount_approved": False,
            "lines": [
                {"product": "Cloud ERP Platform License (Monthly)", "qty": 5, "price": 1000.0, "cost": 350.0, "discount": 10.0},
                {"product": "24/7 Premium SLA Dedicated Support", "qty": 1, "price": 2500.0, "cost": 800.0, "discount": 10.0}
            ]
        }
    ],
    "subscriptions": [
        {
            "id": "SUB/2026/0001",
            "origin": "S00038",
            "partner": "TechVentures Global",
            "billing_cycle": "monthly",
            "stage": "active",
            "start_date": "2026-09-01",
            "next_invoice_date": "2026-10-14",
            "payment_status": "paid",
            "auto_debit": True,
            "mrr": 3500.0,
            "arr": 42000.0,
            "cycle_amount": 3500.0,
            "lines": [
                {"product": "Dedicated High-Performance Postgres Cluster", "qty": 1, "price": 2000.0, "discount": 0.0},
                {"product": "Enterprise API & Webhook Suite", "qty": 1, "price": 1500.0, "discount": 0.0}
            ]
        },
        {
            "id": "SUB/2026/0002",
            "origin": "S00039",
            "partner": "Systems Soft PK",
            "billing_cycle": "annually",
            "stage": "active",
            "start_date": "2026-01-15",
            "next_invoice_date": "2026-10-14",
            "payment_status": "paid",
            "auto_debit": True,
            "mrr": 1200.0,
            "arr": 14400.0,
            "cycle_amount": 14400.0,
            "lines": [
                {"product": "Cloud ERP Platform License (Annual)", "qty": 12, "price": 1200.0, "discount": 0.0}
            ]
        }
    ],
    "invoices": [
        {
            "id": "INV/2026/0014",
            "subscription_id": "SUB/2026/0001",
            "partner": "TechVentures Global",
            "date": "2026-09-01",
            "amount": 3500.0,
            "status": "paid",
            "gateway_ref": "AUTO_SIM_INV_0014_20260901"
        }
    ],
    "cron_logs": []
}


def compute_quote_totals(quote):
    total_untaxed = 0.0
    total_cost = 0.0
    require_approval = False

    for l in quote["lines"]:
        disc = float(l.get("discount", 0.0))
        if disc > 20.0:
            require_approval = True
        subtotal = float(l["qty"]) * float(l["price"]) * (1 - disc / 100.0)
        cost_total = float(l["qty"]) * float(l.get("cost", 0.0))
        total_untaxed += subtotal
        total_cost += cost_total

    profit = total_untaxed - total_cost
    margin_pct = (profit / total_untaxed * 100.0) if total_untaxed > 0 else 0.0

    return {
        "total_untaxed": round(total_untaxed, 2),
        "total_cost": round(total_cost, 2),
        "margin_pct": round(margin_pct, 2),
        "require_approval": require_approval
    }


class OdooSimulatorHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            # Enrich active quotation with computed diagnostics
            q = STATE["quotations"][0]
            diagnostics = compute_quote_totals(q)
            
            # Aggregated Metrics
            active_subs = [s for s in STATE["subscriptions"] if s["stage"] == "active"]
            total_mrr = sum(s["mrr"] for s in active_subs)
            total_arr = sum(s["arr"] for s in active_subs)

            resp = {
                "active_quote": q,
                "quote_diagnostics": diagnostics,
                "subscriptions": STATE["subscriptions"],
                "invoices": STATE["invoices"],
                "cron_logs": STATE["cron_logs"][-10:],
                "metrics": {
                    "total_mrr": round(total_mrr, 2),
                    "total_arr": round(total_arr, 2),
                    "active_count": len(active_subs),
                    "total_invoices": len(STATE["invoices"])
                }
            }
            resp_bytes = json.dumps(resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        elif parsed.path == "/" or parsed.path == "/index.html":
            index_path = os.path.join(os.path.dirname(__file__), "demo_ui", "index.html")
            with open(index_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        payload = json.loads(body) if body else {}

        if parsed.path == "/api/quote/update":
            q = STATE["quotations"][0]
            if "tier" in payload:
                q["tier"] = payload["tier"]
                tier_discounts = {"standard": 0.0, "enterprise": 10.0, "strategic": 20.0}
                d = tier_discounts.get(q["tier"], 0.0)
                for l in q["lines"]:
                    if d > l["discount"]:
                        l["discount"] = d
            if "billing_cycle" in payload:
                q["billing_cycle"] = payload["billing_cycle"]
            if "lines" in payload:
                q["lines"] = payload["lines"]

            self.send_json({"status": "ok"})
            return

        elif parsed.path == "/api/quote/approve-discount":
            q = STATE["quotations"][0]
            q["discount_approved"] = True
            self.send_json({"status": "ok", "message": "High discount authorized by Sales Manager."})
            return

        elif parsed.path == "/api/quote/confirm":
            q = STATE["quotations"][0]
            diag = compute_quote_totals(q)
            if diag["require_approval"] and not q["discount_approved"]:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Quotation validation failed: Line discounts exceed 20% limit. Sales Manager approval required before confirmation."
                }).encode("utf-8"))
                return

            q["state"] = "sale"
            
            # Create Subscription Contract
            sub_id = f"SUB/2026/{len(STATE['subscriptions']) + 1:04d}"
            cycle = q["billing_cycle"]
            total_cycle = diag["total_untaxed"]

            if cycle == "monthly":
                mrr = total_cycle
                arr = total_cycle * 12.0
            elif cycle == "quarterly":
                mrr = total_cycle / 3.0
                arr = (total_cycle / 3.0) * 12.0
            else:
                mrr = total_cycle / 12.0
                arr = total_cycle

            new_sub = {
                "id": sub_id,
                "origin": q["id"],
                "partner": q["partner"],
                "billing_cycle": cycle,
                "stage": "active",
                "start_date": str(date.today()),
                "next_invoice_date": str(date.today()),
                "payment_status": "pending",
                "auto_debit": True,
                "cycle_amount": round(total_cycle, 2),
                "mrr": round(mrr, 2),
                "arr": round(arr, 2),
                "lines": [dict(l) for l in q["lines"]]
            }
            STATE["subscriptions"].insert(0, new_sub)

            self.send_json({
                "status": "ok",
                "subscription_id": sub_id,
                "message": f"Quotation confirmed! Recurring Subscription Contract {sub_id} activated."
            })
            return

        elif parsed.path == "/api/cron/run":
            # Simulate Odoo daily cron ir.cron
            today = date.today()
            processed_count = 0
            logs = []

            for sub in STATE["subscriptions"]:
                if sub["stage"] == "active":
                    # Due for invoice
                    inv_id = f"INV/2026/{len(STATE['invoices']) + 1:04d}"
                    inv_date = str(today)
                    amount = sub["cycle_amount"]

                    inv = {
                        "id": inv_id,
                        "subscription_id": sub["id"],
                        "partner": sub["partner"],
                        "date": inv_date,
                        "amount": amount,
                        "status": "paid",
                        "gateway_ref": f"AUTO_SIM_{inv_id.replace('/', '_')}_{today.strftime('%Y%m%d')}"
                    }
                    STATE["invoices"].insert(0, inv)

                    # Advance date
                    curr_d = date.fromisoformat(sub["next_invoice_date"])
                    if sub["billing_cycle"] == "monthly":
                        new_d = curr_d + relativedelta(months=1)
                    elif sub["billing_cycle"] == "quarterly":
                        new_d = curr_d + relativedelta(months=3)
                    else:
                        new_d = curr_d + relativedelta(years=1)

                    sub["next_invoice_date"] = str(new_d)
                    sub["payment_status"] = "paid"
                    processed_count += 1
                    logs.append(f"[CRON SUCCESS] Contract {sub['id']} ({sub['partner']}): Created {inv_id} for ${amount:,.2f}. Advanced billing date to {new_d}.")

            if not logs:
                logs.append("[CRON IDLE] No contracts due for recurring invoice generation today.")

            STATE["cron_logs"].extend(logs)
            self.send_json({"status": "ok", "processed": processed_count, "logs": logs})
            return

        elif parsed.path == "/api/subscription/toggle-pause":
            sub_id = payload.get("id")
            for sub in STATE["subscriptions"]:
                if sub["id"] == sub_id:
                    if sub["stage"] == "active":
                        sub["stage"] = "paused"
                        msg = f"Subscription {sub_id} put on hold."
                    elif sub["stage"] == "paused":
                        sub["stage"] = "active"
                        msg = f"Subscription {sub_id} resumed."
                    self.send_json({"status": "ok", "message": msg, "stage": sub["stage"]})
                    return

            self.send_json({"error": "Subscription not found"}, status=404)
            return

        self.send_json({"error": "Endpoint not found"}, status=404)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"============================================================")
    print(f"  Odoo 17 Enterprise Sales & Subscriptions Interactive Demo")
    print(f"  Live UI Server listening on http://127.0.0.1:{PORT}")
    print(f"============================================================")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), OdooSimulatorHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
