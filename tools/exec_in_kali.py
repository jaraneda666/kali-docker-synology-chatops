import sys
import paramiko

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.1.100", 22, "admin", os.environ.get("ADMIN_PASS", ""))
    escaped = cmd.replace("'", "'\\''")
    full_cmd = f"echo os.environ.get("ADMIN_PASS", "") | sudo -S /var/packages/ContainerManager/target/usr/bin/docker exec -u 0 kali_linux bash -c '{escaped}'"
    _, stdout, stderr = c.exec_command(full_cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    c.close()
    print("STDOUT:\n" + out)
    print("STDERR:\n" + err)

if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "id"
    run(cmd)
