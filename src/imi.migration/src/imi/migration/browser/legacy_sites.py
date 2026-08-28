# -*- coding: utf-8 -*-
"""Plone 5 browser implementations for the four remaining legacy sites.

The old Plone 4 applications used site-specific portal_skins main templates,
Python Scripts and Archetypes helper methods. Keep their business behavior in
explicit browser views instead of reviving the old global skin machinery.
"""
from datetime import date, datetime, timedelta
from html import escape
from io import BytesIO
import json

from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile


DAY_NAMES = {0:u'ponedeljek',1:u'torek',2:u'sreda',3:u'četrtek',4:u'petek',5:u'sobota',6:u'nedelja'}
MONTH_NAMES = {1:u'januar',2:u'februar',3:u'marec',4:u'april',5:u'maj',6:u'junij',7:u'julij',8:u'avgust',9:u'september',10:u'oktober',11:u'november',12:u'december'}


def _portal(context):
    return api.portal.get()


def _application(context):
    return context.getPhysicalRoot()


def _sibling_site(context, site_id):
    return _application(context).get(site_id)


def _staff_directory(context):
    site = _sibling_site(context, 'dezurstva')
    return site.get('seznam_zaposlenih') if site is not None else None


def _staff_objects(context):
    directory = _staff_directory(context)
    if directory is None:
        return []
    return [employee for employee in directory.objectValues()
            if getattr(employee, 'portal_type', None) == 'imi.staff.employee'
            and not bool(getattr(employee, 'exclude_from_nav', False))]


def _employee_id(employee):
    return str(getattr(employee, 'source_employee_id', '') or employee.getId())


def _employee_by_id(context, identifier):
    identifier = str(identifier or '')
    directory = _staff_directory(context)
    if directory is None:
        return None
    found = directory.get(identifier)
    if found is not None:
        return found
    for employee in _staff_objects(context):
        if _employee_id(employee) == identifier:
            return employee
    return None


def _staff_title(context, identifier):
    employee = _employee_by_id(context, identifier)
    return employee.Title() if employee is not None else str(identifier or '')


def _staff_options(context):
    items = [(_employee_id(employee), employee.Title() or _employee_id(employee)) for employee in _staff_objects(context)]
    return sorted(items, key=lambda item: item[1].lower())


def _parse_date(value, default_today=False):
    value = str(value or '').strip()
    if not value and default_today:
        return date.today()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(u'Datum mora biti veljaven.')


def _formatted_date(value):
    prefix = u'danes, ' if value == date.today() else u''
    return u'%s%s, %02d.%02d.%04d' % (prefix, DAY_NAMES[value.weekday()], value.day, value.month, value.year)


def _rich(value):
    if value is None:
        return u''
    output = getattr(value, 'output', None)
    if output is not None:
        return output
    raw = getattr(value, 'raw', None)
    if raw is not None:
        return raw
    return str(value)


def _period(request):
    mode = str(request.form.get('izbira') or request.form.get('izvoz-1-izbira') or request.form.get('izvoz-2-izbira') or '')
    today = date.today(); monday = today - timedelta(days=today.weekday())
    if mode == 'teden': return monday - timedelta(days=7), monday - timedelta(days=1)
    if mode == 'tedenplus2': return monday, monday + timedelta(days=14)
    if mode == 'tekoci':
        first=today.replace(day=1); next_month=(first.replace(day=28)+timedelta(days=4)).replace(day=1); return first,next_month-timedelta(days=1)
    if mode == 'pretekli':
        first=today.replace(day=1); last=first-timedelta(days=1); return last.replace(day=1),last
    if mode == 'oddo':
        first=_parse_date(request.form.get('od')); last=_parse_date(request.form.get('do')); return (first,last) if first<=last else (last,first)
    raise ValueError(u'Izberite obdobje za izvoz.')


def _date_group(rows):
    grouped={}
    for item in rows: grouped.setdefault(item['date'].year,{}).setdefault(item['date'].month,[]).append(item)
    result=[]
    for year in sorted(grouped,reverse=True):
        months=[]
        for month in sorted(grouped[year],reverse=True):
            months.append({'number':month,'name':MONTH_NAMES[month],'dates':sorted(grouped[year][month],key=lambda row:row['date'],reverse=True)})
        result.append({'year':year,'months':months})
    return result


