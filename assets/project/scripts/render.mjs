import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';
import {once} from 'node:events';
import {pathToFileURL} from 'node:url';
import {createCanvas, GlobalFonts} from '@napi-rs/canvas';

const root = path.resolve(import.meta.dirname, '..');
const json = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const save = (p, data) => {fs.mkdirSync(path.dirname(p), {recursive:true});fs.writeFileSync(p+'.tmp', JSON.stringify(data,null,2)+'\n');fs.renameSync(p+'.tmp',p);};
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const local = p => {const full=path.resolve(root,p);if(!full.startsWith(root+path.sep))throw Error('Path escapes project: '+p);return full;};
const project = json(path.join(root,'project.json'));
const episode = json(path.join(root,'episode.json'));
const facts = json(path.join(root,'facts.json'));
function rational(value){
 const s=String(value);let a,b;
 if(/^\d+\/\d+$/.test(s))[a,b]=s.split('/').map(Number);
 else if(/^\d+(\.\d+)?$/.test(s)){const digits=s.split('.')[1]?.length??0;a=Number(s.replace('.',''));b=10**digits;}
 else throw Error('Use an integer, decimal or rational output.fps');
 const gcd=(x,y)=>y?gcd(y,x%y):x,common=gcd(a,b);return[a/common,b/common];
}
const [rateNum, rateDen] = rational(project.output.fps);
const fps=rateNum/rateDen, count=project.output.total_frames;
const width=project.output.width, height=project.output.height;
if(!Number.isFinite(fps)||fps<=0||fps>240||rateNum*512>2147483647||!Number.isInteger(count)||count<1||!Number.isInteger(width)||!Number.isInteger(height)||width<2||height<2||width%2||height%2)throw Error('Set valid even dimensions, fps and total_frames in project.json');
const formatRate=`${rateNum}/${rateDen}`;
const frames = t => Math.round(t*fps);
let end=0;
const segments=episode.chapters.map((c,index)=>{const start=frames(c.start),last=frames(c.end);if(start!==end||last<=start)throw Error('Chapter gap, overlap or empty interval: '+c.id);end=last;return{...c,index,startFrame:start,count:last-start};});
if(!segments.length||end!==count)throw Error('Chapters must cover the entire movie');
for(const font of project.fonts??[])if(!GlobalFonts.registerFromPath(font.path,font.family))throw Error('Cannot register font: '+font.path);
const args=process.argv.slice(2),mode=args.shift();
const opt=(key,fallback)=>{const at=args.indexOf(key);return at<0?fallback:args[at+1];};

function inputSnapshot(){
 const paths=new Set(['project.json','episode.json','facts.json','reference/analysis.json','package.json','scripts/render.mjs'].map(p=>local(p)));
 if(fs.existsSync(local('package-lock.json')))paths.add(local('package-lock.json'));
 function walk(dir){if(!fs.existsSync(dir))return;for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())walk(p);else if(e.isFile())paths.add(p);}}
 for(const dir of ['production','assets','audio'])walk(local(dir));
 paths.add(local(project.renderer));
 if(project.audio?.mode!=='none')paths.add(local(project.audio.source));
 for(const font of project.fonts??[])paths.add(path.resolve(font.path));
 return [...paths].sort().map(p=>({path:p,sha256:hash(p)}));
}
function sameInputs(a,b){return JSON.stringify(a)===JSON.stringify(b);}
async function painter(){
 const renderer=await import(pathToFileURL(local(project.renderer)).href);
 if(typeof renderer.renderFrame!=='function')throw Error('Renderer must export renderFrame');
 const canvas=createCanvas(width,height),ctx=canvas.getContext('2d');
 return {canvas, draw:async frame=>{ctx.reset();await renderer.renderFrame({canvas,ctx,time:frame/fps,frame,project,episode,facts});}};
}
function stamp(time){let n=Math.round(time*1000);const h=Math.floor(n/3600000);n%=3600000;const m=Math.floor(n/60000);n%=60000;return`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(Math.floor(n/1000)).padStart(2,'0')},${String(n%1000).padStart(3,'0')}`;}
function subtitles(){const text=(episode.captions??[]).map((x,i)=>`${i+1}\n${stamp(x.start)} --> ${stamp(x.end)}\n${x.text}\n`).join('\n');fs.writeFileSync(local('output/subtitles.srt'),text);}

