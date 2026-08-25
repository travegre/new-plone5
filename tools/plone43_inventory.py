#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only Plone 4.3/Data.fs inventory.

Run with the Plone 4.3 instance interpreter:
    bin/instance run tools/plone43_inventory.py /tmp/plone43-inventory

The script only reads ZODB/application objects and writes reports outside the
ZODB. It does not add, edit, delete, publish, reindex, commit, or migrate.
"""
from __future__ import print_function
import datetime, json, os, sys, traceback
from collections import Counter, defaultdict
from Acquisition import aq_base
from OFS.interfaces import IFolderish
from zope.interface import providedBy, implementedBy

SITES = (('portal','/portal','IMI imenik'),('dezurstva','/dezurstva','Dežurstva'),
         ('kiestra','/kiestra','Kiestra'),('preiskave','/preiskave','Preiskave'),
         ('nadomescanja','/nadomescanja','Nadomeščanja'))
MAX_SAMPLES=5; MAX_FIELDS=100; MAX_VALUE=1500; MAX_FORM_DEPTH=8
try: text_type=unicode
except NameError: text_type=str

def text(v, limit=MAX_VALUE):
    if v is None: return None
    try: v=v if isinstance(v,text_type) else text_type(v)
    except Exception: v=repr(v)
    return v if len(v)<=limit else v[:limit]+'...'

def scalar(v):
    if v is None or isinstance(v,(bool,int,float)): return v
    if isinstance(v,(list,tuple,set)): return [scalar(x) for x in list(v)[:100]]
    if isinstance(v,dict): return dict((text(k,300),scalar(x)) for k,x in list(v.items())[:100])
    return text(v)

def call(fn, default=None):
    try: return fn()
    except Exception: return default

def dotted(o):
    c=getattr(o,'__class__',None); return '%s.%s'%(c.__module__,c.__name__) if c else None

def hierarchy(o):
    r=[]; seen=set(); c=getattr(o,'__class__',None)
    while c and c not in seen:
        seen.add(c); r.append('%s.%s'%(c.__module__,c.__name__)); b=getattr(c,'__bases__',()); c=b[0] if b else None
    return r

def interfaces(o):
    def names(spec):
        try: return ['%s.%s'%(i.__module__,i.__name__) for i in spec]
        except Exception: return []
    return {'provided':names(providedBy(o)),'implemented':names(implementedBy(aq_base(o)))}

def path(o):
    try: return o.absolute_url_path()
    except Exception:
        parts=[]; cur=o
        for _ in range(100):
            if cur is None: break
            parts.append(getattr(cur,'id','')); cur=getattr(cur,'aq_parent',None)
        return '/'+ '/'.join(reversed([p for p in parts if p]))

def ptype(o): return call(lambda:o.portal_type) or call(lambda:o.getPortalTypeName())

def vocab(field,obj):
    out={}
    for name in ('Vocabulary','vocabulary','getVocabulary'):
        fn=getattr(field,name,None)
        if callable(fn):
            try:
                v=fn(obj); out['method']=name
                try: out['items']=[scalar(x) for x in list(v)[:200]]
                except Exception: out['items']=[]
                break
            except Exception as e: out['error']=text(e)
    for a in ('vocabulary','enforceVocabulary'):
        if hasattr(field,a): out[a]=scalar(getattr(field,a))
    try: out['name']=text(field.getVocabularyName())
    except Exception: pass
    return out

def schema_field(field,sample):
    out={'name':call(field.getName),'class':dotted(field),'field_type':field.__class__.__name__,
         'required':bool(getattr(field,'required',False)),'multivalued':bool(getattr(field,'multiValued',False)),
         'searchable':bool(getattr(field,'searchable',False)),'index':scalar(getattr(field,'index',None)),
         'storage':dotted(call(field.getStorage)),'default':None,'default_factory':None,'vocabulary':vocab(field,sample)}
    try: out['default']=scalar(field.getDefault(sample))
    except Exception: out['default']=scalar(getattr(field,'default',None))
    try: out['default_factory']=text(field.default_method)
    except Exception: pass
    for a in ('widget','widgetFactory','enforceVocabulary'):
        if hasattr(field,a):
            v=getattr(field,a); out[a]=dotted(v) if not isinstance(v,(str,text_type)) else text(v)
    return out

def schema(o):
    s=call(o.Schema); return [] if s is None else [schema_field(f,o) for f in call(s.fields,[])[:MAX_FIELDS]]

def field_value(o,f):
    try: v=f.getRaw(o)
    except Exception: v=call(lambda:f.get(o))
    out={'value':scalar(v)}
    try: out['content_type']=text(f.getContentType(o))
    except Exception: pass
    return out

def values(o):
    s=call(o.Schema); out={}
    if s is None: return out
    for f in call(s.fields,[])[:MAX_FIELDS]:
        n=call(f.getName)
        if n: out[n]=field_value(o,f)
    return out

def binaries(o):
    s=call(o.Schema); out=[]
    if s is None: return out
    for f in call(s.fields,[]):
        if f.__class__.__name__ not in ('FileField','ImageField'): continue
        v=call(lambda:f.getRaw(o))
        if v is None: continue
        size=call(v.getSize,call(lambda:len(v.data)))
        out.append({'field':call(f.getName),'type':f.__class__.__name__,'size':size,'filename':text(getattr(v,'filename',None))})
    return out

def local_roles(o):
    return {'roles':dict(call(o.get_local_roles,{}) or {}),'blocked':call(o.get_local_role_block),
            'has_ac_local_roles':bool(getattr(aq_base(o),'__ac_local_roles__',None))}

def permissions(o):
    out={}
    for item in getattr(getattr(o,'__class__',None),'__ac_permissions__',()):
        try: out[text(item[0])]=list(item[1] or ())
        except Exception: pass
    return out

def workflow(o,tool):
    out={'chain':[],'review_state':None,'states_by_chain':{}}
    if tool is None: return out
    try: out['chain']=list(tool.getChainForPortalType(ptype(o)) or ())
    except Exception: pass
    try: out['review_state']=tool.getInfoFor(o,'review_state',None)
    except Exception: pass
    try: out['states_by_chain']=dict(tool.getWorkflowStateByChainFor(o) or {})
    except Exception: pass
    return out

def references(o,refcat):
    out={'outgoing':[],'incoming':[],'broken_outgoing':[],'broken_incoming':[]}
    try:
        for t in o.getRefs():
            x={'path':path(t),'uid':call(t.UID),'class':dotted(t)}
            (out['outgoing'] if x['path'] else out['broken_outgoing']).append(x)
    except Exception: pass
    if refcat is not None:
        try:
            for b in refcat.getBackReferences(o):
                t=call(b.getObject); x={'uid':call(lambda:b.UID),'path':path(t) if t else None}
                (out['incoming'] if t else out['broken_incoming']).append(x)
        except Exception: pass
    return out

def summary(o,wf,refcat):
    return {'path':path(o),'id':call(o.getId,getattr(o,'id',None)),'title':text(call(o.Title,call(lambda:o.title))),
            'portal_type':ptype(o),'class':dotted(o),'class_hierarchy':hierarchy(o),'interfaces':interfaces(o),
            'schema':schema(o),'field_values':values(o),'workflow':workflow(o,wf),'local_roles':local_roles(o),
            'permissions':permissions(o),'references':references(o,refcat),'binaries':binaries(o),'folderish':IFolderish.providedBy(o)}

def walk(root):
    stack=[root]
    while stack:
        o=stack.pop(); yield o
        if IFolderish.providedBy(o): stack.extend(reversed(call(o.objectValues,[]) or []))

def type_definition(site,pt):
    ti=call(lambda:site.portal_types.getTypeInfo(pt))
    if ti is None: return None
    out={'id':pt,'title':text(getattr(ti,'title',None)),'factory':text(getattr(ti,'factory',None)),'klass':text(getattr(ti,'klass',None)),
         'allowed_content_types':list(getattr(ti,'allowed_content_types',()) or ()),'global_allow':bool(getattr(ti,'global_allow',False)),
         'filter_content_types':bool(getattr(ti,'filter_content_types',False)),'default_view':text(getattr(ti,'default_view',None)),
         'immediate_view':text(getattr(ti,'immediate_view',None)),'aliases':dict(getattr(ti,'aliases',{}) or {}),'actions':[],
         'workflow_chain':list(call(lambda:site.portal_workflow.getChainForPortalType(pt),()) or ()),'permissions':{}}
    try: out['actions']=[scalar(a) for a in ti.listActions()]
    except Exception: pass
    try: out['permissions']=dict(ti.getPermissionMap())
    except Exception: pass
    return out

def pfg_object(o,depth=0):
    out={'path':path(o),'id':call(o.getId,getattr(o,'id',None)),'title':text(call(o.Title)),'class':dotted(o),'portal_type':ptype(o),
         'interfaces':interfaces(o),'attributes':{},'schema':schema(o),'children':[]}
    attrs=('fgFieldName','fgFieldType','fgFieldDescription','fgRequired','fgDefault','fgVocabulary','fgVocabularyName','fgFormat',
           'fgTales','fgOverride','fgString','fgField','formField','formPrologue','thanksPrologue','thanksEpilogue','thanksPageTemplate',
           'submitLabel','recipient_email','subject','replyto','mailhost','useFormMail','useFormMailer')
    for a in attrs:
        if hasattr(o,a): out['attributes'][a]=scalar(getattr(o,a))
    if depth<MAX_FORM_DEPTH and IFolderish.providedBy(o):
        for c in call(o.objectValues,[])[:500]: out['children'].append(pfg_object(c,depth+1))
    return out

def is_pfg(o):
    pt=ptype(o) or ''; cls=dotted(o) or ''
    return any(x in pt for x in ('FormFolder','FormMailer','FormField','FormCustomScript')) or 'PloneFormGen' in cls or 'Products.PloneFormGen' in cls

def inventory_site(site,name,label):
    wf=call(lambda:site.portal_workflow); refcat=call(lambda:site.reference_catalog)
    counts=Counter(); classes=defaultdict(set); samples=defaultdict(list); pfg=[]; unknown=[]; wfa=defaultdict(Counter); lrc=Counter(); bc=Counter(); bb=Counter(); total=0
    for o in walk(site):
        total+=1; pt=ptype(o) or '<no portal_type>'; counts[pt]+=1; classes[pt].add(dotted(o))
        if len(samples[pt])<MAX_SAMPLES: samples[pt].append(summary(o,wf,refcat))
        if is_pfg(o): pfg.append(pfg_object(o))
        if pt in ('Unknown','<no portal_type>'): unknown.append(summary(o,wf,refcat))
        for b in binaries(o): bc[b['type']]+=1; bb[b['type']]+=b.get('size') or 0
        for chain in workflow(o,wf).get('chain',[]): wfa[pt][chain]+=1
        if local_roles(o).get('roles'): lrc[pt]+=1
    types={}
    for pt in sorted(counts): types[pt]={'count':counts[pt],'classes':sorted(x for x in classes[pt] if x),'definition':type_definition(site,pt),
                                           'workflow_assignments':dict(wfa[pt]),'samples':samples[pt]}
    return {'site':name,'path':site.absolute_url_path(),'title':label,'objects_walked':total,'portal_types':types,'pfg_objects':pfg,'unknown_objects':unknown,
            'binary_summary':{'counts':dict(bc),'bytes':dict(bb)},'objects_with_local_roles':dict(lrc),'class':dotted(site),'class_hierarchy':hierarchy(site),'interfaces':interfaces(site)}

def global_inventory(app):
    out={'portal_types':[],'workflows':[],'tools':{}}
    for n in ('portal_types','portal_workflow','portal_catalog','reference_catalog','portal_registry'): out['tools'][n]=hasattr(app,n)
    pt=call(lambda:app.portal_types)
    if pt:
        for ti in pt.objectValues(): out['portal_types'].append({'id':getattr(ti,'id',None),'title':text(getattr(ti,'title',None)),'factory':text(getattr(ti,'factory',None)),'klass':text(getattr(ti,'klass',None))})
    wf=call(lambda:app.portal_workflow)
    if wf:
        for d in call(wf.objectValues,[]) or []: out['workflows'].append({'id':getattr(d,'id',None),'title':text(getattr(d,'title',None)),'class':dotted(d),'states':[getattr(x,'id',None) for x in call(lambda:d.states.objectValues,[]) or []]})
    return out

def md(data):
    L=['# Plone 4.3 Read-only Database Inventory','','Generated by `tools/plone43_inventory.py`. Field values are representative samples and are truncated; this is not a content export.','',
       '## Runtime','','- Generated: `%s`'%data['generated_at'],'- Python: `%s`'%data['runtime']['python'].replace('\n',' '),'- Zope: `%s`'%data['runtime'].get('zope'),'- Plone: `%s`'%data['runtime'].get('plone'),'']
    for s in data['sites']:
        L += ['## /%s — %s'%(s['site'],s['title']),'','**Objects walked:** %s'%s['objects_walked'],'','| Portal type | Count | Runtime classes | Workflow chains |','|---|---:|---|---|']
        for pt,i in sorted(s['portal_types'].items()): L.append('| `%s` | %s | %s | %s |'%(pt,i['count'],'<br>'.join(i['classes']),'<br>'.join(sorted(i['workflow_assignments']))))
        L += ['','### PloneFormGen','']
        if s['pfg_objects']:
            for f in s['pfg_objects']: L += ['#### `%s`'%f['path'],'','```json',json.dumps(f,ensure_ascii=False,indent=2,sort_keys=True),'```','']
        else: L += ['No PFG objects detected by runtime class/portal-type heuristics.','']
        L += ['### Binary summary','','```json',json.dumps(s['binary_summary'],indent=2,sort_keys=True),'```','','### Unknown/no-portal-type objects','']
        if s['unknown_objects']: L += ['```json',json.dumps(s['unknown_objects'],ensure_ascii=False,indent=2,sort_keys=True),'```','']
        else: L += ['None detected by the inventory heuristics.','']
        L += ['### Representative object samples','']
        for pt,i in sorted(s['portal_types'].items()):
            if i['samples']:
                o=i['samples'][0]; L += ['<details><summary><code>%s</code> — %s</summary>'%(pt,o.get('path')),'','```json',json.dumps(o,ensure_ascii=False,indent=2,sort_keys=True),'```','</details>','']
    if data['errors']: L += ['## Errors','','```json',json.dumps(data['errors'],ensure_ascii=False,indent=2),'```','']
    return '\n'.join(L)+'\n'

def run(app,outdir):
    if not os.path.isdir(outdir): os.makedirs(outdir)
    result={'schema_version':1,'read_only':True,'generated_at':datetime.datetime.utcnow().isoformat()+'Z','runtime':{'python':sys.version,'zope':None,'plone':None},'global':global_inventory(app),'sites':[],'errors':[]}
    try:
        import Zope2; result['runtime']['zope']=text(getattr(Zope2,'__version__',None))
    except Exception: pass
    try:
        import Products.CMFPlone; result['runtime']['plone']=text(getattr(Products.CMFPlone,'__version__',None))
    except Exception: pass
    for name,site_path,label in SITES:
        try: result['sites'].append(inventory_site(app.unrestrictedTraverse(site_path.lstrip('/')),name,label))
        except Exception as e: result['errors'].append({'site':site_path,'error':text(e),'traceback':traceback.format_exc()})
    with open(os.path.join(outdir,'plone43_inventory.json'),'w') as f: json.dump(result,f,ensure_ascii=False,indent=2,sort_keys=True)
    with open(os.path.join(outdir,'plone43_inventory.md'),'wb') as f: f.write(md(result).encode('utf-8'))
    print('Inventory written to %s'%os.path.abspath(outdir))

if 'app' not in globals(): raise SystemExit('Use the Plone 4.3 bin/instance run command; do not execute with system Python.')
outdir=sys.argv[1] if len(sys.argv)>1 else '/tmp/plone43-inventory'
run(app,outdir)
