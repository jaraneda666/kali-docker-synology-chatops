#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: kali_idle_watchdog.py

## Metadata
- Nombre: kali_idle_watchdog.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-12
- Descripción: Monitor de inactividad remoto/local para Kali Linux en Synology DSM. Monitorea sockets establecidos y tareas activas, apagando el contenedor tras 30 minutos de inactividad.
- Parámetros: --host, --port, --user, --password, --timeout (minutos, default: 30), --daemon, --check-once
- Dependencias: paramiko, argparse, requests

## Uso
python tools/kali_idle_watchdog.py --check-once
python tools/kali_idle_watchdog.py --daemon
"""

import os
import sys
import time
import argparse
import paramiko
import requests

DEFAULT_HOST = os.environ.get("SYNO_HOST", "192.168.1.100")
DEFAULT_PORT = int(os.environ.get("SYNO_PORT", "22"))
DEFAULT_USER = os.environ.get("SYNO_USER", "admin")
DEFAULT_PASS = os.environ.get("SYNO_PASS", "")
CONTAINER_NAME = "kali_linux"
CONTAINER_TTY = "kali_ttyd"
DOCKER_BIN = "/var/packages/ContainerManager/target/usr/bin/docker"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")


def get_ssh_client(host, port, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=user, password=password, timeout=10, look_for_keys=False)
    return client


def run_command(client, password, cmd):
    sudo_cmd = f"echo '{password}' | sudo -S {cmd}"
    stdin, stdout, stderr = client.exec_command(sudo_cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    return out


def send_telegram_alert(text):
    if BOT_TOKEN and ALLOWED_USER_ID:
        try:
            payload = {
                "chat_id": ALLOWED_USER_ID,
                "text": text,
                "parse_mode": "Markdown"
            }
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=10)
        except Exception:
            pass


def check_and_evaluate(client, password, timeout_minutes=30):
    # 1. Comprobar si el contenedor está corriendo
    is_running_cmd = f"{DOCKER_BIN} inspect -f '{{{{.State.Running}}}}' {CONTAINER_NAME}"
    out = run_command(client, password, is_running_cmd)
    if "true" not in out.lower():
        return False, "Contenedor no está en ejecución. Cómputo ya liberado."

    # 2. Comprobar sockets TCP activos
    # - En kali_linux (6901, 22, 8080, 5000, 8888)
    ss_cmd = f"{DOCKER_BIN} exec {CONTAINER_NAME} ss -t -H state established '( sport = :6901 or sport = :22 or sport = :8080 or sport = :5000 or sport = :8888 )'"
    ss_out = run_command(client, password, ss_cmd)
    conns_main = len([line for line in ss_out.splitlines() if line.strip()])

    # - En kali_ttyd (7681 -> hex 1E01, state 01 en /proc/net/tcp)
    ttyd_cmd = f"{DOCKER_BIN} exec {CONTAINER_TTY} sh -c \"grep -c ':1E01.* 01 ' /proc/net/tcp 2>/dev/null || echo 0\""
    ttyd_out = run_command(client, password, ttyd_cmd)
    try:
        conns_ttyd = int(ttyd_out.splitlines()[-1].strip())
    except Exception:
        conns_ttyd = 0

    active_conns = conns_main + conns_ttyd

    # 3. Comprobar procesos activos de pentest y sesiones de terminal interactivas (PTS)
    pgrep_cmd = f"{DOCKER_BIN} exec {CONTAINER_NAME} pgrep -f 'nmap|nikto|gobuster|sqlmap|ffuf|hydra|wpscan|python3.*pentest'"
    pgrep_out = run_command(client, password, pgrep_cmd)
    audit_procs = len([line for line in pgrep_out.splitlines() if line.strip()])

    pts_cmd = f"{DOCKER_BIN} exec {CONTAINER_NAME} sh -c \"ps -eo tty,comm 2>/dev/null | grep -E '^pts/' | wc -l || echo 0\""
    pts_out = run_command(client, password, pts_cmd)
    try:
        pts_procs = int(pts_out.splitlines()[-1].strip())
    except Exception:
        pts_procs = 0

    active_procs = audit_procs + pts_procs

    state_file = "/volume1/docker/kali/data/.watchdog_last_active"
    current_time = int(time.time())

    if active_conns > 0 or active_procs > 0:
        run_command(client, password, f"echo '{current_time}' > {state_file}")
        return True, f"Activo (Conexiones TCP: {active_conns}, Procesos: {active_procs}). Temporizador reiniciado."

    # Comprobar tiempo de inactividad
    read_state_cmd = f"cat {state_file} 2>/dev/null || echo '{current_time}'"
    last_active_str = run_command(client, password, read_state_cmd)
    try:
        last_active = int(last_active_str.splitlines()[-1].strip())
    except Exception:
        last_active = current_time

    elapsed = current_time - last_active
    limit_seconds = timeout_minutes * 60

    if elapsed >= limit_seconds:
        msg = f"Inactividad de {elapsed // 60} minutos alcanzada. Apagando {CONTAINER_NAME} y {CONTAINER_TTY}..."
        stop_cmd = f"{DOCKER_BIN} stop {CONTAINER_NAME} {CONTAINER_TTY}"
        run_command(client, password, stop_cmd)
        run_command(client, password, f"rm -f {state_file}")
        send_telegram_alert(
            f"💤 *Kali Linux — Auto-Apagado por Inactividad*\n\n"
            f"Se detectaron más de {timeout_minutes} minutos sin conexiones ni procesos en Synology NAS.\n"
            f"Contenedores `{CONTAINER_NAME}` y `{CONTAINER_TTY}` apagados para liberar RAM y CPU."
        )
        return False, msg
    else:
        remaining = (limit_seconds - elapsed) // 60
        return True, f"Inactivo desde hace {elapsed // 60} min. Faltan {remaining} min para el auto-apagado."


def main():
    parser = argparse.ArgumentParser(description="Watchdog de inactividad para Kali Linux Docker en Synology")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASS)
    parser.add_argument("--timeout", type=int, default=30, help="Tiempo de inactividad en minutos (default: 30)")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar en bucle permanente cada 5 minutos")
    parser.add_argument("--check-once", action="store_true", help="Ejecutar una sola verificación")

    args = parser.parse_args()

    client = get_ssh_client(args.host, args.port, args.user, args.password)
    try:
        if args.daemon:
            print(f"[*] Iniciando demonio Watchdog (Revisión cada 5 min, apagado a los {args.timeout} min)...")
            while True:
                is_active, status_msg = check_and_evaluate(client, args.password, args.timeout)
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {status_msg}")
                time.sleep(300)
        else:
            is_active, status_msg = check_and_evaluate(client, args.password, args.timeout)
            print(f"[*] Resultado: {status_msg}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
