#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import subprocess

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bin_path = os.path.join(base_dir, "caido-mcp-server.exe")
    url = "http://192.168.1.150:8080"
    
    print("[*] Iniciando proceso de autenticación Caido MCP en segundo plano...", flush=True)
    p = subprocess.Popen([bin_path, "login", "--url", url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    
    for line in iter(p.stdout.readline, ''):
        print(line, end='', flush=True)
        
    p.wait()
    token_path = os.path.expanduser("~/.caido-mcp/token.json")
    if os.path.exists(token_path):
        print(f"\n[+] ¡Autenticación exitosa! Token guardado en: {token_path}", flush=True)
    else:
        print(f"\n[-] No se encontró el token tras finalizar el proceso (Code: {p.returncode})", flush=True)

if __name__ == "__main__":
    main()
