#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================================="
echo "  TalentPulse & Odoo Enterprise Stack Manager"
echo "=========================================================="

case "$1" in
    start)
        echo "[+] Building and starting Odoo 17 & PostgreSQL 16..."
        docker compose up -d --build
        echo "[+] Waiting for services to become healthy..."
        docker compose ps
        echo ""
        echo "[✔] Odoo Web is accessible at: http://localhost:8069"
        ;;
    stop)
        echo "[+] Stopping Odoo stack..."
        docker compose down
        ;;
    logs)
        docker compose logs -f odoo
        ;;
    update-addon)
        MODULE_NAME=${2:-smart_sales_recurring_billing}
        DB_NAME=${3:-odoo_prod}
        echo "[+] Updating module '$MODULE_NAME' on database '$DB_NAME'..."
        docker compose exec odoo odoo -u "$MODULE_NAME" -d "$DB_NAME" --stop-after-init
        docker compose restart odoo
        ;;
    test)
        echo "[+] Running automated test suite inside Odoo container..."
        docker compose exec odoo odoo --test-enable -i smart_sales_recurring_billing -d test_db --stop-after-init
        ;;
    *)
        echo "Usage: $0 {start|stop|logs|update-addon [module_name] [db_name]|test}"
        exit 1
        ;;
esac
