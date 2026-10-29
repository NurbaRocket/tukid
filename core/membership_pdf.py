from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape

from django.utils import timezone
from django.utils.translation import gettext as _, override
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

FONT_DIRECTORY = Path(__file__).resolve().parent / 'fonts'
FONT_LOCK = Lock()


class MembershipPDFError(Exception):
    pass


def register_fonts():
    with FONT_LOCK:
        if 'TukidNoto' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('TukidNoto', FONT_DIRECTORY / 'NotoSans-Regular.ttf'))
            pdfmetrics.registerFont(TTFont('TukidNoto-Bold', FONT_DIRECTORY / 'NotoSans-Bold.ttf'))
            pdfmetrics.registerFontFamily('TukidNoto', normal='TukidNoto', bold='TukidNoto-Bold')


def build_membership_pdf(application, site_settings):
    try:
        with override(application.language):
            return _build_pdf(application, site_settings)
    except Exception as error:
        raise MembershipPDFError('Не удалось сформировать PDF заявки.') from error


def _build_pdf(application, site_settings):
    register_fonts()
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
        topMargin=14*mm, bottomMargin=17*mm,
        title=_('Заявка на членство TUKID'), author=site_settings.localized('name'),
        pageCompression=1,
    )
    body = ParagraphStyle('body', fontName='TukidNoto', fontSize=9.5, leading=13,
        spaceAfter=6, splitLongWords=True)
    title = ParagraphStyle('title', parent=body, fontName='TukidNoto-Bold',
        fontSize=16, leading=21, alignment=TA_CENTER, spaceAfter=6)
    subtitle = ParagraphStyle('subtitle', parent=body, alignment=TA_CENTER, spaceAfter=8)
    small = ParagraphStyle('small', parent=body, fontSize=8, leading=11, textColor=colors.HexColor('#555555'))
    meta = ParagraphStyle('meta', parent=small, alignment=TA_RIGHT, spaceAfter=10)
    heading = ParagraphStyle('heading', parent=body, fontName='TukidNoto-Bold', fontSize=10,
        leading=14, spaceBefore=11, spaceAfter=6, keepWithNext=True)
    table_heading = ParagraphStyle('table-heading', parent=heading, keepWithNext=False)
    label = ParagraphStyle('label', parent=body, fontName='TukidNoto-Bold', fontSize=9, leading=12, spaceAfter=0)
    value = ParagraphStyle('value', parent=body, spaceAfter=0)

    def paragraph(text, style=body):
        safe = escape(str(text or '')).replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>')
        return Paragraph(safe or _('Не указано'), style)

    def date(value):
        return value.strftime('%d.%m.%Y') if value else '________________'

    created = timezone.localtime(application.created_at)
    story = [
        paragraph(_('ЗАЯВКА НА ЧЛЕНСТВО'), title),
        paragraph(f"{site_settings.localized('organization_name')} ({site_settings.localized('name')})", subtitle),
        paragraph(_('Заявка %(reference)s · %(date)s\nСтатус: %(status)s') % {'reference': application.reference, 'date': created.strftime('%d.%m.%Y %H:%M'), 'status': _(application.get_status_display())}, meta),
        paragraph(_('Членский №: %(number)s') % {'number': application.membership_number or '________________'}),
        paragraph(application.declaration_text),
        paragraph(_('Дата заявления: %(date)s    ФИО: %(name)s') % {'date': created.strftime('%d.%m.%Y'), 'name': application.full_name}),
        paragraph(_('Подпись заявителя: ______________________________')),
        paragraph(_('Данные заявителя'), table_heading),
    ]
    rows = [
        (_('Название фирмы'), application.company_name),
        (_('Сфера деятельности и краткая информация'), application.activity_description),
        (_('ИНН организации'), application.tax_id),
        (_('ФИО'), application.full_name),
        (_('Должность'), application.position),
        (_('Адрес организации'), application.organization_address),
        (_('Телефоны'), _('Рабочий: %(work)s\nМобильный: %(mobile)s') % {'work': application.work_phone or _('не указан'), 'mobile': application.mobile_phone}),
        ('E-Mail', application.email),
        (_('Рекомендации'), application.recommendations),
        (_('Источник информации об ОО'), application.information_source),
    ]
    table_width = document.width - 12  # SimpleDocTemplate's frame has 6 pt padding on each side.
    table = LongTable(
        [[paragraph(name, label), paragraph(text, value)] for name, text in rows],
        colWidths=[table_width * .32, table_width * .68],
        hAlign='LEFT', splitByRow=0, splitInRow=1,
    )
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), .45, colors.HexColor('#D9D9D9')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.extend([
        paragraph(_('ПРОЦЕДУРА ПРИНЯТИЯ В ЧЛЕНСТВО'), heading),
        paragraph(_('Заполняется Советом Правления'), small),
        paragraph(_('Кандидатура предложена: %(date)s\nГенеральный секретарь: %(name)s') % {'date': date(application.proposed_on), 'name': application.secretary_name or '____________________________'}),
    ])
    if application.status in {'approved', 'rejected'}:
        decision = (_('Заявитель принят в членство в ОО на основании решения Совета Правления № %(number)s от %(date)s.')
            if application.status == 'approved' else
            _('Заявитель не принят в членство в ОО на основании решения Совета Правления № %(number)s от %(date)s.'))
        story.append(paragraph(decision % {'number': application.decision_number, 'date': date(application.decision_date)}))
    else:
        story.append(paragraph(_('Решение: не принято.\nНомер решения: ________________    Дата: ________________')))
    story.extend([
        paragraph(_('Причина / основание: %(reason)s') % {'reason': application.decision_reason or '________________________________________'}),
        KeepTogether([
            paragraph(_('Председатель Совета Правления: %(name)s') % {'name': application.chairperson_name or '____________________________'}),
            paragraph(_('Подписи: генеральный секретарь ______________    председатель ______________'), small),
        ]),
        Spacer(1, 4*mm),
        paragraph(_('Сформировано из электронной заявки. Подписи проставляются на бумаге.'), small),
    ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('TukidNoto', 7)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(document.leftMargin, 10*mm, f"{site_settings.localized('name')} · {application.reference}")
        canvas.drawRightString(A4[0] - document.rightMargin, 10*mm, _('Страница %(number)s') % {'number': doc.page})
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
