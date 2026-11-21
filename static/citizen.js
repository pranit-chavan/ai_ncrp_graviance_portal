/* Citizen workflow: original account + explicit corrections + durable browser draft. */
'use strict';
const $ = id => document.getElementById(id);
const KEY = 'cyberassist.guided.v1';
const titles = ['Tell us what happened', 'Add missing details', 'Check incident details', 'Add personal details', 'Review your complaint', 'Download your report'];
const labels = ['Describe', 'Questions', 'Incident', 'About you', 'Review', 'Report'];
const incident = {date_time_of_incident:'When did it happen?',platform_involved:'App, website, or platform',financial_loss_amount:'Money lost (₹)',bank_name:'Bank or wallet',utr_number:'Transaction reference',suspect_details:'Suspect account, phone, or profile'};
const personal = {name:'Full name',phone:'Phone number',email:'Email address (optional)',age:'Age',state:'State / Union territory',district:'District',pincode:'PIN code',city:'City or town (optional)',address:'Address (optional)'};
const fresh = () => ({version:1,id:crypto.randomUUID(),step:0,furthest:0,story:'',storyAnalyzed:'',history:[],docket:{},fields:{},edited:[],person:{},evidence:[],readings:{},identity:null,idKind:'',suspect:'',analysis:null,category:'',categoryManual:false,submission:null,confirmed:false});
let draft = fresh(), busy=false, recorder=null, stream=null;
let locationData=null;
let voiceCapturing=false, pendingRecording=null, recordingUrl=null, recordingTimer=null, recordingLimit=null;
try {const saved=JSON.parse(localStorage.getItem(KEY)); if(saved?.version===1) draft={...fresh(),...saved};} catch(_) {}
function save(){try{localStorage.setItem(KEY,JSON.stringify(draft));$('save-state').textContent='Saved in this browser';$('resume').hidden=false;}catch(_){$('save-state').textContent='Could not save — keep this page open';}}
function notice(message=''){ $('notice').textContent=message; $('notice').hidden=!message; }
function invalidate(){draft.submissionToken=null;if(!draft.categoryManual)draft.category='';draft.analysis=null;draft.submission=null;draft.confirmed=false;$('confirm').checked=false;draft.furthest=Math.min(draft.furthest,4);}
function localDateValue(date=new Date()){const local=new Date(date.getTime()-date.getTimezoneOffset()*60000);return local.toISOString().slice(0,10);}
function dateFieldValue(value){const text=String(value??'').trim();const iso=text.match(/^(\d{4}-\d{2}-\d{2})/);if(iso)return iso[1];const relative=text.toLowerCase();if(relative.includes('yesterday')){const yesterday=new Date();yesterday.setDate(yesterday.getDate()-1);return localDateValue(yesterday);}if(relative.includes('today'))return localDateValue();return '';}
async function api(url, data, multipart=false){const response=await fetch(url,{method:'POST',headers:multipart?{}:{'Content-Type':'application/json'},body:multipart?data:JSON.stringify(data)});let result;try{result=await response.json();}catch(_){throw Error('The service could not respond. Please try again.');}if(!response.ok||result.ok===false)throw Error(typeof result.detail==='string'?result.detail:result.error||'Please check your details and try again.');return result;}
async function task(message, work){if(busy)return;if(voiceCapturing){notice('Stop your recording before continuing.');return;}busy=true;document.body.classList.add('busy');notice(message);const controls=[...document.querySelectorAll('button,input,textarea,select')];const old=controls.map(x=>x.disabled);controls.forEach(x=>x.disabled=true);try{await work();notice();}catch(error){notice(error.message||'Something went wrong. Your answers are still here.');}finally{controls.forEach((x,i)=>x.disabled=old[i]);busy=false;document.body.classList.remove('busy');renderNavigation();updateVoiceControls();$('person-state').disabled=!locationData;populateDistricts();save();}}
function show(step,focus=true){draft.step=step;draft.furthest=Math.max(draft.furthest,step);$('landing').hidden=true;$('workspace').hidden=false;document.querySelectorAll('[data-step]').forEach(x=>x.hidden=Number(x.dataset.step)!==step);$('step-title').textContent=titles[step];renderNavigation();if(step===1)renderConversation();if(step===4)renderReview();if(step===5&&draft.submission){$('reference').textContent='Complaint reference: '+draft.submission.reference;$('download').href=draft.submission.pdf_url;}save();if(focus)$('step-title').focus();}
function renderNavigation(){ $('steps').replaceChildren();labels.forEach((name,i)=>{const b=document.createElement('button');b.type='button';const n=document.createElement('span');n.className='number';n.textContent=i+1;b.append(n,document.createTextNode(name));if(i===draft.step)b.setAttribute('aria-current','step');b.disabled=busy||voiceCapturing||i>draft.furthest||i===5&&!draft.submission;b.onclick=()=>navigate(i);$('steps').append(b);});$('back').hidden=draft.step===0;$('next').hidden=draft.step===5;$('next').textContent=draft.step===4?'Confirm and create report':draft.step===0?'Continue':'Continue';$('step-counter').textContent=`Step ${draft.step+1} of 6`;}
function fields(container,definitions,prefix,values){
 for(const [key,label] of Object.entries(definitions)){
  const isPerson=prefix==='person-',isLocation=isPerson&&['state','district'].includes(key);
  const wrap=document.createElement('div'),l=document.createElement('label'),input=document.createElement(isLocation?'select':'input');
  l.htmlFor=prefix+key;l.textContent=label;input.id=prefix+key;
  input.value=key==='date_time_of_incident'?dateFieldValue(values[key]):isPerson&&key==='phone'?IndianDetails.nationalPhone(values[key]):values[key]??'';
  if(key==='date_time_of_incident'){input.type='date';input.max=localDateValue();input.autocomplete='off';input.setAttribute('aria-describedby','incident-date-hint');}
  if(key==='financial_loss_amount'||key==='age'){input.type='number';input.min=key==='age'?1:0;input.step=key==='age'?1:'0.01';if(key==='age')input.max=120;}
  if(key==='phone'){input.type='tel';input.inputMode='tel';input.autocomplete='tel-national';input.placeholder='10-digit phone number';input.setAttribute('aria-describedby','phone-country');}
  if(key==='email'){input.type='email';input.autocomplete='email';}
  if(isPerson&&key==='name')input.autocomplete='name';
  if(isPerson&&key==='address')input.autocomplete='street-address';
  if(isPerson&&key==='pincode'){input.type='text';input.inputMode='numeric';input.maxLength=6;input.pattern='[1-9][0-9]{5}';input.autocomplete='postal-code';input.placeholder='e.g. 411001';}
  if(isLocation){input.autocomplete=key==='state'?'address-level1':'address-level2';input.disabled=true;setLocationOptions(input,[],key==='state'?'Loading states…':'Choose a state first',values[key]);}
  if(isPerson&&['name','phone','age','state','district','pincode'].includes(key)){input.required=true;l.textContent+=' *';}
  const changed=()=>{
   values[key]=isPerson&&key==='phone'?IndianDetails.storedPhone(input.value):input.value;
   if(isPerson&&key==='state'){values.district='';populateDistricts();}
   if(prefix==='field-'&&!draft.edited.includes(key))draft.edited.push(key);
   invalidate();save();
  };
  if(isLocation)input.onchange=changed;else input.oninput=changed;
  wrap.append(l);
  if(isPerson&&key==='phone'){
   const group=document.createElement('div'),country=document.createElement('span');group.className='phone-field';country.id='phone-country';country.textContent='+91';country.setAttribute('aria-label','India country code plus 91');group.append(country,input);wrap.append(group);
  }else wrap.append(input);
  if(key==='date_time_of_incident'){const hint=document.createElement('small');hint.id='incident-date-hint';hint.className='small';hint.textContent='Select the day, month, and year. Any approximate time can stay in your description.';wrap.append(hint);}
  $(container).append(wrap);
 }
}
function setLocationOptions(select,items,placeholder,previous=''){
 select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent=placeholder;select.append(empty);
 for(const item of items){const option=document.createElement('option');option.value=item.name;option.textContent=item.name;select.append(option);}
 const match=items.find(item=>item.name.toLowerCase()===String(previous).trim().toLowerCase());
 if(previous&&!match){const old=document.createElement('option');old.value=previous;old.textContent=previous+' — please select from the updated list';old.disabled=true;select.append(old);}
 select.value=match?match.name:previous||'';
}
function populateDistricts(){
 const selected=IndianDetails.state(locationData,draft.person.state);
 setLocationOptions($('person-district'),selected?.districts||[],selected?'Choose your district':'Choose a state first',draft.person.district);
 $('person-district').disabled=busy||!selected;
 if(selected&&selected.districts.some(item=>item.name===$('person-district').value))draft.person.district=$('person-district').value;
}
async function loadLocations(){
 $('location-status').textContent='Loading states and districts…';$('retry-locations').hidden=true;
 try{
  const response=await fetch('/static/data/india-locations.json');if(!response.ok)throw Error('location data');
  const data=await response.json();if(!Array.isArray(data.states)||!data.states.length)throw Error('location data');locationData=data;
  setLocationOptions($('person-state'),data.states,'Choose your state / union territory',draft.person.state);
  const selected=IndianDetails.state(data,draft.person.state);if(selected)draft.person.state=selected.name;
  $('person-state').disabled=busy;populateDistricts();
  $('location-status').textContent='Choose a state to see its districts. These lists work offline.';
 }catch(_){$('location-status').textContent='Could not load the location list. Please try again.';$('retry-locations').hidden=false;}
}
fields('incident-fields',incident,'field-',draft.fields);fields('person-fields',personal,'person-',draft.person);
$('retry-locations').onclick=loadLocations;loadLocations();

