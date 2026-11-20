const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/citizen.js','utf8');

function setup(){
 const nodes=new Map(),storage=new Map(),bindings={};let sequence=0;
 const $=id=>{if(!nodes.has(id))nodes.set(id,{value:'old',textContent:'old',checked:true,hidden:false,disabled:true,children:['old'],replaceChildren(){this.children=[];},removeAttribute(name){delete this[name];}});return nodes.get(id);};
 const context=vm.createContext({$,crypto:{randomUUID:()=>`session-${++sequence}`},busy:false,voiceCapturing:false,recorder:{},pendingRecording:{},locationData:{states:[]},incident:{},personal:{},
  releaseRecording(){context.pendingRecording=null;},stopRecordingResources(){},
  fields(container,definitions,prefix,values){bindings[prefix]=values;},
  setLocationOptions(){},populateDistricts(){},loadLocations(){},renderFiles(){},renderConversation(){},notice(){},updateVoiceControls(){},
  show(step){vm.runInContext(`draft.step=${step};draft.furthest=Math.max(draft.furthest,${step});`,context);storage.set('draft',vm.runInContext('JSON.stringify(draft)',context));}
 });
 vm.runInContext(source.match(/const fresh = .*;/)[0]+'\nlet draft=fresh();',context);
 vm.runInContext(`draft.story='Old complaint';draft.person.name='Old name';draft.history=[{content:'old answer'}];draft.evidence=[{filename:'old.png'}];draft.submission={reference:'old'};draft.submissionToken='old-token';draft.furthest=5;draft.step=4;`,context);
 vm.runInContext(source.slice(source.indexOf('function startNewComplaint(){'),source.indexOf('renderFiles();$(\'resume\').hidden=')),context);
 return {context,$,bindings,storage,state:()=>JSON.parse(vm.runInContext('JSON.stringify(draft)',context))};
}

test('both new complaint buttons clear old state, create a new session and rebind fields',()=>{
 for(const button of ['start','restart']){
  const h=setup(),old=h.state();h.$(button).onclick();const next=h.state();
  assert.notEqual(next.id,old.id);assert.equal(next.step,0);assert.equal(next.furthest,0);
  assert.equal(next.story,'');assert.deepEqual(next.person,{});assert.deepEqual(next.history,[]);assert.deepEqual(next.evidence,[]);
  assert.equal(next.submission,null);assert.equal(next.submissionToken,undefined);assert.equal(h.context.pendingRecording,null);
  assert.equal(h.$('story').value,'');assert.equal(h.$('confirm').checked,false);assert.equal(h.$('transcript-panel').hidden,true);
  assert.deepEqual(JSON.parse(h.storage.get('draft')),next);
  h.bindings['person-'].name='New person';assert.equal(h.state().person.name,'New person');
 }
});
test('resume retains the complaint and current step',()=>{
 const h=setup(),old=h.state();h.$('resume').onclick();assert.deepEqual(h.state(),old);
});
test('new complaint is blocked during active work or recording',()=>{
 for(const flag of ['busy','voiceCapturing']){const h=setup(),old=h.state();h.context[flag]=true;h.$('start').onclick();assert.deepEqual(h.state(),old);}
});
