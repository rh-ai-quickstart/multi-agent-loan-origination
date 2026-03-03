# Stitch UI Design Prompts -- Summit Cap Financial

This document contains screen-by-screen prompts for Google Stitch to generate the UI designs for Summit Cap Financial, a multi-agent mortgage lending application. Each prompt is self-contained and designed for one Stitch generation.

## About This Application

Summit Cap Financial is a Red Hat AI Quickstart -- a reference application demonstrating agentic AI applied to the mortgage lending lifecycle. It covers 5 persona experiences (Prospect, Borrower, Loan Officer, Underwriter, CEO) sharing a common backend with role-based access control, AI chat assistants, compliance tooling, and executive analytics.

This is not a demo-only shell. It is a functional quickstart that people will clone, deploy, explore, and adapt. Every screen should feel like a real product that happens to also demo well.

## Tech Stack Context

The frontend uses React 19, TypeScript, Tailwind CSS, shadcn/ui (Radix primitives), TanStack Router (file-based routing), TanStack Query (server state), and lucide-react icons. Stitch output will be converted to this stack. Design with these component capabilities in mind -- cards, badges, buttons, dropdowns, tooltips, separators, tables, tabs, dialogs, sheets, and form inputs are all available.

## Design System

### Brand Identity

Summit Cap Financial is a fictional mortgage lender headquartered in Denver, Colorado. The brand should convey trust, stability, and modern professionalism -- a fintech company that takes compliance seriously but doesn't feel like a legacy bank.

### Color Palette

Use these colors consistently across all screens. The palette draws subtle warmth from Red Hat's visual language (the crimson accent) while establishing its own professional financial identity.

| Role | Hex | Usage |
|------|-----|-------|
| Primary | #1E3A5F | Navigation, primary buttons, headings, active states |
| Primary Light | #2B5A8F | Hover states, secondary emphasis |
| Accent / CTA | #CC0000 | Call-to-action buttons, urgent badges, critical alerts, logo mark |
| Accent Dark | #990000 | Hover state for accent buttons |
| Success | #16A34A | Approved status, healthy indicators, positive metrics |
| Warning | #D97706 | Expiring rate locks, medium urgency, approaching thresholds |
| Error | #DC2626 | Denied status, critical urgency, failed checks, destructive actions |
| Background | #FFFFFF | Page background (light mode) |
| Surface | #F8FAFC | Card backgrounds, table rows, panels |
| Border | #E2E8F0 | Card borders, dividers, input borders |
| Text Primary | #0F172A | Headings, body text |
| Text Secondary | #64748B | Labels, descriptions, muted content |
| Text Muted | #94A3B8 | Timestamps, metadata, placeholders |

### Typography

- Headings: Inter or system sans-serif, semibold (600) or bold (700)
- Body text: Inter or system sans-serif, regular (400) or medium (500)
- Monospace (code, IDs): JetBrains Mono or system monospace
- Base size: 14px body, 13px secondary, 16px-24px headings

### Layout Principles

- Max content width: 1280px, centered
- Consistent spacing: 16px base unit (multiples of 4px)
- Border radius: 8px for cards and panels, 6px for buttons and inputs, 16px for modals
- Elevation: subtle shadows for cards (shadow-sm), stronger for modals and dropdowns
- All screens should work at 1280px+ viewport width (desktop-first, responsive is secondary)

### Component Patterns

- **Status badges**: pill-shaped with background tint matching status color, dark text
- **Urgency indicators**: colored dot + text label (Critical/High/Medium/Normal) -- colorblind-safe with text, not color alone
- **Data tables**: zebra-striped rows, sticky header, hover highlight, sortable columns indicated by chevron icons
- **Cards**: white background, subtle border, 16px padding, optional colored left border for category
- **Chat messages**: user messages right-aligned (primary background), assistant messages left-aligned (surface background), tool results in collapsible cards

---

## Screen 1: Public Landing Page