def _editor(context):
    return api.user.has_permission('Modify portal content', obj=context)


class DirectoryPublicView(BrowserView):
    template = ViewPageTemplateFile('directory_public.pt')
    def __call__(self): return self.template()
    @property
    def portal(self): return _portal(self.context)
    def categories(self):
        base=self.portal.get('data2')
        if base is None: return []
        result=[]
        for folder in base.objectValues():
            if getattr(folder,'portal_type',None)!='Folder': continue
            children=[child for child in folder.objectValues() if getattr(child,'portal_type',None)=='Folder']
            result.append({'title':folder.Title() or folder.getId(),'children':[child.Title() or child.getId() for child in children]})
        return result
    def is_editor(self): return _editor(self.portal)


class DirectoryHomeView(DirectoryPublicView):
    admin_template=ViewPageTemplateFile('directory_admin.pt')
    def __call__(self): return self.admin_template() if self.is_editor() else self.template()


class DirectorySearchView(BrowserView):
    """Fast legacy-compatible livesearch; cache searchable text per Zope worker."""
    searchable_fields=('title','predime','ime','priimek','zaime','oddelek','telefon','opis','enota','lokacija','dodatna','dect','fax','mobilna','multitone','zunanja','enaslov','zenaslov')

    def _phone(self,value,mobile=False):
        value=str(value or '').strip()
        if not value:return ''
        if mobile:return value if value.startswith('0') else '0'+value
        return '(01)\u00a0522\u00a0'+value if len(value)<7 else value

    def _search_cache(self, portal):
        cache=getattr(portal,'_v_imi_directory_search_cache',None)
        if cache is not None:return cache
        rows=[]
        brains=portal.portal_catalog(portal_type='imi.directory.person',path='/'.join(portal.getPhysicalPath()))
        for brain in brains:
            try: obj=brain.getObject()
            except Exception: continue
            values=[]
            for field in self.searchable_fields:
                value=obj.Title() if field=='title' else getattr(obj,field,'')
                values.append(str(value or '').lower())
            rows.append((u' '.join(values),obj))
        portal._v_imi_directory_search_cache=rows
        return rows

    def __call__(self):
        portal=_portal(self.context)
        query=str(self.request.form.get('q') or self.request.form.get('searchGadget') or '').strip()
        words=[word.lower() for word in query.replace('*',' ').replace('+',' ').split() if word]
        objects=[]
        if words:
            for haystack,obj in self._search_cache(portal):
                if all(word in haystack for word in words): objects.append(obj)
        objects.sort(key=lambda obj:((getattr(obj,'priimek','') or 'ŽŽŽŽŽ').lower(),(getattr(obj,'ime','') or '').lower()))
        objects=objects[:100]
        self.request.response.setHeader('Content-Type','text/html; charset=utf-8')
        if not objects:
            return u'<fieldset class="livesearchContainer"><legend id="livesearchLegend">LiveSearch ↓</legend><div class="LSIEFix"><div id="LSNothingFound">No matching results found.</div></div></fieldset>'
        out=[u'<fieldset class="livesearchContainer"><legend id="livesearchLegend">LiveSearch ↓ zadetkov: %d</legend><div class="LSIEFix"><table class="tabela" cellspacing="0" cellpadding="0"><thead><tr><th></th><th>Ime</th><th>Priimek</th><th></th><th>Oddelek</th><th>Telefon</th><th>DECT</th><th>Mobilna</th><th>Enota</th></tr></thead><tbody>' % len(objects)]
        for obj in objects:
            phone=self._phone(getattr(obj,'telefon','')); dect=self._phone(getattr(obj,'dect','')); mobile=self._phone(getattr(obj,'mobilna',''),mobile=True)
            full_name=u' '.join(filter(None,[str(getattr(obj,'predime','') or ''),str(getattr(obj,'ime','') or ''),str(getattr(obj,'priimek','') or ''),str(getattr(obj,'zaime','') or '')]))
            details=[]
            for label,attr in (('Telefon','telefon'),('Dodatna','dodatna'),('DECT','dect'),('Fax','fax'),('Mobitel','mobilna'),('Multitone','multitone'),('Zunanja','zunanja')):
                raw=getattr(obj,attr,'') or ''
                if raw: details.append(u'<br />%s: %s' % (escape(label),escape(self._phone(raw,mobile=attr in ('mobilna','zunanja')))))
            for label,attr in (('E-naslov','enaslov'),('Zunanji e-naslov','zenaslov')):
                value=str(getattr(obj,attr,'') or '')
                if value: details.append(u'<br />%s: <a href="mailto:%s">%s</a>'%(escape(label),escape(value),escape(value)))
            out.append(u'<tr class="tri"><td class="enota">%s</td><td>%s</td><td>%s</td><td class="enota">%s</td><td class="enota">%s</td><td>%s</td><td class="enota">%s</td><td class="enota">%s</td><td class="enota">%s</td></tr>'%(escape(str(getattr(obj,'predime','') or '')),escape(str(getattr(obj,'ime','') or '')),escape(str(getattr(obj,'priimek','') or '')),escape(str(getattr(obj,'zaime','') or '')),escape(str(getattr(obj,'oddelek','') or '')),escape(phone),escape(dect),escape(mobile),escape(str(getattr(obj,'enota','') or ''))))
            out.append(u'<tr class="person-detail" style="display:none"><td colspan="9"><div class="ime">%s</div><div class="stevilka">%s</div><br />%s<br />%s<br />%s<br />%s%s</td></tr>'%(escape(full_name),escape(phone),escape(str(getattr(obj,'oddelek','') or '')),escape(str(getattr(obj,'opis','') or '')),escape(str(getattr(obj,'enota','') or '')),escape(str(getattr(obj,'lokacija','') or '')),u''.join(details)))
        out.append(u'</tbody></table></div></fieldset>')
        return u''.join(out)


