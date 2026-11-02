import paramiko
import base64

SCRIPT_CONTENT = """#!/usr/bin/env bash
set -e

# Asegurar que dropbear este disponible
if ! command -v dropbear >/dev/null 2>&1; then
    sudo apt-get update && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y dropbear
fi

# Asegurar llaves de host
sudo mkdir -p /etc/dropbear
if [ ! -f /etc/dropbear/dropbear_ed25519_host_key ]; then
    sudo dropbearkey -t ed25519 -f /etc/dropbear/dropbear_ed25519_host_key
fi
if [ ! -f /etc/dropbear/dropbear_rsa_host_key ]; then
    sudo dropbearkey -t rsa -f /etc/dropbear/dropbear_rsa_host_key
fi

# Configurar contrasena de root y kasm-user
echo "root:KaliPass2026!" | sudo chpasswd
echo "kasm-user:KaliPass2026!" | sudo chpasswd

echo "[+] Iniciando servicio SSH (Dropbear) en puerto 22..."
sudo /usr/sbin/dropbear -R -p 22

# Iniciar Caido Proxy en puerto 8080 si esta instalado
if command -v caido-cli >/dev/null 2>&1; then
    mkdir -p /home/kasm_user/data/caido
    pkill -f "caido-cli" || true
    echo "[+] Iniciando Caido Proxy en puerto 8080..."
    nohup /usr/bin/caido-cli --listen 0.0.0.0:8080 --no-open --data-path /home/kasm_user/data/caido > /tmp/caido.log 2>&1 &
fi
"""

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.1.100", 22, "admin", os.environ.get("ADMIN_PASS", ""))
    
    b64 = base64.b64encode(SCRIPT_CONTENT.encode("utf-8")).decode("ascii")
    remote_cmd = (
        f"echo os.environ.get("ADMIN_PASS", "") | sudo -S bash -c '"
        f"echo \"{b64}\" | base64 -d > /volume1/docker/kali/custom_startup.sh && "
        f"chmod 755 /volume1/docker/kali/custom_startup.sh && "
        f"chown 1000:users /volume1/docker/kali/custom_startup.sh'"
    )
    stdin, stdout, stderr = c.exec_command(remote_cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("STDOUT:", out)
    print("STDERR:", err)
    
    # Verificar
    _, stdout, _ = c.exec_command("ls -la /volume1/docker/kali/custom_startup.sh")
    print("Verificacion:", stdout.read().decode())
    c.close()

if __name__ == "__main__":
    main()
