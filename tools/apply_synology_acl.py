import json
import paramiko

target = "192.168.1.100"
user = os.environ.get("ADMIN_USER", "admin")
pwd = os.environ.get("SYNO_PASS", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(target, 22, user, pwd, timeout=10)

def run_sudo(cmd):
    stdin, stdout, stderr = client.exec_command(f"echo {pwd} | sudo -S {cmd}")
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return code, out, err

def write_remote_file(remote_path, content_bytes):
    stdin, stdout, stderr = client.exec_command(f"cat > {remote_path}")
    stdin.write(content_bytes)
    stdin.channel.shutdown_write()
    code = stdout.channel.recv_exit_status()
    return code

try:
    print("=== PASO 1: RESPALDO DE SEGURIDAD EN SYNOLOGY ===")
    code, out, err = run_sudo("cp -f /usr/syno/etc/www/AccessControl.json /usr/syno/etc/www/AccessControl.json.bak && cp -f /usr/syno/etc/www/ReverseProxy.json /usr/syno/etc/www/ReverseProxy.json.bak")
    print(f"Respaldo: exit code {code}")

    print("\n=== PASO 2: LEER Y MODIFICAR AccessControl.json ===")
    _, out, _ = run_sudo("cat /usr/syno/etc/www/AccessControl.json")
    ac_data = json.loads(out)

    acl_id = "daf80561-c4c6-4b03-8bcc-191d9e9fc374"
    if acl_id in ac_data:
        ac_data[acl_id]["name"] = "LAN_y_VPN"
        ac_data[acl_id]["rules"] = [
            {"access": True, "address": "192.168.1.0/24"},
            {"access": True, "address": "10.8.0.0/24"},
            {"access": True, "address": "127.0.0.1"},
            {"access": False, "address": ""}
        ]
        print(f"Reglas actualizadas en perfil '{ac_data[acl_id]['name']}':")
        for r in ac_data[acl_id]["rules"]:
            print(f"  - access: {r['access']}, address: '{r['address']}'")

    print("\n=== PASO 3: LEER Y MODIFICAR ReverseProxy.json ===")
    _, out, _ = run_sudo("cat /usr/syno/etc/www/ReverseProxy.json")
    rp_data = json.loads(out)

    target_services = [
        "Pihole", "AdGuard", "Sshwifty", "NetData", "Portainer",
        "Router", "Ap1Piso", "Ap2Piso", "Unifi", "zabbix"
    ]

    for k, v in rp_data.items():
        if isinstance(v, dict):
            desc = v.get("description", "")
            if desc in target_services:
                v["frontend"]["acl"] = acl_id
                print(f"ACL asignada a: {desc:12} -> {v['frontend']['fqdn']}")

    # Escribir archivos temporales en /tmp via stdin stream
    ac_bytes = json.dumps(ac_data, indent=4).encode('utf-8')
    rp_bytes = json.dumps(rp_data, indent=4).encode('utf-8')

    write_remote_file("/tmp/AccessControl.json.new", ac_bytes)
    write_remote_file("/tmp/ReverseProxy.json.new", rp_bytes)

    # Reemplazar con sudo
    code, _, _ = run_sudo("cp /tmp/AccessControl.json.new /usr/syno/etc/www/AccessControl.json && cp /tmp/ReverseProxy.json.new /usr/syno/etc/www/ReverseProxy.json && chmod 644 /usr/syno/etc/www/AccessControl.json /usr/syno/etc/www/ReverseProxy.json")
    print(f"\nCopia a /usr/syno/etc/www: exit code {code}")

    print("\n=== PASO 4: REGENERAR CONFIGURACION NGINX CON SYNOW3TOOL ===")
    code, out, err = run_sudo("/usr/syno/bin/synow3tool --gen-all")
    print(f"synow3tool gen-all: exit code {code}")
    print(out)

    print("\n=== PASO 5: VALIDAR NGINX Y RECARGAR ===")
    code, out, err = run_sudo("nginx -t")
    print(f"nginx -t: exit code {code}")
    print(err)

    if code == 0:
        code_hup, out_hup, _ = run_sudo("/usr/syno/bin/synow3tool --deploy-hup")
        print(f"synow3tool deploy-hup: exit code {code_hup}")
    else:
        print("ERROR EN TEST NGINX! Restaurando archivos de respaldo...")
        run_sudo("cp -f /usr/syno/etc/www/AccessControl.json.bak /usr/syno/etc/www/AccessControl.json && cp -f /usr/syno/etc/www/ReverseProxy.json.bak /usr/syno/etc/www/ReverseProxy.json")
        run_sudo("/usr/syno/bin/synow3tool --gen-all && /usr/syno/bin/synow3tool --deploy-hup")

    print("\n=== PASO 6: VERIFICAR ARCHIVO .ACL GENERADO EN NGINX ===")
    code, out, _ = run_sudo(f"cat /etc/nginx/conf.d/.acl.{acl_id}.conf 2>/dev/null || cat /usr/local/etc/nginx/conf.d/.acl.{acl_id}.conf 2>/dev/null")
    print(out)

finally:
    client.close()
