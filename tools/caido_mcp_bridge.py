#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: caido_mcp_bridge.py

## Metadata
- Nombre: caido_mcp_bridge.py
- Versión: 1.1
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-13
- Descripción: Puente MCP con auto-encendido on-demand (Wake-on-Request) y resolución automática de token para Caido Web Security Proxy en Kali Linux sobre Synology DSM.
- Parámetros: --url (URL de la instancia Caido, default: http://192.168.1.150:8080)
- Dependencias: requests, paramiko, subprocess, json

## Uso
python tools/caido_mcp_bridge.py --url http://192.168.1.150:8080
"""

import os
import sys
import time
import json
import argparse
import logging
import subprocess
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("caido_mcp_bridge")

DEFAULT_URL = os.environ.get("CAIDO_URL", "http://192.168.1.150:8080")


def ensure_caido_running(target_url: str) -> bool:
    """Verifica si Caido responde en la URL indicada; si el contenedor está apagado, lo enciende vía SSH en Synology DSM."""
    try:
        r = requests.get(target_url, timeout=2)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    logger.info(f"[*] Caido no responde en {target_url}. Activando contenedor Kali Linux on-demand en Synology NAS...")
    syno_host = os.environ.get("SYNO_HOST", "192.168.1.100")
    syno_port = int(os.environ.get("SYNO_PORT", "22"))
    syno_user = os.environ.get("SYNO_USER", "admin")
    syno_pass = os.environ.get("SYNO_PASS", "")
    docker_bin = "/var/packages/ContainerManager/target/usr/bin/docker"

    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(syno_host, port=syno_port, username=syno_user, password=syno_pass, timeout=8, look_for_keys=False)
        cmd = f"echo '{syno_pass}' | sudo -S {docker_bin} start kali_linux kali_ttyd"
        client.exec_command(cmd)
        client.close()

        # Esperar a que Caido inicialice
        for _ in range(15):
            time.sleep(2)
            try:
                r = requests.get(target_url, timeout=2)
                if r.status_code == 200:
                    logger.info("[+] Contenedor Kali Linux encendido y Caido respondiendo en el puerto 8080.")
                    return True
            except Exception:
                continue
    except Exception as e:
        logger.error(f"[-] Error activando contenedor on-demand: {e}")

    return False


def get_access_token(target_url: str) -> str:
    """Obtiene el token de autenticación desde el entorno, archivo guardado o dinámicamente vía GraphQL."""
    # 1. Variable de entorno predefinida
    env_token = os.environ.get("CAIDO_ACCESS_TOKEN") or os.environ.get("CAIDO_PAT")
    if env_token:
        return env_token

    # 2. Archivo ~/.caido-mcp/token.json si ya fue autenticado vía device flow
    token_file = os.path.expanduser("~/.caido-mcp/token.json")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                t = data.get("access_token") or data.get("token")
                if t:
                    return t
        except Exception:
            pass

    # 3. Resolución automática directa con la instancia Caido
    try:
        q = "mutation { loginAsGuest { token { accessToken } } }"
        r = requests.post(f"{target_url.rstrip('/')}/graphql", json={"query": q}, timeout=5)
        if r.status_code == 200:
            res_data = r.json()
            tok = res_data.get("data", {}).get("loginAsGuest", {}).get("token", {}).get("accessToken")
            if tok:
                return tok
    except Exception as e:
        logger.warning(f"[-] Error resolviendo token dinámico: {e}")

    return ""


def main():
    parser = argparse.ArgumentParser(description="Puente MCP con auto-encendido para Caido Proxy")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL de la instancia de Caido")
    args, unknown = parser.parse_known_args()

    ensure_caido_running(args.url)

    # Ubicación del ejecutable MCP de Caido
    base_dir = os.path.dirname(os.path.abspath(__file__))
    win_bin = os.path.join(base_dir, "caido-mcp-server.exe")

    if not os.path.exists(win_bin):
        logger.error(f"[-] No se encontró el binario {win_bin}")
        sys.exit(1)

    cmd = [win_bin, "serve", "--url", args.url]
    if unknown:
        cmd.extend(unknown)

    env = os.environ.copy()
    token = get_access_token(args.url)
    if token:
        env["CAIDO_ACCESS_TOKEN"] = token

    # Ejecutar el servidor stdio heredando stdin, stdout y stderr
    proc = subprocess.Popen(cmd, env=env, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    try:
        sys.exit(proc.wait())
    except KeyboardInterrupt:
        proc.terminate()
        sys.exit(0)


if __name__ == "__main__":
    main()