KIESTRA_FIELDS=(('priprava_vzorcev','priprava_vzorcev_text',u'Priprava vzorcev'),('cepljenje_vzorcev','cepljenje_vzorcev_text',u'Inoqula + Sortera'),('odcitavanje','odcitavanje_text',u'Odčitavanje'),('identifikacija','identifikacija_text',u'Ime bakterije'),('antibiogram','antibiogram_text',u'ID+ATB, ATB, izolacija'),('odpad','odpad_text',u'OFF'))
KIESTRA_COPY_FIELDS=('priprava_vzorcev','priprava_vzorcev_text','cepljenje_vzorcev','cepljenje_vzorcev_text','odcitavanje','odcitavanje_text','identifikacija','identifikacija_text','antibiogram','antibiogram_text','izolacija','izolacija_text','odpad','odpad_text','ciscenje','ciscenje_text','stalni_tekst')

def _settings_days(portal):
    settings=portal.get('nastavitve'); return settings.get('dezurstva') if settings is not None else None

class KiestraPublicView(BrowserView):
    template=ViewPageTemplateFile('kiestra_public.pt')
    def __call__(self): return self.template()
    @property
    def portal(self): return _portal(self.context)
    def selected_date(self):
        try:return _parse_date(self.request.form.get('datum'),default_today=True)
        except ValueError:return date.today()
    def selected_date_id(self):return self.selected_date().strftime('%Y-%m-%d')
    def today_id(self):return date.today().strftime('%Y-%m-%d')
    def formatted_date(self):return _formatted_date(self.selected_date())
    def previous_date(self):return (self.selected_date()-timedelta(days=1)).strftime('%Y-%m-%d')
    def next_date(self):return (self.selected_date()+timedelta(days=1)).strftime('%Y-%m-%d')
    def day_object(self):
        folder=_settings_days(self.portal); return folder.get(self.selected_date_id()) if folder is not None else None
    def last_change(self):
        folder=_settings_days(self.portal)
        if folder is None:return ''
        brains=self.portal.portal_catalog(portal_type='imi.kiestra.work_day',path='/'.join(folder.getPhysicalPath()),sort_on='modified',sort_order='descending')
        return brains[0].modified.asdatetime().strftime('%d.%m.%Y ob %H:%M') if brains else ''
    def _short_name(self,identifier):
        title=_staff_title(self.context,identifier).strip(); parts=title.split(); return u'%s %s.'%(parts[0],parts[-1][0]) if len(parts)>1 else title
    def columns(self):
        obj=self.day_object(); result=[]
        for field,note_field,label in KIESTRA_FIELDS:
            values=list(getattr(obj,field,()) or ()) if obj is not None else []
            result.append({'field':field,'label':label,'names':[self._short_name(v) for v in values],'note':str(getattr(obj,note_field,'') or '') if obj is not None else ''})
        return result
    def rows(self):
        columns=self.columns(); maximum=max([len(col['names']) for col in columns]+[0]); return [[col['names'][idx] if idx<len(col['names']) else '' for col in columns] for idx in range(maximum)]
    def notes(self):return [col['note'] for col in self.columns()]
    def constant_text(self):
        obj=self.day_object(); return _rich(getattr(obj,'stalni_tekst',None)) if obj is not None else ''
    def staff_options(self):return _staff_options(self.context)
    def selected_person(self):return str(self.request.form.get('oseba') or '')
    def selected_person_title(self):return _staff_title(self.context,self.selected_person())
    def person_dates(self):return []
    def person_dates_by_year(self):return _date_group(self.person_dates())
    def is_editor(self):return _editor(self.portal)

