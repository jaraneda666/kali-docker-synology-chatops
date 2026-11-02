import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.100', 22, os.environ.get("ADMIN_USER", "admin"), os.environ.get("SYNO_PASS", ""), timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f'echo "" | sudo -S {cmd}')
    return stdout.read().decode('utf-8', errors='replace').strip()

print(run("grep -E '(transmission|bt|58130)' /usr/syno/etc/firewall_service_mapping_table"))
print("---")
print(run("/usr/syno/bin/synofirewall --service transmission 2>&1"))
print("---")
print(run("/usr/syno/bin/synofirewall --service bt 2>&1"))
client.close()
