#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: manage_kali_mcp.py

## Metadata
- Nombre: manage_kali_mcp.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-12
- Descripción: Administrador de ciclo de vida, verificación de estado de red, monitoreo de procesos y pruebas de salud para los servidores MCP de Kali Linux (Wh0am123/MCP-Kali-Server y 0x4m4/hexstrike-ai).
- Parámetros: --action (status|start|stop|restart|logs|test), --host, --user, --password
- Dependencias: requests, paramiko, argparse, json

## Uso
python tools/global/manage_kali_mcp.py --action status
python tools/global/manage_kali_mcp.py --action restart
python tools/global/manage_kali_mcp.py --action test
"""

import os
import sys
import argparse
import json
import requests
import paramiko

DEFAULT_SYNO_HOST = os.environ.get("SYNO_HOST", "192.168.1.100")
DEFAULT_SYNO_PORT = int(os.environ.get("SYNO_PORT", "22"))
DEFAULT_SYNO_USER = os.environ.get("SYNO_USER", os.environ.get("ADMIN_USER", "admin"))
DEFAULT_SYNO_PASS = os.environ.get("SYNO_PASS", "")

KALI_IP = os.environ.get("KALI_IP", "192.168.1.150")
MCP_KALI_URL = f"http://{KALI_IP}:5000"
HEXSTRIKE_URL = f"http://{KALI_IP}:8888"


def get_ssh_client(host=DEFAULT_SYNO_HOST, port=DEFAULT_SYNO_PORT, user=DEFAULT_SYNO_USER, password=DEFAULT_SYNO_PASS):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username=user, password=password, timeout=10, look_for_keys=False)
    return c


def exec_docker_kali(cmd: str):
    c = get_ssh_client()
    try:
        full_cmd = f"echo '{DEFAULT_SYNO_PASS}' | sudo -S /var/packages/ContainerManager/target/usr/bin/docker exec kali_linux bash -c \"{cmd}\""
        stdin, stdout, stderr = c.exec_command(full_cmd)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        return out, err
    finally:
        c.close()


def action_status():
    print(f"[*] Verificando estado de Servidores MCP en Kali Linux ({KALI_IP}):\n")

    # 1. MCP-Kali-Server (5000)
    try:
        r1 = requests.get(f"{MCP_KALI_URL}/health", timeout=4)
        if r1.status_code == 200:
            data = r1.json()
            tools = [k for k, v in data.get("tools_status", {}).items() if v]
            print(f"[+] MCP-Kali-Server (Puerto 5000): EN LÍNEA (Salud: {data.get('status')})")
            print(f"    Herramientas verificadas: {', '.join(tools) if tools else 'Básicas operativas'}")
        else:
            print(f"[-] MCP-Kali-Server (Puerto 5000): HTTP {r1.status_code}")
    except Exception as e:
        print(f"[-] MCP-Kali-Server (Puerto 5000): NO ACCESIBLE ({e})")

    # 2. HexStrike-AI (8888)
    try:
        r2 = requests.get(f"{HEXSTRIKE_URL}/health", timeout=4)
        if r2.status_code == 200:
            data = r2.json()
            stats = data.get("category_stats", {})
            total_avail = data.get("total_tools_available", 0)
            total_count = data.get("total_tools_count", 0)
            print(f"\n[+] HexStrike-AI (Puerto 8888): EN LÍNEA (v{data.get('version', '6.0.0')})")
            print(f"    Herramientas disponibles: {total_avail}/{total_count}")
            print(f"    Uptime: {round(data.get('uptime', 0), 1)}s | CPU: {data.get('telemetry', {}).get('system_metrics', {}).get('cpu_percent')}%")
        else:
            print(f"[-] HexStrike-AI (Puerto 8888): HTTP {r2.status_code}")
    except Exception as e:
        print(f"[-] HexStrike-AI (Puerto 8888): NO ACCESIBLE ({e})")


def action_start():
    print(f"[*] Iniciando demonios MCP dentro del contenedor Kali Linux...")
    out, err = exec_docker_kali("bash /home/kasm_user/data/start_mcp_services.sh")
    print(out)
    if err and "Password" not in err:
        print("STDERR:", err)


def action_stop():
    print(f"[*] Deteniendo demonios MCP en Kali Linux...")
    out, err = exec_docker_kali("pkill -f 'MCP-Kali-Server/server.py' || true; pkill -f 'hexstrike_server.py' || true")
    print("[+] Procesos detenidos.")


def action_restart():
    action_stop()
    action_start()


def action_logs():
    print(f"[*] Extrayendo logs de los servicios MCP...")
    out, _ = exec_docker_kali("echo '=== MCP-Kali Log ===' && tail -n 20 /tmp/mcp_kali.log && echo '=== HexStrike Log ===' && tail -n 20 /tmp/hexstrike.log")
    print(out)


def action_test():
    print(f"[*] Ejecutando prueba funcional en caliente sobre ambos servidores...")
    # Prueba MCP-Kali con nmap
    try:
        r = requests.post(f"{MCP_KALI_URL}/api/tools/nmap", json={"target": "127.0.0.1", "ports": "5000,8888", "scan_type": "-sT"}, timeout=15)
        print(f"[+] Prueba MCP-Kali (nmap localhost): HTTP {r.status_code}")
        if r.status_code == 200:
            lines = r.json().get("stdout", "").splitlines()
            for l in lines:
                if "/tcp" in l or "Nmap scan" in l:
                    print(f"    {l}")
    except Exception as e:
        print(f"[-] Fallo prueba MCP-Kali: {e}")

    # Prueba HexStrike con analyze-target
    try:
        r = requests.post(f"{HEXSTRIKE_URL}/api/intelligence/analyze-target", json={"target": "http://127.0.0.1:5000"}, timeout=15)
        print(f"\n[+] Prueba HexStrike (analyze-target): HTTP {r.status_code}")
        if r.status_code == 200:
            profile = r.json().get("target_profile", {})
            print(f"    Objetivo: {profile.get('target')}")
            print(f"    Nivel de Riesgo Inicial: {profile.get('risk_level')}")
            print(f"    Score de Superficie: {profile.get('attack_surface_score')}")
    except Exception as e:
        print(f"[-] Fallo prueba HexStrike: {e}")


def main():
    parser = argparse.ArgumentParser(description="Administrador de Servidores MCP en Kali Linux")
    parser.add_argument("--action", choices=["status", "start", "stop", "restart", "logs", "test"], default="status")
    args = parser.parse_args()

    if args.action == "status":
        action_status()
    elif args.action == "start":
        action_start()
    elif args.action == "stop":
        action_stop()
    elif args.action == "restart":
        action_restart()
    elif args.action == "logs":
        action_logs()
    elif args.action == "test":
        action_test()


if __name__ == "__main__":
    main()