class KiestraHomeView(KiestraPublicView): pass
class KiestraSelectView(BrowserView): pass
class KiestraCopyView(BrowserView): pass

EXAM_FIELDS_FOR_SEARCH=('sifra','podrocje','sklop','sinonim','laboratoriji','metode','opis','opombe','trajanje','urnik','vzorci','vzorci_lab','vzorci_lab_kratica')
class ExamsBase(BrowserView):
    @property
    def portal(self): return _portal(self.context)
    def is_editor(self): return _editor(self.portal)
    def base_folder(self): return self.portal.get('preiskave-1')
    def subfolders(self):
        base=self.base_folder(); result=[]
        if base is None:return result
        for child in base.objectValues():
            if getattr(child,'portal_type',None)=='Folder' and not bool(getattr(child,'exclude_from_nav',False)):
                result.append({'title':child.Title() or child.getId(),'url':self.portal.absolute_url()+'/@@'+({'hitro-iskanje':'preiskave_hitro_view','katalog-preiskav':'preiskave_view','nove-preiskave':'preiskave_nove_view','nujne-preiskave':'preiskave_nujne_view','preiskave-po-laboratorijih':'preiskave_lab_view','preiskave-po-podrocjih':'preiskave_podrocja_view','preiskave-po-sklopih':'preiskave_sklopi_view','preiskave-po-vzorcih':'preiskave_vzorci_view'}.get(child.getId(),'preiskave_view'))})
        return result
    def _searchable(self,obj):
        values=[obj.Title(),obj.Description()]
        for name in EXAM_FIELDS_FOR_SEARCH:
            value=getattr(obj,name,''); values.extend(str(v) for v in value) if isinstance(value,(tuple,list)) else values.append(_rich(value))
        return u' '.join(str(v or '') for v in values).lower()
    def all_exams(self):
        base=self.base_folder() or self.portal
        brains=self.portal.portal_catalog(portal_type='imi.exams.examination',path='/'.join(base.getPhysicalPath()),sort_on='sortable_title')
        return [brain.getObject() for brain in brains]
    def filtered_exams(self,query=None):
        query=str(query if query is not None else (self.request.form.get('q') or self.request.form.get('SearchableText') or '')).strip(); words=[w.lower() for w in query.replace('*',' ').replace('+',' ').split() if w]; result=self.all_exams(); return [obj for obj in result if all(w in self._searchable(obj) for w in words)] if words else result
class ExamsPublicView(ExamsBase):
    template=ViewPageTemplateFile('exams_home.pt')
    def __call__(self):return self.template()
    def results(self):
        q=str(self.request.form.get('q') or '').strip(); return self.filtered_exams(q)[:50] if q else []
    def query(self):return str(self.request.form.get('q') or '')
