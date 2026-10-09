// One offline display of the exact Python 3.12 physical report; no CaptureSuite import.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';

const ROOT=path.dirname(fileURLToPath(import.meta.url));
const CFG=JSON.parse(fs.readFileSync(path.join(ROOT,'AUTHORITY.json'),'utf8'));
const REPORT=path.join(ROOT,'recorded-events.html');
const URI=pathToFileURL(REPORT).href;
const PYTHON='/Library/Frameworks/Python.framework/Versions/3.13/bin/python3';
const CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PROFILE=path.join(ROOT,'browser','profile');
const OUTPUT=path.join(ROOT,'results');
const CONTRACT='7fd938b783feb56b3f7bbb29ae52d60146359600';
const MIN_DISK=256*1024**2,MIN_MEMORY=2*1024**3,STATIC_CAP=2*1024**2,BROWSER_CAP=96*1024**2;
const started=performance.now();
const receipt={schema:'capturesuite-independent-offline-browser-v1',contract:CONTRACT,
 scope:['same physical Python3.12 HTML bytes on Mac','private headless Chrome through inherited CDP pipe',
 'no application/debugging TCP listener, CaptureSuite import, default profile, Finder or regenerated report',
 'pointer and keyboard use of native links/details; programmatic scrolling only for targeting and screenshot framing',
 'large integer authority is the frozen Python comparison; browser text is compared as exact strings'],
 groups:{C4_semantics:'pending',C5_mac:'pending',visual_review:'pending: inspect original screenshots after execution'},
 accepted:false,actions:[],observations:{exceptions:[],console:[],log:[],requests:[],responses:[],loading_failed:[]},
 browser:{},guards:[],failure:null};
let chrome=null,chromeExit=null,chromeStarted=null,deadlineTimer=null,profileTimer=null;
let connection=null,session=null,boundaryError=null,before=null;
let chromeStdout=[],chromeStderr=[],stdoutBytes=0,stderrBytes=0,watchPids=new Set();
function require(ok,msg){if(!ok)throw new Error(msg);}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function pin(b){return {bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex'),
 git_blob:crypto.createHash('sha1').update(Buffer.from('blob '+b.length+'\0')).update(b).digest('hex')};}
function samePin(a,b){return ['bytes','sha256','git_blob'].every(k=>a[k]===b[k]);}
function fileIdentity(p){const s=fs.lstatSync(p,{bigint:true});require(s.isFile()&&!s.isSymbolicLink(),'regular file required: '+p);
 const b=fs.readFileSync(p),after=fs.lstatSync(p,{bigint:true});
 require(s.ino===after.ino&&s.size===after.size&&s.mtimeNs===after.mtimeNs,'file changed during observation');
 return {...pin(b),mode:Number(s.mode&0o7777n).toString(8).padStart(4,'0'),mtime_ns:s.mtimeNs.toString()};}
function ownSize(root,skipBrowser=false){let logical=0,allocated=0;if(!fs.existsSync(root))return {logical,allocated};
 function walk(p){let list;try{list=fs.readdirSync(p);}catch(e){if(e.code==='ENOENT')return;throw e;}
  for(const name of list){const q=path.join(p,name);if(skipBrowser&&q===path.join(ROOT,'browser'))continue;
   let s;try{s=fs.lstatSync(q);}catch(e){if(e.code==='ENOENT')continue;throw e;}
   if(s.isSymbolicLink())continue;if(s.isDirectory())walk(q);else if(s.isFile()){logical+=s.size;allocated+=(s.blocks||0)*512;}}}
 walk(root);return {logical,allocated};}
function evidence(name,b){require(b.length<=1024**2,'per-evidence-file cap');const p=path.join(OUTPUT,name);
 fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,b,{flag:'wx',mode:0o600});return {...pin(b),path:'results/'+name};}
