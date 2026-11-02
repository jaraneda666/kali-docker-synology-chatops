#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: deploy_kali_compose.py

## Metadata
- Nombre: deploy_kali_compose.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-12
- Descripción: Despliega y sincroniza docker-compose.yml hacia Synology DSM y gestiona el ciclo de vida de los contenedores de Kali Linux.
- Parámetros: --action (deploy|up|down|pull|status), --file (ruta a docker-compose.yml local)
- Dependencias: paramiko, argparse
"""

import argparse
import base64
import os
import sys
import paramiko

DEFAULT_HOST = os.environ.get("SYNO_HOST", "192.168.1.100")
DEFAULT_PORT = int(os.environ.get("SYNO_PORT", "22"))
DEFAULT_USER = os.environ.get("SYNO_USER", os.environ.get("ADMIN_USER", "admin"))
DEFAULT_PASS = os.environ.get("SYNO_PASS", "")
REMOTE_DIR = "/volume1/docker/kali"
REMOTE_COMPOSE = f"{REMOTE_DIR}/docker-compose.yml"
DOCKER_BIN = "/var/packages/ContainerManager/target/usr/bin/docker"


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
    return out, err


def action_deploy_file(client, password, local_file):
    print(f"[*] Sincronizando '{local_file}' hacia '{REMOTE_COMPOSE}'...")
    with open(local_file, "rb") as f:
        b64_content = base64.b64encode(f.read()).decode("ascii")

    # Escribir en remoto decodificando base64
    remote_write_cmd = f"bash -c 'echo \"{b64_content}\" | base64 -d > {REMOTE_COMPOSE} && chown {DEFAULT_USER}:users {REMOTE_COMPOSE} && chmod 644 {REMOTE_COMPOSE}'"
    out, err = sudo_exec(client, password, remote_write_cmd)

    # Verificar
    chk_out, _ = sudo_exec(client, password, f"ls -la {REMOTE_COMPOSE}")
    print(f"[+] Archivo verificado en Synology: {chk_out}")


def action_up(client, password):
    print(f"[*] Iniciando servicios con Docker Compose en {REMOTE_DIR}...")
    cmd = f"bash -c 'cd {REMOTE_DIR} && {DOCKER_BIN} compose up -d'"
    out, err = sudo_exec(client, password, cmd)
    print(out)
    if err and "sudo" not in err:
        print(f"STDERR: {err}")


def action_down(client, password):
    print(f"[*] Deteniendo servicios con Docker Compose en {REMOTE_DIR}...")
    cmd = f"bash -c 'cd {REMOTE_DIR} && {DOCKER_BIN} compose down'"
    out, err = sudo_exec(client, password, cmd)
    print(out)


def action_pull(client, password):
    print(f"[*] Descargando imágenes actualizadas de Kali Linux en Synology...")
    cmd = f"bash -c 'cd {REMOTE_DIR} && {DOCKER_BIN} compose pull'"
    out, err = sudo_exec(client, password, cmd)
    print(out)


def action_status(client, password):
    print(f"[*] Estado de contenedores en Synology:")
    cmd = f"{DOCKER_BIN} ps -a --filter name=kali"
    out, _ = sudo_exec(client, password, cmd)
    print(out)


def main():
    parser = argparse.ArgumentParser(description="Despliegue de Docker Compose en Synology")
    parser.add_argument("--action", choices=["deploy", "pull", "up", "down", "status"], default="status")
    parser.add_argument("--file", default="", help="Ruta al archivo docker-compose.yml local")
    args = parser.parse_args()

    client = get_client(DEFAULT_HOST, DEFAULT_PORT, DEFAULT_USER, DEFAULT_PASS)
    try:
        if args.action == "deploy":
            if not args.file:
                print("[-] Error: debe especificar --file con la ruta al archivo compose local")
                sys.exit(1)
            action_deploy_file(client, DEFAULT_PASS, args.file)
        elif args.action == "pull":
            action_pull(client, DEFAULT_PASS)
        elif args.action == "up":
            action_up(client, DEFAULT_PASS)
        elif args.action == "down":
            action_down(client, DEFAULT_PASS)
        elif args.action == "status":
            action_status(client, DEFAULT_PASS)
    finally:
        client.close()


if __name__ == "__main__":
    main()
