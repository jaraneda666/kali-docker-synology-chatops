#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: hexstrike_mcp_bridge.py

## Metadata
- Nombre: hexstrike_mcp_bridge.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-12
- Descripción: Puente adaptador MCP (Model Context Protocol) sobre stdio para orquestar la plataforma HexStrike AI (0x4m4/hexstrike-ai) en Kali Linux.
- Parámetros: --server (URL del backend API, por defecto http://192.168.1.150:8888)
- Dependencias: mcp (o fastmcp), requests, argparse

## Uso
python tools/global/hexstrike_mcp_bridge.py --server http://192.168.1.150:8888
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
logger = logging.getLogger("hexstrike_mcp_bridge")

DEFAULT_SERVER = os.environ.get("HEXSTRIKE_SERVER", "http://192.168.1.150:8888")

# Inicialización compatible con mcp 2.x (MCPServer) y mcp 1.x / fastmcp (FastMCP)
try:
    from mcp.server.mcpserver import MCPServer
    app = MCPServer("hexstrike-ai")
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
        app = FastMCP("hexstrike-ai")
    except ImportError:
        from fastmcp import FastMCP
        app = FastMCP("hexstrike-ai")

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

    logger.info(f"[*] HexStrike Server no responde en {SERVER_URL}. Activando contenedor on-demand en Synology NAS...")
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
                return f'{{"error": "Fallo de conexión persistente con HexStrike API en {url}: {str(e2)}"}}'
        logger.error(f"Error conectando con {url}: {e}")
        return f'{{"error": "Fallo de conexión con HexStrike API en {url}: {str(e)}"}}'


@app.tool()
def hexstrike_health_check() -> str:
    """Verifica el estado operativo y telemetría de herramientas de HexStrike AI."""
    return call_api("/health", method="GET", timeout=10)


@app.tool()
def hexstrike_analyze_target(target: str, target_type: str = "web") -> str:
    """Analiza la superficie de ataque inicial y perfil de riesgo de un objetivo con HexStrike."""
    return call_api("/api/intelligence/analyze-target", json_data={"target": target, "target_type": target_type}, timeout=60)


@app.tool()
def hexstrike_select_tools(target: str, objective: str = "full_audit") -> str:
    """Recomienda y selecciona el arsenal óptimo de herramientas según el perfil del objetivo."""
    return call_api("/api/intelligence/select-tools", json_data={"target": target, "objective": objective}, timeout=30)


@app.tool()
def hexstrike_smart_scan(target: str, intensity: str = "standard") -> str:
    """Ejecuta escaneo inteligente multivectorial en el objetivo utilizando herramientas disponibles."""
    return call_api("/api/intelligence/smart-scan", json_data={"target": target, "intensity": intensity}, timeout=300)


@app.tool()
def hexstrike_technology_detection(target: str) -> str:
    """Detecta tecnologías web, frameworks, servidores y CMS subyacentes en el objetivo."""
    return call_api("/api/intelligence/technology-detection", json_data={"target": target}, timeout=60)


@app.tool()
def hexstrike_recon_workflow(target: str) -> str:
    """Ejecuta el pipeline de reconocimiento automatizado de bug bounty en el objetivo."""
    return call_api("/api/bugbounty/reconnaissance-workflow", json_data={"target": target}, timeout=300)


@app.tool()
def hexstrike_vuln_hunting_workflow(target: str) -> str:
    """Ejecuta el flujo automatizado de búsqueda de vulnerabilidades web con HexStrike."""
    return call_api("/api/bugbounty/vulnerability-hunting-workflow", json_data={"target": target}, timeout=300)


@app.tool()
def hexstrike_run_command(command: str) -> str:
    """Ejecuta un comando arbitrario gestionado a través del pipeline de procesos de HexStrike."""
    return call_api("/api/command", json_data={"command": command}, timeout=120)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Puente MCP para 0x4m4/hexstrike-ai")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="URL base del servidor HexStrike API")
    args, unknown = parser.parse_known_args()

    SERVER_URL = args.server
    logger.info(f"Iniciando puente MCP HexStrike apuntando a {SERVER_URL}")
    app.run()