function jsonfile(name,v){return evidence(name,Buffer.from(JSON.stringify(v,null,2)+'\n'));}
function protectedInventory(){const names=['AUTHORITY.json','CONTRACT.md','receiver.mjs','recorded-events.html'];
 return {files:Object.fromEntries(names.map(n=>[n,fileIdentity(path.join(ROOT,n))])),
 runtime:{node:fileIdentity(fs.realpathSync(process.execPath)),python:fileIdentity(fs.realpathSync(PYTHON)),
 chrome:fileIdentity(fs.realpathSync(CHROME))}};}
function resourceSnapshot(label){
 const code="import json,os,re,subprocess\ns=os.statvfs('/Users/me');v=subprocess.run(['/usr/bin/vm_stat'],capture_output=True,text=True,check=True,timeout=5).stdout\np=int(re.search(r'page size of (\\d+) bytes',v).group(1));m=sum(int(re.search(r'^'+re.escape(k)+r':\\s+(\\d+)',v,re.M).group(1)) for k in ('Pages free','Pages inactive','Pages speculative'))*p\nprint(json.dumps({'free_disk':s.f_bavail*s.f_frsize,'conservative_memory':m}))";
 const r=spawnSync(PYTHON,['-I','-B','-c',code],{encoding:'utf8',timeout:7000,maxBuffer:65536});
 require(r.status===0,'capacity observer failed '+r.stderr);
 const g={label,at:new Date().toISOString(),...JSON.parse(r.stdout),receiver:ownSize(ROOT,true),browser:ownSize(path.join(ROOT,'browser'))};
 receipt.guards.push(g);
 require(g.free_disk>=MIN_DISK&&g.conservative_memory>=MIN_MEMORY&&Math.max(g.receiver.logical,g.receiver.allocated)<=STATIC_CAP
  &&Math.max(g.browser.logical,g.browser.allocated)<=BROWSER_CAP,'frozen native resource guard refused: '+label);return g;
}
function psRows(args){const r=spawnSync('/bin/ps',args,{encoding:'utf8',timeout:5000,maxBuffer:2*1024**2});
 require(r.status===0||r.status===1,'owned process observation failed');
 return r.stdout.split('\n').filter(Boolean).map(line=>{const m=line.trim().match(/^(\d+)\s+(\d+)\s+([\s\S]*)$/);
 return m?{pid:+m[1],ppid:+m[2],command:m[3]}:null;}).filter(Boolean);}
function trackOwned(){const current=psRows(['-axo','pid=,ppid=,command=']);
 if(chrome?.pid){watchPids.add(chrome.pid);let changed=true;
  while(changed){changed=false;for(const p of current)if((watchPids.has(p.ppid)||p.command.includes(PROFILE))&&!watchPids.has(p.pid)){
   watchPids.add(p.pid);changed=true;}}}
 return current.filter(p=>watchPids.has(p.pid));}
function checkBoundary(){if(boundaryError)throw boundaryError;
 if(chromeStarted!==null)require(performance.now()-chromeStarted<180000,'180-second active browser deadline');}
