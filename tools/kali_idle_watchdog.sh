#!/bin/bash
# ==============================================================================
# Script: kali_idle_watchdog.sh
# Descripción: Monitor de inactividad para Kali Linux en Synology NAS DSM.
#              Apaga los contenedores tras 30 minutos sin sesiones activas.
# Ubicación en NAS: /volume1/docker/kali/data/tools/kali_idle_watchdog.sh
# Configuración DSM: Programador de Tareas -> Tarea programada (cada 5 min)
# ==============================================================================

set -u

DOCKER_BIN="/var/packages/ContainerManager/target/usr/bin/docker"
if [ ! -x "$DOCKER_BIN" ]; then
    DOCKER_BIN="docker"
fi

CONTAINER_MAIN="kali_linux"
CONTAINER_TTY="kali_ttyd"
DATA_DIR="/volume1/docker/kali/data"
STATE_FILE="${DATA_DIR}/.watchdog_last_active"
LOG_FILE="${DATA_DIR}/watchdog.log"
TIMEOUT_SECONDS=1800  # 30 minutos

# Cargar variables de entorno locales si existen
if [ -f "${DATA_DIR}/.env" ]; then
    set -a
    source "${DATA_DIR}/.env"
    set +a
fi

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [*] $1" | tee -a "$LOG_FILE"
}

send_telegram_alert() {
    local text="$1"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_ALLOWED_USER_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_ALLOWED_USER_ID}" \
            -d "text=${text}" \
            -d "parse_mode=Markdown" > /dev/null 2>&1 || true
    fi
}

# 1. Verificar si el contenedor principal está corriendo
IS_RUNNING=$("$DOCKER_BIN" inspect -f '{{.State.Running}}' "$CONTAINER_MAIN" 2>/dev/null || echo "false")

if [ "$IS_RUNNING" != "true" ]; then
    # Si está apagado, limpiar archivo de estado si existe y salir
    if [ -f "$STATE_FILE" ]; then
        rm -f "$STATE_FILE"
    fi
    exit 0
fi

# 2. Verificar conexiones de red activas en puertos de servicio
# - En kali_linux: 6901 (KasmVNC), 22 (SSH Dropbear), 8080 (Caido Proxy/UI), 5000 (MCP-Kali-Server), 8888 (HexStrike AI)
ACTIVE_CONNS_MAIN=$("$DOCKER_BIN" exec "$CONTAINER_MAIN" ss -t -H state established '( sport = :6901 or sport = :22 or sport = :8080 or sport = :5000 or sport = :8888 )' 2>/dev/null | grep -v '^$' | wc -l)
ACTIVE_CONNS_MAIN=$(echo "$ACTIVE_CONNS_MAIN" | tr -dc '0-9')
[ -z "$ACTIVE_CONNS_MAIN" ] && ACTIVE_CONNS_MAIN=0

# - En kali_ttyd: 7681 (ttyd terminal web). 7681 en hex es 1E01, y state 01 es ESTABLISHED en /proc/net/tcp
ACTIVE_CONNS_TTY=$("$DOCKER_BIN" exec "$CONTAINER_TTY" sh -c "grep ':1E01.* 01 ' /proc/net/tcp 2>/dev/null | wc -l" 2>/dev/null)
ACTIVE_CONNS_TTY=$(echo "$ACTIVE_CONNS_TTY" | tr -dc '0-9')
[ -z "$ACTIVE_CONNS_TTY" ] && ACTIVE_CONNS_TTY=0

ACTIVE_CONNS=$(( ACTIVE_CONNS_MAIN + ACTIVE_CONNS_TTY ))

# 3. Verificar si hay procesos de auditoría en ejecución o sesiones interactivas (PTS)
AUDIT_PROCS=$("$DOCKER_BIN" exec "$CONTAINER_MAIN" pgrep -f 'nmap|nikto|gobuster|sqlmap|ffuf|hydra|wpscan|python3.*pentest' 2>/dev/null | wc -l)
AUDIT_PROCS=$(echo "$AUDIT_PROCS" | tr -dc '0-9')
[ -z "$AUDIT_PROCS" ] && AUDIT_PROCS=0

PTS_PROCS=$("$DOCKER_BIN" exec "$CONTAINER_MAIN" sh -c "ps -eo tty,comm 2>/dev/null | grep -E '^pts/' | wc -l" 2>/dev/null)
PTS_PROCS=$(echo "$PTS_PROCS" | tr -dc '0-9')
[ -z "$PTS_PROCS" ] && PTS_PROCS=0

ACTIVE_PROCS=$(( AUDIT_PROCS + PTS_PROCS ))

CURRENT_TIME=$(date +%s)

if [ "$ACTIVE_CONNS" -gt 0 ] || [ "$ACTIVE_PROCS" -gt 0 ]; then
    # Hay actividad activa: actualizar timestamp
    echo "$CURRENT_TIME" > "$STATE_FILE"
    log_msg "Actividad detectada en Kali (Conexiones TCP: $ACTIVE_CONNS, Procesos: $ACTIVE_PROCS). Temporizador reiniciado."
    exit 0
fi

# 4. No hay conexiones activas: evaluar tiempo de inactividad
if [ ! -f "$STATE_FILE" ]; then
    echo "$CURRENT_TIME" > "$STATE_FILE"
    log_msg "Sin conexiones activas. Iniciando cuenta regresiva de inactividad (30 min)."
    exit 0
fi

LAST_ACTIVE=$(cat "$STATE_FILE" 2>/dev/null || echo "$CURRENT_TIME")
ELAPSED=$(( CURRENT_TIME - LAST_ACTIVE ))

if [ "$ELAPSED" -ge "$TIMEOUT_SECONDS" ]; then
    log_msg "UMBRAL ALCANZADO: Inactividad de $(( ELAPSED / 60 )) minutos. Apagando contenedores para ahorrar cómputo en Synology NAS..."
    
    # Detener contenedores
    "$DOCKER_BIN" stop "$CONTAINER_MAIN" "$CONTAINER_TTY" 2>&1 | tee -a "$LOG_FILE"
    rm -f "$STATE_FILE"
    
    log_msg "Contenedores '$CONTAINER_MAIN' y '$CONTAINER_TTY' apagados exitosamente."
    
    send_telegram_alert "💤 *Kali Linux — Auto-Apagado por Inactividad*%0A%0ASe detectaron más de 30 minutos sin conexiones ni procesos activos en Synology NAS.%0AContenedores \`kali_linux\` y \`kali_ttyd\` detenidos para liberar RAM y CPU."
else
    REMAINING=$(( (TIMEOUT_SECONDS - ELAPSED) / 60 ))
    log_msg "Inactivo durante $(( ELAPSED / 60 )) min. Faltan $REMAINING min para el auto-apagado."
fi
