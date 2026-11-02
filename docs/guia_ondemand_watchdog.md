# Guía de Operación: Activación On-Demand y Auto-Apagado por Inactividad (Scale-to-Zero)

## 1. Visión General y Arquitectura

Para optimizar los recursos de hardware en el Synology NAS (`192.168.1.100`), el contenedor Kali Linux y sus servicios auxiliares (`kali_linux` y `kali_ttyd`) operan bajo un modelo **Scale-to-Zero**:

1. **Auto-Encendido On-Demand (Wake-on-Request):**
   - **Protocolo MCP:** Si un agente o IDE envía una petición mediante los adaptadores MCP (`mcp_kali_server_bridge.py` o `hexstrike_mcp_bridge.py`) y el contenedor está apagado, el adaptador se conecta por SSH a Synology DSM, ejecuta `docker start kali_linux kali_ttyd`, espera a que los servidores web/API respondan (`/health`) y despacha la petición sin errores.
   - **Telegram ChatOps:** El bot `telegram_kali_bot.py` cuenta con botones interactivos dedicados (`🟢 Encender Kali`, `💤 Apagar Kali`), comandos `/encender` y `/apagar`, y activa automáticamente los contenedores si recibe peticiones de `/exec` o `/pentest` mientras están apagados.

2. **Auto-Apagado por Inactividad (Idle Watchdog - 30 Minutos):**
   - El script `kali_idle_watchdog.sh` (o `kali_idle_watchdog.py`) inspecciona periódicamente el contenedor.
   - Monitorea sockets TCP en estado `ESTABLISHED` en los puertos de servicio:
     - `6901`: KasmVNC / Escritorio gráfico web
     - `22`: Dropbear SSH / Terminal remota directa
     - `7681`: `ttyd` / Terminal web interactiva (contenedor `kali_ttyd`)
     - `5000`: Wh0am123/MCP-Kali-Server
     - `8888`: 0x4m4/HexStrike-AI
   - Monitorea procesos activos de auditoría en ejecución (`nmap`, `nikto`, `gobuster`, `sqlmap`, etc.) y sesiones interactivas de terminal (`pts/`).
   - Si no detecta actividad durante **30 minutos consecutivos** (`1800 segundos`), ejecuta `docker stop kali_linux kali_ttyd` y emite una alerta preventiva por Telegram.

---

## 2. Instalación del Watchdog en Synology DSM (Task Scheduler)

Para que el apagado automático funcione de forma 100% nativa y desatendida en el NAS:

### Paso 1: Despliegue en el volumen persistente del NAS
El script reside en `/volume1/docker/kali/data/tools/kali_idle_watchdog.sh` con permisos `755`:
```bash
chmod 755 /volume1/docker/kali/data/tools/kali_idle_watchdog.sh
```

### Paso 2: Tarea Programada en Synology DSM (ID 30 Activa)
La tarea está registrada y activa en el sistema bajo el identificador **ID 30** (`Kali Idle Watchdog 30m`), ejecutándose automáticamente cada 5 minutos (`*/5 * * * *` en `/etc/crontab`).

Para consultar o forzar la ejecución desde DSM CLI:
```bash
# Consultar estado de la tarea en DSM
sudo /usr/syno/bin/synoschedtask --get id=30

# Ejecutar manualmente la tarea
sudo /usr/syno/bin/synoschedtask --run id=30
```

También es visible y configurable desde el portal web:
1. Iniciar sesión en Synology DSM (`https://192.168.1.100:5001`).
2. Ir a **Panel de Control** > **Programador de Tareas** (Task Scheduler).
3. Localizar la tarea `Kali Idle Watchdog 30m` (Usuario: `root`, Estado: `Habilitado`, Frecuencia: cada 5 min).

---

## 3. Verificación de Funcionamiento

### Verificación del Watchdog
Para probar manualmente el comportamiento del watchdog desde la terminal o por SSH:
```bash
# Ejecución directa en DSM
sudo /bin/bash /volume1/docker/kali/data/tools/kali_idle_watchdog.sh

# O verificación remota vía Python
python tools/kali_idle_watchdog.py --check-once
```

### Bitácora de Auditoría
El watchdog registra todos los eventos en `/volume1/docker/kali/data/watchdog.log`:
```text
2026-10-13 10:17:28 [*] Sin conexiones activas. Iniciando cuenta regresiva de inactividad (30 min).
2026-10-13 10:17:36 [*] Inactivo durante 0 min. Faltan 29 min para el auto-apagado.
2026-10-13 10:17:48 [*] Actividad detectada en Kali (Conexiones TCP: 1, Procesos: 0). Temporizador reiniciado.
```
