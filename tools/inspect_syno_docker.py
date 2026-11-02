import paramiko
import json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.100', 22, os.environ.get("ADMIN_USER", "admin"), os.environ.get("SYNO_PASS", ""), timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f'echo "" | sudo -S {cmd}')
    return stdout.read().decode('utf-8', errors='replace').strip()

DOCKER = "/var/packages/ContainerManager/target/usr/bin/docker"
cmd = f"{DOCKER} ps --format '{{{{json .}}}}'"
out = run(cmd)
for line in out.splitlines():
    if not line.strip().startswith('{'):
        continue
    try:
        c = json.loads(line.strip())
        name = c.get('Names')
        image = c.get('Image')
        ports = c.get('Ports')
        status = c.get('Status')
        print(f"Container: {name:<20} | Image: {image:<30} | Ports: {ports}")
    except Exception as e:
        print("Error parsing line:", e)

print("\n=== DOCKER INSPECT SECURITY DETAILS ===")
# Inspect portainer and sshwifty specifically for volumes / privileges
for name in ["portainer", "sshwifty_web", "n8n", "radarr", "Pi-Hole", "Obsidian"]:
    insp = run(f"{DOCKER} inspect {name}")
    try:
        data = json.loads(insp)[0]
        hc = data.get("HostConfig", {})
        binds = hc.get("Binds", [])
        priv = hc.get("Privileged", False)
        net_mode = hc.get("NetworkMode", "")
        restart = hc.get("RestartPolicy", {}).get("Name", "")
        print(f"\n[{name}] Privileged: {priv} | NetMode: {net_mode} | Restart: {restart}")
        print(f"  Binds: {binds}")
    except Exception as e:
        print(f"Error inspecting {name}: {e}")

client.close()
