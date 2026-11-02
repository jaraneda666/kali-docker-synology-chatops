#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# Tool: n8n_manager.py

## Metadata
- Nombre: n8n_manager.py
- Versión: 1.1
- Lenguaje: Python
- Creada en proyecto: N8N Automation
- Fecha de creación: 2026-10-08
- Descripción: Herramienta de auditoría estática de workflows locales y cliente de administración segura para la API pública de n8n.
- Parámetros:
  - audit: Escanea archivos .json de workflows locales en busca de riesgos de seguridad, credenciales expuestas, nodos sin gestión de fallos y ausencia de compuertas HITL.
  - test: Comprueba la conexión y autenticación con una instancia de n8n vía API REST.
  - list: Lista workflows registrados en la instancia de n8n.
  - get: Obtiene la definición completa de un workflow por su ID.
  - deploy: Despliega (crea o actualiza) y opcionalmente activa un workflow en n8n desde un archivo .json local.
  - --api-url: URL base de la instancia de n8n (por defecto http://localhost:5678 o variable N8N_API_URL).
  - --api-key: Llave de API / JWT de n8n (o variable N8N_API_KEY o ruta a n8n_api_key.txt).
  - --path: Ruta a archivo o directorio para auditoría local.
- Dependencias: Python 3.8+ (módulos estándar: urllib.request, json, argparse, pathlib, re, os).

## Uso
  python n8n_manager.py audit --path "G:/Mi unidad/IT/N8n"
  python n8n_manager.py test --api-url "http://192.168.1.10:5678" --api-key-file "G:/Mi unidad/IT/N8n/n8n_api_key.txt"
  python n8n_manager.py list --api-url "http://192.168.1.10:5678" --api-key-file "G:/Mi unidad/IT/N8n/n8n_api_key.txt"
  python n8n_manager.py deploy --file "workflow.json" --activate --api-url "http://192.168.1.10:5678" --api-key-file "G:/Mi unidad/IT/N8n/n8n_api_key.txt"
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def mask_token(token: str) -> str:
    """Enmascara tokens y secretos para salida segura por consola."""
    if not token or len(token) < 12:
        return "[PROTEGIDO]"
    return f"{token[:6]}...{token[-4:]}"

def load_api_key(api_key_arg: str = None, api_key_file: str = None) -> str:
    """Carga la API key desde argumento, archivo o variable de entorno."""
    if api_key_arg:
        return api_key_arg.strip()
    if api_key_file and os.path.exists(api_key_file):
        with open(api_key_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    env_key = os.environ.get("N8N_API_KEY")
    if env_key:
        return env_key.strip()
    # Ubicación conocida por defecto
    default_gdrive_key = Path("G:/Mi unidad/IT/N8n/n8n_api_key.txt")
    if default_gdrive_key.exists():
        with open(default_gdrive_key, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def n8n_api_request(endpoint: str, api_url: str, api_key: str, method: str = "GET", payload: dict = None) -> dict:
    """Realiza una petición HTTP contra la API pública de n8n."""
    clean_url = api_url.rstrip("/")
    target = f"{clean_url}/api/v1/{endpoint.lstrip('/')}"
    headers = {
        "X-N8N-API-KEY": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data_bytes = json.dumps(payload).encode("utf-8") if payload else None
    req = Request(target, data=data_bytes, headers=headers, method=method)
    
    try:
        with urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return {"status": resp.status, "data": json.loads(content)}
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        return {"status": e.code, "error": f"HTTP {e.code}: {e.reason}", "details": error_body}
    except URLError as e:
        return {"status": 0, "error": f"Error de conexión: {e.reason}"}
    except Exception as e:
        return {"status": 0, "error": str(e)}

def audit_workflow_file(file_path: Path) -> dict:
    """Audita de forma estática un archivo JSON de workflow de n8n."""
    results = {
        "file": str(file_path),
        "name": file_path.name,
        "valid_json": False,
        "node_count": 0,
        "triggers": [],
        "external_calls": [],
        "credentials_referenced": [],
        "security_findings": [],
        "hitl_status": "No aplica",
        "has_error_handler": False
    }

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            wf = json.load(f)
        results["valid_json"] = True
    except Exception as e:
        results["security_findings"].append({
            "severity": "CRÍTICO",
            "tipo": "JSON_CORRUPTO",
            "detalle": f"No se pudo parsear el archivo como JSON: {e}"
        })
        return results

    nodes = wf.get("nodes", [])
    results["node_count"] = len(nodes)
    results["name"] = wf.get("name", file_path.stem)

    high_impact_services = ["linkedin", "telegram", "slack", "discord", "email", "gmail", "smtp", "twitter", "x"]
    has_high_impact = False
    has_approval_gate = False

    # Regex para detectar secretos quemados en texto plano
    secret_patterns = [
        (re.compile(r"(?i)(api[_-]?key|secret|token|password|bearer|auth)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{15,}['\"]"), "Secretos o tokens codificados en cadenas"),
        (re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}"), "Token JWT embebido en configuración"),
        (re.compile(r"(?i)https?://[a-zA-Z0-9_\-]+:[a-zA-Z0-9_\-]+@"), "Credenciales Basic Auth en URL")
    ]

    for node in nodes:
        node_name = node.get("name", "Desconocido")
        node_type = (node.get("type", "")).lower()

        # Detectar Triggers
        if "trigger" in node_type or "webhook" in node_type or "cron" in node_type or "schedule" in node_type:
            results["triggers"].append(f"{node_name} ({node_type})")
            if "error" in node_type:
                results["has_error_handler"] = True

        # Detectar Wait / Form Trigger (HITL)
        if "wait" in node_type or "form" in node_type or "approval" in node_name.lower():
            has_approval_gate = True

        # Detectar servicios de alto impacto (publicación / mensajería)
        for srv in high_impact_services:
            if srv in node_type or srv in node_name.lower():
                has_high_impact = True
                break

        # Detectar llamadas HTTP salientes
        if "httprequest" in node_type:
            url_param = node.get("parameters", {}).get("url", "")
            method_param = node.get("parameters", {}).get("requestMethod", "GET")
            results["external_calls"].append(f"{method_param} {url_param} [{node_name}]")

        # Detectar credenciales nativas referenciadas
        creds = node.get("credentials", {})
        for cred_type, cred_val in creds.items():
            results["credentials_referenced"].append(f"{cred_type}: {cred_val.get('id', 'N/A')}")

        # Escanear el nodo completo en busca de secretos expuestos en texto plano
        node_str = json.dumps(node, ensure_ascii=False)
        for pattern, desc in secret_patterns:
            matches = pattern.findall(node_str)
            if matches:
                # Filtrar falsos positivos de schemas conocidos
                results["security_findings"].append({
                    "severity": "ALTO",
                    "tipo": "CREDENCIAL_EXPUESTA",
                    "nodo": node_name,
                    "detalle": f"{desc} en nodo '{node_name}'"
                })

    # Evaluación HITL
    if has_high_impact:
        if has_approval_gate:
            results["hitl_status"] = "PROTEGIDO_CON_HITL"
        else:
            results["hitl_status"] = "VULNERABLE_SIN_HITL"
            results["security_findings"].append({
                "severity": "MEDIO",
                "tipo": "AUSENCIA_HITL",
                "nodo": "Workflow completo",
                "detalle": "El workflow ejecuta acciones externas de publicación/notificación sin compuerta previa de aprobación manual (Wait/Form node)."
            })

    if not results["has_error_handler"] and len(nodes) > 3:
        results["security_findings"].append({
            "severity": "BAJO",
            "tipo": "SIN_MANEJO_ERRORES",
            "nodo": "Global",
            "detalle": "El workflow no cuenta con nodo Error Trigger para notificación centralizada ante fallos."
        })

    return results

def run_audit(path_str: str):
    """Ejecuta la auditoría sobre un archivo o directorio."""
    target_path = Path(path_str)
    if not target_path.exists():
        print(f"[!] Error: La ruta '{path_str}' no existe.")
        return

    json_files = []
    if target_path.is_file() and target_path.suffix.lower() == ".json":
        json_files.append(target_path)
    elif target_path.is_dir():
        json_files.extend(list(target_path.rglob("*.json")))

    if not json_files:
        print(f"[*] No se encontraron archivos .json de workflows en '{path_str}'.")
        return

    print("=" * 70)
    print(f" AUDITORÍA DE WORKFLOWS N8N - {len(json_files)} ARCHIVOS ENCONTRADOS")
    print("=" * 70)

    total_findings = 0
    for jf in json_files:
        # Ignorar archivos no relacionados como client secrets o configs de gcp
        if "ferrous-wonder" in jf.name or "package" in jf.name:
            continue
            
        audit = audit_workflow_file(jf)
        print(f"\n[+] Workflow: {audit['name']} ({jf.name})")
        print(f"    - Nodos: {audit['node_count']}")
        print(f"    - Triggers: {', '.join(audit['triggers']) if audit['triggers'] else 'Ninguno detectado'}")
        print(f"    - Llamadas externas: {len(audit['external_calls'])}")
        print(f"    - Estado HITL: {audit['hitl_status']}")
        print(f"    - Manejador de error global: {'Sí' if audit['has_error_handler'] else 'No'}")
        
        if audit["security_findings"]:
            print("    [!] Hallazgos de Seguridad:")
            for f in audit["security_findings"]:
                total_findings += 1
                print(f"        [{f['severity']}] {f['tipo']}: {f['detalle']}")
        else:
            print("    [✓] Sin hallazgos críticos detectados.")

    print("\n" + "=" * 70)
    print(f" TOTAL HALLAZGOS AUDITADOS: {total_findings}")
    print("=" * 70)

def deploy_workflow(file_path: str, api_url: str, api_key: str, activate: bool = False, workflow_id: str = None) -> dict:
    """Despliega (crea o actualiza) y opcionalmente activa un workflow desde un JSON local."""
    path_obj = Path(file_path)
    if not path_obj.exists():
        print(f"[!] Error: El archivo '{file_path}' no existe.")
        return {"status": 0, "error": "Archivo no encontrado"}

    try:
        with open(path_obj, "r", encoding="utf-8") as f:
            wf_data = json.load(f)
    except Exception as e:
        print(f"[!] Error al parsear JSON de '{file_path}': {e}")
        return {"status": 0, "error": str(e)}

    payload = {
        "name": wf_data.get("name", path_obj.stem),
        "nodes": wf_data.get("nodes", []),
        "connections": wf_data.get("connections", {})
    }
    if "settings" in wf_data:
        payload["settings"] = wf_data["settings"]

    target_id = workflow_id or wf_data.get("id")

    if not target_id:
        list_res = n8n_api_request("workflows", api_url, api_key)
        if list_res.get("status") == 200:
            existing = list_res.get("data", {}).get("data", [])
            for item in existing:
                if item.get("name") == payload["name"]:
                    target_id = item.get("id")
                    break

    if target_id:
        print(f"[*] Actualizando workflow existente ID '{target_id}' ('{payload['name']}')...")
        res = n8n_api_request(f"workflows/{target_id}", api_url, api_key, method="PUT", payload=payload)
    else:
        print(f"[*] Creando nuevo workflow '{payload['name']}'...")
        res = n8n_api_request("workflows", api_url, api_key, method="POST", payload=payload)

    if res.get("status") in [200, 201]:
        wf_info = res.get("data", {})
        wf_id = wf_info.get("id", target_id)
        print(f"[✓] Workflow desplegado con éxito:")
        print(f"    - ID: {wf_id}")
        print(f"    - Nombre: {wf_info.get('name')}")
        print(f"    - Nodos: {len(wf_info.get('nodes', []))}")

        if activate and wf_id:
            print(f"[*] Activando workflow {wf_id}...")
            act_res = n8n_api_request(f"workflows/{wf_id}/activate", api_url, api_key, method="POST")
            if act_res.get("status") == 200:
                print(f"[✓] Workflow activado exitosamente.")
            else:
                act_res = n8n_api_request(f"workflows/{wf_id}", api_url, api_key, method="PUT", payload={"active": True})
                if act_res.get("status") == 200:
                    print(f"[✓] Workflow activado exitosamente.")
                else:
                    print(f"[!] Advertencia al activar: {act_res.get('error', act_res)}")
        return res
    else:
        print(f"[!] Error al desplegar workflow: {res.get('error', res)}")
        if res.get("details"):
            print(f"    Detalles: {res.get('details')}")
        return res

def main():
    parser = argparse.ArgumentParser(description="Cliente y Auditor de Workflows para n8n")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Audita estáticamente archivos de workflows locales")
    audit_parser.add_argument("--path", required=True, help="Ruta al archivo o carpeta con workflows .json")

    # Test connection
    test_parser = subparsers.add_parser("test", help="Verifica conectividad y autenticación con API n8n")
    test_parser.add_argument("--api-url", default="http://localhost:5678", help="URL base de n8n")
    test_parser.add_argument("--api-key", help="API key directa")
    test_parser.add_argument("--api-key-file", help="Ruta a archivo con API key")

    # List workflows
    list_parser = subparsers.add_parser("list", help="Lista workflows registrados vía API de n8n")
    list_parser.add_argument("--api-url", default="http://localhost:5678", help="URL base de n8n")
    list_parser.add_argument("--api-key", help="API key directa")
    list_parser.add_argument("--api-key-file", help="Ruta a archivo con API key")

    # Get workflow
    get_parser = subparsers.add_parser("get", help="Obtiene un workflow específico vía API")
    get_parser.add_argument("--id", required=True, help="ID del workflow")
    get_parser.add_argument("--api-url", default="http://localhost:5678", help="URL base de n8n")
    get_parser.add_argument("--api-key", help="API key directa")
    get_parser.add_argument("--api-key-file", help="Ruta a archivo con API key")

    # Deploy workflow
    deploy_parser = subparsers.add_parser("deploy", help="Despliega y opcionalmente activa un workflow vía API")
    deploy_parser.add_argument("--file", required=True, help="Ruta al archivo .json del workflow")
    deploy_parser.add_argument("--id", help="ID opcional para forzar actualización de un workflow existente")
    deploy_parser.add_argument("--activate", action="store_true", help="Activa el workflow tras desplegarlo")
    deploy_parser.add_argument("--api-url", default="http://localhost:5678", help="URL base de n8n")
    deploy_parser.add_argument("--api-key", help="API key directa")
    deploy_parser.add_argument("--api-key-file", help="Ruta a archivo con API key")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "audit":
        run_audit(args.path)

    elif args.command in ["test", "list", "get", "deploy"]:
        api_key = load_api_key(getattr(args, "api_key", None), getattr(args, "api_key_file", None))
        if not api_key:
            print("[!] Error: No se encontró API key de n8n. Proporciónela vía --api-key, --api-key-file o variable N8N_API_KEY.")
            sys.exit(1)

        masked = mask_token(api_key)
        print(f"[*] Conectando a {args.api_url} usando API Key: {masked}")

        if args.command == "test":
            res = n8n_api_request("workflows?limit=1", args.api_url, api_key)
            if res.get("status") == 200:
                print("[✓] Conexión y autenticación exitosas con la API de n8n.")
            else:
                print(f"[!] Fallo de conexión/autenticación: {res.get('error', res)}")

        elif args.command == "list":
            res = n8n_api_request("workflows", args.api_url, api_key)
            if res.get("status") == 200:
                workflows = res.get("data", {}).get("data", [])
                print(f"[*] Workflows encontrados: {len(workflows)}")
                for wf in workflows:
                    active = "ACTIVO" if wf.get("active") else "INACTIVO"
                    print(f"    - [{wf.get('id')}] {wf.get('name')} ({active})")
            else:
                print(f"[!] Error al listar workflows: {res.get('error', res)}")

        elif args.command == "get":
            res = n8n_api_request(f"workflows/{args.id}", args.api_url, api_key)
            if res.get("status") == 200:
                print(json.dumps(res.get("data"), indent=2, ensure_ascii=False))
            else:
                print(f"[!] Error al obtener workflow {args.id}: {res.get('error', res)}")

        elif args.command == "deploy":
            deploy_workflow(args.file, args.api_url, api_key, activate=args.activate, workflow_id=args.id)

if __name__ == "__main__":
    main()
