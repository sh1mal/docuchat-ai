"""Build original fictional sample PDFs and a code-grounded DocuChat guide.
Run with Python containing reportlab and pypdf; not a backend dependency.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
PUBLIC = ROOT / 'my-react-app/public/samples'
OUT.mkdir(parents=True, exist_ok=True)
PUBLIC.mkdir(parents=True, exist_ok=True)
GREEN = colors.HexColor('#35573b')
INK = colors.HexColor('#26352b')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleDoc', fontName='Helvetica-Bold', fontSize=26, leading=31, textColor=INK, spaceAfter=16))
styles.add(ParagraphStyle(name='SectionDoc', fontName='Helvetica-Bold', fontSize=16, leading=21, textColor=GREEN, spaceBefore=10, spaceAfter=13))
styles.add(ParagraphStyle(name='BodyDoc', fontName='Helvetica', fontSize=10.5, leading=16, textColor=INK, spaceAfter=12))
styles.add(ParagraphStyle(name='SmallDoc', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#64705e'), spaceAfter=10))
styles.add(ParagraphStyle(name='CodeDoc', fontName='Courier', fontSize=8, leading=12, backColor=colors.HexColor('#f0f4ec'), borderPadding=10, spaceAfter=14))

def p(text, style='BodyDoc'):
    return Paragraph(text, styles[style])

def facts(rows):
    t = Table([[p(escape(str(a)), 'SmallDoc'), p(escape(str(b)), 'BodyDoc')] for a,b in rows], colWidths=[140, 335], hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f2f5ee')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),3),('LINEBELOW',(0,0),(-1,-2),.5,colors.HexColor('#dce4d4'))]))
    return t

def footer(title):
    def draw(c, doc):
        c.setStrokeColor(colors.HexColor('#dce4d4')); c.line(60, 54, A4[0]-60, 54)
        c.setFont('Helvetica',8); c.setFillColor(colors.HexColor('#66745e'))
        c.drawString(60,39,title); c.drawRightString(A4[0]-60,39,f'Page {doc.page}')
    return draw

def write_pdf(path, title, pages):
    story=[]
    for i,content in enumerate(pages):
        if i: story.append(PageBreak())
        story.extend(content)
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=60,leftMargin=60,topMargin=48,bottomMargin=72,title=title,author='DocuChat AI project',pageCompression=1)
    doc.build(story,onFirstPage=footer(title),onLaterPages=footer(title))

# Each section is one physical page. All organizations, people and policies below are fictional.
DATA = [
 dict(id='handbook',title='Employee handbook',filename='sample-employee-handbook.pdf',question='How many remote work days are allowed each week?',answer='Up to three remote work days per week, with Tuesday and Thursday in the office.',page=3,pages=[
 ('Company and handbook scope',
  'Cedar Labs is a fictional software company with 42 employees working on internal business applications. Its teams are Engineering, Product, Customer Operations and People Operations. The main office is in the fictional city of Lakebridge. This handbook is a synthetic reading exercise, not a real employment policy or legal document.',
  'The handbook describes everyday working arrangements for full-time employees in this fictional organization. Contractors follow their individual agreements. Questions about an unclear section go to People Operations; managers should not invent exceptions. The current handbook is version 1.2, effective 1 July 2026. Employees receive a copy during onboarding and can request an accessible text version.',
  [('Organization','Cedar Labs'),('Employees','42'),('Version','1.2'),('Effective date','1 July 2026')]),
 ('Onboarding and equipment',
  'A new employee completes onboarding during the first five working days. People Operations verifies the joining checklist, Engineering provisions a company laptop, and the manager assigns an onboarding buddy. The buddy answers practical questions and introduces the new employee to the team. Production access is not automatically granted during onboarding.',
  'The standard equipment kit contains one laptop, one headset and one external monitor. Employees acknowledge receipt in the equipment register. A manager reviews access requests after the employee finishes the security orientation. During the first week, the employee attends a product walkthrough, reads the team runbook and completes a small supervised task. The manager holds a check-in at the end of day five.',
  [('Onboarding period','First five working days'),('Equipment','Laptop, headset and external monitor'),('First manager check-in','End of day five'),('Production access','Separate manager review required')]),
 ('Remote work and office attendance',
  'Cedar Labs allows full-time employees to work remotely for up to three days per week. Tuesday and Thursday are the standard office days for team collaboration. Monday, Wednesday and Friday may be remote days when the employee has reliable internet and an appropriate workspace. Remote work does not change agreed working hours or delivery responsibilities.',
  'An employee requests a temporary change to an office day through the team manager at least one working day beforehand. A manager may approve a one-week exception for a specific situation and records it in the attendance calendar. The exception does not create a permanent remote arrangement. Employees update the shared calendar before starting a remote day so teammates can plan meetings.',
  [('Remote allowance','Up to three days per week'),('Office days','Tuesday and Thursday'),('Exception notice','At least one working day'),('Attendance record','Shared team calendar')]),
 ('Working hours and meetings',
  'The standard workday has eight working hours, excluding a lunch break. Teams share a core collaboration window from 10:00 to 16:00 local office time. Start and finish times may vary around that window when agreed with the manager. Employees record planned absences rather than sending repeated status updates throughout the day.',
  'The engineering stand-up begins at 10:15 and lasts no longer than fifteen minutes. Longer technical discussions move to a separate session. Wednesday afternoons are reserved for focused work unless a customer incident requires coordination. Meeting owners send an agenda in advance and write down decisions afterward. People who cannot attend can review the notes and add questions asynchronously.',
  [('Daily working time','Eight hours, excluding lunch'),('Core window','10:00 to 16:00'),('Stand-up','10:15, maximum fifteen minutes'),('Focus time','Wednesday afternoons')]),
 ('Leave requests',
  'Full-time employees receive eighteen days of annual leave in this fictional policy. They submit planned annual leave through the leave register at least five working days before the first day away. The manager checks delivery coverage and replies within two working days. Approval is recorded in the register rather than inferred from a calendar invitation.',
  'Unexpected illness is reported to the manager as soon as practical; the five-day planning rule does not apply to illness. Employees do not share medical details in the team channel. Before planned leave, employees identify a backup owner for active work and add a short handover note. Unused annual leave treatment is outside this sample and must not be inferred from the eighteen-day allowance.',
  [('Annual leave','Eighteen days'),('Planned notice','Five working days'),('Manager response','Within two working days'),('Handover','Backup owner and short note')]),
 ('Learning and development',
  'Each employee has a learning budget of 12,000 credits per calendar year. Credits are fictional internal accounting units, not a real currency. The budget may cover technical books, approved online courses or a conference ticket. A manager approves the learning request before the employee makes a purchase.',
  'Employees may reserve two working hours each week for approved learning. They agree on a useful outcome with the manager, such as a small prototype, written notes or a team demonstration. The company encourages learning related to current responsibilities and future team needs. Unused learning credits expire at the end of the calendar year and cannot be exchanged for cash. A course completion alone does not guarantee promotion.',
  [('Annual budget','12,000 fictional credits'),('Learning time','Two working hours per week'),('Approval','Before purchase'),('Unused credits','Expire at calendar-year end')]),
 ('Expenses and reimbursements',
  'Employees submit approved business expenses within thirty calendar days of the purchase. Each request includes a receipt, a business purpose and the name of the approving manager. People Operations checks the request for completeness before sending it to Finance. Missing receipts are returned for clarification rather than automatically reimbursed.',
  'Finance processes complete reimbursement requests in the next monthly expense cycle. The submission deadline for that cycle is the twentieth day of the month. Requests received after the deadline move to the following cycle. Personal subscriptions, commuting costs and unapproved equipment are excluded from this sample policy. An employee should request approval before spending money rather than assuming that submitting a receipt guarantees repayment.',
  [('Submission window','Thirty calendar days from purchase'),('Monthly cutoff','Twentieth day of the month'),('Required evidence','Receipt, purpose and manager approval'),('Processing','Next eligible monthly expense cycle')]),
 ('Security and data handling',
  'Employees use multi-factor authentication for company accounts and keep work on managed devices. They lock their screens when leaving a desk. Customer data must not be copied into personal cloud drives or public AI tools. A tool requires approval before it receives confidential information, even if the tool offers a free account.',
  'A suspected account compromise or lost company device is reported to the security contact immediately. Employees preserve relevant details and do not attempt to hide an accidental disclosure. The security team coordinates containment and records the incident. The handbook does not authorize employees to test systems they do not own. Access follows the minimum permissions needed for an assigned task and is reviewed when responsibilities change.',
  [('Account protection','Multi-factor authentication'),('Device policy','Managed work devices'),('Incident notice','Immediately'),('Access principle','Minimum permissions for the task')]),
 ('Feedback and performance',
  'Managers hold a thirty-minute one-to-one meeting with each employee every two weeks. The conversation covers current work, obstacles, feedback and development. Either participant can add agenda items. The meeting is a regular support mechanism rather than a surprise performance assessment.',
  'Formal performance reviews happen twice each year, in June and December. Review notes describe observable work and agreed goals. The employee can add written context before the review is finalized. Promotion decisions consider role expectations and available responsibilities; they are not determined by course certificates or hours online. Employees can raise unresolved concerns with People Operations when direct discussion with the manager does not resolve them.',
  [('One-to-one cadence','Every two weeks'),('Meeting length','Thirty minutes'),('Formal reviews','June and December'),('Escalation','People Operations')]),
 ('Leaving and returning equipment',
  'When an employee leaves Cedar Labs, People Operations opens an exit checklist and confirms the last working day with the manager. The employee documents active tasks and identifies where working files are stored. Ownership of shared documents moves to a designated teammate before access is removed.',
  'Company equipment is returned within five working days of the last working day. The equipment team checks the register and issues a return receipt. Access to company accounts is disabled on the last working day according to the exit checklist. Personal copies of company information are not retained. This fictional handbook does not specify notice periods, severance or final-pay rules, so those topics cannot be answered from this document.',
  [('Equipment return','Within five working days'),('Account removal','Last working day'),('Handover record','Active tasks, files and new owners'),('Not specified','Notice period, severance and final pay')]),
 ]),
 dict(id='product',title='Product specification',filename='sample-product-specification.pdf',question='What is the maximum CSV import size in TaskBoard Lite?',answer='2,000 task rows and 5 MB per CSV file.',page=6,pages=[
 ('Product overview',
  'TaskBoard Lite is a fictional task-tracking application for small project teams. It helps a team assign tasks, record due dates and follow work through a simple board. The intended team size is between five and twenty people. This specification is synthetic test material for PDF question answering, not a description of an existing commercial product.',
  'The first release focuses on predictable task management rather than automated planning. A user creates a workspace, invites teammates and adds tasks to a shared board. The product has a web interface backed by an HTTP API. Requirements in this document describe planned behavior for the fictional product; they do not claim that DocuChat implements these features.',
  [('Product','TaskBoard Lite'),('Target team size','Five to twenty people'),('Release','Version 1.0'),('Primary goal','Shared task ownership and status tracking')]),
 ('User roles and permissions',
  'A workspace has three roles: owner, editor and viewer. The owner manages invitations, changes roles and can archive the workspace. Editors create and update tasks, assign work and add comments. Viewers can read boards and comments but cannot modify tasks. Each workspace must retain at least one owner.',
  'A role applies only within its workspace. Being an editor in one workspace does not grant access to another workspace. The API checks membership on every request instead of trusting hidden interface buttons. Only an owner can export the workspace audit log. When a member is removed, their existing comments remain attributed to their display name but their session no longer grants access to that workspace.',
  [('Owner','Membership, roles and workspace archiving'),('Editor','Create and update tasks and comments'),('Viewer','Read only'),('Audit-log export','Owner only')]),
 ('Task fields and validation',
  'Each task has an identifier, title, status, creation timestamp and workspace identifier. The title is required and contains between one and 120 characters after trimming whitespace. A description is optional and may contain up to 4,000 characters. A task can have one assigned member or remain unassigned.',
  'A due date is optional. The interface displays dates using the workspace timezone while the server stores timestamps in UTC. Priority can be low, normal or high, with normal as the default. A task may have up to five labels. Validation happens on both client and server; the server remains responsible for rejecting invalid requests even when a user bypasses the interface.',
  [('Title length','One to 120 characters'),('Description limit','4,000 characters'),('Default priority','Normal'),('Label limit','Five labels per task')]),
 ('Board workflow',
  'The default board has four statuses: Backlog, Ready, In Progress and Done. A task starts in Backlog unless a CSV import explicitly specifies another supported status. Editors can move a task between statuses. Moving a task to Done records a completion timestamp; moving it out of Done clears that timestamp.',
  'The board initially sorts tasks by their most recent update. Users can filter by assignee, priority and label. Filters change the visible results without deleting tasks. Custom columns, task dependencies and time tracking are outside the first release. The interface must announce successful status changes to assistive technology and allow users to move tasks with the keyboard as well as a pointer.',
  [('Statuses','Backlog, Ready, In Progress, Done'),('Default status','Backlog'),('Filters','Assignee, priority and label'),('Excluded','Dependencies, custom columns and time tracking')]),
 ('Search and pagination',
  'Task search matches text in task titles and descriptions within the selected workspace. Search results must not include tasks from workspaces where the requester has no membership. The first release uses case-insensitive text matching; semantic search and AI-generated summaries are outside scope.',
  'The API returns twenty-five tasks per page by default. A client can request a page size between one and one hundred. Cursor-based pagination identifies the next result position. The server sorts by update time and uses the task identifier to break ties so that pagination is deterministic. An empty search returns an empty array and no next cursor, not an error response.',
  [('Default page size','Twenty-five tasks'),('Maximum page size','One hundred tasks'),('Search fields','Title and description'),('Pagination','Cursor based')]),
 ('CSV imports',
  'TaskBoard Lite accepts CSV imports containing at most 2,000 task rows and a file size of at most 5 MB. Both limits apply independently. The header row is not counted as a task row. Accepted columns are title, description, assignee_email, priority, status and due_date. The title column is mandatory; other columns are optional.',
  'Before publishing imported tasks, the server validates every row and checks that assigned users belong to the workspace. An invalid row causes the entire import to fail with row-level error details; partial imports are not allowed. Duplicate rows inside the same file are reported rather than silently merged. The due_date format is YYYY-MM-DD. An import never creates new workspace memberships from email addresses.',
  [('Task-row limit','2,000 rows, excluding the header'),('File-size limit','5 MB'),('Required column','title'),('Failure behavior','Reject the whole import with row errors')]),
 ('Notifications',
  'An assigned member receives an in-app notification when another member assigns a task to them. A mentioned member receives a notification when a comment uses their workspace mention identifier. Users do not receive notifications for actions they perform themselves. Notifications link to the relevant task and show the actor and action.',
  'The first release includes in-app notifications only. Email, push notifications and daily digests are excluded. A user can mark one notification or all notifications as read. Read status is scoped to the recipient. If a user loses workspace access, task links from old notifications stop opening the task. Notification delivery failures must not roll back a successful task update; failures are recorded for investigation.',
  [('Channels','In-app only'),('Triggers','Task assignment and comment mentions'),('Self-notifications','Suppressed'),('Failure handling','Record failure; preserve task update')]),
 ('Performance and accessibility targets',
  'The fictional acceptance target is a p95 API response time below 400 milliseconds for normal task reads under the defined test workload. This is a target, not a measured production result. The workload contains twenty concurrent users, ten workspaces and 10,000 total tasks on a fixed test environment.',
  'Keyboard navigation covers task creation, board movement, filters and comments. Form errors are connected to their fields with accessible labels. Status is communicated with text rather than color alone. The application respects reduced-motion preferences. Performance reports must record the test environment and distinguish browser rendering time from API time. A single successful request is insufficient evidence for meeting a p95 target.',
  [('Read latency target','p95 below 400 ms'),('Concurrent test users','Twenty'),('Test dataset','Ten workspaces and 10,000 tasks'),('Evidence requirement','Repeatable workload and environment record')]),
 ('Reliability and data lifecycle',
  'A task update and its audit event commit in one database transaction. The audit event stores the actor, task identifier, action and timestamp. A failed database write returns an error and must not leave a successful-looking task update in the interface. The client allows a retry after an error but does not blindly repeat destructive actions.',
  'Archiving a task hides it from the default board without permanently deleting it. An editor can restore an archived task. Workspace owners can request an export containing active and archived tasks. The fictional recovery objective is a maximum data-loss window of twenty-four hours for backups; restoration must be tested before claiming the objective is met. Backup goals in this specification are not guarantees about DocuChat storage.',
  [('Task removal','Archive with restore support'),('Audit writes','Same transaction as task update'),('Export access','Workspace owner'),('Recovery objective','Maximum twenty-four-hour data-loss window')]),
 ('Release acceptance and exclusions',
  'Release 1.0 is accepted when workspace permissions, task validation, board changes, search, imports and in-app notifications pass the agreed acceptance suite. The permission suite includes cross-workspace access attempts, not only successful requests. The import suite includes malformed CSV, excessive rows and assignment to a non-member.',
  'The first release excludes native mobile applications, calendar synchronization, billing, AI summaries and external automation integrations. A feature is not complete merely because a button or route exists. Reviewers need successful behavior, failure handling and recorded checks. This document does not specify subscription prices or an exact public launch date. A reader should report those details as absent rather than infer them from the release version.',
  [('Release','1.0'),('Key checks','Permissions, validation, import failures and notifications'),('Not specified','Subscription prices and public launch date'),('Excluded AI feature','AI-generated summaries')]),
 ]),
 dict(id='report',title='Project report',filename='sample-project-report.pdf',question='What was the p95 response time after the search optimization?',answer='310 milliseconds, compared with 780 milliseconds before optimization.',page=7,pages=[
 ('Project summary',
  'The Harbor Library Search Pilot is a fictional six-week software project for a small public-library catalog. The team built a search interface, a catalog API and an import process for a synthetic collection of 18,000 catalog records. All organizations, schedules and measurements in this report are invented for testing DocuChat; they are not achievements of the DocuChat project.',
  'The pilot addressed inconsistent search results and slow catalog browsing. It did not replace library circulation software. The final deliverables were a browser interface, a documented API, a repeatable import command and a test report. The pilot ran from 3 August to 11 September 2026. A demonstration used a synthetic dataset rather than real borrower information.',
  [('Project duration','Six weeks'),('Pilot dates','3 August to 11 September 2026'),('Catalog size','18,000 synthetic records'),('Excluded system','Library circulation software')]),
 ('Scope and stakeholders',
  'The pilot supported title, author and subject searches. Readers could filter by publication year and material type. A catalog administrator could replace the synthetic catalog through a validated import. Borrower accounts, loans, fines and reservation handling were outside scope.',
  'The fictional team included a coordinator, two developers and one tester. A library representative reviewed search terminology and result presentation. The coordinator maintained acceptance criteria and scheduled weekly demonstrations. The representative approved the scope but did not administer the test infrastructure. Change requests were logged separately so that an attractive extra feature could not silently replace a required search behavior.',
  [('Search fields','Title, author and subject'),('Filters','Publication year and material type'),('Team','Coordinator, two developers and one tester'),('Excluded','Borrower accounts, loans, fines and reservations')]),
 ('Requirements and acceptance',
  'The catalog search endpoint accepted a query string and optional year and material-type filters. Empty queries returned a browsable catalog page. Each result included a record identifier, title, author, publication year and material type. Results used deterministic ordering to make pagination repeatable.',
  'Acceptance required correct filters, no missing mandatory result fields and a repeatable import. The team prepared forty functional search cases with expected identifiers. A reviewer checked accessibility with keyboard navigation and visible focus states. Response-time targets were recorded before optimization to prevent the team from redefining success after seeing measurements. No requirement included machine-learning recommendations or personalized ranking.',
  [('Functional search cases','Forty'),('Mandatory result fields','Identifier, title, author, year and type'),('Ordering','Deterministic'),('Not included','Personalized ranking')]),
 ('System architecture',
  'The fictional pilot used a static browser interface, an HTTP catalog API and a relational database. The browser sent queries to the API rather than connecting directly to the database. Database credentials remained on the server. The import command validated a CSV file before inserting catalog records.',
  'The service separated request validation, search queries and response formatting into different modules. A database index supported common search filters. The system used structured logs to record request duration and status. The report describes the Harbor pilot architecture only; it must not be confused with DocuChat, which uses a Gemini-backed retrieval pipeline and optional Qdrant storage.',
  [('Components','Browser, HTTP API and relational database'),('Import format','CSV'),('Secret boundary','Database credentials on server'),('Logging','Request duration and response status')]),
 ('Schedule and milestones',
  'Week one covered requirements and a synthetic dataset. Week two delivered catalog import validation and the initial database schema. Week three delivered search endpoints and pagination. Week four connected the browser interface and filters. Week five focused on optimization and accessibility. Week six covered regression checks, deployment rehearsal and handover.',
  'Each milestone included a brief demonstration and a written issue list. An incomplete feature carried into the next week with an explicit owner. The team postponed a proposed recommendation panel because it was outside the accepted scope. The schedule left the last week for verification rather than treating the first successful demonstration as the end of the project.',
  [('Week two','Import validation and schema'),('Week three','Search endpoints and pagination'),('Week five','Optimization and accessibility'),('Week six','Regression, rehearsal and handover')]),
 ('Testing approach',
  'The final test suite contained 68 automated cases: forty search cases, sixteen import-validation cases and twelve API error-handling cases. The suite used a disposable database loaded from the synthetic catalog fixture. Tests did not depend on real borrower records or a production account.',
  'The tester separately checked keyboard navigation, empty states and readable error messages. Automated cases verified expected record identifiers rather than only checking for HTTP 200. Import tests covered missing required columns, duplicate identifiers and invalid years. A successful local suite established behavior in that environment; the team still ran a deployment smoke check and restoration rehearsal afterward.',
  [('Automated cases','68 total'),('Search cases','40'),('Import cases','16'),('API error cases','12')]),
 ('Search performance results',
  'Under the same synthetic workload, the measured p95 search API response time fell from 780 milliseconds before optimization to 310 milliseconds after optimization. The workload used twenty concurrent simulated users against 18,000 catalog records. Measurements excluded browser rendering and covered the API request duration only.',
  'The optimization added an index for frequent filters, removed repeated per-result database queries and limited the returned fields. The test environment used two virtual CPU cores and 4 GB of memory. The report records these results as fictional sample data. They must not be quoted as DocuChat performance. Average latency was not recorded, so it cannot be derived from the p95 values.',
  [('Before optimization','p95 780 ms'),('After optimization','p95 310 ms'),('Concurrency','Twenty simulated users'),('Environment','Two virtual CPU cores and 4 GB memory')]),
 ('Issues and corrective actions',
  'An early import accepted duplicate catalog identifiers and caused inconsistent result counts. The team added a uniqueness constraint and a validation error listing duplicate identifiers before commit. This made invalid imports fail as a whole rather than publishing a partially replaced catalog.',
  'A second issue reset filters when moving between result pages. The client began carrying filter parameters into every pagination request. A regression case verified that a year filter remained active on the second page. The team also corrected a keyboard focus trap in the filter panel. Each issue was linked to a reproduction procedure and a verification check, not closed solely because a developer had changed code.',
  [('Import issue','Duplicate catalog identifiers'),('Import fix','Uniqueness constraint and pre-commit validation'),('Pagination issue','Filters reset between pages'),('Accessibility issue','Keyboard focus trap')]),
 ('Deployment and handover',
  'The team rehearsed deployment in a staging environment using a fresh database and the documented import command. Configuration values were supplied through server environment variables. The handover package contained setup steps, an environment-variable checklist, API examples and a recovery procedure.',
  'A reviewer restarted the staging API and checked that catalog records remained available. The reviewer also restored the synthetic catalog into a separate database from an export. These checks demonstrated behavior in staging only; they did not prove long-term production reliability. The report includes no public service URL or service-level agreement. Ownership after handover passed to the fictional catalog maintenance team.',
  [('Environment','Staging'),('Persistence check','Restart API and query catalog'),('Recovery check','Restore export to a separate database'),('Handover owner','Catalog maintenance team')]),
 ('Conclusions and next steps',
  'The pilot met its recorded functional acceptance cases and improved search latency in the defined synthetic environment. The main engineering lesson was to connect claims to repeatable evidence: expected result identifiers, fixed test data, workload details and a clear separation between local, staging and production verification.',
  'Proposed next steps were typo-tolerant search, richer catalog descriptions and larger workload tests. These proposals were not implemented during the six-week pilot. Personalized recommendations remained outside scope because they would need an evaluation dataset and additional design work. The report does not provide user-satisfaction scores, deployment costs or production traffic figures. A question about those missing measurements should receive an explicit statement that the report does not contain them.',
  [('Completed','Recorded functional checks and staging rehearsal'),('Proposed','Typo tolerance and larger workload tests'),('Not measured','User satisfaction and production traffic'),('Not provided','Deployment costs')]),
 ])
]

for sample in DATA:
    pages=[]
    for n,(heading,one,two,rows) in enumerate(sample['pages'],1):
        pages.append([p('DOCUCHAT SAMPLE / FICTIONAL DATA','SmallDoc'),p(sample['title'],'TitleDoc'),p(f'{n:02d}  {heading}','SectionDoc'),p(escape(one)),p(escape(two)),Spacer(1,12),facts(rows),Spacer(1,18),p('Reading note: answer from this document only. If a requested detail is absent, say that it is not specified.','SmallDoc')])
    write_pdf(PUBLIC/sample['filename'],sample['title'],pages)

manifest=[{k:s[k] for k in ('id','title','filename','question')} | {'pages':10,'url':'/samples/'+s['filename']} for s in DATA]
(ROOT/'my-react-app/src/data/samples.json').write_text(json.dumps(manifest,indent=2)+'\n')

class Architecture(Flowable):
    def __init__(self):
        Flowable.__init__(self); self.width=475; self.height=250
    def draw(self):
        c=self.canv
        def box(x,y,w,h,title,subtitle):
            c.setFillColor(colors.HexColor('#eff4e9')); c.setStrokeColor(colors.HexColor('#b5c8a7')); c.roundRect(x,y,w,h,8,fill=1,stroke=1)
            c.setFillColor(INK); c.setFont('Helvetica-Bold',10); c.drawCentredString(x+w/2,y+h-20,title); c.setFont('Helvetica',8); c.drawCentredString(x+w/2,y+14,subtitle)
        def arrow(x,y,a,b):
            c.setStrokeColor(GREEN);c.line(x,y,a,b);c.line(a,b,a-4,b+5);c.line(a,b,a+4,b+5)
        box(0,185,215,55,'React browser','Upload / samples / chat / source panels')
        box(0,92,215,55,'FastAPI backend','Validate -> extract -> retrieve -> cite')
        arrow(107,185,107,147)
        box(260,185,215,55,'Static sample PDFs','Three original 10-page documents')
        box(260,92,215,55,'Gemini APIs','Document/query embeddings + generation')
        c.setStrokeColor(GREEN);c.line(215,120,260,120)
        box(0,0,215,55,'SQLite - local option','Metadata, chunk text and vectors in a file')
        box(260,0,215,55,'Qdrant - hosted option','Metadata, chunk text and vectors remotely')
        arrow(107,92,107,55);c.line(190,92,367,55)
        c.setFont('Helvetica',8);c.setFillColor(GREEN);c.drawString(231,71,'Choose one store')
        c.drawString(224,164,'Samples use the same upload API')

GUIDE=[]
def page(title, intro, sections, extras=None):
    content=[p('DOCUCHAT AI / ARCHITECTURE & STUDY NOTES','SmallDoc'),p(title,'TitleDoc'),p(intro)]
    for head,body in sections:
        content.extend([p(head,'SectionDoc'),p(body)])
    if extras: content.extend(extras)
    GUIDE.append(content)

page('01 / The project at a glance',
 'DocuChat is a PDF question-answering application. You upload a text PDF, select it, ask a question, and inspect the page excerpts referenced by the answer. This guide describes the local source as updated on 6 November 2026.',[
 ('What is implemented','A single React workspace, light/dark preference, public shared document library, upload/select/delete actions, Gemini embeddings and answers, document-filtered search, and expandable citation references. Three fictional sample PDFs are bundled with the frontend and indexed only when a visitor chooses Use.'),
 ('What this project demonstrates','Frontend state and HTTP integration, Python API design, PDF processing, vector retrieval, persistent storage choices, input validation, provider error handling and offline tests. Using a pretrained model through an API is inference integration; this project does not train or fine-tune a language model.'),
 ('Evidence boundary','Before these notes, 42 offline backend tests passed and frontend lint/build passed. The sample additions receive separate checks. Offline tests mock Gemini and Qdrant HTTP calls. The current preview uses local SQLite. The updated UI and key removal have not been verified on the public Render deployment.'),
 ('How to use these notes','Read the architecture first, then trace one upload and one question through the actual files. Run a check, change a small behavior and explain what changed. Treat planned improvements as proposals until they are implemented and measured.')])
page('02 / System architecture',
 'RAG means retrieval-augmented generation: retrieve relevant document excerpts first, then give those excerpts to a language model when asking it to answer.',[],[Architecture(),Spacer(1,15),p('The browser calls FastAPI, not Gemini or Qdrant directly. Provider credentials belong on the backend. The sample PDFs are public static files; selecting one sends its bytes through the normal upload route.'),p('The storage adapter selects SQLite or Qdrant. They are alternatives, not a replication pair. Qdrant stores extracted text, metadata and vectors; it does not store the original PDF. The current code does not retain chat history on the server.'),p('Deployment mapping','SectionDoc'),facts([('Frontend','React/Vite static build on Render Static Site'),('Backend','FastAPI on Render Web Service, one worker'),('Hosted storage','Qdrant Cloud when configured'),('Model service','Gemini embedding and generation APIs')])])
page('03 / Follow a PDF upload',
 'Start in my-react-app/src/App.jsx at handleUpload or handleUseSample. Both send multipart form data to POST /upload. FormData is the browser object used to send a file without manually building MIME boundaries.',[
 ('1. Validate before processing','backend/main.py bounds request bodies before multipart parsing and allows one modifying operation at a time with a process-local Lock. The upload handler checks the 5 MB file limit and the %PDF- signature. A signature is a quick filter, not proof that the file is valid.'),
 ('2. Extract in another process','extract_pdf runs backend/pdf_extract.py as a subprocess and sends PDF bytes through stdin. pypdf extracts text page by page. The subprocess has a 25-second wall timeout; Linux adds memory/CPU limits. Encrypted, malformed and overly complex PDFs are rejected. Scanned image-only PDFs need OCR, which is not implemented.'),
 ('3. Chunk and embed','chunk_text uses 120-word windows with 20-word overlap, plus a 1,600-byte cap for unusual text. Each chunk keeps its physical PDF page and a document-wide chunk number. embed_texts uses RETRIEVAL_DOCUMENT and 768-dimensional vectors. It batches up to twenty texts per request and normalizes valid vectors.'),
 ('4. Publish the document','The handler creates a UUID document_id and records filename, pages, characters, chunks and embedding dimensions. The selected store writes chunk data and metadata. The UI reloads the library and selects the new document. No original PDF or server-side chat history is retained.')])
page('04 / Follow a question',
 'handleSubmit sends JSON containing message and document_id to POST /chat. document_id is what keeps a question associated with one selected PDF.',[
 ('Request validation','ChatRequest is a Pydantic model: message must have 1 to 2,000 characters and document_id must match 32 lowercase hexadecimal characters. The handler separately rejects whitespace-only questions. Schema validation protects the API even if a client bypasses the interface.'),
 ('Retrieve once','retrieve_matches checks that the document exists, embeds the question with RETRIEVAL_QUERY, and calls store.search(document_id, vector, limit=3). Only the top three chunks from that document are returned. The code does not use hybrid search, reranking or an adaptive retry loop.'),
 ('Generate from the retrieved text','backend/llm.py labels excerpts with chunk and page numbers. The prompt asks Gemini to use only those excerpts, ignore document instructions, and admit when information is absent. This is a behavioral instruction, not a guarantee that unsupported claims are impossible.'),
 ('Validate references and render','cited_response checks cited chunk IDs and pages against retrieved matches. The frontend renders Markdown, cited sources and other retrieved context separately. Each chat request contains one question; previous messages are visible in the UI but are not sent as conversation memory.')], [Preformatted('POST /chat\n{"message": "What is the CSV limit?",\n "document_id": "<32-character document identifier>"}',styles['CodeDoc'])])
page('05 / Embeddings and retrieval',
 'An embedding is a list of numbers representing a piece of text. A query vector is compared with stored chunk vectors to find passages that may answer the question. Retrieval selects evidence; generation writes the answer.',[
 ('Why two task types?','Document chunks use RETRIEVAL_DOCUMENT; questions use RETRIEVAL_QUERY. Both use the same embedding model and 768 dimensions. A different model can produce a different vector space even with the same length, so changing embedding models requires reindexing documents.'),
 ('Similarity and normalization','llm.py converts embedding values to floats, rejects non-finite values, checks length, rejects zero vectors, and divides by the vector norm. SQLite ranks by a dot product of normalized vectors. Qdrant uses a Cosine collection and a document_id/type filter.'),
 ('Chunking tradeoff','A small chunk is cheap and specific but may omit necessary context. A large chunk includes more context but may dilute retrieval or cost more tokens. Overlap preserves nearby words across chunk boundaries. Page-by-page chunking keeps page citations understandable but can split ideas that span pages.'),
 ('Important current limitation','Top-three retrieval can return irrelevant text when the answer is absent. There is no calibrated confidence cutoff. Similarity scores are not answer-accuracy percentages. Broad whole-document summaries can miss sections because the model receives only a few retrieved chunks.')])
page('06 / Citation checking',
 'Read backend/citations.py carefully: its purpose is to validate reference identifiers, not to prove that a cited passage supports every sentence.',[
 ('What the code checks','The available dictionary maps retrieved chunk numbers to their metadata. A regular expression finds bracketed references such as [Chunk 4, page 2]. A reference is retained only when its chunk was retrieved and its supplied page matches. A bare chunk reference can be resolved to that chunk\'s actual page.'),
 ('What the API returns','reply contains the answer after invalid reference markers are removed. sources contains only the distinct retrieved excerpts actually cited, in citation order. other_context contains retrieved excerpts not cited. citation_warning explains invalid or missing references.'),
 ('What checking does not prove','A real page can be cited beside an incorrect claim. Removing a fabricated citation marker does not remove or verify the associated claim. The code can therefore return answer text with a warning and no verified reference IDs. Do not describe this as factual validation or hallucination prevention.'),
 ('A useful manual check','Use the employee sample and ask about remote days. The expected evidence is page 3. Check the answer, the page reference and the supporting excerpt. Then ask for the chief executive\'s salary, which is not provided. Record whether the model explicitly reports the information as absent.')])
page('07 / Storage and consistency',
 'backend/storage.py supplies the same document operations for two storage choices. This lets the API call a stable interface while deployment configuration chooses the implementation.',[
 ('SQLite for local work','SQLite stores documents and chunks in related tables inside one file. Chunk rows contain text, page numbers and serialized vectors. A transaction prevents partially inserted documents; foreign keys and cascade deletion keep document deletion consistent. Reopening the same retained file preserves the local library.'),
 ('Qdrant for hosted indexing','Qdrant stores chunk points and a separate document manifest point. Search filters by document_id and type=chunk so the manifest never becomes a search result. Metadata listing uses paginated scroll queries without returning vector arrays.'),
 ('Avoid half-published documents','Qdrant writes chunks first and publishes the manifest after successful writes. A failed insertion attempts cleanup; an absent manifest keeps orphan chunks out of the library/search flow. This is application-level publishing behavior, not a multi-request database transaction. Deletion removes chunks before the manifest so a failed chunk deletion remains retryable.'),
 ('Retention is a separate question','Local files on Render Free are temporary. Hosted Qdrant separates the index from a backend restart, but account inactivity and provider retention still matter. The app has no backup/restore workflow or per-user library isolation. All visitors can read and delete shared documents.')])
page('08 / Frontend reading guide',
 'my-react-app/src/App.jsx contains requestApi, the workspace state, upload/sample actions, document selection, chat submission and source rendering. App.css defines layout; index.css defines shared colors and light/dark themes.',[
 ('State and references','useState stores values that change what React renders: documents, selectedDocumentId, messages, operation and theme. useRef stores mutable handles without causing a render: the active AbortController, file input and scroll target. A ref is useful for tracking an in-flight request between event callbacks.'),
 ('Request lifecycle','runOperation disables conflicting actions, creates an AbortController and starts a timeout. It applies results only for the current component session, reports readable failures and clears busy state in finally. The initial library load runs in useEffect and aborts on unmount. These steps avoid stale results changing an abandoned view.'),
 ('Theme and persistence','The sun/moon button changes theme state. A useEffect writes data-theme on the document root and stores docuchat-theme in localStorage. CSS variables supply both palettes. Only the theme preference is saved there; provider keys and chat history are not.'),
 ('Sample behavior','The frontend bundles three ten-page PDFs and a small manifest listing title, filename and example question. Use reuses a same-name library entry when present; otherwise it fetches the static PDF and uploads it normally. The input placeholder changes to the selected sample\'s question. Typing a question still submits an ordinary /chat request.')])
page('09 / API and failure handling',
 'The routes are public after removal of the shared demo key. Removing that key did not make the library private, add accounts or introduce user isolation.',[],[
 facts([('GET /health','Process liveness only'),('GET /documents','Document metadata and storage notice'),('POST /upload','Multipart file field named file'),('POST /search','question + document_id; retrieved chunks only'),('POST /chat','message + document_id; answer and citations'),('DELETE /documents/{id}','Remove document and chunks')]),Spacer(1,18),
 p('Bounds and error responses','SectionDoc'),p('The current code limits a PDF to 5 MB, 50 pages, 200,000 extracted characters and 250 chunks. The shared library is limited to twenty documents and 2,000 chunks. The middleware serializes POST/DELETE operations in one process. This is not per-IP rate limiting and does not coordinate across multiple workers.'),
 p('Provider failures','SectionDoc'),p('Gemini quota errors map to 429, timeouts to 504, and selected provider/access errors to sanitized 502 messages. Storage failures return a controlled 503. Credentials are sent in request headers, not in provider URLs or frontend bundles. CORS controls browser origins; it is not authentication and does not prevent direct HTTP clients from calling a public API.')])
page('10 / Verification and deployment',
 'Separate three kinds of evidence: offline checks, local live-provider checks and deployed acceptance checks. Passing one category does not establish the others.',[
 ('Offline commands','Run backend/.venv/bin/python -m unittest discover -s backend/tests -v from the repository root. In my-react-app run npm run lint and npm run build. Backend tests exercise real PDF extraction and SQLite behavior, while Gemini/Qdrant HTTP contracts use mocks. The last verified backend run had 42 tests.'),
 ('Live acceptance checklist','With valid provider configuration: upload two distinct PDFs, ask a question about each, inspect sources, switch documents, delete one and verify the other remains. Restart the backend and verify retained storage. Check a missing-answer question, a cold start and an oversized upload. Observe memory during indexing, not just at startup.'),
 ('Render configuration','Frontend root: my-react-app; build: npm ci &amp;&amp; npm run build; publish: dist; SPA rewrite to /index.html. Backend root: backend; install requirements; start uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1. Set VITE_API_URL when building the frontend and FRONTEND_ORIGIN on the backend.'),
 ('Backend-only configuration','GEMINI_API_KEY, GEMINI_MODEL, VECTOR_STORE, QDRANT_URL, QDRANT_API_KEY and QDRANT_COLLECTION configure the hosted services. Keep secrets outside source control. The generation-model default in this checkout is gemini-3.5-flash-lite; it is a code default, not proof that the account can access it. Updated public deployment remains pending.')])
page('11 / Interview explanations',
 'Describe the system using one concrete request. Explain what you built, why a choice fits the constraints and which claims you have actually tested.',[
 ('Why Gemini instead of self-hosting?','A hosted API keeps inference outside the lightweight backend and avoids maintaining model-serving hardware for the public demo. Free quota helped the budget. Tradeoffs include provider dependence, quotas, network latency and sending excerpts to an external service. No open-model benchmark has been completed, so do not claim Gemini is better.'),
 ('Why no LangChain or LangGraph?','The current request flow is linear and implemented in separate Python functions. A framework is not needed for its present control flow. If a later feature needs saved workflow state, branching or human approval, evaluate orchestration then. Adding a framework alone would not establish retrieval quality.'),
 ('What did you build around the model?','File validation and isolated extraction, chunk/page metadata, vector-store adapters, document filtering, citation-ID checking, failure handling, a React client and offline regression tests. The model and embedding service are pretrained external dependencies. Hosting an open-weight model would still be inference, not model training.'),
 ('What would you improve next?','Build an answerable/unanswerable evaluation set and measure retrieval success, reference correctness, unsupported claims and latency. Compare one suitable open model under the same test questions. Add per-user isolation and usage controls only when the intended audience requires them. These are proposals, not implemented capabilities.')])
page('12 / Sample questions and practice',
 'All three samples are original fictional documents with ten physical pages each. Their facts are deliberately stable so you can check retrieval and citations without uploading personal information.',[],[
 facts([(s['title'],f"{s['question']} Answer: {s['answer']} Evidence: physical page {s['page']}.") for s in DATA]),Spacer(1,16),
 p('Questions with no answer','SectionDoc'),p('Handbook: What is the chief executive\'s salary? Product spec: What does the subscription cost? Project report: What was the user-satisfaction score? These facts are absent; the assistant should say so. The fictional project report\'s performance figures must never be presented as DocuChat results.'),
 p('Exercises grounded in the code','SectionDoc'),p('1. Trace message from the input to ChatRequest and generate_answer. 2. Explain why search must filter by document_id. 3. Compare chunk sizes using the same ten questions. 4. Add a test for a concrete failure you reproduce. 5. Explain why a valid citation ID can accompany an unsupported claim. 6. Restart local storage and distinguish that check from hosted persistence.'),
 p('Primary references','SectionDoc'),p('<link href="https://fastapi.tiangolo.com/">FastAPI documentation</link> | <link href="https://react.dev/learn">React learning guide</link> | <link href="https://ai.google.dev/gemini-api/docs/embeddings">Gemini embeddings</link> | <link href="https://qdrant.tech/documentation/">Qdrant documentation</link> | <link href="https://render.com/docs/free">Render Free limits</link>. Consult these for current provider behavior; this guide describes the checked-out code, not an availability guarantee.','SmallDoc')])
write_pdf(OUT/'DocuChat-Architecture-and-Study-Notes.pdf','DocuChat AI - Architecture and Study Notes',GUIDE)

for s in DATA:
    reader=PdfReader(PUBLIC/s['filename']); assert len(reader.pages)==10
    for index,pg in enumerate(reader.pages,1):
        txt=pg.extract_text(); assert len(txt)>700,(s['id'],index,len(txt)); assert '\ufffd' not in txt
    expected = {'handbook': ['three days', 'Tuesday'], 'product': ['2,000', '5 MB'], 'report': ['780', '310']}
    evidence = reader.pages[s['page'] - 1].extract_text()
    assert all(term in evidence for term in expected[s['id']]), s['id']
reader=PdfReader(OUT/'DocuChat-Architecture-and-Study-Notes.pdf'); assert len(reader.pages)==12,len(reader.pages)
print(json.dumps({'guide_pages':len(reader.pages),'samples':[{ 'file':s['filename'],'pages':10} for s in DATA]},indent=2))
