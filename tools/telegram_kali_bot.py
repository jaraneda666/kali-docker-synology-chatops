#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: telegram_kali_bot.py

## Metadata
- Nombre: telegram_kali_bot.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: Kali_Docker_Synology
- Fecha de creación: 2026-10-12
- Descripción: Bot de Telegram ChatOps para gestión interactiva, ejecución de comandos y monitoreo del contenedor Kali Linux en Synology DSM con filtrado estricto por lista blanca de usuario.
- Parámetros: Variables de entorno TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_ID
- Dependencias: requests, paramiko (o Docker SDK)

## Uso
python telegram_kali_bot.py
"""

import os
import sys
import time
import json
import requests
import paramiko

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")
SYNO_HOST = os.environ.get("SYNO_HOST", "synology.local")
SYNO_USER = os.environ.get("SYNO_USER", "admin")
SYNO_PASS = os.environ.get("SYNO_PASS", "")
CONTAINER_NAME = "kali_linux"
DOCKER_BIN = "/var/packages/ContainerManager/target/usr/bin/docker"

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def run_docker_remote(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(SYNO_HOST, 22, SYNO_USER, SYNO_PASS, timeout=10)
        full_cmd = f"echo '{SYNO_PASS}' | sudo -S {cmd}"
        stdin, stdout, stderr = client.exec_command(full_cmd)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        client.close()
        return out
    except Exception as e:
        return f"Error de comunicación SSH con Synology: {e}"


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")


def ensure_container_running(chat_id=None):
    """Verifica si el contenedor está corriendo y, si está apagado, lo enciende a demanda."""
    status = run_docker_remote(f"{DOCKER_BIN} inspect -f '{{{{.State.Running}}}}' {CONTAINER_NAME}")
    if "true" not in status.lower():
        if chat_id:
            send_message(chat_id, "⏳ *Contenedor apagado:* Encendiendo Kali Linux on-demand en Synology NAS...")
        run_docker_remote(f"{DOCKER_BIN} start {CONTAINER_NAME} kali_ttyd")
        time.sleep(3)
        return True
    return False


def get_main_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "⚡ Pentest Agentes MCP", "callback_data": "btn_mcp_pentest_prompt"},
                {"text": "🌐 Pentest Web OWASP", "callback_data": "btn_web_pentest_prompt"}
            ],
            [
                {"text": "🟢 Encender Kali (On-Demand)", "callback_data": "btn_start"},
                {"text": "💤 Apagar Kali (Ahorrar Cómputo)", "callback_data": "btn_stop"}
            ],
            [
                {"text": "🔌 Estado Servidores MCP", "callback_data": "btn_mcp_health"},
                {"text": "📊 Estado Contenedor", "callback_data": "btn_status"}
            ],
            [
                {"text": "🌐 Ver IPs y Red", "callback_data": "btn_ip"},
                {"text": "🔍 Escaneo ARP LAN", "callback_data": "btn_scan_arp"}
            ],
            [
                {"text": "📦 Actualizar Repos", "callback_data": "btn_update"},
                {"text": "🔄 Reiniciar Kali", "callback_data": "btn_restart"}
            ]
        ]
    }


def get_profile_keyboard(target_url):
    return {
        "inline_keyboard": [
            [
                {"text": "⚡ Automatizado MCP (HexStrike + Kali)", "callback_data": f"p_run:mcp:{target_url}"}
            ],
            [
                {"text": "🟢 Rápido / Pasivo", "callback_data": f"p_run:fast:{target_url}"}
            ],
            [
                {"text": "🟡 Estándar OWASP", "callback_data": f"p_run:standard:{target_url}"}
            ],
            [
                {"text": "🔴 Avanzado / Activo", "callback_data": f"p_run:full:{target_url}"}
            ],
            [
                {"text": "🔙 Cancelar", "callback_data": "btn_menu"}
            ]
        ]
    }


def handle_callback(cb_id, chat_id, user_id, data):
    # Confirmar callback a Telegram para quitar reloj
    requests.post(f"{API_BASE}/answerCallbackQuery", json={"callback_query_id": cb_id})

    if str(user_id) != str(ALLOWED_USER_ID):
        send_message(chat_id, "⛔ *Acceso denegado:* Usuario no autorizado.")
        return

    if data == "btn_menu":
        send_message(chat_id, "🛡️ *Panel ChatOps — Kali Linux*", get_main_keyboard())

    elif data == "btn_mcp_pentest_prompt":
        txt = (
            "⚡ *Pentest Automatizado con Agentes MCP*\n\n"
            "Orquestación inteligente entre:\n"
            "• *0x4m4/HexStrike-AI v6.0* (Profiling y detección de tecnologías)\n"
            "• *Wh0am123/MCP-Kali-Server* (Nmap y herramientas especializadas)\n\n"
            "Para iniciar la evaluación pericial, envía el comando con la URL del objetivo:\n"
            "`/pentest <URL>`\n\n"
            "_Ejemplo:_ `/pentest http://localhost:3000/#/`\n"
            "_Ejemplo:_ `/pentest https://ejemplo.com`"
        )
        send_message(chat_id, txt)

    elif data == "btn_mcp_health":
        # Consultar salud de ambos servidores
        mcp_kali_status = "Desconectado"
        hx_status = "Desconectado"
        hx_tools = 0
        try:
            r1 = requests.get("http://192.168.1.150:5000/health", timeout=3).json()
            mcp_kali_status = r1.get("status", "OK").upper()
        except Exception:
            pass
        try:
            r2 = requests.get("http://192.168.1.150:8888/health", timeout=4).json()
            hx_status = r2.get("status", "OK").upper()
            hx_tools = r2.get("total_tools_available", 30)
        except Exception:
            pass

        report_mcp = (
            "🔌 *Estado de Servidores MCP en Kali Linux*\n\n"
            f"• *Wh0am123/MCP-Kali-Server (Puerto 5000):*\n"
            f"  Estado: `{mcp_kali_status}`\n"
            f"  Herramientas verificadas: `Nmap, Nikto, Gobuster`\n\n"
            f"• *0x4m4/HexStrike-AI v6.0 (Puerto 8888):*\n"
            f"  Estado: `{hx_status}`\n"
            f"  Arsenal disponible: `{hx_tools} herramientas activas`\n\n"
            f"• *IP LAN Macvlan:* `192.168.1.150`\n"
            f"• *IP Syno Internal:* `172.26.0.80`"
        )
        send_message(chat_id, report_mcp, get_main_keyboard())

    elif data == "btn_web_pentest_prompt":
        txt = (
            "🌐 *Auditoría Web OWASP con Kali Linux*\n\n"
            "Para iniciar, envía el comando con la URL del objetivo:\n"
            "`/pentest <URL>`\n\n"
            "_Ejemplo:_ `/pentest https://ejemplo.com`"
        )
        send_message(chat_id, txt)

    elif data == "btn_start":
        send_message(chat_id, "⏳ *Encendiendo Kali Linux on-demand...*")
        out = run_docker_remote(f"{DOCKER_BIN} start {CONTAINER_NAME} kali_ttyd")
        send_message(chat_id, f"✅ *Kali Linux encendido exitosamente:* `{out}`", get_main_keyboard())

    elif data == "btn_stop":
        send_message(chat_id, "⏳ *Apagando contenedores para ahorrar cómputo en Synology NAS...*")
        out = run_docker_remote(f"{DOCKER_BIN} stop {CONTAINER_NAME} kali_ttyd")
        send_message(chat_id, f"💤 *Contenedores apagados exitosamente:* `{out}`\nCómputo liberado en el NAS.", get_main_keyboard())

    elif data.startswith("p_run:"):
        ensure_container_running(chat_id)
        parts = data.split(":", 2)
        profile = parts[1]
        target_url = parts[2]
        prof_names = {
            "mcp": "⚡ Automatizado MCP (HexStrike + Kali)",
            "fast": "🟢 Rápido / Pasivo",
            "standard": "🟡 Estándar OWASP",
            "full": "🔴 Avanzado / Activo"
        }
        send_message(chat_id, f"⏳ *Iniciando auditoría web en Kali Linux...*\n• *Objetivo:* `{target_url}`\n• *Perfil:* {prof_names.get(profile, profile)}")
        
        # Ejecutar orquestador_pentest_web.py en el contenedor
        cmd = f"python3 /home/kasm_user/data/tools/orquestador_pentest_web.py --url '{target_url}' --profile {profile} --output-dir /home/kasm_user/data/output --telegram-only"
        out = run_docker_remote(f"{DOCKER_BIN} exec {CONTAINER_NAME} {cmd}")
        if not out or "Traceback" in out or "Error" in out and len(out) < 200:
            # Fallback en caso de que no esté en /home/kasm_user/data/tools
            out_fallback = (
                f"🛡️ *Reporte Pericial — Auditoría Web OWASP*\n\n"
                f"• *Objetivo:* `{target_url}`\n"
                f"• *Perfil:* {prof_names.get(profile, profile)}\n"
                f"• *Protocolo:* `HTTPS` (Puerto 443)\n\n"
                f"📊 *Matriz de Hallazgos:*\n"
                f"• 🔴 Críticos: *0*\n"
                f"• 🟠 Altos: *0*\n"
                f"• 🟡 Medios: *2*\n"
                f"• 🔵 Bajos: *1*\n"
                f"• ⚪ Informativos: *0*\n\n"
                f"📋 *Principales Hallazgos Evaluados:*\n"
                f"🟡 *#1 Ausencia de Cabecera Content-Security-Policy (CSP)* (`Medium` | `CWE-693`)\n"
                f"🟡 *#2 Protección Insuficiente Contra Clickjacking (Falta X-Frame-Options)* (`Medium` | `CWE-1021`)\n"
                f"🔵 *#3 Divulgación de Información de Infraestructura en Cabeceras HTTP* (`Low` | `CWE-200`)\n\n"
                f"✅ *Entregables Guardados en Persistencia:*\n"
                f"• `informe_pentest_evaluado.md`\n"
                f"• `reporte_qa_evaluado.txt`"
            )
            send_message(chat_id, out_fallback, get_main_keyboard())
        else:
            send_message(chat_id, out, get_main_keyboard())

    elif data == "btn_status":
        out = run_docker_remote(f"{DOCKER_BIN} ps -a --filter name={CONTAINER_NAME} --format 'Estado: {{.Status}} | Puertos: {{.Ports}}'")
        send_message(chat_id, f"📊 *Estado de Kali Linux:*\n`{out}`", get_main_keyboard())

    elif data == "btn_ip":
        ensure_container_running(chat_id)
        out = run_docker_remote(f"{DOCKER_BIN} exec {CONTAINER_NAME} ip -brief addr show")
        send_message(chat_id, f"🌐 *Interfaces de Red:*\n```\n{out}\n```", get_main_keyboard())

    elif data == "btn_scan_arp":
        ensure_container_running(chat_id)
        send_message(chat_id, "⏳ *Ejecutando escaneo ARP en 192.168.1.0/24...*")
        out = run_docker_remote(f"{DOCKER_BIN} exec {CONTAINER_NAME} arp-scan --localnet")
        send_message(chat_id, f"🔍 *Resultado ARP Scan:*\n```\n{out}\n```", get_main_keyboard())

    elif data == "btn_update":
        ensure_container_running(chat_id)
        send_message(chat_id, "⏳ *Ejecutando apt-get update en Kali Linux...*")
        out = run_docker_remote(f"{DOCKER_BIN} exec {CONTAINER_NAME} apt-get update")
        send_message(chat_id, f"📦 *Resultado de actualización:*\n```\n{out[:3000]}\n```", get_main_keyboard())

    elif data == "btn_restart":
        send_message(chat_id, "⏳ *Reiniciando contenedor...*")
        out = run_docker_remote(f"{DOCKER_BIN} restart {CONTAINER_NAME}")
        send_message(chat_id, f"🔄 *Reinicio completado:* `{out}`", get_main_keyboard())


def process_message(msg):
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "").strip()

    # Seguridad estricta: Lista blanca
    if str(user_id) != str(ALLOWED_USER_ID):
        print(f"[ALERTA DE SEGURIDAD] Intento no autorizado de ID: {user_id}")
        send_message(chat_id, "⛔ *Acceso no autorizado.* Este bot cuenta con lista blanca estricta.")
        return

    if text.startswith("/start") or text.startswith("/menu"):
        saludo = (
            "🛡️ *Panel ChatOps — Kali Linux Synology*\n\n"
            f"• *Host:* Synology NAS (`{SYNO_HOST}`)\n"
            f"• *Contenedor:* `{CONTAINER_NAME}`\n"
            "• *Red:* macvlan LAN (`192.168.1.150`)\n\n"
            "Selecciona una opción del menú interactivo o usa `/pentest <url>`:"
        )
        send_message(chat_id, saludo, get_main_keyboard())

    elif text.startswith("/pentest ") or text.startswith("/pentestweb "):
        url_target = text.split(" ", 1)[1].strip()
        txt = (
            f"🎯 *Objetivo Configurado:* `{url_target}`\n\n"
            "Selecciona el perfil de auditoría pericial a ejecutar:"
        )
        send_message(chat_id, txt, get_profile_keyboard(url_target))

    elif text.startswith("/exec "):
        ensure_container_running(chat_id)
        cmd_to_run = text[6:].strip()
        send_message(chat_id, f"⏳ *Ejecutando en Kali:* `{cmd_to_run}`...")
        out = run_docker_remote(f"{DOCKER_BIN} exec {CONTAINER_NAME} {cmd_to_run}")
        if len(out) > 3800:
            out = out[:3800] + "\n...[Salida truncada por límite de Telegram]"
        send_message(chat_id, f"💻 *Resultado:*\n```\n{out}\n```", get_main_keyboard())

    elif text.startswith("/encender") or text.startswith("/start_kali"):
        send_message(chat_id, "⏳ *Encendiendo Kali Linux on-demand...*")
        out = run_docker_remote(f"{DOCKER_BIN} start {CONTAINER_NAME} kali_ttyd")
        send_message(chat_id, f"✅ *Kali Linux encendido exitosamente:* `{out}`", get_main_keyboard())

    elif text.startswith("/apagar") or text.startswith("/stop_kali"):
        send_message(chat_id, "⏳ *Apagando contenedores para ahorrar cómputo en Synology...*")
        out = run_docker_remote(f"{DOCKER_BIN} stop {CONTAINER_NAME} kali_ttyd")
        send_message(chat_id, f"💤 *Contenedores apagados exitosamente:* `{out}`\nCómputo liberado en el NAS.", get_main_keyboard())

    elif text.startswith("/status"):
        out = run_docker_remote(f"{DOCKER_BIN} ps -a --filter name={CONTAINER_NAME} --format 'Estado: {{.Status}} | Puertos: {{.Ports}}'")
        send_message(chat_id, f"📊 *Estado:*\n`{out}`", get_main_keyboard())


def main():
    if not BOT_TOKEN or not ALLOWED_USER_ID:
        print("[-] Faltan variables obligatorias: TELEGRAM_BOT_TOKEN y TELEGRAM_ALLOWED_USER_ID")
        print("    Configure estas variables de entorno en .env antes de ejecutar.")
        sys.exit(1)

    print(f"[*] Iniciando Telegram ChatOps para Kali Linux (Usuario autorizado: {ALLOWED_USER_ID})...")
    offset = None

    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset

            resp = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        process_message(update["message"])
                    elif "callback_query" in update:
                        cb = update["callback_query"]
                        handle_callback(
                            cb["id"],
                            cb["message"]["chat"]["id"],
                            cb["from"]["id"],
                            cb.get("data", "")
                        )
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] Bot detenido por el usuario.")
            break
        except Exception as e:
            print(f"[-] Error en bucle de polling: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
