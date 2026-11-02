# Arquitectura de Red — Kali Linux en Synology Docker

## 1. Topología y Solución de Conectividad Dual

En entornos Docker sobre Linux y Synology DSM, el modo de red `macvlan` aísla por diseño de kernel el tráfico directo entre la interfaz física del host anfitrión (`192.168.1.100`) y la IP virtual del contenedor (`192.168.1.150`).

Para resolver esta limitación sin requerir complejas interfaces shim volátiles en DSM, el contenedor Kali Linux se conecta a **dos redes simultáneas**:

```text
                               +--------------------------------------------+
                               |            Router OpenWrt                  |
                               |             192.168.1.1                   |
                               +---------------------+----------------------+
                                                     |
                               +---------------------+----------------------+
                               |          Switch UniFi US-8-60W             |
                               +---------------------+----------------------+
                                                     |
                    +--------------------------------+--------------------------------+
                    |                                                                 |
         +----------+-----------+                                          +----------+-----------+
         |     PC Usuario       |                                          |   NAS Synology DS    |
         |    127.0.0.1      |                                          |     192.168.1.100     |
         +----------------------+                                          +----------+-----------+
                    |                                                                 | (eth0)
                    | Acceso Directo LAN                                             |
                    v                                                                 v
+-----------------------------------------------------------------------------------------------+
|  Contenedor Docker: kali_linux                                                                 |
|                                                                                               |
|  [Interfaz eth0 / macvlan_lan]  ---> IP Estática LAN: 192.168.1.150 (Escaneo de red crudo)     |
|  [Interfaz eth1 / syno_bridge]  ---> Red interna Docker Bridge (Para Nginx RP y n8n)          |
|                                                                                               |
|  Servicios Web:                                                                               |
|  - Puerto 3000 / 6901 : Escritorio Web XFCE (KasmVNC / noVNC)                                 |
|  - Puerto 7681        : Terminal Web interactiva (ttyd)                                       |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Ventajas del Enfoque Híbrido

1. **Escaneo de Red Nativo (Fase 1 Reconocimiento):**
   - Al tener su propia MAC y dirección IP (`192.168.1.150`), las herramientas como `nmap`, `arp-scan` y `masscan` emiten y reciben paquetes ARP/ICMP/TCP crudos sin colisionar con los sockets ni el firewall del NAS Synology.
2. **Compatibilidad Total con Reverse Proxy Nginx en DSM:**
   - Al pertenecer también a la red bridge interna de Docker, Nginx en DSM 7 puede enrutar el tráfico HTTP/HTTPS y WebSocket hacia el contenedor sin verse afectado por el bloqueo de kernel entre host y macvlan.
3. **Integración Directa con n8n:**
   - La instancia de n8n que corre en Docker sobre el NAS puede invocar la API o sockets del contenedor de Kali directamente por nombre de host o red bridge.

---

## 3. Asignación de Puertos y Servicios

| Servicio | Puerto Contenedor | Acceso Directo LAN | Acceso Seguro Proxy Inverso |
| :--- | :--- | :--- | :--- |
| **Escritorio Web (XFCE GUI)** | `3000` / `6901` | `http://192.168.1.150:3000` | `https://kali-desktop.admin.synology.me` |
| **Terminal Web CLI (`ttyd`)** | `7681` | `http://192.168.1.150:7681` | `https://kali-term.admin.synology.me` |
| **Control SSH (Opcional)** | `22` | `192.168.1.150:22` | Confinado a LAN |

---

## 4. Política de Confinamiento y Seguridad OWASP

- **Perfil ACL Nginx:** Ambos subdominios se vinculan a la lista de control de acceso `LAN_y_VPN` (`192.168.1.0/24`, `10.8.0.0/24`, `127.0.0.1`), asegurando un bloqueo `403 Forbidden` absoluto para cualquier intento de conexión desde fuera de la red de confianza.
- **Autenticación en Terminal:** `ttyd` exige credenciales HTTP Digest / Basic con contraseña fuerte definida en `.env`.
