"""Plain-language citizen complaint report. Internal audit data stays in JSON."""
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone, timedelta
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


FIELD_LABELS = {'date_time_of_incident':'When it happened', 'platform_involved':'App or website',
    'financial_loss_amount':'Money lost (INR)', 'bank_name':'Bank or wallet',
    'utr_number':'Payment reference', 'suspect_details':'Suspect details'}


def structured_summary(case):
    facts = dict(case.get('reviewed_fields') or {})
    incident = case.get('incident') or {}
    facts.setdefault('date_time_of_incident', incident.get('datetime'))
    facts.setdefault('platform_involved', ', '.join(incident.get('location') or []))
    lines = ['The complainant reported the following details.']
    for key, label in FIELD_LABELS.items():
        val = facts.get(key)
        if val not in (None, '', 'not supplied'):
            lines.append(f'{label}: {val}')
    for index, payment in enumerate(case.get('transactions') or [], 1):
        details = '; '.join(f'{key.replace("_", " ")}: {val}' for key,val in payment.items() if val not in (None, '', 'Not provided'))
        lines.append(f'Payment {index}: {details}')
    for suspect in case.get('suspects') or []:
        details = '; '.join(str(suspect.get(key)) for key in ('name','id_number','details') if suspect.get(key))
        lines.append('Suspect information: ' + details)
    return '\n'.join(lines) if len(lines)>1 else 'No structured details were saved for this complaint.'