function observe(m){const p=m.params||{},o=receipt.observations;
 if(m.method==='Runtime.exceptionThrown')o.exceptions.push(p);
 if(m.method==='Runtime.consoleAPICalled')o.console.push(p);
 if(m.method==='Log.entryAdded')o.log.push(p.entry);
 if(m.method==='Network.requestWillBeSent')o.requests.push({requestId:p.requestId,url:p.request.url,method:p.request.method,type:p.type});
 if(m.method==='Network.responseReceived')o.responses.push({requestId:p.requestId,url:p.response.url,status:p.response.status,type:p.type});
 if(m.method==='Network.loadingFailed')o.loading_failed.push(p);
}
class PipeCDP{
 constructor(child){this.id=0;this.pending=new Map();this.buffer='';this.child=child;
 child.stdio[4].setEncoding('utf8');child.stdio[4].on('data',chunk=>{this.buffer+=chunk;let i;
  while((i=this.buffer.indexOf('\0'))>=0){const line=this.buffer.slice(0,i);this.buffer=this.buffer.slice(i+1);if(!line)continue;
   let m;try{m=JSON.parse(line);}catch(e){this.fail(e);continue;}
   if(m.id){const p=this.pending.get(m.id);if(p){clearTimeout(p.timer);this.pending.delete(m.id);
    m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result??{});}}else observe(m);}});
 child.stdio[4].on('error',e=>this.fail(e));child.once('exit',()=>this.fail(new Error('owned Chrome pipe closed')));}
 fail(e){for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(e);}this.pending.clear();}
 send(method,params={},sid=null,timeoutMs=10000){checkBoundary();return new Promise((resolve,reject)=>{
  const id=++this.id,timer=setTimeout(()=>{this.pending.delete(id);reject(new Error('CDP timeout '+method));},timeoutMs);
  this.pending.set(id,{resolve,reject,timer});const message={id,method,params};if(sid)message.sessionId=sid;
  this.child.stdio[3].write(JSON.stringify(message)+'\0');});}
}
async function evaluate(expression){const r=await connection.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},session);
 if(r.exceptionDetails)throw new Error('DOM observer exception: '+JSON.stringify(r.exceptionDetails));return r.result?.value;}
async function waitFor(expression,ms=10000){const t=performance.now();while(performance.now()-t<ms){checkBoundary();const v=await evaluate(expression);
 if(v)return v;await pause(50);}throw new Error('DOM condition timeout: '+expression);}
async function click(selector){const q=JSON.stringify(selector);
 const box=await evaluate("(()=>{const e=document.querySelector("+q+");if(!e)throw Error('missing target');e.scrollIntoView({block:'center',inline:'nearest'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);return {x,y,width:r.width,height:r.height,visible:r.width>0&&r.height>0&&!!h&&(h===e||e.contains(h)),text:e.textContent};})()");
 require(box.visible,'target not visible: '+selector);
 for(const type of ['mouseMoved','mousePressed','mouseReleased'])await connection.send('Input.dispatchMouseEvent',
  {type,x:box.x,y:box.y,...(type==='mouseMoved'?{}:{button:'left',clickCount:1})},session);
 receipt.actions.push({action:'trusted_pointer_via_Input.dispatchMouseEvent',selector,text:box.text,at:new Date().toISOString(),
  framing:'DOM scrollIntoView used only to expose the native target before pointer input'});
}
async function keyEnter(){for(const type of ['keyDown','keyUp'])await connection.send('Input.dispatchKeyEvent',
 {type,key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13},session);
 receipt.actions.push({action:'trusted_keyboard_via_Input.dispatchKeyEvent',key:'Enter',at:new Date().toISOString()});}
async function screenshot(name){const r=await connection.send('Page.captureScreenshot',
 {format:'png',captureBeyondViewport:false,fromSurface:true},session);const b=Buffer.from(r.data,'base64');
 require(b.length>1000&&b.length<700000,'screenshot byte cap');return evidence(name,b);}
