/* Indian contact details. Directory data is loaded from this application only. */
(function(root) {
  'use strict';
  function nationalPhone(value) {
    const text=String(value||'').trim();
    if(!/^[+\d\s()-]*$/.test(text))return text;
    const digits=text.replace(/\D/g,'');
    if(digits.length===12&&digits.startsWith('91'))return digits.slice(2);
    if(text.startsWith('+91'))return digits.slice(2);
    if(digits.length===11&&digits.startsWith('0'))return digits.slice(1);
    return digits;
  }
  function storedPhone(value){const number=nationalPhone(value);return number?'+91 '+number:'';}
  function states(data){return data?.states||[];}
  function state(data,name){return states(data).find(item=>item.name.toLowerCase()===String(name||'').trim().toLowerCase());}
  function error(person,data){
    if(!String(person.name||'').trim())return 'Please enter your full name.';
    if(!/^[1-9]\d{9}$/.test(nationalPhone(person.phone)))return 'Please enter a 10-digit Indian phone number. +91 is already included.';
    if(!/^\d{1,3}$/.test(String(person.age||''))||Number(person.age)<1||Number(person.age)>120)return 'Please enter your age in completed years, from 1 to 120.';
    if(person.email&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(person.email))return 'Please check your email address.';
    if(!data)return 'The location list has not loaded. Please retry loading it in About you.';
    const selected=state(data,person.state);
    if(!selected)return 'Please choose your state or union territory from the list.';
    if(!selected.districts.some(item=>item.name===person.district))return 'Please choose a district for your selected state or union territory.';
    if(!/^[1-9]\d{5}$/.test(String(person.pincode||'')))return 'Please enter a six-digit PIN code.';
    return '';
  }
  const api={nationalPhone,storedPhone,states,state,error};
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.IndianDetails=api;
})(globalThis);
