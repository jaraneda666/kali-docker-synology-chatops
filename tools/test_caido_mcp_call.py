#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import json
import time

def call_mcp(p, req_id, method, params=None):
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    p.stdin.write(json.dumps(payload) + "\n")
    p.stdin.flush()
    line = p.stdout.readline()
    return json.loads(line)

def main():
    p = subprocess.Popen(["python", "tools/caido_mcp_bridge.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # 1. Initialize
    init_res = call_mcp(p, 1, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "Antigravity-Agent", "version": "1.0"}
    })
    print("[*] MCP Initialize:", init_res.get("result", {}).get("serverInfo"))

    # 2. List Projects
    proj_res = call_mcp(p, 2, "tools/call", {
        "name": "caido_list_projects",
        "arguments": {}
    })
    print("[*] List Projects:", proj_res.get("result"))

    # Check if we have an active project or create one
    projects_content = proj_res.get("result", {}).get("content", [])
    has_current = False
    proj_list = []
    if projects_content:
        try:
            data = json.loads(projects_content[0].get("text", "{}"))
            proj_list = data.get("projects", []) if isinstance(data, dict) else data
            for prj in proj_list:
                if prj.get("isCurrent"):
                    has_current = True
                    break
        except Exception as e:
            print("Error parsing projects:", e)

    if not has_current:
        if not proj_list:
            print("[*] Creando nuevo proyecto 'Auditoria_LAN_3000'...")
            create_res = call_mcp(p, 3, "tools/call", {
                "name": "caido_create_project",
                "arguments": {"name": "Auditoria_LAN_3000"}
            })
            print("[+] Create Project:", create_res.get("result"))
            # get list again
            p2 = call_mcp(p, 4, "tools/call", {"name": "caido_list_projects", "arguments": {}})
            data2 = json.loads(p2.get("result", {}).get("content", [])[0].get("text", "{}"))
            proj_list = data2.get("projects", []) if isinstance(data2, dict) else data2
        
        if proj_list:
            target_id = proj_list[0].get("id")
            print(f"[*] Seleccionando proyecto ID: {target_id}...")
            sel_res = call_mcp(p, 5, "tools/call", {
                "name": "caido_select_project",
                "arguments": {"id": target_id}
            })
            print("[+] Select Project:", sel_res.get("result"))

    # 3. Send HTTP Request to 127.0.0.1:3000
    print("[*] Enviando petición HTTP a http://127.0.0.1:3000 vía Caido MCP...")
    raw_req = "GET / HTTP/1.1\r\nHost: 127.0.0.1:3000\r\nUser-Agent: Caido-MCP-Audit/1.0\r\nAccept: */*\r\nConnection: close\r\n\r\n"
    send_res = call_mcp(p, 6, "tools/call", {
        "name": "caido_send_request",
        "arguments": {
            "raw": raw_req,
            "host": "127.0.0.1",
            "port": 3000,
            "tls": False
        }
    })

    print("\n[+] RESULTADO CAIDO MCP SEND_REQUEST:")
    res_content = send_res.get("result", {}).get("content", [])
    for c in res_content:
        text = c.get("text", "")
        try:
            parsed = json.loads(text)
            print(json.dumps(parsed, indent=2))
        except Exception:
            print(text)

    p.terminate()

if __name__ == "__main__":
    main()
