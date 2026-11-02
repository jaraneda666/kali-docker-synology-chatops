#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: configure_kali_reverse_proxy.py

## Metadata
- Nombre: configure_kali_reverse_proxy.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-12
- Descripción: Configura las reglas de Proxy Reverso en Nginx de Synology DSM para Kali Linux (Web Desktop y Web Terminal) con perfiles ACL LAN_y_VPN y WebSockets.
- Parámetros: --host, --user, --password, --action (apply|remove|test)
- Dependencias: paramiko, argparse, json
"""

import argparse
import base64
import json
import os
import sys
import uuid
import paramiko

DEFAULT_HOST = os.environ.get("SYNO_HOST", "192.168.1.100")
DEFAULT_PORT = int(os.environ.get("SYNO_PORT", "22"))
DEFAULT_USER = os.environ.get("SYNO_USER", os.environ.get("ADMIN_USER", "admin"))
DEFAULT_PASS = os.environ.get("SYNO_PASS", "")
ACL_ID = "daf80561-c4c6-4b03-8bcc-191d9e9fc374"  # Perfil LAN_y_VPN


def get_client(host, port, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    if os.path.exists(key_path):
        try:
            client.connect(host, port=port, username=user, key_filename=key_path, timeout=10)
            return client
        except Exception:
            pass
    client.connect(host, port=port, username=user, password=password, timeout=10)
    return client


def sudo_exec(client, password, cmd):
    full_cmd = f"echo '{password}' | sudo -S {cmd}"
    stdin, stdout, stderr = client.exec_command(full_cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out, err


def action_apply(client, password):
    print("[*] Paso 1: Creando respaldo de ReverseProxy.json en Synology...")
    code, _, _ = sudo_exec(client, password, "cp -f /usr/syno/etc/www/ReverseProxy.json /usr/syno/etc/www/ReverseProxy.json.bak_kali")
    if code != 0:
        print("[-] Error creando respaldo en Synology")
        return False

    print("[*] Paso 2: Leyendo ReverseProxy.json existente...")
    code, out, err = sudo_exec(client, password, "cat /usr/syno/etc/www/ReverseProxy.json")
    try:
        rp_data = json.loads(out)
    except Exception as e:
        print(f"[-] Error parseando JSON: {e}")
        return False

    # Buscar si ya existen reglas de Kali para actualizarlas o crearlas
    desktop_key = None
    term_key = None

    for k, v in rp_data.items():
        if isinstance(v, dict):
            fqdn = v.get("frontend", {}).get("fqdn", "")
            if fqdn == "kali-desktop.admin.synology.me" or v.get("description") == "Kali Web Desktop":
                desktop_key = k
            elif fqdn == "kali-term.admin.synology.me" or v.get("description") == "Kali Web Terminal":
                term_key = k

    if not desktop_key:
        desktop_key = str(uuid.uuid4())
    if not term_key:
        term_key = str(uuid.uuid4())

    headers_ws = [
        {"name": "Upgrade", "value": "$http_upgrade"},
        {"name": "Connection", "value": "$connection_upgrade"}
    ]

    rp_data[desktop_key] = {
        "_key": str(uuid.uuid4()),
        "description": "Kali Web Desktop",
        "frontend": {
            "acl": ACL_ID,
            "fqdn": "kali-desktop.admin.synology.me",
            "https": {"hsts": True},
            "port": 443,
            "protocol": 1
        },
        "backend": {
            "fqdn": "172.26.0.80",
            "port": 6901,
            "protocol": 1
        },
        "customize_headers": headers_ws,
        "proxy_connect_timeout": 600,
        "proxy_read_timeout": 600,
        "proxy_send_timeout": 600,
        "proxy_http_version": 1,
        "proxy_intercept_errors": False
    }

    rp_data[term_key] = {
        "_key": str(uuid.uuid4()),
        "description": "Kali Web Terminal",
        "frontend": {
            "acl": ACL_ID,
            "fqdn": "kali-term.admin.synology.me",
            "https": {"hsts": True},
            "port": 443,
            "protocol": 1
        },
        "backend": {
            "fqdn": "172.26.0.81",
            "port": 7681,
            "protocol": 0
        },
        "customize_headers": headers_ws,
        "proxy_connect_timeout": 600,
        "proxy_read_timeout": 600,
        "proxy_send_timeout": 600,
        "proxy_http_version": 1,
        "proxy_intercept_errors": False
    }

    print("[*] Paso 3: Escribiendo configuración actualizada...")
    b64_json = base64.b64encode(json.dumps(rp_data, indent=2).encode("utf-8")).decode("ascii")
    write_cmd = f"bash -c 'echo \"{b64_json}\" | base64 -d > /usr/syno/etc/www/ReverseProxy.json && chmod 644 /usr/syno/etc/www/ReverseProxy.json'"
    code, _, _ = sudo_exec(client, password, write_cmd)

    print("[*] Paso 4: Regenerando archivos Nginx con synow3tool...")
    code, gen_out, gen_err = sudo_exec(client, password, "/usr/syno/bin/synow3tool --gen-all")
    print(gen_out)

    print("[*] Paso 5: Validando sintaxis Nginx con nginx -t...")
    code, t_out, t_err = sudo_exec(client, password, "nginx -t")
    print(f"nginx -t resultado: {t_err if t_err else t_out}")

    if code == 0:
        print("[+] Sintaxis válida. Aplicando recarga suave en caliente (deploy-hup)...")
        code_hup, _, _ = sudo_exec(client, password, "/usr/syno/bin/synow3tool --deploy-hup")
        print(f"[+] synow3tool deploy-hup exit code: {code_hup}")
        print("[+] ¡Proxy Inverso configurado exitosamente!")
        return True
    else:
        print("[-] Error de sintaxis en Nginx. Restaurando respaldo previo...")
        sudo_exec(client, password, "cp -f /usr/syno/etc/www/ReverseProxy.json.bak_kali /usr/syno/etc/www/ReverseProxy.json && /usr/syno/bin/synow3tool --gen-all && /usr/syno/bin/synow3tool --deploy-hup")
        return False


def main():
    parser = argparse.ArgumentParser(description="Configuración de Proxy Inverso para Kali Linux")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASS)
    parser.add_argument("--action", choices=["apply", "test"], default="apply")
    args = parser.parse_args()

    client = get_client(args.host, args.port, args.user, args.password)
    try:
        if args.action == "apply":
            action_apply(client, args.password)
    finally:
        client.close()


if __name__ == "__main__":
    main()