async function recordSection(kind){const selector='pre[data-kind="'+kind+'"]';
 const rows=await evaluate("Array.from(document.querySelectorAll("+JSON.stringify(selector)+"),e=>({kind:e.dataset.kind,index:e.dataset.index,json_text:e.textContent}))");
 const expected=CFG.structured_record_text.filter(x=>x.kind===kind);
 require(JSON.stringify(rows)===JSON.stringify(expected),'complete saved JSON text differs: '+kind);
 return rows;
}
async function closeOwnedBrowser(){
 if(profileTimer)clearInterval(profileTimer);if(deadlineTimer)clearTimeout(deadlineTimer);if(!chrome)return;
 receipt.browser.tracked_owned_processes=trackOwned();let requested=false;
 if(!chromeExit){try{await connection.send('Browser.close',{},null,2000);requested=true;}catch(e){receipt.browser.close_request_note=String(e);}}
 for(let i=0;i<60&&!chromeExit;i++)await pause(50);
 if(!chromeExit){chrome.kill('SIGTERM');receipt.browser.owned_SIGTERM=true;for(let i=0;i<60&&!chromeExit;i++)await pause(50);}
 if(!chromeExit){chrome.kill('SIGKILL');receipt.browser.owned_SIGKILL=true;for(let i=0;i<60&&!chromeExit;i++)await pause(50);}
 let remaining=[];
 for(let i=0;i<30;i++){remaining=psRows(['-p',Array.from(watchPids).join(','),'-o','pid=,ppid=,command=']);
  if(remaining.length===0)break;await pause(100);}
 receipt.browser.close_requested=requested;receipt.browser.actual_exit=chromeExit;receipt.browser.remaining_owned_processes=remaining;
 require(chromeExit!==null&&remaining.length===0,'owned browser closure incomplete');
 receipt.browser.active_seconds=(performance.now()-chromeStarted)/1000;
}
async function main(){
 require(!fs.existsSync(OUTPUT),'exclusive evidence directory required');fs.mkdirSync(OUTPUT,{mode:0o700});
 require(pin(fs.readFileSync(path.join(ROOT,'CONTRACT.md'))).git_blob===CONTRACT,'frozen contract identity');
 require(samePin(pin(fs.readFileSync(REPORT)),CFG.physical_html),'physical Linux report identity');
 require(pin(fs.readFileSync(fileURLToPath(import.meta.url))).git_blob===CFG.receiver_source.git_blob,'frozen observer identity');
 before=protectedInventory();jsonfile('IDENTITY-BEFORE.json',before);
 for(const [key,expected] of Object.entries(CFG.runtime_preflight))require(
  before.runtime[key].bytes===expected.bytes&&before.runtime[key].sha256===expected.sha256,'existing runtime identity changed: '+key);
 require(process.version==='v26.3.0','existing Node version changed');
 resourceSnapshot('before-single-offline-browser');
 require(!fs.existsSync(path.join(ROOT,'browser')),'new private browser allocation required');
 fs.mkdirSync(PROFILE,{recursive:true,mode:0o700});
 const args=['--headless=new','--remote-debugging-pipe','--user-data-dir='+PROFILE,'--no-first-run','--no-default-browser-check',
 '--disable-background-networking','--disable-component-update','--disable-sync','--disable-extensions','--disable-default-apps',
 '--metrics-recording-only','--password-store=basic','--use-mock-keychain','--disable-breakpad','--disable-crash-reporter',
 '--disk-cache-size=1048576','--media-cache-size=1048576','about:blank'];
 chromeStarted=performance.now();chrome=spawn(CHROME,args,{stdio:['ignore','pipe','pipe','pipe','pipe'],cwd:'/tmp'});
 chrome.stdout.on('data',b=>{chromeStdout.push(b);stdoutBytes+=b.length;if(stdoutBytes>1024**2)boundaryError=new Error('Chrome stdout cap');});
 chrome.stderr.on('data',b=>{chromeStderr.push(b);stderrBytes+=b.length;if(stderrBytes>1024**2)boundaryError=new Error('Chrome stderr cap');});
 chrome.on('exit',(code,signal)=>{chromeExit={pid:chrome.pid,code,signal,at:new Date().toISOString()};});
 chrome.on('error',e=>{boundaryError=e;});
 receipt.browser.command={executable:CHROME,args,cwd:'/tmp',pid:chrome.pid,control:'private inherited CDP pipe, no TCP listener'};
 connection=new PipeCDP(chrome);watchPids.add(chrome.pid);
 deadlineTimer=setTimeout(()=>{boundaryError=new Error('180-second browser limit');connection.fail(boundaryError);chrome.kill('SIGTERM');},180000);
 profileTimer=setInterval(()=>{try{const a=ownSize(ROOT,true),b=ownSize(path.join(ROOT,'browser'));
 if(Math.max(a.logical,a.allocated)>STATIC_CAP||Math.max(b.logical,b.allocated)>BROWSER_CAP||boundaryError){
 boundaryError=boundaryError||new Error('owned evidence/profile limit');connection.fail(boundaryError);chrome.kill('SIGTERM');}}
 catch(e){boundaryError=e;connection.fail(e);chrome.kill('SIGTERM');}},500);
 const version=await connection.send('Browser.getVersion');receipt.browser.version=version;
 require(version.product==='Chrome/'+CFG.chrome_version,'existing Chrome version changed');
 const target=await connection.send('Target.createTarget',{url:'about:blank'});
 session=(await connection.send('Target.attachToTarget',{targetId:target.targetId,flatten:true})).sessionId;
 for(const method of ['Page.enable','Runtime.enable','Network.enable','Log.enable'])await connection.send(method,{},session);
 await connection.send('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false},session);
 const navigation=await connection.send('Page.navigate',{url:URI},session);require(!navigation.errorText,'file navigation error');
 await waitFor("document.readyState==='complete'&&document.querySelectorAll('pre[data-kind]').length===8");
 const entry=await evaluate("({url:location.href,title:document.title,text:document.body.innerText,scriptNodes:document.scripts.length,sentinelType:typeof globalThis.__captureReceiverSentinel,links:Array.from(document.querySelectorAll('nav a'),e=>({href:e.getAttribute('href'),text:e.textContent})),counts:Array.from(document.querySelectorAll('td[id^=\"count-\"]'),e=>({id:e.id,text:e.textContent})),details:Array.from(document.querySelectorAll('details'),e=>e.open),fonts:{body:getComputedStyle(document.body).fontFamily,pre:getComputedStyle(document.querySelector('pre')).fontFamily}})");
 require(entry.url===URI&&entry.title==='CaptureSuite — recorded-event report','actual offline entry/title');
 require(entry.scriptNodes===0&&entry.sentinelType==='undefined','literal script-looking annotation executed or active node');
 require(entry.details.length===8&&entry.details.every(Boolean),'initial native disclosure state');
 for(const row of entry.counts)require(row.text==='2','returned-count display mismatch');
 require(entry.text.includes('Recovered session — recorded gaps preserved')&&entry.text.includes('reader-returned records'),'honest recovered/returned labeling absent');
 jsonfile('ENTRY-DOM.json',entry);
 receipt.overview_screenshot=await screenshot('01-overview.png');
 receipt.sections={};
 await click('nav a[href="#checkpoints"]');await waitFor("location.hash==='#checkpoints'");
 receipt.sections.checkpoints=await recordSection('checkpoints');
 await click('nav a[href="#annotations"]');await waitFor("location.hash==='#annotations'");
 receipt.sections.annotations=await recordSection('annotations');
 const summary='#annotations details:first-of-type summary';
 await click(summary);require(await evaluate("document.querySelector('#annotations details').open===false"),'native details pointer collapse failed');
 require(await evaluate("document.activeElement===document.querySelector('#annotations details summary')"),'summary did not receive native focus');
 await keyEnter();await waitFor("document.querySelector('#annotations details').open===true");
 receipt.native_disclosure={pointer_collapsed:true,keyboard_enter_reopened:true};
 await evaluate("document.querySelector('#annotations pre').scrollIntoView({block:'center'});true");
 receipt.annotation_screenshot=await screenshot('02-literal-annotation.png');
 await click('nav a[href="#sync-anchors"]');await waitFor("location.hash==='#sync-anchors'");
 receipt.sections.sync_anchors=await recordSection('sync-anchors');
 await click('nav a[href="#gaps"]');await waitFor("location.hash==='#gaps'");
 receipt.sections.gaps=await recordSection('gaps');
 await evaluate("document.querySelector('#gaps').scrollIntoView({block:'center'});true");
 receipt.gaps_screenshot=await screenshot('03-normalized-gaps.png');
 const final=await evaluate("({url:location.href,sentinelType:typeof globalThis.__captureReceiverSentinel,scriptNodes:document.scripts.length,records:Array.from(document.querySelectorAll('pre[data-kind]'),e=>({kind:e.dataset.kind,index:e.dataset.index,json_text:e.textContent})),coverage:document.querySelector('#coverage').innerText,gapProjection:document.querySelector('[aria-labelledby=\"gap-projection-title\"]').innerText,bodyText:document.body.innerText})");
 require(final.sentinelType==='undefined'&&final.scriptNodes===0,'literal script protection changed');
 require(JSON.stringify(final.records)===JSON.stringify(CFG.structured_record_text),'complete final record text changed');
 jsonfile('FINAL-DOM.json',final);
 await pause(200);
 receipt.page_external_requests=receipt.observations.requests.filter(r=>/^https?:|^wss?:|^ftp:/i.test(r.url));
 require(receipt.page_external_requests.length===0,'page requested an external resource');
 require(receipt.observations.exceptions.length===0,'page runtime exception observed');
 receipt.groups.C4_semantics='PASS: one physical file, all record text, native navigation/disclosure and literal-data behavior';
 await closeOwnedBrowser();
 receipt.chrome_stdout=evidence('chrome.stdout.txt',Buffer.concat(chromeStdout));
 receipt.chrome_stderr=evidence('chrome.stderr.txt',Buffer.concat(chromeStderr));
 const after=protectedInventory();jsonfile('IDENTITY-AFTER.json',after);
 receipt.protected_files_and_runtime_unchanged=JSON.stringify(before)===JSON.stringify(after);
 require(receipt.protected_files_and_runtime_unchanged,'protected file/runtime identity changed');
 resourceSnapshot('after-owned-browser-closure');
 receipt.groups.C5_mac='PASS: actual owned browser exit and measured immutable input/runtime preservation';
 receipt.accepted=true;
}
try{await main();}
catch(error){receipt.failure={message:error.message,stack:error.stack};receipt.accepted=false;
 try{await closeOwnedBrowser();}catch(closeError){receipt.closure_failure={message:closeError.message,stack:closeError.stack};}
 try{if(!receipt.chrome_stdout)receipt.chrome_stdout=evidence('chrome.stdout.txt',Buffer.concat(chromeStdout));
 if(!receipt.chrome_stderr)receipt.chrome_stderr=evidence('chrome.stderr.txt',Buffer.concat(chromeStderr));}catch(e){receipt.stream_custody_error=String(e);}
 if(before){try{const after=protectedInventory();receipt.failure_protected_unchanged=JSON.stringify(before)===JSON.stringify(after);
 jsonfile('FAILURE-IDENTITY-AFTER.json',after);}catch(e){receipt.preservation_error=String(e);}}}
finally{
 if(profileTimer)clearInterval(profileTimer);if(deadlineTimer)clearTimeout(deadlineTimer);
 receipt.completed_utc=new Date().toISOString();receipt.controller_pid=process.pid;receipt.total_seconds=(performance.now()-started)/1000;
 receipt.controller_exit_pending_until_parent_wait=true;receipt.final_owned={receiver:ownSize(ROOT,true),browser:ownSize(path.join(ROOT,'browser'))};
 if(Math.max(receipt.final_owned.receiver.logical,receipt.final_owned.receiver.allocated)>STATIC_CAP
 ||Math.max(receipt.final_owned.browser.logical,receipt.final_owned.browser.allocated)>BROWSER_CAP)receipt.accepted=false;
 fs.mkdirSync(OUTPUT,{recursive:true});
 const rp=jsonfile('MAC-RECEIPT.json',receipt);
 console.log(JSON.stringify({accepted:receipt.accepted,groups:receipt.groups,failure:receipt.failure,receipt:rp,
 chrome_exit:chromeExit,controller_pid:process.pid,visual_review:'Pending original screenshot display; no all-error-free claim.'}));
 process.exitCode=receipt.accepted?0:1;
}
