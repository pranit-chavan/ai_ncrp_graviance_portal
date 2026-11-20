const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Exercise the shipped voice handlers with a fake microphone and local API.
function harness() {
  const source = fs.readFileSync(path.join(__dirname, '../static/citizen.js'), 'utf8');
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {disabled:false, hidden:true, textContent:'', value:'', files:[],
      setAttribute(k,v){this[k]=v;}, removeAttribute(k){delete this[k];}, pause(){}, load(){}});
    return elements.get(id);
  };
  const stats = {requests:0, stops:0, revoked:[], recorders:[], timers:new Map(), fail:false, deny:false};
  let timerId=0;
  class Recorder {
    static isTypeSupported(){return true;}
    constructor(){this.state='inactive';this.mimeType='audio/webm';stats.recorders.push(this);}
    start(){this.state='recording';}
    stop(){this.state='inactive';this.ondataavailable({data:new Blob(['voice'])});this.onstop();}
  }
  const context = vm.createContext({
    $, stats, Blob, File, FormData, MediaRecorder:Recorder, window:{MediaRecorder:Recorder},
    navigator:{mediaDevices:{getUserMedia:async()=>{if(stats.deny)throw Object.assign(new Error('denied'),{name:'NotAllowedError'});return {getTracks:()=>[{stop(){stats.stops++;}}]};}}},
    URL:{createObjectURL:()=>`blob:${timerId}`,revokeObjectURL:url=>stats.revoked.push(url)},
    setInterval:fn=>{stats.timers.set(++timerId,fn);return timerId;},
    setTimeout:fn=>{stats.timers.set(++timerId,fn);return timerId;},
    clearInterval:id=>stats.timers.delete(id),clearTimeout:id=>stats.timers.delete(id),
    document:{body:{classList:{add(){},remove(){}}},querySelectorAll:()=>[...elements.values()]},
    notice:message=>{stats.notice=message;},renderNavigation(){},save(){},
    api:async()=>{stats.requests++;if(stats.fail)throw Error('Service unavailable');return {text:'Test complaint transcript'};}
  });
  function $(id){return element(id);}
  vm.runInContext('let busy=false, recorder=null, stream=null, voiceCapturing=false, pendingRecording=null, recordingUrl=null, recordingTimer=null, recordingLimit=null;',context);
  vm.runInContext(source.slice(source.indexOf('async function task('),source.indexOf('\nfunction show(')),context);
  vm.runInContext(source.slice(source.indexOf('function updateVoiceControls('),source.indexOf("$('use-transcript').onclick")),context);
  return {element, stats, run:code=>vm.runInContext(code,context)};
}

test('recording is visible; stopping previews locally without transcription',async()=>{
  const h=harness();await h.run('startRecording()');
  assert.equal(h.element('recording-indicator').hidden,false);
  assert.equal(h.element('record').textContent,'Stop recording');
  assert.equal(h.element('next').disabled,true);
  h.run('recorder.stop()');
  assert.equal(h.stats.requests,0);
  assert.equal(h.element('recording-preview').hidden,false);
  assert.equal(h.element('recording-indicator').hidden,true);
  assert.equal(h.stats.stops,1);
  assert.equal(h.stats.timers.size,0);
});

test('explicit use transcribes, while discard never sends audio',async()=>{
  const h=harness();await h.run('startRecording()');h.run('recorder.stop()');
  h.element('discard-recording').onclick();assert.equal(h.stats.requests,0);
  assert.equal(h.element('recording-preview').hidden,true);
  await h.run('startRecording()');h.run('recorder.stop()');
  await h.run('transcribe(pendingRecording)');
  assert.equal(h.stats.requests,1);
  assert.equal(h.element('transcript').value,'Test complaint transcript');
  assert.equal(h.element('transcript-panel').hidden,false);
  assert.equal(h.element('transcribe-recording').disabled,true);
});

test('failed transcription preserves audio and permits retry',async()=>{
  const h=harness();await h.run('startRecording()');h.run('recorder.stop()');
  h.stats.fail=true;await h.run('transcribe(pendingRecording)');
  assert.equal(h.element('recording-preview').hidden,false);
  assert.equal(h.element('transcribe-recording').disabled,false);
  h.stats.fail=false;await h.run('transcribe(pendingRecording)');
  assert.equal(h.stats.requests,2);
});

test('record again clears old timers; denied permission preserves the old clip',async()=>{
  const h=harness();await h.run('startRecording()');h.run('recorder.stop()');
  h.stats.deny=true;await h.element('record-again').onclick();
  assert.equal(h.element('recording-preview').hidden,false);
  assert.equal(h.stats.requests,0);
  h.stats.deny=false;await h.element('record-again').onclick();
  assert.equal(h.element('recording-preview').hidden,true);
  assert.equal(h.stats.timers.size,2);
  h.run('recorder.stop()');assert.equal(h.stats.timers.size,0);
});

test('choosing a file and the two minute stop both wait for confirmation',async()=>{
  const h=harness();h.element('audio').files=[new File(['voice'],'example.wav',{type:'audio/wav'})];
  h.element('audio').onchange();assert.equal(h.stats.requests,0);
  assert.equal(h.element('recording-name').textContent,'example.wav');
  await h.run('startRecording()');[...h.stats.timers.values()].at(-1)();
  assert.equal(h.element('recording-preview').hidden,false);
  assert.equal(h.stats.requests,0);
});
