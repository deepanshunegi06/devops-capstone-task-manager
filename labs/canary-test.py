"""Local, reproducible weighted-traffic and failover experiment; no production target."""
import subprocess,time,json,urllib.request,statistics,pathlib,threading
root=pathlib.Path(__file__).resolve().parent; evidence=root.parent.parent/'evidence'; config=root/'proxy';config.mkdir(exist_ok=True)
def cmd(*args):return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT)
image='orbit-labs-app:2.0.1'
for color,version in [('blue','2.0.0'),('green','2.0.1')]:
 cmd('docker','run','-d','--name','orbit-labs-'+color,'--network','orbit-labs_backend','-e','DATABASE_URL=sqlite:////tmp/lab.db','-e','DEPLOY_COLOR='+color,'-e','APP_VERSION='+version,image)
def configure(green,failover=False):
 upstream='server orbit-labs-blue:5000 max_fails=1 fail_timeout=1s; server orbit-labs-green:5000 backup;' if failover else ('server orbit-labs-green:5000;' if green==100 else 'server orbit-labs-blue:5000;' if green==0 else f'server orbit-labs-blue:5000 weight={100-green}; server orbit-labs-green:5000 weight={green};')
 text=f'upstream release {{ {upstream} }}\nserver {{ listen 80; location / {{ proxy_pass http://release; proxy_next_upstream error timeout http_502 http_503; }} }}\n'
 (config/'default.conf').write_text(text)
 if not failover:(root/'canary.conf').write_text(text)
def sample(n=200):
 rows=[]
 for _ in range(n):
  start=time.monotonic()
  try:
   with urllib.request.urlopen('http://127.0.0.1:18081/version',timeout=5) as r: data=json.load(r);rows.append({'status':r.status,'color':data['color'],'ms':(time.monotonic()-start)*1000})
  except Exception as e:rows.append({'status':0,'error':str(e)})
 return rows
time.sleep(3);configure(0)
cmd('docker','run','-d','--name','orbit-labs-proxy','--network','orbit-labs_backend','-p','127.0.0.1:18081:80','-v',str(config)+':/etc/nginx/conf.d:ro','nginx:1.27-alpine');time.sleep(1)
# Sample continuously across blue -> green -> blue reloads.
rows=[]; stop=threading.Event()
def poll():
 while not stop.is_set(): rows.extend(sample(1));time.sleep(.02)
t=threading.Thread(target=poll);t.start();time.sleep(.5)
for target in [100,0]: configure(target);cmd('docker','exec','orbit-labs-proxy','nginx','-s','reload');time.sleep(1)
stop.set();t.join()
(evidence/'blue-green.txt').write_text(json.dumps({'requests_during_switch':len(rows),'errors':sum(x['status']!=200 for x in rows),'observed_colors':sorted(set(x.get('color','error') for x in rows)),'samples':rows[:5]+rows[-5:]},indent=2))
results=[]
for green in [10,50,100,0]:
 configure(green);cmd('docker','exec','orbit-labs-proxy','nginx','-s','reload');time.sleep(1);r=sample()
 times=sorted(x['ms'] for x in r if 'ms'in x)
 results.append({'configured_green_percent':green,'requests':len(r),'blue':sum(x.get('color')=='blue' for x in r),'green':sum(x.get('color')=='green' for x in r),'errors':sum(x['status']!=200 for x in r),'p95_ms':times[int(len(times)*.95)-1]})
(evidence/'canary.txt').write_text(json.dumps(results,indent=2))
configure(0,failover=True);cmd('docker','exec','orbit-labs-proxy','nginx','-s','reload');time.sleep(1)
cmd('docker','stop','orbit-labs-blue');r=sample(20);cmd('docker','start','orbit-labs-blue')
(evidence/'failover.txt').write_text(json.dumps({'scenario':'blue primary stopped; green marked backup','requests':len(r),'success':sum(x['status']==200 for x in r),'green':sum(x.get('color')=='green' for x in r)},indent=2))
configure(0);cmd('docker','exec','orbit-labs-proxy','nginx','-s','reload')
