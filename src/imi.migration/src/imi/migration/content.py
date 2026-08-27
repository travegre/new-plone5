# -*- coding: utf-8 -*-
from plone.app.textfield import RichText
from plone.app.z3cform.widget import SelectFieldWidget
from plone.autoform import directives as form
from plone.namedfile.field import NamedBlobFile
from plone.supermodel import model
from zope import schema


def _textline(title, required=False):
    return schema.TextLine(title=title, required=required)


def _text(title, required=False):
    return schema.Text(title=title, required=required)


def _tuple(title):
    return schema.Tuple(title=title, required=False, value_type=schema.TextLine())


def _staff_tuple(title):
    """A roster value: stored legacy person ids, displayed as staff names."""
    return schema.Tuple(
        title=title,
        required=False,
        value_type=schema.Choice(vocabulary='imi.duty.staff'),
    )


class IDirectoryPerson(model.Schema):
    predime = _textline(u'Predpona')
    ime = _textline(u'Ime')
    priimek = _textline(u'Priimek')
    zaime = _textline(u'Zapona')
    oddelek = _textline(u'Oddelek')
    telefon = _textline(u'Telefon')
    vuporabi = _textline(u'V uporabi')
    maticna = _textline(u'Matična številka')
    opis = _textline(u'Opis delovnega mesta')
    enota = _textline(u'Enota')
    lokacija = _textline(u'Lokacija')
    dodatna = _textline(u'Dodatna')
    dect = _textline(u'DECT')
    fax = _textline(u'Fax')
    multitone = _textline(u'Multitone')
    mobilna = _textline(u'Mobilna')
    zunanja = _textline(u'Zunanja')
    enaslov = _textline(u'E-naslov')
    zenaslov = _textline(u'Zunanji e-naslov')
    star = _textline(u'Star zapis')


class IStaffDirectory(model.Schema):
    """Container replacing the legacy seznam_zaposlenih import object."""


class IStaffEmployee(model.Schema):
    source_employee_id = _textline(u'Legacy employee ID', required=True)
    contact = _textline(u'Kontakt')
    email = _textline(u'E-naslov')


