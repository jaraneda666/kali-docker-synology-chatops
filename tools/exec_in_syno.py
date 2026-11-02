import sys
import paramiko

def run(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.1.100", 22, "admin", os.environ.get("ADMIN_PASS", ""))
    sudo_cmd = f"echo os.environ.get("ADMIN_PASS", "") | sudo -S {cmd}"
    _, stdout, stderr = c.exec_command(sudo_cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    c.close()
    if out:
        print("STDOUT:\n" + out.strip())
    if err and "Password:" not in err:
        print("STDERR:\n" + err.strip())

if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "uname -a"
    run(cmd)
