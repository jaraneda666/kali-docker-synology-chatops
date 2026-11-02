#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: mcp_kali_server_bridge.py

## Metadata
- Nombre: mcp_kali_server_bridge.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-12
- Descripción: Puente adaptador MCP (Model Context Protocol) sobre stdio para orquestar herramientas de pentesting en Kali Linux vía Wh0am123/MCP-Kali-Server.
- Parámetros: --server (URL del backend API, por defecto http://192.168.1.150:5000)
- Dependencias: mcp (o fastmcp), requests, argparse

## Uso
python tools/global/mcp_kali_server_bridge.py --server http://192.168.1.150:5000
"""

import os
import sys
import argparse
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("mcp_kali_server_bridge")

DEFAULT_SERVER = os.environ.get("KALI_MCP_SERVER", "http://192.168.1.150:5000")

# Inicialización compatible con mcp 2.x (MCPServer) y mcp 1.x / fastmcp (FastMCP)
try:
    from mcp.server.mcpserver import MCPServer
    app = MCPServer("mcp-kali-server")
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
        app = FastMCP("mcp-kali-server")
    except ImportError:
        from fastmcp import FastMCP
        app = FastMCP("mcp-kali-server")

SERVER_URL = DEFAULT_SERVER


def ensure_kali_running() -> bool:
    """Verifica si el servidor de herramientas está activo y, si está apagado, lo enciende en Synology."""
    syno_host = os.environ.get("SYNO_HOST", "192.168.1.100")
    syno_port = int(os.environ.get("SYNO_PORT", "22"))
    syno_user = os.environ.get("SYNO_USER", os.environ.get("ADMIN_USER", "admin"))
    syno_pass = os.environ.get("SYNO_PASS", "")
    docker_bin = "/var/packages/ContainerManager/target/usr/bin/docker"

    try:
        r = requests.get(f"{SERVER_URL.rstrip('/')}/health", timeout=2)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    logger.info(f"[*] Kali MCP Server no responde en {SERVER_URL}. Activando contenedor on-demand en Synology NAS...")
    try:
        import paramiko
        import time
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(syno_host, port=syno_port, username=syno_user, password=syno_pass, timeout=8, look_for_keys=False)
        cmd = f"echo '{syno_pass}' | sudo -S {docker_bin} start kali_linux kali_ttyd"
        client.exec_command(cmd)
        client.close()

        # Esperar hasta que el backend MCP inicialice
        for _ in range(12):
            time.sleep(2)
            try:
                r = requests.get(f"{SERVER_URL.rstrip('/')}/health", timeout=2)
                if r.status_code == 200:
                    logger.info("[+] Contenedor Kali Linux encendido on-demand y respondiendo.")
                    return True
            except Exception:
                continue
    except Exception as e:
        logger.error(f"[-] Error activando contenedor on-demand: {e}")
    return False


def call_api(endpoint: str, method: str = "POST", json_data: dict = None, timeout: int = 300) -> str:
    url = f"{SERVER_URL.rstrip('/')}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=timeout)
        else:
            r = requests.post(url, json=json_data or {}, timeout=timeout)
        return r.text
    except Exception as e:
        logger.warning(f"Primer intento de conexión fallido con {url}. Intentando encender on-demand...")
        if ensure_kali_running():
            try:
                if method == "GET":
                    r = requests.get(url, timeout=timeout)
                else:
                    r = requests.post(url, json=json_data or {}, timeout=timeout)
                return r.text
            except Exception as e2:
                logger.error(f"Error tras reintento en {url}: {e2}")
                return f'{{"error": "Fallo de conexión persistente con Kali API en {url}: {str(e2)}"}}'
        logger.error(f"Error conectando con {url}: {e}")
        return f'{{"error": "Fallo de conexión con Kali API en {url}: {str(e)}"}}'


@app.tool()
def kali_health_check() -> str:
    """Verifica el estado operativo del servidor de herramientas Kali Linux."""
    return call_api("/health", method="GET", timeout=10)


@app.tool()
def kali_run_command(command: str) -> str:
    """Ejecuta un comando arbitrario de terminal dentro del contenedor Kali Linux."""
    return call_api("/api/command", json_data={"command": command}, timeout=120)


@app.tool()
def kali_nmap(target: str, scan_type: str = "-sT", ports: str = "", extra_args: str = "") -> str:
    """Ejecuta escaneo de puertos y servicios con Nmap en Kali Linux."""
    payload = {"target": target, "scan_type": scan_type}
    if ports:
        payload["ports"] = ports
    if extra_args:
        payload["extra_args"] = extra_args
    return call_api("/api/tools/nmap", json_data=payload, timeout=300)


@app.tool()
def kali_gobuster(url: str, mode: str = "dir", wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> str:
    """Ejecuta enumeración de directorios o vhosts con Gobuster."""
    payload = {"url": url, "target": url, "mode": mode, "wordlist": wordlist}
    return call_api("/api/tools/gobuster", json_data=payload, timeout=300)


@app.tool()
def kali_nikto(url: str, options: str = "") -> str:
    """Ejecuta escaneo de vulnerabilidades web con Nikto."""
    payload = {"url": url, "target": url}
    if options:
        payload["options"] = options
    return call_api("/api/tools/nikto", json_data=payload, timeout=300)


@app.tool()
def kali_sqlmap(url: str, options: str = "--batch --dbs") -> str:
    """Ejecuta auditoría automatizada de inyecciones SQL con Sqlmap (Requiere autorización previa)."""
    payload = {"url": url, "target": url, "options": options}
    return call_api("/api/tools/sqlmap", json_data=payload, timeout=300)


@app.tool()
def kali_wpscan(url: str, options: str = "--enumerate vp,u") -> str:
    """Ejecuta auditoría de seguridad sobre sitios WordPress con WPScan."""
    payload = {"url": url, "target": url, "options": options}
    return call_api("/api/tools/wpscan", json_data=payload, timeout=300)


@app.tool()
def kali_enum4linux(target: str, options: str = "-a") -> str:
    """Ejecuta enumeración de información en servicios SMB/Windows con enum4linux."""
    payload = {"target": target, "options": options}
    return call_api("/api/tools/enum4linux", json_data=payload, timeout=300)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Puente MCP para Wh0am123/MCP-Kali-Server")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="URL base del servidor Kali API")
    args, unknown = parser.parse_known_args()

    SERVER_URL = args.server
    logger.info(f"Iniciando puente MCP Kali apuntando a {SERVER_URL}")
    app.run()
