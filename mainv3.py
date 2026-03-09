import requests
import time
import json

EMAIL="0xartezy@gmail.com"
PASSWORD_MD5="9bf1b193b9d15f8908991547b921a8b4"
EXCLUDED_DEVICES=[]  # contoh: ["ATP5CK519UH0B7RH", "APP5BK4M191F1KDX"]
EARLY_PROCEED_THRESHOLD=0  # 0 = run semua device, isi angka untuk early proceed (misal 5)

BASE="https://api.vsphone.com/vsphone/api"

session=requests.Session()

headers={
 "Content-Type":"application/json",
 "Channel":"web",
 "Clienttype":"web",
 "Appversion":"2003602"
}

TOKEN=None
USER_ID=None
REFERRAL_CODE=None
RESOLUTION="1080x1920"
DPI="420"


import datetime, sys

# ── ANSI ─────────────────────────────────────────
_R    = "\033[0m"
_B    = "\033[1m"
_DIM  = "\033[2m"
_CYAN = "\033[96m"
_GRN  = "\033[92m"
_YLW  = "\033[93m"
_RED  = "\033[91m"
_BLU  = "\033[94m"

def _ts():
 return datetime.datetime.now().strftime("%H:%M:%S")

def _pad(code):
 """Shorten padCode for display: last 8 chars"""
 return code[-8:] if len(code) > 8 else code

def log(msg):
 print(f" {_DIM}{_ts()}{_R}  {msg}")

def log_ok(msg):
 print(f" {_DIM}{_ts()}{_R}  {_GRN}✔{_R}  {msg}")

def log_err(msg):
 print(f" {_DIM}{_ts()}{_R}  {_RED}✖{_R}  {_RED}{msg}{_R}")

def log_wait(msg):
 print(f" {_DIM}{_ts()}{_R}  {_YLW}◷{_R}  {msg}", end="\r")
 sys.stdout.flush()

def log_wait_nl(msg):
 print(f" {_DIM}{_ts()}{_R}  {_YLW}◷{_R}  {msg}")

def log_adb(cmd, result=None):
 # Only show result lines — skip the command itself
 if not result:
  return
 try:
  items = json.loads(result)
  for item in items:
   code   = _pad(item.get("padCode","?"))
   status = item.get("taskStatus","?")
   raw    = item.get("cmdResult","").strip()
   # Clean up multi-line monkey/bash noise — keep only first meaningful line
   lines  = [l.strip() for l in raw.splitlines() if l.strip() and not l.strip().startswith("bash arg")]
   out    = lines[0][:72] if lines else ""
   dot    = f"{_GRN}●{_R}" if status == 3 else f"{_YLW}○{_R}"
   if out:
    print(f"            {dot} {_B}{code}{_R}  {_DIM}{out}{_R}")
   else:
    print(f"            {dot} {_B}{code}{_R}")
 except:
  pass

def log_section(title):
 bar = "─" * 48
 print(f"\n {_CYAN}{_B}{bar}{_R}")
 print(f" {_CYAN}{_B}  {title}{_R}")
 print(f" {_CYAN}{_B}{bar}{_R}\n")

def log_progress(done, total, label=""):
 pct   = int(done / total * 20) if total else 0
 bar   = f"{_GRN}{'█'*pct}{_DIM}{'░'*(20-pct)}{_R}"
 print(f" {_DIM}{_ts()}{_R}  {bar}  {_B}{done}/{total}{_R}  {label}", end="\r")
 sys.stdout.flush()

def log_progress_nl(done, total, label=""):
 pct   = int(done / total * 20) if total else 0
 bar   = f"{_GRN}{'█'*pct}{_DIM}{'░'*(20-pct)}{_R}"
 print(f" {_DIM}{_ts()}{_R}  {bar}  {_B}{done}/{total}{_R}  {label}")


# ======================
# LOGIN
# ======================

def login():

 global TOKEN,USER_ID

 payload={
  "mobilePhone":EMAIL,
  "loginType":1,
  "password":PASSWORD_MD5,
  "channel":"web"
 }

 r=session.post(f"{BASE}/user/login",json=payload,headers=headers)
 data=r.json()

 TOKEN=data["data"]["token"]
 USER_ID=data["data"]["userId"]

 headers["token"]=TOKEN
 headers["userid"]=str(USER_ID)

 log_ok("Login success")


# ======================
# GET DEVICES
# ======================

def get_devices():

 r=session.get(
  f"{BASE}/userEquipment/list?supplierType=-1&queryAuthorizedEquipments=true",
  headers=headers
 )

 data=r.json()
 pads=[]

 for g in data.get("data",[]):
  for p in g.get("userPads",[]):
   code=p.get("padCode")
   equipment_id=str(p.get("id") or p.get("equipmentId") or p.get("padId",""))
   log_ok(f"Found device: {code}")
   pads.append({"padCode":code,"equipmentId":equipment_id})

 return pads


# ======================
# SET RESOLUTION AND DPI
# ======================

def set_resolution_dpi(pads):

 pad_codes=[p["padCode"] for p in pads]

 r=session.post(
  f"{BASE}/pcVersion/updateSize",
  json={"padCodeList":pad_codes,"size":RESOLUTION,"density":DPI},
  headers=headers
 )

 if r.status_code==200:
  log_ok(f"Resolution set to {RESOLUTION}, DPI {DPI}")
 else:
  log_err(f"Set resolution failed: {r.status_code}")