class IDutyRosterDay(model.Schema):
    """Duty roster with the Plone-4 editor semantics preserved.

    The old Archetypes InAndOutWidgets stored employee ids and displayed the
    title from seznam_zaposlenih.  SelectFieldWidget gives us the equivalent
    searchable multi-select in Plone 5 while keeping those ids untouched.
    CSS wrapper classes reproduce the old three-column working layout.
    """

    # These four fields were explicitly hidden by the old Archetypes widgets.
    form.omitted('dezurni_tehnik', 'izobrazevanje', 'VINVZV', 'VINDIF')

    form.widget(
        'dezurni_zdravnik', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third duty-team-start')
    form.widget(
        'nadzorni_zdravnik', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'specializant', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'sarsifon', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'bakterioloski_tehnik', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'inoqula_tehnik', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'sprejem_predpriprava_tehnik', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'vpis', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'intervencijska_skupina', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'intervencijska_skupina_telefon',
        wrapper_css_class='duty-roster-field duty-roster-third')

    form.widget(
        'BOR', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third duty-ready-start')
    form.widget(
        'HIV', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'HUM', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'IT', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'PRZ', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'KLM', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'KOV', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'WHO', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget(
        'kiestra', SelectFieldWidget,
        wrapper_css_class='duty-roster-field duty-roster-third')
    form.widget('klukca', wrapper_css_class='duty-roster-clear')

    dezurni_zdravnik = _staff_tuple(u'Dežurni zdravnik')
    nadzorni_zdravnik = _staff_tuple(u'Nadzorni zdravnik')
    specializant = _staff_tuple(u'Specializant na usposabljanju')
    sarsifon = _staff_tuple(u'Virološki laboratoriji')
    dezurni_tehnik = _staff_tuple(u'Dežurni tehnik')
    izobrazevanje = _staff_tuple(u'Izobraževanje')
    bakterioloski_tehnik = _staff_tuple(u'Urgentni laboratorij')
    inoqula_tehnik = _staff_tuple(u'BMK laboratorij')
    sprejem_predpriprava_tehnik = _staff_tuple(u'Sprejem/predpriprava')
    vpis = _staff_tuple(u'Vpis')
    intervencijska_skupina = _staff_tuple(u'Intervencijska skupina')
    intervencijska_skupina_telefon = _textline(u'Intervencijska skupina telefon')
    BOR = _staff_tuple(u'BOR')
    HIV = _staff_tuple(u'HIV')
    HUM = _staff_tuple(u'HUM')
    IT = _staff_tuple(u'IT')
    PRZ = _staff_tuple(u'PRZ')
    KLM = _staff_tuple(u'KLM')
    KOV = _staff_tuple(u'VZ')
    VINVZV = _staff_tuple(u'VIN (VZV, EBV)')
    VINDIF = _staff_tuple(u'VIN (DIF ali PCR)')
    WHO = _staff_tuple(u'WHO')
    kiestra = _staff_tuple(u'Kiestra')
    klukca = schema.Bool(
        title=u'Kopiraj to stanje pripravljenosti na cel tekoči teden',
        required=False)


class IKiestraWorkDay(model.Schema):
    priprava_vzorcev = _tuple(u'Priprava vzorcev')
    priprava_vzorcev_text = _textline(u'Priprava vzorcev - opomba')
    cepljenje_vzorcev = _tuple(u'Inoqula + Sortera')
    cepljenje_vzorcev_text = _textline(u'Inoqula + Sortera - opomba')
    odcitavanje = _tuple(u'Odčitavanje')
    odcitavanje_text = _textline(u'Odčitavanje - opomba')
    identifikacija = _tuple(u'Ime bakterije')
    identifikacija_text = _textline(u'Identifikacija - opomba')
    antibiogram = _tuple(u'ID+ATB, ATB, izolacija')
    antibiogram_text = _textline(u'Antibiogram - opomba')
    izolacija = _tuple(u'Waste')
    izolacija_text = _textline(u'Izolacija - opomba')
    odpad = _tuple(u'OFF')
    odpad_text = _textline(u'OFF - opomba')
    ciscenje = _tuple(u'Čiščenje kiestre')
    ciscenje_text = _textline(u'Čiščenje - opomba')
    stalni_tekst = RichText(title=u'Stalni tekst', required=False)


class IReplacementDay(model.Schema):
    # Keep this lossless during the first migration. Later normalization can
    # happen only after parity has been proven.
    nadomescanja_json = _text(u'Nadomeščanja (legacy JSON)')


class IReplacementLaboratory(model.Schema):
    okrajsava = _textline(u'Okrajšava', required=True)
    privzeti_vodja = _tuple(u'Privzeti vodja')


class IExamination(model.Schema):
    sifra = _textline(u'Šifra preiskave')
    podrocje = _tuple(u'Področje preiskave')
    sklop = RichText(title=u'Sklop', required=False)
    sinonim = RichText(title=u'Sinonim preiskave', required=False)
    laboratoriji = _textline(u'Laboratoriji')
    metode = RichText(title=u'Metode preiskave', required=False)
    opis = RichText(title=u'Kratek opis preiskave', required=False)
    opombe = RichText(title=u'Opombe', required=False)
    trajanje = RichText(title=u'Trajanje preiskave', required=False)
    urnik = RichText(title=u'Urnik izvajanja preiskave', required=False)
    link_sop = _textline(u'Link SOP')
    nova_pre = _textline(u'Nova preiskava')
    nujna_pre = _textline(u'Nujna preiskava')
    vzorci = _text(u'Vzorci (legacy raw value)')
    preiskava_vzorec_nujno = _tuple(u'Preiskava Vzorec Nujno')
    vzorci_lab_kratica = _textline(u'Kratica laboratorija')
    vzorci_lab = _text(u'Laboratoriji (legacy raw value)')
    vzorci_lab_tel = _text(u'Telefoni (legacy raw value)')
    vzorci_odvzem = _text(u'Odvzemi (legacy raw value)')
    vzorci_odvzem_video_sifra = _text(u'Navodilo za odvzem - video šifra')
    vzorci_kolicina = _text(u'Količine (legacy raw value)')
    embalaza_slika_sifra = _text(u'Embalaža slika šifra')
    vzorci_transport = _text(u'Transporti (legacy raw value)')
    vzorci_opomba = _text(u'Opomba za klinika')
    vzorci_nivo1 = _text(u'Vzorci nivo1')
    vzorci_nivo2 = _text(u'Vzorci nivo2')
    vzorci_nivo3 = _text(u'Vzorci nivo3')
    vzorci_nivo4 = _text(u'Vzorci nivo4')
    vzorci_nivo5 = _text(u'Vzorci nivo5')
    vzorci_nivo6 = _text(u'Vzorci nivo6')
    datoteka = NamedBlobFile(title=u'Dodatni opis preiskave', required=False)
