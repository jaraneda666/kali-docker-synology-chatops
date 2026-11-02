# Guía Operativa: Integración MCP de HexStrike AI y MCP-Kali-Server

Esta guía documenta la arquitectura, despliegue, administración y articulación operativa en las fases de pentesting de los dos servidores Model Context Protocol (MCP) integrados en el contenedor Kali Linux en Synology DSM:
1. **Wh0am123/MCP-Kali-Server** (Puerto `5000`)
2. **0x4m4/hexstrike-ai** (Puerto `8888`)

---

## 1. Arquitectura de Integración

```
┌────────────────────────────────────────────────────────┐
│             Cliente AI / Orquestador Central          │
│   (Antigravity IDE / Claude Desktop / n8n ChatOps)     │
└──────────┬─────────────────────────────────┬───────────┘
           │ stdio MCP                       │ stdio MCP / HTTP
           ▼                                 ▼
┌───────────────────────┐         ┌──────────────────────┐
│ mcp_kali_server_bridge│         │ hexstrike_mcp_bridge │
│ (Puerto 5000)         │         │ (Puerto 8888)        │
└──────────┬────────────┘         └──────────┬───────────┘
           │ HTTP                            │ HTTP
           ▼                                 ▼
┌────────────────────────────────────────────────────────┐
│             Contenedor Kali Linux (Synology DSM)       │
│                  IP Macvlan: 192.168.1.150             │
│                                                        │
│  • MCP-Kali-Server: /home/kasm-user/MCP-Kali-Server    │
│    API REST: http://192.168.1.150:5000                 │
│                                                        │
│  • HexStrike AI v6.0: /home/kasm-user/hexstrike-ai     │
│    API REST: http://192.168.1.150:8888                 │
│                                                        │
│  • Persistencia: /volume1/docker/kali/data             │
│    (montado en /home/kasm_user/data)                   │
└────────────────────────────────────────────────────────┘
```

---

## 2. Articulación en las Fases del Pentest Web (OWASP WSTG)

### Fase 1: Reconocimiento y OSINT (WSTG-INFO)
- **HexStrike AI (`hexstrike_analyze_target`, `hexstrike_recon_workflow`):**
  - Mapeo inicial de superficie de ataque, profiling de dominio y cálculo de score de riesgo.
  - Recolección pasiva con `theHarvester`, `dnsenum` y fingerprinting de cabeceras.
- **MCP-Kali-Server (`kali_nmap`):**
  - Escaneo de puertos TCP/UDP, detección de versiones de servicio (`-sV`) y scripts NSE (`-sC`).

### Fase 2: Escaneo y Detección de Vulnerabilidades (WSTG-CONF / WSTG-INPV)
- **HexStrike AI (`hexstrike_smart_scan`, `hexstrike_technology_detection`):**
  - Detección de tecnologías web (CMS, frameworks backend, servidores, balanceadores WAF con `wafw00f`).
  - Detección automática de vectores de ataque relevantes según la pila tecnológica observada.
- **MCP-Kali-Server (`kali_gobuster`, `kali_nikto`, `kali_wpscan`):**
  - Fuzzing y fuerza bruta de directorios ocultos, backups y archivos sensibles (`gobuster dir`).
  - Escaneo de configuraciones deficientes del servidor web (`nikto`).
  - Auditoría especializada si el objetivo es WordPress (`wpscan`).

### Fase 3: Validación Controlada y Pruebas Dirigidas (HITL)
- **Supervisión Humana Obligatoria (Human-in-the-Loop):**
  - Toda acción invasiva o de comprobación de inyecciones (`kali_sqlmap`, explotación dirigida) exige confirmación explícita previa del operador a través de ChatOps o terminal.
  - Validación de falsos positivos en aplicaciones Single Page Applications (SPAs).

### Fase 4: Mitigación y Hardening Defensivo
- Clasificación de hallazgos bajo estándar CVSS v3.1 y asociación formal a debilidades CWE.
- Generación de recomendaciones específicas de mitigación (HSTS, CSP, CORS restrictivo, configuración Nginx/Apache).

### Fase 5: Documentación Pericial y Aseguramiento de Calidad (QA)
- Los resultados de las fases anteriores se procesan con `orquestador_pentest_web.py` y `generar_reporte_pentest.py`.
- Generación automática de:
  - `output/informe_pentest_[objetivo]_[fecha].md`
  - `output/reporte_qa_[objetivo]_[fecha].txt`
  - `output/hallazgos_[objetivo]_[fecha].json`

