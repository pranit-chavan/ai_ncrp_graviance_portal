"""Plain-language citizen complaint report. Internal audit data stays in JSON."""
from decimal import Decimal, InvalidOperation
from numbers import Real
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def write_complaint_pdf(case, path):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('Copy', fontName='Helvetica', fontSize=10, leading=13, spaceAfter=4))
    styles['Heading2'].textColor = colors.HexColor('#175b47')
    story = []

    def para(text, style='Copy'):
        return Paragraph(escape(str(text).replace('₹', 'INR ')).replace('\n', '<br/>'), styles[style])

    def section(title):
        story.append(para(title, 'Heading2'))

    def rows(items):
        data = [[para(label), para(val)] for label, val in items if val not in (None, '', 'not supplied', 'Not provided')]
        if not data:
            return
        table = Table(data, colWidths=[135, 376], hAlign='LEFT')
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eef5f1')), ('BOTTOMPADDING',(0,0),(-1,-1),3), ('TOPPADDING',(0,0),(-1,-1),3)]))
        story.extend([table, Spacer(1,4)])

    story.append(para('Cybercrime Complaint Report', 'Title'))
    rows([('Complaint reference',case.get('reference')), ('Created',case.get('generated_at','').replace('T',' '))])
    person = case.get('complainant') or {}
    section('About you')
    rows([(label,person.get(key)) for key,label in [('name','Name'),('age','Age'),('phone','Phone'),('email','Email'),('state','State / Union territory'),('district','District'),('pincode','PIN code'),('city','City / town'),('address','Address')]])
    inc = case.get('incident') or {}
    cl = case.get('classification') or {}
    section('Complaint details')
    rows([('Category',inc.get('sub_category_reported') or cl.get('sub_category')), ('When it happened',inc.get('datetime')), ('App or website',', '.join(inc.get('location') or []))])
    section('What happened')
    complaint = case.get('complaint') or {}
    story.append(para(complaint.get('raw_text') or complaint.get('standardised_narrative') or 'Not provided'))
    section('Money lost')
    transactions = case.get('transactions') or []
    amounts = []
    for item in transactions:
        try:
            amount = Decimal(str(item.get('amount','')).replace(',',''))
            if not amount.is_finite() or amount < 0:
                raise InvalidOperation
            amounts.append(amount)
        except (InvalidOperation, ValueError):
            amounts.append(None)
    if amounts and all(amount is not None for amount in amounts):
        story.append(para(f'Total reported loss: INR {sum(amounts):,.2f}', 'Heading3'))
    else:
        story.append(para('Total reported loss: Not confirmed'))
    for index,item in enumerate(transactions,1):
        rows([(f'Payment {index}' if len(transactions)>1 else 'Reported amount', f'INR {amounts[index-1]:,.2f}' if amounts[index-1] is not None else 'Not confirmed'), ('Bank / wallet',item.get('bank')), ('Payment reference',item.get('transaction_id')), ('Payment date',item.get('transaction_date'))])
    section('Details of the suspect')
    suspects = case.get('suspects') or []
    if not suspects:
        story.append(para('Not provided'))
    for suspect in suspects:
        rows([('Name',suspect.get('name')), ('Account / phone / profile',suspect.get('id_number')), ('Other details',suspect.get('details'))])
    section('Evidence attached')
    evidence = case.get('evidence') or {}
    attachments = evidence.get('table') or evidence.get('attachments') or []
    if not attachments:
        story.append(para('No files attached'))
    for index,item in enumerate(attachments,1):
        label = (item.get('name') or item.get('filename') or 'Attached file') if isinstance(item,dict) else item
        story.append(para(f'{index}. {label}'))
    section('Category check')
    score = cl.get('confidence')
    rows([('Suggested category',cl.get('sub_category')), ('Category match score',f'{score*100:.0f} / 100' if isinstance(score,Real) and not isinstance(score,bool) and 0 <= score <= 1 else 'Not available')])
    story.append(para('This score shows how strongly the system matched the description to the suggested category. It is not proof of the complaint or a chance of recovering money.'))
    legal = case.get('legal_sections') or {}
    sections = []
    for group,label in [('it_act','IT Act'),('bns','BNS'),('other','Other law')]:
        for item in legal.get(group,[]):
            sections.append(f"{item.get('act') or label}, Section {item.get('section','Not specified')}: {item.get('description','')}")
    if sections:
        section('Laws suggested for review')
        story.append(para('The reviewing officer will decide which laws apply.'))
        for item in sections:
            story.append(para(item))
    section('Your review')
    story.append(para('This report records the details provided for this complaint. Keep your original payment records, messages and screenshots.'))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#496259'))
        canvas.drawString(42,25,str(case.get('reference','Complaint report')))
        canvas.drawRightString(A4[0]-42,25,f'Page {doc.page}')
        canvas.restoreState()

    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=36, bottomMargin=42, title='Cybercrime Complaint Report').build(story,onFirstPage=footer,onLaterPages=footer)
    return str(path)
