#!/bin/sh
# Shroud DNS Server — one-shot deployment script for pfSense 2.8.x (FreeBSD 15)
#
# Usage (run ON the pfSense box):
#   sh deploy.sh
#
# Or remotely:
#   ssh admin@pfsense "sh -s" < deploy.sh
#
# What this does:
#   1. Creates /usr/local/etc/shroud_dns/ directory
#   2. Generates a self-signed TLS cert (valid 10 years)
#   3. Generates a shared HMAC secret
#   4. Copies shroud_dns_server.py into place
#   5. Creates an rc.d service script so it starts on boot
#   6. Starts the service
#   7. Opens port 8853 in pf firewall (if not already open)

set -e

INSTALL_DIR="/usr/local/etc/shroud_dns"
SECRET_FILE="/usr/local/etc/shroud_dns.key"
CERT_FILE="${INSTALL_DIR}/cert.pem"
KEY_FILE="${INSTALL_DIR}/key.pem"
SERVER_SCRIPT="${INSTALL_DIR}/shroud_dns_server.py"
RC_SCRIPT="/usr/local/etc/rc.d/shroud_dns"
PORT=8853

echo "=== Shroud DNS Server Deployment ==="
echo ""

# 0. Clean up legacy Blade DNS installation if present
OLD_RC="/usr/local/etc/rc.d/blade_dns"
OLD_PID="/var/run/blade_dns.pid"
OLD_DIR="/usr/local/etc/blade_dns"
OLD_SECRET="/usr/local/etc/blade_dns.key"

if [ -f "${OLD_RC}" ] || [ -d "${OLD_DIR}" ]; then
    echo "[0/7] Removing legacy Blade DNS installation..."
    # Stop old service
    if [ -f "${OLD_PID}" ] && kill -0 "$(cat "${OLD_PID}")" 2>/dev/null; then
        "${OLD_RC}" stop 2>/dev/null || true
        sleep 1
    fi
    # Kill by name if pid stop didn't work
    pkill -f "blade_dns_server.py" 2>/dev/null || true
    # Disable old service
    sysrc -x blade_dns_enable 2>/dev/null || true
    # Remove old files
    rm -f "${OLD_RC}"
    rm -f "${OLD_PID}"
    rm -f "${OLD_SECRET}"
    rm -rf "${OLD_DIR}"
    echo "       Legacy Blade DNS removed."
fi

# 1. Create directory
echo "[1/7] Creating ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

# 2. Generate self-signed cert
if [ -f "${CERT_FILE}" ] && [ -f "${KEY_FILE}" ]; then
    echo "[2/7] TLS cert already exists, skipping..."
else
    echo "[2/7] Generating self-signed TLS certificate..."
    openssl req -x509 -newkey rsa:2048 -keyout "${KEY_FILE}" -out "${CERT_FILE}" \
        -days 3650 -nodes -subj "/CN=shroud-dns" 2>/dev/null
    chmod 600 "${KEY_FILE}"
    echo "       Cert: ${CERT_FILE}"
    echo "       Key:  ${KEY_FILE}"
fi

# 3. Generate shared secret
if [ -f "${SECRET_FILE}" ]; then
    echo "[3/7] Shared secret already exists, skipping..."
else
    echo "[3/7] Generating shared HMAC secret..."
    python3.11 -c "import secrets; print(secrets.token_hex(32))" > "${SECRET_FILE}"
    chmod 600 "${SECRET_FILE}"
fi
echo "       Secret generated (auto-fetched during browser registration)"
echo ""

# 4. Install / update server script
echo "[4/7] Installing shroud_dns_server.py..."
# If this script is run via: ssh admin@pfsense "sh -s" < deploy.sh
# the server script must already be on the box. Copy it there first:
#   scp shroud_dns_server.py admin@pfsense:/usr/local/etc/shroud_dns/
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/shroud_dns_server.py" ]; then
    cp "${SCRIPT_DIR}/shroud_dns_server.py" "${SERVER_SCRIPT}"
elif [ ! -f "${SERVER_SCRIPT}" ]; then
    echo "ERROR: ${SERVER_SCRIPT} not found."
    echo "Copy shroud_dns_server.py to ${INSTALL_DIR}/ first:"
    echo "  scp shroud_dns_server.py admin@pfsense:${SERVER_SCRIPT}"
    exit 1
fi
chmod 755 "${SERVER_SCRIPT}"

# 5. Create rc.d service
echo "[5/7] Creating rc.d service..."
cat > "${RC_SCRIPT}" << 'RCEOF'
#!/bin/sh

# PROVIDE: shroud_dns
# REQUIRE: NETWORKING unbound
# KEYWORD: shutdown

. /etc/rc.subr

name="shroud_dns"
rcvar="shroud_dns_enable"
pidfile="/var/run/${name}.pid"

command="/usr/sbin/daemon"
command_args="-P ${pidfile} -r -f /usr/local/bin/python3.11 /usr/local/etc/shroud_dns/shroud_dns_server.py --port 8853"

load_rc_config $name
: ${shroud_dns_enable:="YES"}

run_rc_command "$1"
RCEOF
chmod 755 "${RC_SCRIPT}"

# 6. Start the service
echo "[6/7] Starting shroud_dns service..."
# Stop if already running
if [ -f /var/run/shroud_dns.pid ] && kill -0 "$(cat /var/run/shroud_dns.pid)" 2>/dev/null; then
    echo "       Stopping existing instance..."
    "${RC_SCRIPT}" stop 2>/dev/null || true
    sleep 1
fi
sysrc shroud_dns_enable="YES" >/dev/null 2>&1 || true
"${RC_SCRIPT}" start

# 7. Check if port is reachable (basic test)
echo "[7/7] Verifying..."
sleep 2
if sockstat -l | grep -q ":${PORT}"; then
    echo "       Shroud DNS server is listening on port ${PORT}"
else
    echo "       WARNING: Server may not be running. Check: sockstat -l | grep ${PORT}"
fi

echo ""
echo "=== Deployment Complete ==="
echo ""
SERVER_URL="https://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'YOUR_PFSENSE_IP'):${PORT}"
echo "Server: ${SERVER_URL}"
echo ""
echo "In Shroudbyte settings (Shroud DNS section):"
echo "  1. Enter: ${SERVER_URL}"
echo "  2. Click Register"
echo "  3. Restart the browser"
echo ""
echo "To check logs:  tail -f /var/log/messages | grep shroud"
echo "To test:        curl -k https://localhost:${PORT}/health"