---

## 3. Comandos de Administración del Sistema

Todas las operaciones se gestionan centralizadamente desde la herramienta:
[`tools/global/manage_kali_mcp.py`](file:///c:/Users/Juan%20Carlos/Documents/Antigravity%20projects/tools/global/manage_kali_mcp.py) (o su enlace local [`Kali_Docker_Synology/tools/manage_kali_mcp.py`](file:///c:/Users/Juan%20Carlos/Documents/Antigravity%20projects/Kali_Docker_Synology/tools/manage_kali_mcp.py)).

### Comprobar Estado y Salud en Vivo
```bash
python tools/manage_kali_mcp.py --action status
```

### Ejecutar Pruebas Funcionales en Caliente
```bash
python tools/manage_kali_mcp.py --action test
```

### Iniciar Demonios en Kali
```bash
python tools/manage_kali_mcp.py --action start
```

### Detener Demonios en Kali
```bash
python tools/manage_kali_mcp.py --action stop
```

### Reiniciar Demonios en Kali
```bash
python tools/manage_kali_mcp.py --action restart
```

### Consultar Registros de Ejecución
```bash
python tools/manage_kali_mcp.py --action logs
```

---

## 4. Configuración en Clientes MCP

### Antigravity IDE (`.agents/mcp_config.json`)
El workspace ya cuenta con la configuración activa en `.agents/mcp_config.json`:
```json
{
  "mcpServers": {
    "mcp-kali-server": {
      "command": "python",
      "args": [
        "c:/Users/Developer/Documents/Antigravity projects/Kali_Docker_Synology/tools/mcp_kali_server_bridge.py",
        "--server",
        "http://192.168.1.150:5000"
      ]
    },
    "hexstrike-ai": {
      "command": "python",
      "args": [
        "c:/Users/Developer/Documents/Antigravity projects/Kali_Docker_Synology/tools/hexstrike_mcp_bridge.py",
        "--server",
        "http://192.168.1.150:8888"
      ]
    }
  }
}
```

### Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "mcp-kali-server": {
      "command": "python",
      "args": [
        "C:\\Users\\Developer\\Documents\\Antigravity projects\\Kali_Docker_Synology\\tools\\mcp_kali_server_bridge.py",
        "--server",
        "http://192.168.1.150:5000"
      ]
    },
    "hexstrike-ai": {
      "command": "python",
      "args": [
        "C:\\Users\\Developer\\Documents\\Antigravity projects\\Kali_Docker_Synology\\tools\\hexstrike_mcp_bridge.py",
        "--server",
        "http://192.168.1.150:8888"
      ]
    }
  }
}
```

---

## 5. Endpoints REST Directos para n8n / Telegram ChatOps

El flujo de n8n en Synology puede invocar directamente las APIs HTTP de los backends sin intermediarios:

| Servicio | Método | Endpoint | Descripción |
| :--- | :---: | :--- | :--- |
| **MCP-Kali** | `GET` | `http://192.168.1.150:5000/health` | Verificación de salud y herramientas |
| **MCP-Kali** | `POST` | `http://192.168.1.150:5000/api/tools/nmap` | Escaneo Nmap (`target`, `ports`, `scan_type`) |
| **MCP-Kali** | `POST` | `http://192.168.1.150:5000/api/tools/gobuster` | Fuzzing Gobuster (`url`, `mode`, `wordlist`) |
| **MCP-Kali** | `POST` | `http://192.168.1.150:5000/api/tools/nikto` | Escaneo web con Nikto (`url`) |
| **HexStrike** | `GET` | `http://192.168.1.150:8888/health` | Verificación de salud y telemetría |
| **HexStrike** | `POST` | `http://192.168.1.150:8888/api/intelligence/analyze-target` | Profiling de superficie de ataque (`target`) |
| **HexStrike** | `POST` | `http://192.168.1.150:8888/api/intelligence/smart-scan` | Escaneo multivectorial automatizado (`target`) |
| **HexStrike** | `POST` | `http://192.168.1.150:8888/api/bugbounty/reconnaissance-workflow` | Flujo de reconocimiento de bug bounty (`target`) |
