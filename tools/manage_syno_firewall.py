import paramiko
import json
import sys

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.100', 22, os.environ.get("ADMIN_USER", "admin"), os.environ.get("SYNO_PASS", ""), timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f'echo "" | sudo -S {cmd}')
    return stdout.read().decode('utf-8', errors='replace').strip()

print("=== FIREWALL SCRIPTS / BINARIES ===")
print(run("ls -la /usr/syno/bin/*firewall* /usr/syno/sbin/*firewall* 2>/dev/null"))
print(run("find /usr/syno/bin/ /usr/syno/sbin/ /usr/syno/etc/rc.sysv/ -name '*firewall*' 2>/dev/null"))

print("\n=== SYSTEMD / INIT SERVICE FOR FIREWALL ===")
print(run("systemctl list-unit-files | grep -i firewall 2>/dev/null || synoservice --list | grep -i firewall 2>/dev/null"))

print("\n=== BACKUP OF FIREWALL DIRS ===")
print(run("mkdir -p /tmp/syno_firewall_bak && cp -r /usr/syno/etc/firewall.d/ /tmp/syno_firewall_bak/ && cp /etc/firewall* /tmp/syno_firewall_bak/ 2>/dev/null && ls -la /tmp/syno_firewall_bak/"))

client.close()
