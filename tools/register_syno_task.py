import paramiko
import base64

TASK_CONTENT = """id=30
last work hour=23
can edit owner=1
can delete from ui=1
edit dialog=SYNO.SDS.TaskScheduler.EditDialog
type=daily
action=#common:run#: /bin/bash /volume1/docker/kali/data/tools/kali_idle_watchdog.sh
systemd slice=
monthly week=0
can edit from ui=1
week=1111111
app name=#common:command_line#
name=Kali Idle Watchdog 30m
can run app same time=1
owner=0
repeat min store config=[1,5,10,15,20,30]
repeat hour store config=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]
simple edit form=1
repeat hour=0
listable=1
app args={"notify_enable":false,"notify_if_error":false,"notify_mail":"","script":"/bin/bash /volume1/docker/kali/data/tools/kali_idle_watchdog.sh"}
state=enabled
can run task same time=0
start day=0
cmd=L2Jpbi9iYXNoIC92b2x1bWUxL2RvY2tlci9rYWxpL2RhdGEvdG9vbHMva2FsaV9pZGxlX3dhdGNoZG9nLnNo
run hour=0
edit form=SYNO.SDS.TaskScheduler.Script.FormPanel
app=SYNO.SDS.TaskScheduler.Script
run min=0
start month=0
can edit name=1
start year=0
can run from ui=1
repeat min=5
cmdArgv=
"""

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.1.100", 22, "admin", os.environ.get("ADMIN_PASS", ""))

    b64 = base64.b64encode(TASK_CONTENT.strip().encode("utf-8")).decode("ascii")
    remote_cmd = (
        "echo os.environ.get("ADMIN_PASS", "") | sudo -S bash -c '"
        f"echo \"{b64}\" | base64 -d > /usr/syno/etc/synoschedule.d/root/30.task && "
        "chmod 660 /usr/syno/etc/synoschedule.d/root/30.task && "
        "chown root:administrators /usr/syno/etc/synoschedule.d/root/30.task && "
        "/usr/syno/bin/synoschedtask --sync && "
        "/usr/syno/bin/synoschedtask --get id=30'"
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