async function encodeWorker(){
 const index=Number(opt('--segment')),runDir=path.resolve(opt('--run-dir',''));
 if(!runDir.startsWith(local('.render')+path.sep))throw Error('Worker run directory must be inside .render');
 const segment=segments[index];if(!segment)throw Error('Invalid segment');
 const output=path.join(runDir,`part-${String(index).padStart(4,'0')}.mp4`),{canvas,draw}=await painter();
 const ff=spawn('ffmpeg',['-hide_banner','-loglevel','error','-f','rawvideo','-pixel_format','rgba','-video_size',`${width}x${height}`,'-framerate',formatRate,'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf',String(project.render?.crf??18),'-threads',String(project.render?.encoder_threads??2),'-pix_fmt','yuv420p','-r',formatRate,'-video_track_timescale',String(rateNum*512),'-y',output],{stdio:['pipe','inherit','inherit']});
 const finished=once(ff,'exit');let pipeError;ff.stdin.on('error',e=>{pipeError=e;});
 try{
  for(let i=0;i<segment.count;i++){
   if(pipeError)throw pipeError;await draw(segment.startFrame+i);
   if(!ff.stdin.write(canvas.data()))await once(ff.stdin,'drain');
   if(i>0&&i%300===0)process.stdout.write(JSON.stringify({chapter:segment.id,frames:i,total:segment.count})+'\n');
  }
  ff.stdin.end();const [code]=await finished;if(code!==0)throw Error('FFmpeg encoder exit '+code);
 }catch(e){ff.stdin.destroy();ff.kill('SIGTERM');await finished.catch(()=>{});throw e;}
}