# ======================
# RESTART DEVICES
# ======================

def restart_devices(pads):

 pad_codes=[p["padCode"] for p in pads]

 r=session.post(
  f"{BASE}/padManage/padReboot",
  json={"padCodes":pad_codes,"changeIpFlag":False},
  headers=headers
 )

 if r.status_code==200:
  log_ok("Restart command sent to all devices")
 else:
  log_err(f"Restart failed: {r.status_code}")


# ======================
# SEND ADB COMMAND
# ======================

# Commands whose results should NOT be printed (silent execution)
_SILENT_CMDS = ("input tap", "input text", "input keyevent", "monkey", "am start",
                "ime ", "settings put", "uiautomator dump", "ls /sdcard")

def _is_silent(cmd):
 return any(cmd.strip().startswith(s) for s in _SILENT_CMDS)

def send_adb(pads, cmd, timeout=30, interval=3, silent=None):

 pad_codes=[p["padCode"] for p in pads]

 r=session.post(
  f"{BASE}/vcAdb/asyncAdb",
  json={"padCodes":pad_codes,"adbStr":cmd},
  headers=headers
 )

 base_task_id=r.json().get("data","")

 if not base_task_id:
  log_err("Failed to get ADB taskId")
  return

 start=time.time()

 while True:

  elapsed=int(time.time()-start)

  if elapsed>timeout:
   log_err("ADB timeout")
   break

  time.sleep(interval)

  r2=session.post(
   f"{BASE}/vcAdb/getAdbResult",
   json={"baseTaskId":base_task_id},
   headers=headers
  )

  result=r2.json().get("data","")

  if result:
   # Only print result for meaningful commands
   show = silent if silent is not None else not _is_silent(cmd)
   if show:
    log_adb(cmd, result)
   break

  return result



# ======================
# MAIL.TM EMAIL CREATION
# ======================

def get_mailtm_domain():
 r = requests.get("https://api.mail.tm/domains", headers={"Accept":"application/json"})
 data = r.json()
 # API may return a list directly or a hydra object
 if isinstance(data, list):
  domains = data
 else:
  domains = data.get("hydra:member", [])
 if not domains:
  raise Exception("No mail.tm domains available")
 return domains[0]["domain"]

def create_mailtm_account(email, password="Passw0rd123!"):
 payload = {"address": email, "password": password}
 r = requests.post("https://api.mail.tm/accounts", json=payload, headers={"Content-Type":"application/json","Accept":"application/json"})
 if r.status_code not in (200, 201):
  raise Exception(f"Failed to create account: {r.status_code} {r.text}")
 return r.json()

def create_emails_for_devices(devices):
 import random
 log("Fetching mail.tm domain...")
 domain = get_mailtm_domain()
 log_ok(f"Using domain: @{domain}")

 import string as _str
 device_emails = {}
 used = set()

 def gen_email(domain):
  while True:
   # 5-6 random lowercase letters + 2-3 digits = 8-9 chars total
   letters = ''.join(random.choices(_str.ascii_lowercase, k=random.randint(5,6)))
   digits  = ''.join(random.choices(_str.digits, k=random.randint(2,3)))
   name = letters + digits  # e.g. "kxmvra27"
   addr = f"{name}@{domain}"
   if addr not in used:
    used.add(addr)
    return addr

 device_emails = {}
 for d in devices:
  password = "Passw0rd123!"
  success = False
  for attempt in range(1, 11):  # max 10 attempts per device
   email = gen_email(domain)
   try:
    create_mailtm_account(email, password)
    device_emails[d["padCode"]] = {"email": email, "password": password}
    log_ok(f"{d['padCode']} -> {email}")
    success = True
    break
   except Exception as e:
    err_str = str(e)
    if "429" in err_str:
     wait = attempt * 3  # 3s, 6s, 9s, 12s backoff
     log_wait_nl(f"{d['padCode']} rate limited (429), waiting {wait}s before retry ({attempt}/10)...")
     time.sleep(wait)
    else:
     log_err(f"{d['padCode']} email failed ({email}): {e}")
     break
  if not success:
   log_err(f"{d['padCode']} — could not create email after 10 attempts")

 return device_emails

# ======================
# MAIN
# ======================

