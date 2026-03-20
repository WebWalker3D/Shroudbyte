#!/bin/sh
# Blade DNS Server — one-shot deployment script for pfSense 2.8.x (FreeBSD 15)
#
# Usage (run ON the pfSense box):
#   sh deploy.sh
#
# Or remotely:
#   ssh admin@pfsense "sh -s" < deploy.sh
#
# What this does:
#   1. Creates /usr/local/etc/blade_dns/ directory
#   2. Generates a self-signed TLS cert (valid 10 years)
#   3. Generates a shared HMAC secret
#   4. Copies blade_dns_server.py into place
#   5. Creates an rc.d service script so it starts on boot
#   6. Starts the service
#   7. Opens port 8853 in pf firewall (if not already open)

set -e

INSTALL_DIR="/usr/local/etc/blade_dns"
SECRET_FILE="/usr/local/etc/blade_dns.key"
CERT_FILE="${INSTALL_DIR}/cert.pem"
KEY_FILE="${INSTALL_DIR}/key.pem"
SERVER_SCRIPT="${INSTALL_DIR}/blade_dns_server.py"
RC_SCRIPT="/usr/local/etc/rc.d/blade_dns"
PORT=8853

echo "=== Blade DNS Server Deployment ==="
echo ""

# 1. Create directory
echo "[1/7] Creating ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

# 2. Generate self-signed cert
if [ -f "${CERT_FILE}" ] && [ -f "${KEY_FILE}" ]; then
    echo "[2/7] TLS cert already exists, skipping..."
else
    echo "[2/7] Generating self-signed TLS certificate..."
    openssl req -x509 -newkey rsa:2048 -keyout "${KEY_FILE}" -out "${CERT_FILE}" \
        -days 3650 -nodes -subj "/CN=blade-dns" 2>/dev/null
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
echo ""
echo "  *** YOUR SHARED SECRET (paste this into Blade Browser settings): ***"
echo "  $(cat ${SECRET_FILE})"
echo ""

# 4. Install server script
echo "[4/7] Installing blade_dns_server.py..."
# If this script is run via: ssh admin@pfsense "sh -s" < deploy.sh
# the server script must already be on the box. Copy it there first:
#   scp blade_dns_server.py admin@pfsense:/usr/local/etc/blade_dns/
if [ ! -f "${SERVER_SCRIPT}" ]; then
    # Check if blade_dns_server.py is in the same directory as this script
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    if [ -f "${SCRIPT_DIR}/blade_dns_server.py" ]; then
        cp "${SCRIPT_DIR}/blade_dns_server.py" "${SERVER_SCRIPT}"
    else
        echo "ERROR: ${SERVER_SCRIPT} not found."
        echo "Copy blade_dns_server.py to ${INSTALL_DIR}/ first:"
        echo "  scp blade_dns_server.py admin@pfsense:${SERVER_SCRIPT}"
        exit 1
    fi
fi
chmod 755 "${SERVER_SCRIPT}"

# 5. Create rc.d service
echo "[5/7] Creating rc.d service..."
cat > "${RC_SCRIPT}" << 'RCEOF'
#!/bin/sh

# PROVIDE: blade_dns
# REQUIRE: NETWORKING unbound
# KEYWORD: shutdown

. /etc/rc.subr

name="blade_dns"
rcvar="blade_dns_enable"
pidfile="/var/run/${name}.pid"

command="/usr/sbin/daemon"
command_args="-P ${pidfile} -r -f /usr/local/bin/python3.11 /usr/local/etc/blade_dns/blade_dns_server.py --port 8853"

load_rc_config $name
: ${blade_dns_enable:="YES"}

run_rc_command "$1"
RCEOF
chmod 755 "${RC_SCRIPT}"

# 6. Start the service
echo "[6/7] Starting blade_dns service..."
# Stop if already running
if [ -f /var/run/blade_dns.pid ] && kill -0 "$(cat /var/run/blade_dns.pid)" 2>/dev/null; then
    echo "       Stopping existing instance..."
    "${RC_SCRIPT}" stop 2>/dev/null || true
    sleep 1
fi
sysrc blade_dns_enable="YES" >/dev/null 2>&1 || true
"${RC_SCRIPT}" start

# 7. Check if port is reachable (basic test)
echo "[7/7] Verifying..."
sleep 2
if sockstat -l | grep -q ":${PORT}"; then
    echo "       Blade DNS server is listening on port ${PORT}"
else
    echo "       WARNING: Server may not be running. Check: sockstat -l | grep ${PORT}"
fi

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Server: https://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'YOUR_PFSENSE_IP'):${PORT}/blade-dns-query"
echo "Secret: $(cat ${SECRET_FILE})"
echo ""
echo "In Blade Browser settings:"
echo "  1. Enable 'Custom DNS'"
echo "  2. DNS Server URL: https://YOUR_PFSENSE_IP:${PORT}/blade-dns-query"
echo "  3. Auth Secret: $(cat ${SECRET_FILE})"
echo "  4. Restart the browser"
echo ""
echo "To check logs:  tail -f /var/log/messages | grep blade"
echo "To test:        curl -k https://localhost:${PORT}/health"