class ExamsHomeView(ExamsPublicView):pass
class ExamsLiveSearchView(ExamsBase):pass
class ExamsListView(ExamsBase):
    template=ViewPageTemplateFile('exams_list.pt')
    def __call__(self):return self.template()
    def mode(self):return str(self.request.get('URL') or '').rstrip('/').rsplit('/',1)[-1]
    def title(self):return u'Preiskave'
    def results(self):return self.filtered_exams()
    def query(self):return str(self.request.form.get('q') or self.request.form.get('SearchableText') or '')
class ExaminationView(ExamsBase):
    template=ViewPageTemplateFile('examination_public.pt')
    def __call__(self):return self.template()
    def rich(self,name):return _rich(getattr(self.context,name,''))
    def text(self,name):
        value=getattr(self.context,name,''); return u', '.join(str(v) for v in value if v) if isinstance(value,(tuple,list)) else str(value or '')
    def code(self):
        value=str(getattr(self.context,'sifra','') or ''); return value or (self.context.getId().split('_',1)[1] if '_' in self.context.getId() else self.context.getId())

class ReplacementsBase(BrowserView):
    @property
    def portal(self):return _portal(self.context)
    def days_folder(self):return _settings_days(self.portal)
    def selected_date(self):
        try:return _parse_date(self.request.form.get('datum'),default_today=True)
        except ValueError:return date.today()
    def selected_date_id(self):return self.selected_date().strftime('%Y-%m-%d')
    def today_id(self):return date.today().strftime('%Y-%m-%d')
    def day_object(self):
        folder=self.days_folder(); return folder.get(self.selected_date_id()) if folder is not None else None
    def labs_folder(self):return self.portal.get('laboratoriji')
    def laboratories(self):
        folder=self.labs_folder(); return [obj for obj in folder.objectValues() if getattr(obj,'portal_type',None)=='imi.replacements.laboratory'] if folder is not None else []
    def staff_options(self):return _staff_options(self.context)
    def _rows_from_obj(self,obj):
        if obj is None:return []
        try:
            value=json.loads(str(getattr(obj,'nadomescanja_json','') or '[]')); return value if isinstance(value,list) else []
        except Exception:return []
    def replacement_map(self):return {str(row.get('laboratorij_okrajsava') or ''):row for row in self._rows_from_obj(self.day_object())}
    def public_rows(self):
        replacements=self.replacement_map(); result=[]
        for lab in self.laboratories():
            abbr=str(getattr(lab,'okrajsava','') or lab.getId()); leaders=tuple(getattr(lab,'privzeti_vodja',()) or ()); leader=_staff_title(self.context,leaders[0]) if leaders else ''; row=replacements.get(abbr,{}); replacement=str(row.get('nadomestni_vodja_naziv') or '')
            result.append({'abbreviation':abbr,'leader':leader,'replacement':replacement,'replaced':bool(replacement)})
        return result
    def is_editor(self):return _editor(self.portal)
    def formatted_date(self):return _formatted_date(self.selected_date())
    def previous_date(self):return (self.selected_date()-timedelta(days=1)).strftime('%Y-%m-%d')
    def next_date(self):return (self.selected_date()+timedelta(days=1)).strftime('%Y-%m-%d')
    def selected_person(self):return str(self.request.form.get('oseba') or '')
    def selected_person_title(self):return _staff_title(self.context,self.selected_person())
    def person_dates(self):return []
    def person_dates_by_year(self):return _date_group(self.person_dates())
    def last_change(self):return ''
class ReplacementsPublicView(ReplacementsBase):
    template=ViewPageTemplateFile('replacements_public.pt')
    def __call__(self):return self.template()
class ReplacementsHomeView(ReplacementsPublicView):pass
class ReplacementsSelectView(ReplacementsBase):pass
class ReplacementsCopyView(ReplacementsBase):pass
class ReplacementEditView(ReplacementsBase):pass
class ReplacementsExportView(ReplacementsBase):pass
class ReplacementsChangeRequestView(ReplacementsBase):pass