function hydrate(){for(const key of Object.keys(incident)){if(!draft.edited.includes(key)){draft.fields[key]=draft.docket[key]??'';$('field-'+key).value=key==='date_time_of_incident'?dateFieldValue(draft.fields[key]):draft.fields[key];}}if(draft.docket.complainant_age&&!draft.person.age){draft.person.age=draft.docket.complainant_age;$('person-age').value=draft.person.age;}}
function renderConversation(){ $('conversation').replaceChildren();for(const item of draft.history){const b=document.createElement('div');b.className='bubble '+item.role;const label=document.createElement('strong');label.textContent=item.role==='user'?'You':'Complaint assistant';b.append(label,document.createTextNode(item.content));$('conversation').append(b);} $('answer-box').hidden=!!draft.docket.is_complete;renderReadings();}
async function turn(message,reset=false){const history=reset?[]:draft.history;const docket={...(reset?{}:draft.docket),evidence_available:draft.evidence.length?true:(reset?null:draft.docket.evidence_available)};const reviewed={date_time_of_incident:'date_time_of_incident',platform_involved:'platform_involved',financial_loss_amount:'financial_loss_amount',bank_name:'bank_name',utr_number:'utr_number',suspect_details:'suspect_details'};for(const [slot,key]of Object.entries(reviewed)){const value=draft.fields[key];if(value!==undefined&&value!==null&&String(value).trim()!=='')docket[slot]=value;}const result=await api('/api/guided/turn',{message,history:history.slice(-20),docket});const evidenceMessage=/\b(?:evidence|screenshot|receipt|payment slip)\b.*\b(?:added|attached|uploaded|sent|provided|shared)\b|\b(?:added|attached|uploaded|sent|provided|shared)\b.*\b(?:evidence|screenshot|receipt|payment slip)\b/i.test(message);draft.history=[...history,{role:'user',content:message,field:evidenceMessage?'evidence':docket.pending_field||'story'},{role:'assistant',content:result.reply}];draft.docket=result.docket;draft.storyAnalyzed=draft.story;hydrate();invalidate();renderConversation();}
function narrative(){const names={utr:'Transaction reference',suspect:'Suspect details',date:'Incident date',platform:'Platform',bank:'Bank or wallet',amount:'Money lost',age:'Age',evidence:'Evidence available'};const isClosureOrUnknown=text=>/^(?:i\s+)?(?:don['’]?t|do not) know(?:\s+(?:the )?(?:bank|reference|utr|number|name|details|answer))?[.! ]*$/i.test(text.trim())||/^(?:this|that) (?:was|is) all (?:the )?(?:information|info|details) i (?:had|have|know)[.! ]*$/i.test(text.trim())||/^(?:nothing else|no more (?:information|info|details)|that['’]?s everything|that is everything|everything i know)[.! ]*$/i.test(text.trim());const extras=draft.history.slice(2).filter(x=>x.role==='user'&&!isClosureOrUnknown(x.content)).map(x=>(names[x.field]||'Additional information')+': '+x.content);return draft.story+(extras.length?'\n\nAdditional details:\n'+extras.join('\n'):'');}
async function classify(){const result=await api('/api/guided/review',{narrative:narrative(),fields:draft.fields,age:draft.person.age?Number(draft.person.age):null,category:draft.category||null});draft.analysis=result;if(!draft.category)draft.category=result.category;$('category').value=draft.category;}
async function navigate(step){if(busy||voiceCapturing)return;if(step===4){await task('Checking the updated complaint…',async()=>{if(!validatePersonal())return;if(!draft.analysis)await classify();show(4);});}else show(step);}
function validatePersonal(){
 const message=IndianDetails.error(draft.person,locationData);
 if(message){show(3);throw Error(message);}
 draft.person.phone=IndianDetails.storedPhone(draft.person.phone);
 return true;
}
$('next').onclick=()=>task(draft.step===0?'Checking your description…':draft.step===4?'Creating your complaint report…':'Checking your details…',async()=>{
 const step=draft.step;
 if(step===0){if(draft.story.trim().length<20)throw Error('Please describe what happened in a little more detail.');if(draft.story!==draft.storyAnalyzed){draft.categoryManual=false;draft.category='';await turn(draft.story,true);}show(1);}
 else if(step===1){hydrate();await classify();show(2);}
 else if(step===2){if(draft.fields.financial_loss_amount!==''&&draft.fields.financial_loss_amount!=null&&(!Number.isFinite(Number(draft.fields.financial_loss_amount))||Number(draft.fields.financial_loss_amount)<0))throw Error('Enter a valid amount, or leave it blank.');if(!draft.analysis)await classify();show(3);}
 else if(step===3){if(!validatePersonal())return;await classify();show(4);}
 else if(step===4){if(!draft.confirmed)throw Error('Please confirm you have checked the complaint before creating the report.');if(!draft.analysis)throw Error('Your details changed. Please review them again.');await submit();show(5);}
});
$('back').onclick=()=>{if(!voiceCapturing)show(Math.max(0,draft.step-1));};
$('story').value=draft.story;$('story').oninput=()=>{draft.story=$('story').value;invalidate();draft.category='';draft.furthest=0;save();};
$('send-answer').onclick=()=>task('Checking your answer…',async()=>{const text=$('answer').value.trim();if(!text)throw Error('Type an answer, or choose “I don’t know”.');await turn(text);$('answer').value='';});
$('unknown').onclick=()=>task('Saving your answer…',()=>turn("I don't know"));
$('category').onchange=()=>{draft.category=$('category').value;draft.categoryManual=!!draft.category;invalidate();save();};
$('suspect').value=draft.suspect;$('suspect').oninput=()=>{draft.suspect=$('suspect').value;invalidate();save();};
$('id-kind').value=draft.idKind;$('id-kind').onchange=()=>{draft.idKind=$('id-kind').value;invalidate();save();};
$('confirm').checked=draft.confirmed;$('confirm').onchange=()=>{draft.confirmed=$('confirm').checked;save();};
function renderFiles(){ $('evidence-list').replaceChildren();draft.evidence.forEach((item,index)=>{const li=document.createElement('li'),a=document.createElement('a'),remove=document.createElement('button');a.href='/api/evidence/'+encodeURIComponent(item.filename);a.target='_blank';a.rel='noopener';a.textContent=item.name;remove.textContent='Remove';remove.onclick=()=>{draft.evidence.splice(index,1);draft.readings={};invalidate();renderFiles();save();};li.append(a,remove);$('evidence-list').append(li);});$('identity-status').textContent=draft.identity?'Attached: '+draft.identity.name:'';}
async function upload(input,identity=false){const files=[...input.files];await task(identity?'Saving identity document…':'Reading your evidence…',async()=>{for(const file of files){if(file.size>5*1024*1024)throw Error('Choose images or PDFs smaller than 5 MB.');const body=new FormData();body.append('file',file);const data=await api('/api/upload_evidence',body,true);const item={name:file.name,filename:data.filename,entities:data.entities||{},errors:data.ocr_errors||[]};if(identity)draft.identity=item;else draft.evidence.push(item);invalidate();renderFiles();save();}});input.value='';}
$('evidence').onchange=()=>upload($('evidence'));$('identity').onchange=()=>upload($('identity'),true);
function renderReadings(){const box=$('evidence-readings');box.replaceChildren();const map={amount:'financial_loss_amount',date:'date_time_of_incident',transaction_ref:'utr_number',bank_name:'bank_name',platform:'platform_involved',upi_id:'suspect_details'};if(!draft.evidence.length)return;const h=document.createElement('h3');h.textContent='Check details from your evidence';box.append(h);for(const file of draft.evidence){if(file.errors.length){const p=document.createElement('p');p.textContent=`${file.name}: Some text could not be read. You can enter the details yourself.`;box.append(p);}for(const [key,value] of Object.entries(file.entities)){if(!map[key]||value==null||value==='')continue;const id=file.filename+':'+key;const card=document.createElement('div');card.className='reading';const val=Array.isArray(value)?value.join(', '):String(value);const text=document.createElement('div');text.textContent=`${file.name} · ${key.replaceAll('_',' ')}: ${val}`;card.append(text);if(draft.fields[map[key]]&&String(draft.fields[map[key]])!==val){const diff=document.createElement('p');diff.textContent='Your current answer: '+draft.fields[map[key]]+'. Choose which detail to keep.';card.append(diff);}for(const [title,choice] of [['Use this detail','use'],['Keep my answer','keep']]){const b=document.createElement('button');b.textContent=draft.readings[id]===choice?'✓ '+title:title;b.onclick=()=>{draft.readings[id]=choice;if(choice==='use'){draft.fields[map[key]]=key==='amount'?val.replace(/[^\d.]/g,''):val;if(!draft.edited.includes(map[key]))draft.edited.push(map[key]);$('field-'+map[key]).value=draft.fields[map[key]];}invalidate();save();renderReadings();};card.append(b);}box.append(card);}}}
function reviewBlock(title,values){const b=document.createElement('section');b.className='review-block';const h=document.createElement('h3');h.textContent=title;b.append(h);if(typeof values==='string'){const p=document.createElement('p');p.textContent=values;b.append(p);}else for(const [key,value] of Object.entries(values)){const row=document.createElement('div');row.className='review-row';const label=document.createElement('span'),val=document.createElement('strong');label.textContent=key;val.textContent=value===0?'0':value||'Not provided';row.append(label,val);b.append(row);}return b;}
function renderReview(){const box=$('review');box.replaceChildren();box.append(reviewBlock('Your account',narrative()),reviewBlock('Incident details',Object.fromEntries(Object.entries(incident).map(([k,label])=>[label,draft.fields[k]]))),reviewBlock('Complaint category',draft.analysis?.category||draft.category),reviewBlock('Your details',Object.fromEntries(Object.entries(personal).map(([k,label])=>[label,draft.person[k]]))),reviewBlock('Suspect information',draft.suspect||draft.fields.suspect_details||'Unknown'),reviewBlock('Attachments',[...draft.evidence.map(x=>x.name),...(draft.identity?[draft.idKind+': '+draft.identity.name]:[])].join('\n')||'No attachments'));const law=draft.analysis?.legal||{};const lines=[];for(const [key,act]of [['it_act','IT Act'],['bns','BNS'],['other','Other']])for(const entry of law[key]||[])lines.push(`${entry.act||act} ${entry.section}: ${entry.description||''}`);box.append(reviewBlock('Suggested legal provisions',lines.join('\n\n')||'No matching provisions found. Further review is needed.'));}
async function submit(){if(!draft.submissionToken){draft.submissionToken=crypto.randomUUID();save();}const d=draft.fields;const evidence=[...draft.evidence.map(x=>({filename:x.filename,name:x.name,type:'Incident evidence'})),...(draft.identity?[{filename:draft.identity.filename,name:draft.identity.name,type:'Identity document: '+draft.idKind}]:[])];const body={submission_token:draft.submissionToken,intake_session_id:draft.id,investigator_consent:true,consent_details:{version:'guided-1',accepted_at:new Date().toISOString()},complainant:{...draft.person,age:draft.person.age?Number(draft.person.age):null,id_type:draft.idKind||'',id_upload_name:draft.identity?.filename||''},incident:{datetime:d.date_time_of_incident||'',category:draft.analysis.main_category,location:d.platform_involved?[d.platform_involved]:[]},incident_text:narrative(),original_complaint:draft.story,reviewed_fields:{...draft.fields},standardised_narrative:narrative(),sub_category:draft.analysis.category,evidence,transactions:d.financial_loss_amount!==''&&d.financial_loss_amount!=null?[{amount:Number(d.financial_loss_amount),bank:d.bank_name||'',account_no:'Not provided',transaction_id:d.utr_number||'',transaction_date:d.date_time_of_incident||''}]:[],suspects:draft.suspect||d.suspect_details?[{name:'Unknown',id_type:'Details provided by complainant',id_number:d.suspect_details||'Unknown',address:'Not provided',details:draft.suspect||''}]:[]};const saved=await api('/api/cases/submit',body);draft.submission={reference:saved.reference,pdf_url:saved.pdf_url};save();}
function updateVoiceControls(){
 $('record').disabled=busy||voiceCapturing&&recorder?.state!=='recording';
 $('record').textContent=voiceCapturing?(recorder?.state==='recording'?'Stop recording':'Opening microphone…'):'Record my voice';
 $('record').setAttribute('aria-pressed',String(recorder?.state==='recording'));
 $('audio').disabled=busy||voiceCapturing;
 for(const id of ['transcribe-recording','record-again','discard-recording'])$(id).disabled=busy||voiceCapturing||!pendingRecording;
 $('recording-indicator').hidden=recorder?.state!=='recording';
 $('recording-preview').hidden=!pendingRecording||voiceCapturing;
 for(const id of ['back','next','home','restart'])$(id).disabled=busy||voiceCapturing;
}
function releaseRecording(){
 $('recording-player').pause();$('recording-player').removeAttribute('src');$('recording-player').load();
 if(recordingUrl)URL.revokeObjectURL(recordingUrl);
 recordingUrl=null;pendingRecording=null;updateVoiceControls();
}
function stageRecording(file){
 if(!file.size){notice('The recording is empty. Please record again.');return;}
 if(file.size>25*1024*1024){notice('Choose a recording smaller than 25 MB.');return;}
 releaseRecording();pendingRecording=file;recordingUrl=URL.createObjectURL(file);
 $('recording-player').src=recordingUrl;$('recording-name').textContent=file.name;
 $('transcript-panel').hidden=true;
 $('voice-status').textContent='Recording ready. Listen, then choose Use recording, Record again, or Discard.';
 updateVoiceControls();
}
function stopRecordingResources(){
 clearInterval(recordingTimer);clearTimeout(recordingLimit);recordingTimer=null;recordingLimit=null;
 stream?.getTracks().forEach(track=>track.stop());stream=null;voiceCapturing=false;
}
async function startRecording(){
 if(busy||voiceCapturing)return;
 voiceCapturing=true;notice();$('voice-status').textContent='Allow microphone access to start recording.';updateVoiceControls();renderNavigation();
 try{
  if(!navigator.mediaDevices||!window.MediaRecorder)throw Error('Recording is unavailable in this browser. Choose a recording or type instead.');
  stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
  const mime=['audio/webm;codecs=opus','audio/mp4','audio/webm'].find(x=>MediaRecorder.isTypeSupported(x));
  const current=new MediaRecorder(stream,mime?{mimeType:mime}:{});recorder=current;
  const chunks=[];let recordingFailed=false;
  current.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
  current.onerror=()=>{recordingFailed=true;notice('Recording was interrupted. Please try again.');$('voice-status').textContent='Recording was interrupted. Please record again or choose a recording.';};
  current.onstop=()=>{
   stopRecordingResources();recorder=null;
   if(!recordingFailed){const type=current.mimeType||'audio/webm';stageRecording(new File(chunks,type.includes('mp4')?'recording.m4a':'recording.webm',{type}));}
   updateVoiceControls();renderNavigation();
  };
  current.start();
  // Replace the previous clip only once microphone access and recording succeed.
  releaseRecording();$('transcript-panel').hidden=true;
  const started=Date.now();$('recording-time').textContent='00:00';
  recordingTimer=setInterval(()=>{const seconds=Math.floor((Date.now()-started)/1000);$('recording-time').textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');},250);
  recordingLimit=setTimeout(()=>{if(current.state==='recording')current.stop();},120000);
  $('voice-status').textContent='Recording started. Speak clearly, then press Stop recording.';updateVoiceControls();
 }catch(error){stopRecordingResources();recorder=null;notice(error.name==='NotAllowedError'?'Microphone access was denied. Allow access in your browser, choose a recording, or type instead.':error.message);$('voice-status').textContent='Recording did not start. You can try again or choose a recording.';updateVoiceControls();renderNavigation();}
}
async function transcribe(file){await task('Transcribing your recording. You can check the words before continuing…',async()=>{
 $('recording-player').pause();$('voice-status').textContent='Transcribing your recording…';
 try{const body=new FormData();body.append('audio',file);const result=await api('/api/guided/transcribe',body,true);if(!result.text?.trim())throw Error('No clear speech was found. Try recording again or type your description.');$('transcript').value=result.text;$('transcript-panel').hidden=false;releaseRecording();$('voice-status').textContent='Transcript ready. Please check names, dates, and amounts.';}
 catch(error){$('voice-status').textContent='Transcription failed. Your recording is still here. Try again, record again, or discard it.';throw error;}
});}
$('audio').onchange=()=>{const file=$('audio').files[0];if(file&&!busy&&!voiceCapturing){notice();stageRecording(file);}$('audio').value='';};
$('record').onclick=()=>{if(recorder?.state==='recording'){recorder.stop();return;}startRecording();};
$('record-again').onclick=startRecording;
$('discard-recording').onclick=()=>{if(busy||voiceCapturing)return;releaseRecording();notice();$('voice-status').textContent='Recording discarded. You can record again, choose a recording, or type.';};
$('transcribe-recording').onclick=()=>{if(pendingRecording&&!busy&&!voiceCapturing)transcribe(pendingRecording);};
updateVoiceControls();
$('use-transcript').onclick=()=>{const text=$('transcript').value.trim();if(!text)return;$('story').value=[$('story').value,text].filter(Boolean).join('\n');$('story').dispatchEvent(new Event('input'));$('transcript-panel').hidden=true;};
$('home').onclick=()=>{if(busy||voiceCapturing)return;save();$('workspace').hidden=true;$('landing').hidden=false;};
function startNewComplaint(){
 if(busy||voiceCapturing)return;
 releaseRecording();stopRecordingResources();recorder=null;
 draft=fresh();
 for(const id of ['story','answer','suspect','id-kind','category','transcript','audio','evidence','identity'])$(id).value='';
 $('confirm').checked=false;$('transcript-panel').hidden=true;
 for(const id of ['voice-status','recording-name','reference'])$(id).textContent='';
 $('recording-time').textContent='00:00';$('download').removeAttribute('href');
 for(const id of ['incident-fields','person-fields','conversation','evidence-readings','review'])$(id).replaceChildren();
 // Rebuild field handlers so they write to the new draft's objects.
 fields('incident-fields',incident,'field-',draft.fields);
 fields('person-fields',personal,'person-',draft.person);
 if(locationData){setLocationOptions($('person-state'),locationData.states,'Choose your state / union territory');$('person-state').disabled=false;populateDistricts();}
 else loadLocations();
 renderFiles();renderConversation();notice();updateVoiceControls();show(0);
}
$('start').onclick=startNewComplaint;$('resume').onclick=()=>show(draft.step);
$('restart').onclick=startNewComplaint;
renderFiles();$('resume').hidden=!(draft.story||draft.evidence.length);fetch('/api/guided/warmup',{method:'POST'}).catch(()=>{});
fetch('/api/taxonomy').then(r=>r.json()).then(data=>{const cats=Array.isArray(data)?data:Object.values(data).flatMap(x=>Array.isArray(x)?x:typeof x==='object'?Object.values(x).flat():[]);const names=[...new Set(cats.filter(x=>typeof x==='string'))];for(const name of names){const option=document.createElement('option');option.value=name;option.textContent=name;$('category').append(option);}$('category').value=draft.category;}).catch(()=>{});
window.addEventListener('beforeunload',e=>{if(busy||voiceCapturing||pendingRecording){e.preventDefault();e.returnValue='';}});
