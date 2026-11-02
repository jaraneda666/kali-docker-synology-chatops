import paramiko
import base64
import os

def main():
    script_path = os.path.join(os.path.dirname(__file__), "kali_idle_watchdog.sh")
    with open(script_path, "rb") as f:
        content = f.read()

    b64 = base64.b64encode(content).decode("ascii")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.1.100", 22, "admin", os.environ.get("ADMIN_PASS", ""))

    remote_cmd = (
        "echo os.environ.get("ADMIN_PASS", "") | sudo -S bash -c '"
        "mkdir -p /volume1/docker/kali/data/tools && "
        f"echo \"{b64}\" | base64 -d > /volume1/docker/kali/data/tools/kali_idle_watchdog.sh && "
        "chmod 755 /volume1/docker/kali/data/tools/kali_idle_watchdog.sh && "
        "cp /volume1/docker/kali/data/tools/kali_idle_watchdog.sh /volume1/docker/kali/data/kali_idle_watchdog.sh && "
        "chmod 755 /volume1/docker/kali/data/kali_idle_watchdog.sh && "
        "ls -la /volume1/docker/kali/data/tools/kali_idle_watchdog.sh'"
    )

    stdin, stdout, stderr = c.exec_command(remote_cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print("STDOUT:\n", out)
    if err and "Password:" not in err:
        print("STDERR:\n", err)

    c.close()

if __name__ == "__main__":
    main()
