#!/usr/bin/env bash
# Prepare an AlmaLinux 9 VPS for Dokploy and close the dashboard port. DRY RUN by default:
# it prints every command; add --apply to run them. Run on the VPS as root.
#
# Why this script exists: Dokploy's documented tested OS list does not include AlmaLinux
# or Rocky, and it says nothing about SELinux or firewalld. Everything marked CHECK below
# is a point where the installed behaviour must be verified (runbook S5) before trusting it.
#
# The thing that matters most: the Dokploy dashboard has been reported listening on
# 0.0.0.0:3000 even behind Traefik/HTTPS (Dokploy issue #2661). Docker-published ports
# bypass firewalld's normal zone rules, so closing it needs the DOCKER-USER chain AND the
# hosting provider's firewall. The final step proves it from OUTSIDE.
set -euo pipefail

APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
run() { echo "+ $*"; [ "$APPLY" -eq 1 ] && eval "$*"; }

grep -q 'AlmaLinux' /etc/os-release || { echo "not AlmaLinux; read this script before using it elsewhere"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }

echo "== 1. base system =="
run "dnf -y update"
run "dnf -y install firewalld iptables-services curl ca-certificates"
run "systemctl enable --now firewalld"

echo "== 2. Docker CE (Dokploy's installer may not recognise AlmaLinux; CHECK) =="
run "dnf -y install dnf-plugins-core"
run "dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo"
run "dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin"
run "systemctl enable --now docker"

echo "== 3. SELinux stays ENFORCING (CHECK: if Traefik or builds fail with AVC denials, add a narrow policy; do not disable) =="
run "getenforce"

echo "== 4. firewalld: only SSH, HTTP, HTTPS from outside; 3000 is NOT opened =="
run "firewall-cmd --permanent --add-service=ssh --add-service=http --add-service=https"
run "firewall-cmd --permanent --remove-port=3000/tcp || true"
run "firewall-cmd --reload"

echo "== 5. DOCKER-USER: drop external traffic to the dashboard port (Docker bypasses zone rules) =="
echo "   Adjust EXT_IF to the public interface. CHECK that this survives a reboot and a docker restart."
EXT_IF="${EXT_IF:-eth0}"
run "iptables -I DOCKER-USER -i $EXT_IF -p tcp --dport 3000 -j DROP"
run "service iptables save"

echo "== 6. install Dokploy (official script; CHECK its output for OS detection errors) =="
run "curl -sSL https://dokploy.com/install.sh | sh"

echo "== 7. after install, in the Dokploy UI (over the HTTPS domain, not :3000) =="
cat <<'TXT'
   - create the project named exactly: previews   (agents deploy only into this project)
   - create an API key for the office; if Dokploy offers scoped keys, limit it to the previews project
   - enable 2FA on the admin account; no other users
   - set the wildcard DNS record for DOKPLOY_PREVIEW_DOMAIN to this server
TXT

echo "== 8. PROOF, run from a machine OUTSIDE this server (your laptop on another network) =="
cat <<'TXT'
   curl -m 8 -sS http://SERVER_PUBLIC_IP:3000 && echo "STILL OPEN - fix before connecting any agent" || echo "closed - good"
   nmap -Pn -p 22,80,443,2377,3000,4789,7946 SERVER_PUBLIC_IP     # only 22, 80, 443 may be open
TXT
[ "$APPLY" -eq 1 ] || echo; echo "(dry run: nothing was changed; re-run with --apply)"