async function video(){
 const audio=project.audio??{};
 if(!['copy-full','prepared','none'].includes(audio.mode))throw Error('Explicitly choose an audio mode; silent export is not a default');
 if(audio.mode==='none'&&!audio.reason)throw Error('A silent movie needs an explicit reason');
 if(audio.mode!=='none'){
  const probe=spawnSync('ffprobe',['-v','error','-show_streams','-show_format','-of','json',local(audio.source)],{encoding:'utf8'});
  if(probe.status!==0)throw Error('Cannot inspect audio source: '+probe.stderr);
  const meta=JSON.parse(probe.stdout),track=meta.streams.find(s=>s.codec_type==='audio');if(!track)throw Error('Audio source has no audio stream');
  const seconds=Number(track.duration??meta.format.duration),expected=count/fps;
  if(!Number.isFinite(seconds)||Math.abs(seconds-expected)>.15)throw Error(`Audio ${seconds}s does not cover the intended ${expected}s; prepare a continuous full-length mix, do not silently loop or truncate`);
  if(audio.mode==='copy-full'&&track.codec_name!=='aac')throw Error('This MP4 runtime requires AAC for copy-full. Explicitly prepare a compatible mix or use a suitable external muxer.');
 }
 const base=local('.render');fs.mkdirSync(base,{recursive:true});
 const lock=path.join(base,'active.lock');
 if(fs.existsSync(lock)){
  const pid=json(lock).pid;let alive=true;try{process.kill(pid,0);}catch(e){if(e.code==='ESRCH')alive=false;}
  if(alive)throw Error(`Render already has a live handle: PID ${pid}. Observe it instead of restarting.`);fs.unlinkSync(lock);
 }
 const lockFd=fs.openSync(lock,'wx');fs.writeFileSync(lockFd,JSON.stringify({pid:process.pid}));fs.closeSync(lockFd);
 const runDir=path.join(base,'run-'+Date.now()+'-'+crypto.randomBytes(3).toString('hex'));fs.mkdirSync(runDir);
 const logs=path.resolve(project.logs_dir??path.join(base,'logs'));fs.mkdirSync(logs,{recursive:true});
 const progress={status:'rendering',pid:process.pid,runDir,startedAt:new Date().toISOString(),completed:[],totalFrames:count};
 const update=()=>save(path.join(base,'progress.json'),progress);update();
 const before=inputSnapshot(),children=new Set();
 const run=(program,a,log)=>new Promise((resolve,reject)=>{
  const fd=fs.openSync(log,'w'),child=spawn(program,a,{cwd:root,stdio:['ignore',fd,fd]});children.add(child);
  child.on('error',reject);child.on('close',code=>{children.delete(child);fs.closeSync(fd);code===0?resolve():reject(Error(`${program} exit ${code}; ${log}`));});
 });
 try{
  let cursor=0;
  async function worker(){while(cursor<segments.length){const i=cursor++;await run(process.execPath,[path.resolve(import.meta.filename),'worker','--segment',String(i),'--run-dir',runDir],path.join(logs,`${path.basename(runDir)}-${i}.log`));progress.completed.push(segments[i].id);update();process.stdout.write(`Rendered ${progress.completed.length}/${segments.length}\n`);}}
  const workers=Array.from({length:Math.min(4,Math.max(1,Number(project.render?.workers??2)),segments.length)},()=>worker());
  try{await Promise.all(workers);}catch(e){for(const child of children)child.kill('SIGTERM');await Promise.allSettled(workers);throw e;}
  const list=path.join(runDir,'concat.txt');fs.writeFileSync(list,segments.map((_,i)=>`file 'part-${String(i).padStart(4,'0')}.mp4'`).join('\n')+'\n');
  const merged=path.join(runDir,'merged.mp4'),command=['-hide_banner','-loglevel','warning','-f','concat','-safe','0','-i',list];
  if(audio.mode!=='none')command.push('-i',local(audio.source));
  command.push('-map','0:v:0','-c:v','copy');
  if(audio.mode==='none')command.push('-an');else command.push('-map','1:a:0','-c:a',audio.mode==='copy-full'?'copy':'aac');
  if(audio.mode==='prepared')command.push('-b:a','192k');
  command.push('-movflags','+faststart','-y',merged);
  await run('ffmpeg',command,path.join(logs,path.basename(runDir)+'-mux.log'));
  if(!sameInputs(before,inputSnapshot()))throw Error('Production inputs changed during rendering; do not deliver mixed versions');
  const output=local(project.output.file);fs.mkdirSync(path.dirname(output),{recursive:true});fs.renameSync(merged,output);subtitles();
  const receipt={status:'rendered',engine:'canvas',movie_sha256:hash(output),inputs:before,frames:count,fps:formatRate,finishedAt:new Date().toISOString()};save(local('qa/render.json'),receipt);
  progress.status='rendered';progress.finishedAt=receipt.finishedAt;update();
  const state=json(local('STATE.json'));state.stage='rendered';state.stages.video='rendered';state.running=null;save(local('STATE.json'),state);
  process.stdout.write(JSON.stringify({movie:output,...receipt})+'\n');
 }catch(e){progress.status='failed';progress.error=e.message;update();throw e;}finally{if(fs.existsSync(lock)&&json(lock).pid===process.pid)fs.unlinkSync(lock);}
}

if(mode==='worker')await encodeWorker();
else if(mode==='video')await video();
else if(mode==='frame'){
 const time=Number(opt('--time','0'));if(!Number.isFinite(time)||time<0||time>=count/fps)throw Error('Frame time is outside complete movie');
 const target=path.resolve(opt('--out',local('qa/frame.png')));if(!target.startsWith(root+path.sep))throw Error('Keep preview frames inside project');
 const {canvas,draw}=await painter();await draw(Math.floor(time*fps));fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,canvas.toBuffer('image/png'));console.log(target);
}else throw Error('Usage: node scripts/render.mjs frame --time N --out FILE | video');