def main():

 global REFERRAL_CODE, EXCLUDED_DEVICES

 print()
 print(f" {_CYAN}{_B}{'━'*48}{_R}")
 print(f" {_CYAN}{_B}{'VSPhone Bot':^50}{_R}")
 print(f" {_CYAN}{_B}{'━'*48}{_R}")
 print()

 log("Logging in...")
 login()

 log("Fetching devices...")
 devices=get_devices()

 if EXCLUDED_DEVICES:
  before=len(devices)
  devices=[d for d in devices if d["padCode"] not in EXCLUDED_DEVICES]
  skipped=before-len(devices)
  if skipped:
   for ex in EXCLUDED_DEVICES:
    log(f"  ⊘  {ex} — excluded (manual use)")
  
 log_ok(f"Total devices: {len(devices)}")

 print()
 log("Setting resolution and DPI...")
 set_resolution_dpi(devices)

 print()
 log("Waiting 5 seconds before restart...")
 time.sleep(5)

 log("Restarting all devices...")
 restart_devices(devices)

 print()
 log("Waiting 2 minutes for devices to reboot...")
 for remaining in range(120,0,-10):
  print(f"  {_DIM}  Rebooting... {_YLW}{remaining:3d}s{_R}", end="\r", flush=True)
  time.sleep(10)
 print(" " * 40, end="\r")
 log_ok("Devices back online")

 print()
 log("Opening browser and downloading TopNod APK...")

 def open_browser(pads):
  send_adb(pads,"am start -a android.intent.action.VIEW -d https://statistic.topnod.com/TopNod.apk -p com.android.yzbrowser")
  time.sleep(5)
  tap_ok=(
   "uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 && "
   "BOUNDS=$(grep -o 'text=\"OK\"[^>]*bounds=\"[^\"]*\"' /sdcard/ui.xml | grep -o 'bounds=\"[^\"]*\"' | head -1 | grep -o '[0-9 ]*') && "
   "X1=$(echo $BOUNDS | awk '{print $1}') && Y1=$(echo $BOUNDS | awk '{print $2}') && "
   "X2=$(echo $BOUNDS | awk '{print $3}') && Y2=$(echo $BOUNDS | awk '{print $4}') && "
   "input tap $(( (X1+X2)/2 )) $(( (Y1+Y2)/2 ))"
  )
  send_adb(pads,tap_ok)

 open_browser(devices)

 print()
 log("Waiting for TopNod.apk to download (max 6 min, auto-retry)...")

 pending=list(devices)
 retried=set()

 for i in range(36):
  time.sleep(10)
  r=session.post(
   f"{BASE}/vcAdb/asyncAdb",
   json={"padCodes":[d["padCode"] for d in pending],"adbStr":"ls /sdcard/Download/TopNod.apk 2>/dev/null && echo FOUND || echo NOT_FOUND"},
   headers=headers
  )
  task_id=r.json().get("data","")
  time.sleep(5)
  r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
  result=r2.json().get("data","")
  if result:
   try:
    items=json.loads(result)
    done=[x["padCode"] for x in items if "FOUND" in x.get("cmdResult","") and "NOT_FOUND" not in x.get("cmdResult","")]
    not_done=[x["padCode"] for x in items if "NOT_FOUND" in x.get("cmdResult","")]
    pending=[d for d in pending if d["padCode"] not in done]
    done_count = len(devices)-len(pending)
    log_progress(done_count, len(devices), "downloading")
    if not pending:
     print()
     log_ok("All devices finished downloading!")
     break
    # Retry device yang belum download setelah 30 detik
    for d in pending:
     if d["padCode"] not in retried and (i+1)*10 >= 30:
      log_err(f"Retrying browser on {d['padCode']}...")
      open_browser([d])
      retried.add(d["padCode"])
   except:
    pass
 else:
  log_err("Download timeout, proceeding with downloaded devices only...")

 # === CONFIRM APK FILE EXISTS BEFORE INSTALL ===
 print()
 log("Final confirmation: checking APK file on all devices...")
 r=session.post(
  f"{BASE}/vcAdb/asyncAdb",
  json={"padCodes":[d["padCode"] for d in devices],"adbStr":"ls -lh /sdcard/Download/TopNod.apk 2>/dev/null && echo APK_OK || echo APK_MISSING"},
  headers=headers
 )
 task_id=r.json().get("data","")
 time.sleep(5)
 r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
 result=r2.json().get("data","")
 apk_ready=[]
 apk_missing=[]
 if result:
  try:
   items=json.loads(result)
   apk_ready=[x["padCode"] for x in items if "APK_OK" in x.get("cmdResult","")]
   apk_missing=[x["padCode"] for x in items if "APK_MISSING" in x.get("cmdResult","")]
   if apk_ready:
    log_ok(f"APK confirmed on {len(apk_ready)} device(s): {apk_ready}")
   if apk_missing:
    log_err(f"APK missing on {len(apk_missing)} device(s): {apk_missing} — skipping those")
    devices=[d for d in devices if d["padCode"] not in apk_missing]
  except:
   pass

 time.sleep(3)

 print()
 log("Tapping INSTALL on all devices...")
 tap_install=(
  "uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 && "
  "BOUNDS=$(grep -o 'text=\"INSTALL\"[^>]*bounds=\"[^\"]*\"' /sdcard/ui.xml | grep -o 'bounds=\"[^\"]*\"' | head -1 | grep -o '[0-9 ]*') && "
  "X1=$(echo $BOUNDS | awk '{print $1}') && Y1=$(echo $BOUNDS | awk '{print $2}') && "
  "X2=$(echo $BOUNDS | awk '{print $3}') && Y2=$(echo $BOUNDS | awk '{print $4}') && "
  "input tap $(( (X1+X2)/2 )) $(( (Y1+Y2)/2 ))"
 )
 send_adb(devices,tap_install)

 log("Waiting for installation to complete...")
 installed_so_far = []

 for i in range(22):  # max ~3 menit
  time.sleep(10)

  r=session.post(
   f"{BASE}/vcAdb/asyncAdb",
   json={"padCodes":[d["padCode"] for d in devices],"adbStr":"pm list packages | grep -i topnod"},
   headers=headers
  )
  task_id=r.json().get("data","")

  # Poll result hingga semua device return atau timeout 20s
  for _p in range(10):
   time.sleep(2)
   r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
   raw=r2.json().get("data","")
   if raw:
    try:
     items=json.loads(raw)
     if len(items)==len(devices):  # semua device sudah return
      break
    except: pass

  if raw:
   try:
    items=json.loads(raw)
    installed_so_far=[x["padCode"] for x in items if x.get("cmdResult","").strip()]
   except: pass

  log_progress(len(installed_so_far), len(devices), "installing")

  if EARLY_PROCEED_THRESHOLD and len(installed_so_far) >= EARLY_PROCEED_THRESHOLD:
   print()
   log_ok(f"{len(installed_so_far)}/{len(devices)} device(s) installed — proceeding without waiting for the rest...")
   skipped_install=[d["padCode"] for d in devices if d["padCode"] not in installed_so_far]
   if skipped_install:
    for s in skipped_install: log_err(f"  {s} — install not complete, skipped")
    log(f"Menjalankan 'Perangkat Baru Satu Klik' pada {len(skipped_install)} device yang diskip...")
    r_skip=session.post(
     f"{BASE}/padManage/replacePad",
     json={"padCodes": skipped_install, "goodFingerprintBrand": "", "setProxyFlag": False},
     headers=headers
    )
    if r_skip.status_code == 200:
     log_ok(f"Perangkat Baru Satu Klik berhasil dikirim ke: {skipped_install}")
    else:
     log_err(f"Perangkat Baru Satu Klik gagal: {r_skip.status_code}")
   break

  if len(installed_so_far)==len(devices):
   print()
   log_ok("TopNod installed on all devices!")
   break
 else:
  print()
  timed_out=[d["padCode"] for d in devices if d["padCode"] not in installed_so_far]
  if timed_out:
   log_err(f"Install timeout — {len(timed_out)} device(s) belum terinstall, skipped:")
   for s in timed_out: log_err(f"  {s} — install timeout, skipped")
   log(f"Menjalankan 'Perangkat Baru Satu Klik' pada {len(timed_out)} device timeout...")
   r_to=session.post(
    f"{BASE}/padManage/replacePad",
    json={"padCodes": timed_out, "goodFingerprintBrand": "", "setProxyFlag": False},
    headers=headers
   )
   if r_to.status_code == 200:
    log_ok(f"Perangkat Baru Satu Klik berhasil dikirim ke: {timed_out}")
   else:
    log_err(f"Perangkat Baru Satu Klik gagal: {r_to.status_code}")
  else:
   log_err("Install timeout, proceeding anyway...")

 # Trim devices to only those confirmed installed
 devices=[d for d in devices if d["padCode"] in installed_so_far]

 # === CONFIRM INSTALLATION ===
 print()
 log("Final confirmation: verifying installed packages on all devices...")
 r=session.post(
  f"{BASE}/vcAdb/asyncAdb",
  json={"padCodes":[d["padCode"] for d in devices],
        "adbStr":"pm list packages | grep -E 'com.ant.dt.topnod|com.topnod' | head -1 || echo NOT_INSTALLED"},
  headers=headers
 )
 task_id=r.json().get("data","")
 time.sleep(5)
 r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
 result=r2.json().get("data","")
 confirmed_installed=[]
 failed_install=[]
 if result:
  try:
   items=json.loads(result)
   confirmed_installed=[x["padCode"] for x in items if x.get("cmdResult","").strip() and "NOT_INSTALLED" not in x.get("cmdResult","")]
   failed_install=[x["padCode"] for x in items if not x.get("cmdResult","").strip() or "NOT_INSTALLED" in x.get("cmdResult","")]
   if confirmed_installed:
    log_ok(f"Install confirmed on {len(confirmed_installed)} device(s): {confirmed_installed}")
   if failed_install:
    log_err(f"Install FAILED on {len(failed_install)} device(s): {failed_install}")
    # Retry install on failed devices
    retry_pads=[d for d in devices if d["padCode"] in failed_install]
    log(f"Retrying install on {[d['padCode'] for d in retry_pads]}...")
    send_adb(retry_pads, tap_install)
    time.sleep(15)
    # Re-check after retry
    r=session.post(
     f"{BASE}/vcAdb/asyncAdb",
     json={"padCodes":[d["padCode"] for d in retry_pads],
           "adbStr":"pm list packages | grep -E 'com.ant.dt.topnod|com.topnod' | head -1 || echo NOT_INSTALLED"},
     headers=headers
    )
    task_id=r.json().get("data","")
    time.sleep(5)
    r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
    result=r2.json().get("data","")
    if result:
     try:
      items=json.loads(result)
      now_ok=[x["padCode"] for x in items if x.get("cmdResult","").strip() and "NOT_INSTALLED" not in x.get("cmdResult","")]
      still_fail=[x["padCode"] for x in items if not x.get("cmdResult","").strip() or "NOT_INSTALLED" in x.get("cmdResult","")]
      if now_ok: log_ok(f"Install retry succeeded on: {now_ok}")
      if still_fail: log_err(f"Install still failed on: {still_fail} — skipping")
      devices=[d for d in devices if d["padCode"] not in still_fail]
     except:
      pass
  except:
   pass

 # === OPEN APP WITH CONFIRMATION ===
 print()
 log("Opening TopNod app on all devices...")
 send_adb(devices,"monkey -p com.ant.dt.topnod -c android.intent.category.LAUNCHER 1 2>/dev/null || monkey -p com.topnod.app 1 2>/dev/null || monkey -p com.topnod 1 2>/dev/null")

 # === CONFIRM APP IS RUNNING ===
 time.sleep(5)
 log("Confirming app is running on all devices...")
 r=session.post(
  f"{BASE}/vcAdb/asyncAdb",
  json={"padCodes":[d["padCode"] for d in devices],
        "adbStr":"dumpsys activity activities | grep -E 'com.ant.dt.topnod|com.topnod' | grep -c 'mResumedActivity' || echo 0"},
  headers=headers
 )
 task_id=r.json().get("data","")
 time.sleep(5)
 r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
 result=r2.json().get("data","")
 if result:
  try:
   items=json.loads(result)
   app_running=[x["padCode"] for x in items if x.get("cmdResult","").strip() not in ("0","")]
   app_not_running=[x["padCode"] for x in items if x.get("cmdResult","").strip() in ("0","")]
   if app_running:
    log_ok(f"App confirmed running on {len(app_running)} device(s): {app_running}")
   if app_not_running:
    log_err(f"App not detected on {len(app_not_running)} device(s): {app_not_running} — retrying open...")
    retry_pads=[d for d in devices if d["padCode"] in app_not_running]
    send_adb(retry_pads,"monkey -p com.ant.dt.topnod -c android.intent.category.LAUNCHER 1 2>/dev/null || monkey -p com.topnod.app 1 2>/dev/null")
  except:
   pass

 print()
 log("Waiting 7 seconds for app to load...")
 time.sleep(7)

 # === TAP CREATE WALLET (540, 1536) with verification ===
 print()
 log("Tapping 'Create Wallet' at (540, 1536) with verification...")
 for attempt in range(1, 3):
  log(f"Create Wallet - attempt {attempt}...")
  send_adb(devices, "input tap 540 1536")
  time.sleep(2)
  # Verify: dump UI and check if 'Create Wallet' button is gone (screen changed)
  r=session.post(
   f"{BASE}/vcAdb/asyncAdb",
   json={"padCodes":[d["padCode"] for d in devices],
         "adbStr":"uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 && grep -c 'Create Wallet' /sdcard/ui.xml || echo 0"},
   headers=headers
  )
  task_id=r.json().get("data","")
  time.sleep(5)
  r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
  result=r2.json().get("data","")
  if result:
   try:
    items=json.loads(result)
    still_visible=[x["padCode"] for x in items if x.get("cmdResult","").strip() not in ("0","")]
    gone=[x["padCode"] for x in items if x.get("cmdResult","").strip() in ("0","")]
    if gone:
     log_ok(f"Create Wallet confirmed tapped on: {gone}")
    if still_visible:
     log_err(f"Create Wallet still visible on: {still_visible}, retrying tap...")
     # Retry tap on devices that still show the button
     retry_pads=[d for d in devices if d["padCode"] in still_visible]
     send_adb(retry_pads, "input tap 540 1536")
     time.sleep(2)
    if not still_visible:
     break
   except:
    pass
 else:
  log_ok("Create Wallet done")

 log("Waiting 3 seconds...")
 time.sleep(3)

 # === TAP AGREE (540, 1728) with verification ===
 print()
 log("Tapping 'Agree' at (540, 1728) with verification...")
 for attempt in range(1, 3):
  log(f"Agree - attempt {attempt}...")
  send_adb(devices, "input tap 540 1728")
  time.sleep(2)
  # Verify: dump UI and check if 'Agree' button is gone (screen changed)
  r=session.post(
   f"{BASE}/vcAdb/asyncAdb",
   json={"padCodes":[d["padCode"] for d in devices],
         "adbStr":"uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 && grep -c 'Agree' /sdcard/ui.xml || echo 0"},
   headers=headers
  )
  task_id=r.json().get("data","")
  time.sleep(5)
  r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
  result=r2.json().get("data","")
  if result:
   try:
    items=json.loads(result)
    still_visible=[x["padCode"] for x in items if x.get("cmdResult","").strip() not in ("0","")]
    gone=[x["padCode"] for x in items if x.get("cmdResult","").strip() in ("0","")]
    if gone:
     log_ok(f"Agree confirmed tapped on: {gone}")
    if still_visible:
     log_err(f"Agree still visible on: {still_visible}, retrying tap...")
     retry_pads=[d for d in devices if d["padCode"] in still_visible]
     send_adb(retry_pads, "input tap 540 1728")
     time.sleep(2)
    if not still_visible:
     break
   except:
    pass
 else:
  log_ok("Agree done")

 # === TAP REFERRAL CODE BUTTON (540, 1012) ===
 print()
 log("Waiting 3 seconds for next screen...")
 time.sleep(3)

 log("Tapping 'Referral Code' button at (540, 1012)...")
 send_adb(devices, "input tap 540 1012")
 time.sleep(2)
 log_ok("Referral Code tapped")


 # === TAP "Enter other's referral code" (540, 1100) ===
 print()
 log("Waiting 2 seconds...")
 time.sleep(2)

 log("Tapping \"Enter other's referral code\" at (540, 1100)...")
 send_adb(devices, "input tap 540 1100")
 time.sleep(1)
 log_ok("Field tapped")

 # === TYPE REFERRAL CODE ===
 print()
 log(f"Typing referral code: {REFERRAL_CODE}")
 send_adb(devices, f"input text '{REFERRAL_CODE}'")
 send_adb(devices, "input keyevent 4")  # dismiss keyboard
 time.sleep(2)

 # Verify referral code was typed
 r=session.post(
  f"{BASE}/vcAdb/asyncAdb",
  json={"padCodes":[d["padCode"] for d in devices],
        "adbStr":f"uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 && grep -c '{REFERRAL_CODE}' /sdcard/ui.xml || echo 0"},
  headers=headers
 )
 task_id=r.json().get("data","")
 time.sleep(5)
 r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
 result=r2.json().get("data","")
 if result:
  try:
   items=json.loads(result)
   typed=[x["padCode"] for x in items if x.get("cmdResult","").strip() not in ("0","")]
   not_typed=[x["padCode"] for x in items if x.get("cmdResult","").strip() in ("0","")]
   if typed:
    log_ok(f"Referral code confirmed typed on: {typed}")
   if not_typed:
    log_err(f"Referral code not detected on: {not_typed}, retrying input...")
    retry_pads=[d for d in devices if d["padCode"] in not_typed]
    send_adb(retry_pads, "input tap 540 1100")
    time.sleep(1)
    send_adb(retry_pads, f"input text '{REFERRAL_CODE}'")
    send_adb(retry_pads, "input keyevent 4")  # dismiss keyboard
    time.sleep(2)
  except:
   pass

 # === CONFIRM WITH ENTER ===
 print()
 log("Pressing Enter to confirm referral code...")
 send_adb(devices, "input keyevent 66")
 time.sleep(2)


 log_ok("Referral code submitted!")

 # === CREATE EMAIL PER DEVICE (mail.tm) ===
 print()
 log("Creating unique email for each device via mail.tm...")
 device_emails = create_emails_for_devices(devices)

 print()
 log("Filling email into field at (540, 595) per device...")
 time.sleep(2)
 for d in devices:
  pad = d["padCode"]
  if pad not in device_emails:
   log(f"{pad}: no email, skipping")
   continue
  email = device_emails[pad]["email"]
  log(f"{pad} -> typing email: {email}")
  # Tap email field, type, dismiss keyboard
  session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":"input tap 540 595"},headers=headers)
  time.sleep(1)
  session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":f"input text '{email}'"},headers=headers)
  session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":"input keyevent 4"},headers=headers)  # dismiss keyboard
  time.sleep(2)
  # Verify
  r=session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":f"uiautomator dump /sdcard/ui.xml>/dev/null 2>&1 && grep -c '{email.split(chr(64))[0]}' /sdcard/ui.xml||echo 0"},headers=headers)
  task_id=r.json().get("data","")
  time.sleep(5)
  r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
  result=r2.json().get("data","")
  try:
   items=json.loads(result)
   if items and items[0].get("cmdResult","").strip() not in ("0",""):
    log_ok(f"{pad}: email confirmed in field")
   else:
    log_err(f"{pad}: retrying email input...")
    session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":"input tap 540 595"},headers=headers)
    time.sleep(1)
    session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":f"input text '{email}'"},headers=headers)
    session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":"input keyevent 4"},headers=headers)  # dismiss keyboard
    time.sleep(2)
  except:
   pass

 # === CLICK SEND (950, 860) ===
 print()
 log("Clicking Send button at (950, 860) on all devices...")
 send_adb(devices, "input tap 950 860")
 time.sleep(3)
 log_ok("Send clicked — captcha may appear")

 # === WAIT FOR MANUAL CAPTCHA ===
 print()
 print(f" {_YLW}{_B}{'━'*48}{_R}")
 print(f" {_YLW}{_B}  ⚠  CAPTCHA  —  solve manually on each device{_R}")
 print(f" {_YLW}{_B}{'━'*48}{_R}")
 input(f" {_YLW}  Press ENTER when ALL captchas are solved...{_R}  ")
 print()

 # === CLICK OTP FIELD (540, 860) ===
 print()
 log("Clicking OTP field at (540, 860) on all devices...")
 send_adb(devices, "input tap 540 860")
 time.sleep(1)
 log_ok("OTP field tapped")

 # === FETCH OTP FROM MAIL.TM PER DEVICE ===
 print()
 log("Fetching OTP from email inboxes...")
 time.sleep(5)

 def get_mailtm_token(email, password):
  r = requests.post("https://api.mail.tm/token",
   json={"address": email, "password": password},
   headers={"Content-Type":"application/json"})
  return r.json().get("token","")

 def get_otp_from_inbox(email, password, retries=3, wait=6):
  import re
  token = get_mailtm_token(email, password)
  if not token:
   return None
  headers_mail = {"Authorization": f"Bearer {token}", "Accept":"application/json"}
  for attempt in range(retries):
   r = requests.get("https://api.mail.tm/messages", headers=headers_mail)
   messages = r.json()
   if isinstance(messages, list):
    msgs = messages
   else:
    msgs = messages.get("hydra:member", [])
   if msgs:
    # Get latest message content
    msg_id = msgs[0]["id"]
    r2 = requests.get(f"https://api.mail.tm/messages/{msg_id}", headers=headers_mail)
    msg = r2.json()
    text = msg.get("text","") or msg.get("html","") or ""
    # Extract OTP: look for 4-8 digit number
    match = re.search(r'\b(\d{4,8})\b', text)
    if match:
     return match.group(1)
   log_wait_nl(f"No OTP yet, retrying... ({attempt+1}/{retries})")
   time.sleep(wait)
  return None

 otp_failed_devices = []

 for d in devices:
  pad = d["padCode"]
  if pad not in device_emails:
   continue
  email = device_emails[pad]["email"]
  password = device_emails[pad]["password"]
  log(f"{pad}: fetching OTP for {email}...")
  otp = get_otp_from_inbox(email, password)
  if not otp:
   log_err(f"{pad}: OTP not received — registrasi gagal, skipped")
   otp_failed_devices.append(pad)
   continue
  log_ok(f"{pad}: OTP = {otp}")
  # Tap OTP field, type, dismiss keyboard
  session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":"input tap 540 860"},headers=headers)
  time.sleep(1)
  session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":f"input text '{otp}'"},headers=headers)
  session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":"input keyevent 4"},headers=headers)  # dismiss keyboard
  time.sleep(2)
  # Verify OTP in field
  r=session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":f"uiautomator dump /sdcard/ui.xml>/dev/null 2>&1 && grep -c '{otp}' /sdcard/ui.xml||echo 0"},headers=headers)
  task_id=r.json().get("data","")
  time.sleep(5)
  r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
  result=r2.json().get("data","")
  try:
   items=json.loads(result)
   if items and items[0].get("cmdResult","").strip() not in ("0",""):
    log_ok(f"{pad}: OTP confirmed in field")
   else:
    log_err(f"{pad}: OTP not detected in field, retrying...")
    session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":"input tap 540 860"},headers=headers)
    time.sleep(1)
    session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":f"input text '{otp}'"},headers=headers)
    session.post(f"{BASE}/vcAdb/asyncAdb",json={"padCodes":[pad],"adbStr":"input keyevent 4"},headers=headers)  # dismiss keyboard
    time.sleep(2)
  except:
   pass

 if otp_failed_devices:
  print()
  log(f"Menjalankan 'Perangkat Baru Satu Klik' pada {len(otp_failed_devices)} device gagal OTP...")
  r_otp=session.post(
   f"{BASE}/padManage/replacePad",
   json={"padCodes": otp_failed_devices, "goodFingerprintBrand": "", "setProxyFlag": False},
   headers=headers
  )
  if r_otp.status_code == 200:
   log_ok(f"Perangkat Baru Satu Klik berhasil: {otp_failed_devices}")
  else:
   log_err(f"Perangkat Baru Satu Klik gagal: {r_otp.status_code}")
  devices=[d for d in devices if d["padCode"] not in otp_failed_devices]

 print()
 log_ok("Email assignment complete!")
 print()
 log("Summary of device emails:")
 for pad, info in device_emails.items():
  log_ok(f"  {pad} -> {info['email']}")

 # === CLICK NEXT (540, 1344) ===
 print()
 log("Clicking Next at (540, 1344) on all devices...")
 send_adb(devices, "input tap 540 1344")
 time.sleep(2)
 log_ok("Next clicked")

 # === SET PASSWORD ===
 # Koordinat field Password dan Confirm Password — sesuaikan jika perlu
 PASSWORD      = "Max7000."
 PASS_FIELD    = (540, 807)   # Enter your password    (mid of 765-850)
 CONFIRM_FIELD = (540, 1070)  # Re-enter your password (mid of 1040-1100)
 CHECKBOX      = (76,  1506)  # Checkbox               (mid of 42-110, 1462-1550)
 CONTINUE_BTN  = (640, 1715)  # Continue               (mid of 602-678, 1670-1760)

 print()
 log("Waiting 2 seconds for Set Password screen...")
 time.sleep(2)

 # Tap & isi Password field
 log(f"Tapping Password field at {PASS_FIELD}...")
 send_adb(devices, f"input tap {PASS_FIELD[0]} {PASS_FIELD[1]}")
 time.sleep(1)
 log("Typing password...")
 send_adb(devices, f"input text '{PASSWORD}'")
 send_adb(devices, "input keyevent 4")  # dismiss keyboard
 time.sleep(1)

 # Tap & isi Confirm Password field
 log(f"Tapping Confirm Password field at {CONFIRM_FIELD}...")
 send_adb(devices, f"input tap {CONFIRM_FIELD[0]} {CONFIRM_FIELD[1]}")
 time.sleep(1)
 log("Typing confirm password...")
 send_adb(devices, f"input text '{PASSWORD}'")
 send_adb(devices, "input keyevent 4")  # dismiss keyboard
 time.sleep(1)

 # Tap checkbox
 log(f"Tapping checkbox at {CHECKBOX}...")
 send_adb(devices, f"input tap {CHECKBOX[0]} {CHECKBOX[1]}")
 time.sleep(1)

 # Tap Continue
 log(f"Tapping Continue at {CONTINUE_BTN}...")
 send_adb(devices, f"input tap {CONTINUE_BTN[0]} {CONTINUE_BTN[1]}")
 time.sleep(2)
 log_ok("Password set, Continue tapped")

 # === CLICK SKIP (980, 125) ===
 print()
 log("Waiting 2 seconds for next screen...")
 time.sleep(2)
 log("Tapping Skip at (980, 125)...")
 send_adb(devices, "input tap 980 125")
 time.sleep(2)
 log_ok("Skip tapped")

 # === CLICK SET UP LATER (540, 1700) ===
 print()
 log("Tapping 'Set up later' at (540, 1700)...")
 send_adb(devices, "input tap 540 1700")
 time.sleep(2)
 log_ok("Set up later tapped")

 # === VERIFY ACCOUNT CREATION SUCCESS (3x retry, 5s delay) ===
 print()
 log("Waiting 6 seconds for Welcome screen...")
 time.sleep(6)

 success_devices=[]
 failed_devices=list(devices)  # start assuming all failed

 for attempt in range(1, 4):
  check_pads=[d["padCode"] for d in failed_devices]
  log(f"Verifying Welcome screen — attempt {attempt}/3 ({len(check_pads)} device(s))...")

  # Send to all pending devices individually to avoid partial result
  all_items=[]
  for pad in check_pads:
   r=session.post(
    f"{BASE}/vcAdb/asyncAdb",
    json={"padCodes":[pad],
          "adbStr":"uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 && grep -c 'Welcome to TopNod' /sdcard/ui.xml || echo 0"},
    headers=headers
   )
   task_id=r.json().get("data","")
   time.sleep(6)  # wait longer for uiautomator to complete
   # Poll until data is not empty (max 10x, 2s interval)
   result=""
   for _poll in range(10):
    r2=session.post(f"{BASE}/vcAdb/getAdbResult",json={"baseTaskId":task_id},headers=headers)
    raw=r2.json()
    result=raw.get("data","")
    if result:
     break
    time.sleep(2)
   if result:
    try:
     items=json.loads(result) if isinstance(result,str) else result
     if isinstance(items,dict): items=[items]
     all_items.extend(items)
    except:
     pass

  newly_ok=[x["padCode"] for x in all_items if x.get("cmdResult","").strip() not in ("0","")]
  still_fail=[x["padCode"] for x in all_items if x.get("cmdResult","").strip() in ("0","")]

  for pad in newly_ok:
   if pad not in success_devices:
    success_devices.append(pad)
    log_ok(f"  {pad} — Welcome screen detected")

  failed_devices=[d for d in devices if d["padCode"] in still_fail]

  if not failed_devices:
   break
  if attempt < 3:
   log(f"  {len(failed_devices)} device(s) not yet detected, retrying in 5s...")
   time.sleep(5)

 # === PERANGKAT BARU SATU KLIK ===
 print()
 log("Menjalankan 'Perangkat Baru Satu Klik' pada semua perangkat...")
 pad_codes = [d["padCode"] for d in devices]
 r = session.post(
  f"{BASE}/padManage/replacePad",
  json={"padCodes": pad_codes, "goodFingerprintBrand": "", "setProxyFlag": False},
  headers=headers
 )
 if r.status_code == 200:
  log_ok("Perangkat Baru Satu Klik berhasil dikirim ke semua perangkat")
 else:
  log_err(f"Perangkat Baru Satu Klik gagal: {r.status_code} {r.text[:100]}")

 # === ACCOUNT CREATION RESULT ===
 print()
 print(f" {_CYAN}{_B}{'━'*48}{_R}")
 print(f" {_CYAN}{_B}  Account Creation Result{_R}")
 print(f" {_CYAN}{_B}{'━'*48}{_R}")
 print()
 if success_devices:
  for pad in success_devices:
   email = device_emails.get(pad,{}).get("email","?")
   log_ok(f"  {pad}  →  {email}")
 if failed_devices:
  for pad in failed_devices:
   email = device_emails.get(pad,{}).get("email","?")
   log_err(f"  {pad}  →  {email}  (Welcome screen not detected)")
 if otp_failed_devices:
  for pad in otp_failed_devices:
   email = device_emails.get(pad,{}).get("email","?")
   log_err(f"  {pad}  →  {email}  (OTP tidak diterima)")
 print()
 total = EARLY_PROCEED_THRESHOLD if EARLY_PROCEED_THRESHOLD else len(devices)+len(otp_failed_devices)
 log_ok(f"Success: {len(success_devices)}/{total} devices")
 if failed_devices:
  log_err(f"Failed (Welcome screen) : {len(failed_devices)}/{total} devices")
 if otp_failed_devices:
  log_err(f"Failed (OTP)            : {len(otp_failed_devices)}/{total} devices")
 print()

 log_section("All tasks completed ✔")


if __name__=="__main__":
 REFERRAL_CODE=input("[?] Masukkan kode referral: ").strip()
 main()