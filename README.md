# Kali Linux Docker en Synology NAS con ChatOps

Infraestructura de auditoría de seguridad que despliega una instancia contenerizada de Kali Linux sobre Synology DSM 7.2 en red macvlan, administrada de forma remota mediante un bot de ChatOps en Telegram.

---

## Arquitectura y Componentes

- **Contenedor:** Imagen Kali Linux ejecutada bajo Docker Compose con dirección IP dedicada en la subred local.
- **Control remoto:** Bot en Python para ejecución de utilitarios de red (Nmap, arp-scan).
- **Seguridad:** Filtrado de acceso por lista blanca estricta de identificadores de usuario.

---

## Instrucciones de Uso

```bash
# Despliegue de infraestructura
docker compose up -d
python tools/telegram_kali_bot.py
```

---

## Consideraciones de Seguridad

- Este repositorio almacena código fuente, utilitarios de prueba y documentación técnica de ingeniería.
- Todas las credenciales, llaves privadas y variables de entorno deben suministrarse de forma local mediante archivos no versionados.
- Las herramientas de auditoría contenidas deben utilizarse exclusivamente en entornos autorizados y laboratorios de prueba.

---

**Autor:** Security Analyst  
**Licencia:** Uso Privado / Propietario
