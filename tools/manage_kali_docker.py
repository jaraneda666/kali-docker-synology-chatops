#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: manage_kali_docker.py

## Metadata
- Nombre: manage_kali_docker.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-12
- Descripción: Administrador de ciclo de vida, verificación de red macvlan, auditoría y ejecución de comandos en el contenedor Kali Linux en Synology DSM.
- Parámetros: --host, --port, --user, --password, --action (status|inspect|start|stop|restart|logs|exec|test-net), --cmd
- Dependencias: paramiko, argparse, json

## Uso
python manage_kali_docker.py --action status
python manage_kali_docker.py --action exec --cmd "nmap --version"
python manage_kali_docker.py --action test-net
"""

import argparse
import json
import os
import sys
import paramiko

DEFAULT_HOST = os.environ.get("SYNO_HOST", "192.168.1.100")
DEFAULT_PORT = int(os.environ.get("SYNO_PORT", "22"))
DEFAULT_USER = os.environ.get("SYNO_USER", os.environ.get("ADMIN_USER", "admin"))
DEFAULT_PASS = os.environ.get("SYNO_PASS", "")
CONTAINER_NAME = "kali_linux"
KALI_IP = "192.168.1.150"
DOCKER_BIN = "/var/packages/ContainerManager/target/usr/bin/docker"


def get_client(host, port, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Intentar autenticación por clave o contraseña
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    if os.path.exists(key_path):
        try:
            client.connect(host, port=port, username=user, key_filename=key_path, timeout=10)
            return client
        except Exception:
            pass
    client.connect(host, port=port, username=user, password=password, timeout=10)
    return client


def run_command(client, password, cmd):
    sudo_cmd = f"echo '{password}' | sudo -S {cmd}"
    stdin, stdout, stderr = client.exec_command(sudo_cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return out, err


def action_status(client, password):
    print(f"[*] Consultando estado de contenedor '{CONTAINER_NAME}' en {DEFAULT_HOST}...")
    cmd = f"{DOCKER_BIN} ps -a --filter name={CONTAINER_NAME} --format '{{{{json .}}}}'"
    out, err = run_command(client, password, cmd)
    if not out:
        print(f"[-] Contenedor '{CONTAINER_NAME}' no encontrado en el host.")
        return
    for line in out.splitlines():
        if line.strip().startswith("{"):
            try:
                info = json.loads(line.strip())
                print(f"[+] Estado: {info.get('Status')}")
                print(f"[+] Imagen: {info.get('Image')}")
                print(f"[+] Puertos/Red: {info.get('Ports', 'N/A')}")
            except Exception as e:
                print(f"Error procesando json: {e}")


def action_inspect(client, password):
    print(f"[*] Inspeccionando configuración y redes de '{CONTAINER_NAME}'...")
    cmd = f"{DOCKER_BIN} inspect {CONTAINER_NAME}"
    out, err = run_command(client, password, cmd)
    try:
        data = json.loads(out)
        if data:
            c = data[0]
            state = c.get("State", {})
            net = c.get("NetworkSettings", {}).get("Networks", {})
            hc = c.get("HostConfig", {})
            print(f"[+] Running: {state.get('Running')} (PID: {state.get('Pid')})")
            print(f"[+] Redes asignadas: {list(net.keys())}")
            for net_name, n_info in net.items():
                print(f"    -> {net_name}: IP {n_info.get('IPAddress')} | MAC {n_info.get('MacAddress')}")
            print(f"[+] Modo Privilegiado: {hc.get('Privileged')}")
            print(f"[+] CapAdd: {hc.get('CapAdd')}")
            print(f"[+] Volúmenes/Binds: {hc.get('Binds')}")
    except Exception as e:
        print(f"[-] Error parseando inspect: {e}\nSalida cruda:\n{out}")


def action_control(client, password, operation):
    print(f"[*] Ejecutando '{operation}' sobre '{CONTAINER_NAME}'...")
    cmd = f"{DOCKER_BIN} {operation} {CONTAINER_NAME}"
    out, err = run_command(client, password, cmd)
    print(f"[+] Salida: {out if out else 'OK'}")


def action_logs(client, password):
    print(f"[*] Obteniendo últimos logs de '{CONTAINER_NAME}'...")
    cmd = f"{DOCKER_BIN} logs --tail 50 {CONTAINER_NAME}"
    out, err = run_command(client, password, cmd)
    print(out)


def action_exec(client, password, user_cmd, as_root=False):
    if not user_cmd:
        print("[-] Debe especificar un comando con --cmd")
        return
    user_flag = "-u 0 " if as_root else ""
    print(f"[*] Ejecutando en '{CONTAINER_NAME}' ({'root' if as_root else 'kasm_user'}): {user_cmd}")
    cmd = f"{DOCKER_BIN} exec {user_flag}{CONTAINER_NAME} {user_cmd}"
    out, err = run_command(client, password, cmd)
    print(f"--- STDOUT ---\n{out}")
    if err and "sudo" not in err:
        print(f"--- STDERR ---\n{err}")


def action_test_net(client, password):
    print(f"[*] Probando conectividad hacia IP de Kali ({KALI_IP}) desde Synology...")
    cmd = f"ping -c 3 -W 2 {KALI_IP}"
    out, err = run_command(client, password, cmd)
    print(out)


def main():
    parser = argparse.ArgumentParser(description="Administrador de Kali Linux Docker en Synology")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host Synology")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Puerto SSH")
    parser.add_argument("--user", default=DEFAULT_USER, help="Usuario SSH")
    parser.add_argument("--password", default=DEFAULT_PASS, help="Contraseña SSH")
    parser.add_argument("--action", choices=["status", "inspect", "start", "stop", "restart", "logs", "exec", "test-net"], default="status")
    parser.add_argument("--cmd", default="", help="Comando a ejecutar en el contenedor (para action=exec)")
    parser.add_argument("--root", action="store_true", help="Ejecutar comando como usuario root dentro del contenedor")

    args = parser.parse_args()

    try:
        client = get_client(args.host, args.port, args.user, args.password)
    except Exception as e:
        print(f"[-] Error de conexión SSH a {args.host}: {e}")
        sys.exit(1)

    try:
        if args.action == "status":
            action_status(client, args.password)
        elif args.action == "inspect":
            action_inspect(client, args.password)
        elif args.action in ["start", "stop", "restart"]:
            action_control(client, args.password, args.action)
        elif args.action == "logs":
            action_logs(client, args.password)
        elif args.action == "exec":
            action_exec(client, args.password, args.cmd, as_root=args.root)
        elif args.action == "test-net":
            action_test_net(client, args.password)
    finally:
        client.close()


if __name__ == "__main__":
    main()