def write_complaint_pdf(case, path, downloaded_at=None):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('Copy', fontName='Helvetica', fontSize=10, leading=13, spaceAfter=4))
    styles['Heading2'].textColor = colors.HexColor('#175b47')
    story = []
    download_label = downloaded_at.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime('%d %B %Y, %I:%M:%S %p IST') if downloaded_at else None

    def para(text, style='Copy'):
        return Paragraph(escape(str(text).replace('₹', 'INR ')).replace('\n', '<br/>'), styles[style])

    def section(title):
        story.append(para(title, 'Heading2'))

    def rows(items):
        data = [[para(label), para(val)] for label, val in items if val not in (None, '', 'not supplied', 'Not provided')]
        if not data:
            return
        table = Table(data, colWidths=[135, 376], hAlign='LEFT', splitInRow=1)
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eef5f1')), ('BOTTOMPADDING',(0,0),(-1,-1),3), ('TOPPADDING',(0,0),(-1,-1),3)]))
        story.extend([table, Spacer(1,4)])

    def details(values):
        if isinstance(values, dict):
            for key,val in values.items():
                if key.startswith('_') or key in ('confidence','confidence_note','confidence_band','score'):
                    continue
                if isinstance(val, (dict,list)):
                    story.append(para(key.replace('_',' ').capitalize(), 'Heading3'))
                    details(val)
                elif val not in (None, ''):
                    rows([(key.replace('_',' ').capitalize(), val)])
        elif isinstance(values,list):
            for val in values:
                details(val)
        elif values not in (None, ''):
            story.append(para(values))

    story.append(para('Cybercrime Complaint Report', 'Title'))
    rows([('Complaint reference',case.get('reference')), ('Complaint created',case.get('generated_at','').replace('T',' ')), ('Download date and time',download_label), ('Status',str(case.get('status','Pending review')).replace('_',' ').capitalize())])
    person = case.get('complainant') or {}
    section('About you')
    rows([(label,person.get(key)) for key,label in [('name','Name'),('age','Age'),('phone','Phone'),('email','Email'),('state','State / Union territory'),('district','District'),('pincode','PIN code'),('city','City / town'),('address','Address'),('title','Title'),('gender','Gender'),('dob','Date of birth'),('relative_name','Parent / spouse name'),('relative_type','Relationship'),('police_station','Police station'),('relationship_with_victim','Relationship with victim'),('id_type','Identity document type'),('id_upload_name','Identity document file')]])
    inc = case.get('incident') or {}
    cl = case.get('classification') or {}
    section('Complaint details')
    rows([('Main category',inc.get('category')), ('Category',inc.get('sub_category_reported') or cl.get('sub_category')), ('When it happened',inc.get('datetime')), ('App or website',', '.join(inc.get('location') or []))])
    section('Your original complaint')
    complaint = case.get('complaint') or {}
    story.append(para(complaint.get('original_text') or complaint.get('raw_text') or complaint.get('standardised_narrative') or 'Not provided'))
    if complaint.get('original_text') and complaint.get('raw_text') != complaint.get('original_text'):
        follow_up = str(complaint.get('raw_text') or '').partition('\n\nAdditional details:\n')[2].strip()
        if follow_up:
            section('Details added during follow-up questions')
            story.append(para(follow_up))
    section('Structured complaint prepared by the system')
    structured = complaint.get('standardised_narrative')
    if not structured or structured == complaint.get('raw_text') or structured.startswith('NOT AVAILABLE'):
        structured = structured_summary(case)
    story.append(para(structured))
    section('Additional incident details')
    rows([(label,(case.get('reviewed_fields') or {}).get(key)) for key,label in FIELD_LABELS.items()])
    rows([('How it happened',inc.get('modus_operandi')), ('Delay in reporting',inc.get('delay_in_reporting')), ('Reason for delay',inc.get('delay_reason'))])
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
        rows([(f'Payment {index}' if len(transactions)>1 else 'Reported amount', f'INR {amounts[index-1]:,.2f}' if amounts[index-1] is not None else 'Not confirmed'), ('Bank / wallet',item.get('bank')), ('Payment reference',item.get('transaction_id')), ('Payment date',item.get('transaction_date')), ('Account number',item.get('account_no')), ('Other reference',item.get('reference_no'))])
        details({key:val for key,val in item.items() if key not in ('amount','bank','transaction_id','transaction_date','account_no','reference_no')})
    if case.get('suspect_transactions'):
        section('Payments linked to the suspect')
        details(case['suspect_transactions'])
    section('Details of the suspect')
    suspects = case.get('suspects') or []
    if not suspects:
        story.append(para('Not provided'))
    for suspect in suspects:
        details(suspect)
    section('Evidence attached')
    evidence = case.get('evidence') or {}
    attachment_map = {}
    for item in (evidence.get('attachments') or []) + (evidence.get('table') or []):
        entry = item if isinstance(item,dict) else {'filename':str(item)}
        key = entry.get('filename') or entry.get('name') or str(entry)
        attachment_map[key] = {**attachment_map.get(key,{}), **entry}
    attachments = list(attachment_map.values())
    if not attachments:
        story.append(para('No files attached'))
    for index,item in enumerate(attachments,1):
        label = (item.get('name') or item.get('filename') or 'Attached file') if isinstance(item,dict) else item
        story.append(para(f'{index}. {label}'))
        if isinstance(item,dict):
            details({key:val for key,val in item.items() if key not in ('name','filename')})
    legal = case.get('legal_sections') or {}
    section('Associated laws and legal sections')
    story.append(para('These are possible laws for review. The investigating officer will decide which ones apply.'))
    if not legal or '_status' in legal:
        story.append(para('No legal sections were saved for this complaint.'))
    for group,label in [('it_act','Information Technology Act, 2000'),('bns','Bharatiya Nyaya Sanhita, 2023'),('other','Other laws')]:
        if legal.get(group):
            story.append(para(label,'Heading3'))
            for item in legal[group]:
                if not isinstance(item,dict):
                    story.append(para(item))
                    continue
                law_label = item.get('act') or item.get('name') or ''
                section_number = item.get('section')
                if section_number:
                    law_label = (law_label + ' - ' if law_label else '') + 'Section ' + str(section_number)
                if item.get('ipc_equivalent'):
                    law_label += ' (IPC equivalent: Section ' + str(item['ipc_equivalent']) + ')'
                rows([(law_label or 'Legal provision',item.get('description',''))])
                details({key:value for key,value in item.items() if key not in ('act','name','section','ipc_equivalent','description')})
    extra_labels = {'conditional_applied':'Laws that depend on further details', 'statutory_elements':'What needs to be established', 'notes':'Legal notes', 'procedural_notes':'Notes for reviewing the complaint'}
    for key,label in extra_labels.items():
        if legal.get(key):
            story.append(para(label,'Heading3'))
            details(legal[key])
    if legal.get('statute_year'):
        rows([('Relevant law year',legal['statute_year'])])
    if legal.get('verified') is not None:
        rows([('Legal mapping checked', 'Yes' if legal['verified'] else 'No')])
    for key,label in [('extracted_entities','Details read from evidence'),('intake_gaps_identified','Details still needed'),('suggested_actions','Suggested next steps')]:
        val=case.get(key)
        if val and not (isinstance(val,dict) and '_status' in val):
            section(label)
            details(val)
    reconciliation=case.get('reconciliation') or {}
    for key,label in [('agreements','Matching details'),('conflicts','Details to check'),('gaps','Missing details'),('ocr_only','Details found only in evidence')]:
        if reconciliation.get(key):
            section(label)
            details(reconciliation[key])
    section('Please check this report')
    story.append(para('This report contains the details provided and possible laws for review. Keep your original payment records, messages and screenshots.'))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold',8)
        canvas.drawString(42,A4[1]-27,'Intelligent Cybercrime Complaint Analysis and Category Classification')
        canvas.drawString(42,A4[1]-38,'System using NLP')
        canvas.setStrokeColor(colors.HexColor('#175b47'))
        canvas.line(42,A4[1]-47,A4[0]-42,A4[1]-47)
        canvas.line(42,46,A4[0]-42,46)
        canvas.setFont('Helvetica',8)
        if download_label:
            canvas.drawString(42,34,'Downloaded: '+download_label)
        canvas.setFillColor(colors.HexColor('#496259'))
        canvas.drawString(42,25,str(case.get('reference','Complaint report')))
        canvas.drawRightString(A4[0]-42,25,f'Page {doc.page}')
        canvas.restoreState()

    SimpleDocTemplate(path if hasattr(path,'write') else str(path), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=62, bottomMargin=62, title='Cybercrime Complaint Report').build(story,onFirstPage=footer,onLaterPages=footer)
    return str(path)
