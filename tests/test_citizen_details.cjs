const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const details=require('../static/citizen-details.js');
const data=require('../static/data/india-locations.json');
const valid=()=>({name:'Example Citizen',phone:'9876543210',age:'25',state:'Maharashtra',district:'Pune',pincode:'411001'});

test('offline directory contains all state/UT entries and consistent district codes',()=>{
 assert.equal(data.states.length,36);
 const codes=data.states.flatMap(state=>state.districts.map(district=>district.code));
 assert.equal(new Set(codes).size,codes.length);
 assert.ok(details.state(data,'Maharashtra').districts.some(d=>d.name==='Nashik'));
 assert.equal(data.states.filter(s=>s.type==='U').length,8);
});
test('Indian phone numbers retain one +91 prefix across saved drafts and pasted input',()=>{
 for(const number of ['9876543210','+91 9876543210','919876543210','09876543210']){
  assert.equal(details.nationalPhone(number),'9876543210');
  assert.equal(details.storedPhone(number),'+91 9876543210');
 }
 assert.ok(details.error({...valid(),phone:'+1 2125551234'},data));
 assert.ok(details.error({...valid(),phone:'not a number'},data));
});
test('required age, selected district and six-digit PIN are checked',()=>{
 assert.equal(details.error(valid(),data),'');
 for(const age of ['',null,'0','121','25.5'])assert.match(details.error({...valid(),age},data),/age/);
 for(const pincode of ['','12345','012345','1234567','ABCDEF'])assert.match(details.error({...valid(),pincode},data),/PIN/);
 assert.match(details.error({...valid(),district:'Bengaluru Urban'},data),/district/);
 assert.match(details.error(valid(),null),/not loaded/);
});
test('form uses a fixed country prefix, required age and dependent dropdowns',async()=>{
 const source=fs.readFileSync(path.join(__dirname,'../static/citizen.js'),'utf8');
 const elements=new Map();
 const create=tag=>({tagName:tag,children:[],value:'',append(...items){this.children.push(...items);for(const item of items)if(item.id)elements.set(item.id,item);},replaceChildren(){this.children=[];},setAttribute(k,v){this[k]=v;}});
 const get=id=>{if(!elements.has(id))elements.set(id,create('div'));return elements.get(id);};
 const person=valid();
 const ctx=vm.createContext({$:get,IndianDetails:details,document:{createElement:create},draft:{person,edited:[]},busy:false,locationData:null,invalidate(){},save(){},fetch:async()=>({ok:true,json:async()=>data})});
 vm.runInContext(source.match(/const personal = .*;/)[0],ctx);
 vm.runInContext(source.slice(source.indexOf('function fields('),source.indexOf("fields('incident-fields'")),ctx);
 vm.runInContext("fields('person-fields',personal,'person-',draft.person)",ctx);
 await vm.runInContext('loadLocations()',ctx);
 assert.equal(get('person-age').required,true);
 assert.equal(get('phone-country').textContent,'+91');
 assert.equal(get('person-state').tagName,'select');
 assert.equal(get('person-district').value,'Pune');
 get('person-state').value='Karnataka';get('person-state').onchange();
 assert.equal(person.district,'');
 assert.equal(get('person-district').value,'');
 assert.ok(!get('person-district').children.some(item=>item.value==='Pune'));
 assert.equal(get('person-pincode').autocomplete,'postal-code');
 assert.equal(get('person-pincode').required,true);
});