Design a professional landing page for Summit Cap Financial, a mortgage lending company. This is the public-facing homepage that prospects see before logging in.

**Layout (top to bottom):**

**Header bar** (sticky, white background, subtle bottom border): Summit Cap Financial logo on the left (a clean geometric logomark in crimson #CC0000 next to "Summit Cap Financial" in dark navy #1E3A5F, semibold). Right side has navigation links: Products, Calculator, About, and a "Sign In" button (outline style, navy).

**Hero section**: Full-width section with a very subtle gradient background (white to light blue-gray #F0F4F8). Large heading: "Your path to homeownership starts here" in dark navy. Subheading in secondary text: "AI-powered mortgage lending with transparent rates, personalized guidance, and a streamlined application process." Two buttons below: "Get Pre-Qualified" (solid crimson #CC0000, white text) and "Calculate Affordability" (outline navy). On the right side or below, a subtle decorative element suggesting a house or financial growth -- keep it abstract and professional, not clip-art.

**Products section**: Section heading "Our Mortgage Products" centered. A 3x2 grid of product cards, each card with: an icon at top (use simple line icons -- home, calendar, shield, star, flag, chart-line), product name bold (e.g., "30-Year Fixed", "15-Year Fixed", "Adjustable Rate", "Jumbo", "FHA", "VA"), a brief 1-line description, and a "typical rate" number displayed prominently (e.g., "6.25%"). Cards have white background, subtle border, and a navy top border accent.

**Affordability calculator section**: Light surface background (#F8FAFC). Section heading "Affordability Calculator". A clean form with 4 input fields in a 2x2 grid: Annual Income, Monthly Debts, Down Payment, Interest Rate. Each input has a label above it and a dollar sign or percent prefix inside the field. Below the inputs, a prominent "Calculate" button (crimson). Results area to the right showing: Maximum Loan Amount (large number), Estimated Monthly Payment, Purchase Price, DTI Ratio -- each in a stat card with the number large and the label small below it. The results area should look like it's waiting for input (show placeholder dashes or example numbers in muted text).

**Chat widget**: A floating chat button in the bottom-right corner -- a circular button (crimson background, white chat bubble icon, 56px diameter) with a subtle shadow. When conceptually "open", show a chat panel (400px wide, 500px tall) anchored to the bottom-right with: a header bar ("Summit Cap Assistant" with a bot avatar icon), a message area showing a welcome message ("Hi! I can help you learn about our mortgage products, estimate affordability, or start your pre-qualification. What would you like to know?"), and an input bar at the bottom with a text field and send button.

**Footer**: Navy (#1E3A5F) background, white text. Three columns: Company info (logo + tagline), Quick Links (Products, Calculator, Apply, Contact), Legal (Privacy Policy, Terms of Service, NMLS disclosure). At the bottom, a thin line and copyright text. Include a small disclaimer: "Summit Cap Financial is a fictional company created for demonstration purposes."

**Overall feel**: Clean, modern, trustworthy. Think Rocket Mortgage meets a well-designed fintech startup. Professional but approachable. Plenty of white space.

---

## Screen 2: Authentication / Sign-In

Design a clean sign-in page for Summit Cap Financial. This page redirects to Keycloak for authentication, so it is a transitional screen rather than a traditional login form.

**Layout**: Centered card on a light background with a subtle pattern or gradient. The card (max 420px wide) contains: the Summit Cap Financial logo at top center, a heading "Sign in to your account", a brief description "You'll be redirected to our secure identity provider", and a prominent "Continue to Sign In" button (solid crimson). Below the button, text: "Don't have an account? Contact us to get started."

Below the card, show 5 small persona cards in a horizontal row (for demo purposes), each showing: a small avatar circle, persona name, and role badge. These are: "Sarah Mitchell" (Borrower, green badge), "James Torres" (Loan Officer, blue badge), "Maria Chen" (Underwriter, purple badge), "David Park" (CEO, navy badge), "Admin" (Admin, gray badge). Above this row, a small label: "Demo Accounts" in muted text. This row is clearly a demo convenience, not production UI.

**Overall feel**: Simple, focused, branded. The demo account row should feel secondary -- visually de-emphasized but accessible.

---

## Screen 3: Borrower Dashboard

Design the main dashboard for a logged-in borrower (Sarah Mitchell). This is what a borrower sees after signing in -- their application status and primary interaction point.

**Layout**:

**Top nav bar** (sticky, white, bottom border): Left side shows logo + "Summit Cap Financial". Center or right shows the current user's name ("Sarah Mitchell") with a small avatar circle and role badge ("Borrower" in a green pill badge). Far right has a notification bell icon (with optional red dot for unread) and a user dropdown menu icon.

**Page content** (max-width 1280px, centered, padded):

**Application status card** (prominent, full width): A large card at the top showing the current application state. Inside: "Application #1042" as a heading with a stage badge to the right ("Underwriting" in a blue pill). Below, a horizontal progress stepper showing all stages as connected dots/segments: Inquiry > Pre-Qualification > Application > Processing > Underwriting (current, highlighted) > Conditional Approval > Clear to Close > Closed. The current stage dot is filled and larger, completed stages have checkmarks, future stages are gray. Below the stepper, three stat items in a row: "Days in Stage: 3", "Next Step: Underwriter review in progress", "Loan Amount: $425,000".

**Two-column layout below the status card**:

**Left column (wider, ~60%)**:

"Documents" card: A table or list showing uploaded documents. Columns: Document Type (with icon -- file, image), Status (badge: "Accepted" green, "Processing" amber, "Needs Resubmission" red), Upload Date. Show 4-5 example rows (W-2, Pay Stub, Bank Statement, Tax Return, Property Appraisal). Below the list, a "Missing Documents" callout (amber left border) listing what is still needed: "Employment Verification, Insurance Quote". At the bottom, a dashed-border upload zone: "Drag and drop files here or click to browse" with file type hints.

"Conditions" card: A list of underwriting conditions. Each item shows: condition description text, severity badge (Critical/Standard in red/blue pills), status ("Open" / "Responded" / "Cleared"), and an action button ("Respond") for open conditions. Show 2-3 example conditions like "Provide letter of explanation for employment gap" (Standard, Open) and "Submit updated bank statement within 30 days" (Critical, Open).

**Right column (~40%)**:

"Rate Lock" card: Shows lock status with a colored indicator. "Rate Locked" heading with a green badge. Display: Rate (6.25%), Lock Date (Jan 15, 2026), Expiration (Mar 15, 2026), Days Remaining (13 -- in amber text if under 14 days). A small progress bar showing time remaining.

"Application Summary" card: Key details in a label-value list. Loan Type: 30-Year Fixed. Property: 1234 Elm Street, Denver, CO. Purchase Price: $500,000. Down Payment: $75,000 (15%). Estimated Monthly Payment: $2,614.

**Chat panel** (right side, collapsible): A slide-out panel or always-visible right sidebar (320px wide) containing the borrower's AI assistant chat. Header: "Your Assistant" with a bot avatar. Shows conversation history with the borrower's messages on the right and assistant responses on the left. Example exchange: User: "What documents do I still need?" / Assistant: "You're missing your Employment Verification and Insurance Quote. Would you like me to explain what's needed for each?" Input bar at the bottom.

**Overall feel**: Informative but not overwhelming. The borrower should immediately understand where their application stands and what they need to do next. The chat is accessible but doesn't dominate -- the dashboard provides at-a-glance status, and the chat handles deeper questions.

---

## Screen 4: Loan Officer Pipeline

Design the pipeline dashboard for a loan officer (James Torres). This is the LO's primary workspace -- a table of their assigned applications with filtering, sorting, and urgency indicators.

**Layout**:

**Top nav bar**: Same structure as borrower but with "James Torres" and a blue "Loan Officer" badge. Add a left-side navigation: "Pipeline" (active, bold), "Messages", "Settings".

**Page header area**: "My Pipeline" as the page heading. Below, a row of summary stat cards (4 cards, horizontal): "Active Applications: 12" (navy icon), "In Underwriting: 4" (blue icon), "Critical Urgency: 2" (red icon), "Avg Days to Close: 34" (gray icon). Each card has the number large and the label small below.

**Filter bar**: A horizontal bar below the stats with: a search input ("Search by borrower name..."), a dropdown for Stage filter (All Stages, Application, Processing, Underwriting, Conditional Approval, Clear to Close), a dropdown for Urgency filter (All, Critical, High, Medium, Normal), a toggle button "Stalled Only" (filters to applications with 7+ days no activity), and a Sort dropdown (Urgency, Updated, Loan Amount, Borrower Name). Filters are compact, inline, with clear/reset capability.

**Pipeline table** (main content): A data table with these columns:

| Urgency | Borrower | Loan Amount | Stage | Days in Stage | Rate Lock | Last Activity | Actions |
|---------|----------|-------------|-------|--------------|-----------|--------------|---------|

- **Urgency**: A colored dot (red/orange/yellow/green) with a text label on hover tooltip. Critical rows have a subtle red-tinted left border.
- **Borrower**: Full name, clickable link
- **Loan Amount**: Formatted currency ($425,000)
- **Stage**: Pill badge, color-coded by stage category (blues for processing stages, greens for approval stages, red for denied)
- **Days in Stage**: Number, with amber text if exceeding expected duration
- **Rate Lock**: "Active (13d)" in green, "Expiring (3d)" in amber, "Expired" in red, or "None" in gray
- **Last Activity**: Relative time ("2 hours ago", "3 days ago") with amber text if stale (7+ days)
- **Actions**: A small "View" button or chevron icon to open the application detail

Show 8-10 rows with varied data -- a mix of urgency levels, stages, and rate lock statuses. Include at least one Critical (rate lock expiring in 2 days) and one stalled application (12 days, amber indicators).

**Pagination**: Below the table, showing "Showing 1-10 of 12 applications" with page controls.

**Chat panel**: Same right-side collapsible pattern. LO assistant header. Example: User: "Which applications need my attention today?" / Assistant: "You have 2 critical items: Sarah Mitchell's rate lock expires in 2 days and needs underwriting submission. Robert Kim's application has been stalled for 12 days awaiting your document review."

**Overall feel**: Data-dense but organized. The urgency indicators and filtering should let the LO instantly identify what needs attention. Think of a well-designed CRM pipeline view.

---

## Screen 5: Loan Officer Application Detail

Design the application detail view that a loan officer sees when they click into a specific application from their pipeline. This is a deep-dive workspace for reviewing an application.

**Layout**:

**Breadcrumb**: "Pipeline > Sarah Mitchell -- #1042"

**Application header** (full width card): Left side: Borrower name "Sarah Mitchell" large, with application ID "#1042" in muted text. Stage badge ("Underwriting", blue pill). Below the name: key stats in a row -- Loan Amount: $425,000 | Property: 1234 Elm St, Denver CO | Loan Type: 30-Year Fixed | Rate Lock: Active (13 days). Right side: action buttons -- "Submit to Underwriting" (primary, solid navy -- disabled if already submitted, with tooltip explaining why), "Request Documents" (outline), and a three-dot overflow menu.

**Tab navigation** below the header: Profile | Financial Summary | Documents | Conditions | Audit Trail. Tabs are underline-style, the active tab has a navy bottom border.

**Profile tab content** (shown by default): Two-column layout.

Left column: "Borrower Information" card. Label-value pairs: Full Name, Email, Phone, Date of Birth, SSN (shown as ***-**-4321), Employment Status, Employer, Annual Income ($95,000), Employment Tenure (3 years). If there's a co-borrower, show a "Co-Borrower" sub-section with similar fields.

Right column: "Property Information" card: Address, Property Type (Single Family), Occupancy (Primary Residence), Appraised Value ($500,000), Down Payment ($75,000 / 15%), LTV Ratio (85%). Below that, a "Loan Details" card: Loan Type, Loan Amount, Interest Rate, Term, Estimated Monthly Payment, DTI Ratio (38% -- shown in amber if above 36%, with tooltip "Approaching DTI threshold").

**Documents tab content** (described for reference): Similar to borrower's document view but with additional LO actions -- "Accept", "Request Resubmission" buttons on each document row. Quality flags shown as amber warning badges next to affected documents. A document completeness progress bar at the top: "6 of 8 required documents provided" with a segmented bar.

**Conditions tab content**: Same condition list as borrower view but with additional LO context -- underwriter notes, iteration count, response history per condition.

**Chat sidebar** (persistent right panel, 360px): The LO assistant, contextualized to this application. Example exchange: User: "Is this file ready for underwriting?" / Assistant: "Almost. Sarah is missing Employment Verification and the bank statement has a quality flag (wrong period -- shows Q2 instead of Q3). I recommend requesting an updated bank statement before submission." The chat panel has a subtle header showing "Reviewing: Sarah Mitchell #1042" to confirm context.

**Overall feel**: A comprehensive but well-organized workspace. Tabs prevent information overload. The chat sidebar provides intelligent assistance without leaving the review context.

---

## Screen 6: Underwriter Queue and Review

Design the underwriter workspace for Maria Chen. This combines the queue view (list of applications awaiting underwriting) with a preview of the detailed review interface. Show the queue as the primary view.

**Layout**:

**Top nav bar**: "Maria Chen" with purple "Underwriter" badge. Left nav: "Queue" (active), "Decided", "Settings".

**Queue view**:

**Page header**: "Underwriting Queue" heading. Stat row: "Pending Review: 6" | "In Progress: 2" | "Decided Today: 3" | "Avg Review Time: 2.1 days".

**Queue table**: Columns: Borrower, Loan Amount, Property, Assigned LO, Days in Queue, Rate Lock, Priority. Similar styling to LO pipeline table but focused on underwriting concerns. Show 6-8 rows. Include sort and filter controls above the table.

**When an application is selected** (shown as a split-view or full page):

**Review workspace** with these panels arranged in a two-column layout:

**Left column (wider, ~65%)**:

"Risk Assessment" panel: A structured results display after the underwriter requests analysis. Sections with headers: Credit Risk (score, factors, rating), Capacity Risk (DTI ratio, income stability, employment verification), Collateral Risk (LTV, property type, appraisal), Compensating Factors (listed as green chips/badges). At the bottom, a "Preliminary Recommendation" box with a colored left border: "Approve with Conditions" in amber, with the AI's reasoning in smaller text.

"Compliance" panel below risk: Three compliance check results shown as cards in a row. Each card shows: regulation name (ECOA, ATR/QM, TRID), a large pass/fail icon (green checkmark or red X), a brief description of what was checked, and details expandable on click. If any check fails, it has a red border and action guidance.

"Conditions" panel: List of existing conditions (if any from prior review cycle) plus an "Issue New Condition" button that opens a form: Description (text area), Severity (dropdown: Critical, Standard, Optional), Due Date.

**Right column (~35%)**:

"Decision" panel (sticky): The underwriter's decision interface. Radio buttons for: Approve, Approve with Conditions, Suspend, Deny. A text area for "Decision Rationale". Below, an "AI Recommendation" read-only box showing what the AI suggested, for comparison. A prominent "Record Decision" button (navy, solid). Warning text: "This decision will be recorded in the audit trail and cannot be modified."

"Application Summary" panel: Compact label-value list of key application data (borrower, loan amount, property, LTV, DTI, credit score) for quick reference without switching tabs.

"Compliance KB" panel: A search box labeled "Search Compliance Knowledge Base". Below, example search results showing: regulation title, tier badge (Federal/Agency/Internal with corresponding blue/purple/gray badges), relevant section citation, and a brief excerpt. A conflict warning callout if conflicting guidance is found across tiers.

**Chat sidebar**: Underwriter assistant. Example: User: "Run a risk assessment on this application" / Assistant: (shows structured risk assessment results inline). The chat here supports complex tool outputs rendered as structured cards within the conversation.

**Overall feel**: Analytical and authoritative. The underwriter needs to see risk factors, compliance status, and decision tools all accessible without excessive navigation. Dense but structured -- this is a power-user workspace.

---

## Screen 7: CEO Executive Dashboard

Design the executive dashboard for David Park (CEO). This is a four-panel analytics view with aggregate metrics, trends, and an optional chat assistant for drill-down questions.

**Layout**:

**Top nav bar**: "David Park" with a dark navy "CEO" badge. Left nav: "Dashboard" (active), "Audit Trail", "Settings".

**Dashboard controls** (below nav): A time range selector as a button group: "30 Days" | "60 Days" | "90 Days" (active/selected) | "180 Days". Right-aligned: "Export" button (outline) and a "Refresh" icon button.

**Four-panel grid** (2x2 layout, each panel is a card with a heading, content area, and optional footer):

**Panel 1 -- Pipeline Health** (top-left): Heading: "Pipeline Overview". A horizontal funnel or bar chart showing application count by stage: Inquiry (24), Pre-Qualification (18), Application (15), Processing (8), Underwriting (6), Conditional Approval (4), Clear to Close (3), Closed (12). Bars colored in a gradient from light to dark navy. Below the chart, three key metrics in a row: "Pull-Through Rate: 32%" (with a small up-arrow in green indicating improvement), "Avg Days to Close: 42", "Active Applications: 78".

**Panel 2 -- Denial Trends** (top-right): Heading: "Denial Analysis". A line chart showing denial rate over time (monthly data points, last 6-9 months). The line is in crimson (#CC0000). Current denial rate displayed prominently: "12.4%". Below the chart, a "Top Denial Reasons" mini-table: Reason | Count | %. Show 4-5 rows (Insufficient Income, High DTI, Credit History, Incomplete Documentation, Property Issues). A small dropdown to filter by product type.

**Panel 3 -- LO Performance** (bottom-left): Heading: "Loan Officer Performance". A table showing LO metrics. Columns: Name, Active, Closed, Pull-Through %, Avg Days to UW, Denial Rate. Show 4-5 loan officers with varied performance. The top performer has a subtle green highlight. The lowest performer has a subtle amber highlight. Sortable column headers.

**Panel 4 -- Model Monitoring** (bottom-right): Heading: "AI Model Health". This panel shows inference metrics. Top row: three stat boxes showing "p50: 245ms" | "p95: 890ms" | "p99: 1.4s" for latency. Below, a small area chart showing token usage over time (input tokens in one shade, output tokens in another). Below that, two compact metrics: "Error Rate: 0.3%" (green, healthy) and "Model Distribution" with a small horizontal stacked bar showing the split between models (e.g., 72% fast model, 28% capable model). If monitoring data is unavailable, show a tasteful empty state: "Model monitoring unavailable -- configure LangFuse to enable."

**Audit Trail panel** (full width, below the grid): A collapsible section headed "Recent Audit Events". When expanded, shows a searchable/filterable table: Timestamp | Event Type (badge) | User | Role | Description. Filter controls: date range picker, event type dropdown, search box. Show 5-6 example rows. Note that PII values are masked (SSN shows as ***-**-4321). An "Export Audit Trail" button.

**Chat panel**: Right-side collapsible panel. "Executive Assistant" header. Example: User: "What's driving our denial rate up this quarter?" / Assistant: "The denial rate increased from 10.1% to 12.4% over the past 90 days. The primary driver is 'Insufficient Income' denials, which increased 40% quarter-over-quarter. This correlates with 3 new jumbo loan applications that were denied for income requirements. Excluding jumbo products, the denial rate is stable at 9.8%."

**Regulatory disclaimer** (footer of the fair lending section or bottom of dashboard): Small muted text: "These metrics are computed on aggregate data for internal monitoring. This content is simulated for demonstration purposes and does not constitute legal or regulatory advice."

**Overall feel**: Executive and polished. Charts should be clean with minimal chartjunk. The dashboard should tell a story at a glance -- is the pipeline healthy? Are there concerning trends? How are the LOs performing? Is the AI infrastructure stable? Think Bloomberg Terminal meets a modern SaaS dashboard, but cleaner and less dense.

---

## Screen 8: Chat Interface (Full View)

Design a dedicated full-screen chat interface that works for any persona. This is the expanded version of the chat sidebar, used when the user wants to focus entirely on the AI assistant conversation.

**Layout**:

**Chat area** (centered, max 800px wide, full height minus nav):

**Chat header**: A bar showing the assistant name and context. Left: bot avatar icon + "Borrower Assistant" (or whatever persona). Right: a "Minimize" button (to return to sidebar mode) and a conversation menu (three dots) with options: Clear History, Export Conversation.

**Message area** (scrollable, flex-grow): Messages displayed in a conversation thread. User messages are right-aligned with a primary-colored background (#1E3A5F, white text) and rounded corners (rounded on all corners except bottom-right). Assistant messages are left-aligned with a light surface background (#F8FAFC, dark text) and rounded corners (all except bottom-left). Each message shows a small timestamp below it in muted text.

**Tool result cards**: When the assistant invokes a tool (risk assessment, document check, compliance search, analytics query), the results are displayed as an embedded card within the message flow. These cards have: a header with tool name and an icon, structured content (tables, key-value pairs, status badges), and a subtle border distinguishing them from regular text messages. Example: a "Document Completeness" tool result card showing a mini-table of required vs provided documents with status badges.

**Typing indicator**: Three animated dots in a pill shape, shown while the assistant is generating a response.

**Input area** (bottom, sticky): A text input field with rounded corners, placeholder "Type a message...", and a send button (crimson circle with white arrow icon) on the right. Above the input, optionally show suggested quick actions as small chip buttons: "Check my status", "Upload a document", "What's needed next?" -- contextual to the persona.

**Empty state** (when no conversation history): Center-aligned content: a large bot avatar icon, "How can I help you today?", and 3-4 suggested conversation starters as clickable cards: "What mortgage products do you offer?", "Help me with my application", "Check my document status", "Explain rate locks".

**Overall feel**: Clean, conversational, modern. Think ChatGPT's interface but with financial branding and embedded structured data cards. The focus is on the conversation with clear visual hierarchy between user input, assistant responses, and tool results.

---

## Screen 9: Document Upload Interface

Design the document upload and management view for borrowers. This can be accessed from the borrower dashboard or through the chat assistant.

**Layout**:

**Page header**: "Documents" heading with application context ("Application #1042"). A completeness indicator: "6 of 8 required documents" with a segmented progress bar (filled segments in green, missing in gray with a dashed border).

**Upload area** (top): A large drop zone with dashed border (200px tall), centered icon (cloud-upload), heading "Upload Documents", subtext "Drag and drop files here, or click to browse. Supported: PDF, JPG, PNG, XLSX (max 10MB)". When a file is being dragged over, the border turns solid crimson and the background gets a subtle tint.

**Required documents checklist**: A grid of cards (2-3 columns) showing each required document type. Each card shows: document type icon and name (W-2, Pay Stub, Tax Return, Bank Statement, Employment Verification, ID, Property Appraisal, Insurance), status indicator (green checkmark if provided, amber clock if processing, red X if rejected/needs resubmission, gray circle if not yet uploaded), and if uploaded: the file name, upload date, and a "View" link. Cards for missing documents have a dashed border and muted styling with an "Upload" button.

**Upload queue** (appears when files are selected): A list of files being uploaded, each showing: file name, file size, a progress bar, and status (Uploading... / Processing... / Complete / Failed). Completed items show a green checkmark. Failed items show a red X with an error message and "Retry" button.

**Overall feel**: Straightforward and reassuring. Document management is stressful for borrowers -- the UI should make it clear what's needed, what's done, and what's next. Progress indicators everywhere.

---

## Screen 10: Shared Navigation and Layout Shell

Design the application shell -- the persistent navigation and layout structure that wraps all authenticated views. This establishes the consistent chrome across all persona experiences.

**Layout**:

**Top navigation bar** (sticky, 56px height, white background, subtle bottom shadow):
- Left: Summit Cap Financial logo (crimson mark + navy text, compact). Clicking returns to the persona's home/dashboard.
- Center-left: Main navigation items as text links. These vary by role:
  - Borrower: Dashboard, Documents, Messages
  - Loan Officer: Pipeline, Messages, Settings
  - Underwriter: Queue, Decided, Settings
  - CEO: Dashboard, Audit Trail, Settings
  - The active page has a navy bottom border indicator.
- Right: Notification bell icon (with red dot badge for unread count), user avatar circle (initials-based, e.g., "SM" for Sarah Mitchell, background color varies by role), clicking the avatar opens a dropdown with: user name, role badge, "Profile", "Settings", "Sign Out".

**Sidebar** (optional, collapsible, 240px, shown on larger screens for Underwriter and CEO where the workspace benefits from persistent navigation): If present, shows a vertical nav with icons + labels matching the top nav items. Collapsible to icon-only mode (64px). Has a bottom section with: version number, "Help" link, and the regulatory disclaimer link.

**Content area**: Below the nav bar (or beside the sidebar), padded content area. For most views, this is a single scrollable column. For workspace views (LO detail, UW review), this splits into main content + chat sidebar.

**Chat toggle button**: A floating action button in the bottom-right corner (56px circle, crimson background, white chat icon) visible on all pages. Shows an unread message count badge if the assistant has sent a message the user hasn't seen. Clicking opens the chat sidebar (320-360px wide, slides in from the right, pushes content or overlays it).

**Toast notifications**: Appear in the top-right corner. Used for: document upload complete, condition response received, status change alerts. Auto-dismiss after 5 seconds. Subtle animation, colored left border matching severity.

**Overall feel**: The shell should be clean and not compete with the content. Navigation is minimal and role-appropriate. The chat button is always available but unobtrusive. The layout should feel native to the role -- a borrower sees a consumer-grade app, a loan officer sees a CRM, an underwriter sees an analytical workspace, and a CEO sees a BI dashboard.

---

## Design Iteration Notes

After generating initial designs with Stitch, plan to iterate on:

1. **Consistency**: Ensure all screens use the same color palette, spacing, and component styles
2. **Data density balance**: LO/UW screens can be denser; Borrower/Prospect screens should be spacious
3. **Chat integration**: The chat sidebar should feel integrated, not bolted on -- consistent across all persona views
4. **Empty states**: Every list, table, and panel needs an empty state design (no data yet, no results found, service unavailable)
5. **Loading states**: Skeleton screens for data-loading views, spinners for actions
6. **Mobile responsiveness**: Secondary priority, but the Prospect landing page and Borrower dashboard should be usable on tablet
7. **Dark mode**: The existing codebase supports dark mode. Consider generating dark variants of key screens.
8. **Accessibility**: Verify color contrast ratios meet WCAG 2.1 AA (4.5:1 for normal text, 3:1 for large text). The urgency indicators must be distinguishable without color alone (always include text labels alongside colored dots).

## Stitch Workflow

1. Generate each screen one at a time, starting with Screen 1 (Landing Page)
2. After each generation, refine with single-change prompts (one adjustment per iteration)
3. Use the Stitch sidebar theme controls for global color/font adjustments rather than reprompting
4. Export HTML + Tailwind output for each finalized screen
5. Convert to React + shadcn/ui components in the codebase
