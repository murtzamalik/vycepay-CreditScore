# VyceScore Admin Portal -- UAT Testing Document

**Version:** 1.0
**Date:** 2026-03-09
**Prepared by:** QA Lead
**Application:** VyceScore Admin Portal (Frontend)

---

## Test Summary Table

| ID | Test Case Name | Page / Feature | Role(s) | Status |
|----|---------------|----------------|---------|--------|
| TC-001 | Login with valid credentials | Login | All | [ ] Pass / [ ] Fail |
| TC-002 | Login with invalid credentials | Login | All | [ ] Pass / [ ] Fail |
| TC-003 | Login with empty fields | Login | All | [ ] Pass / [ ] Fail |
| TC-004 | Password visibility toggle | Login | All | [ ] Pass / [ ] Fail |
| TC-005 | Forgot password flow | Login | All | [ ] Pass / [ ] Fail |
| TC-006 | Forgot password with empty email | Login | All | [ ] Pass / [ ] Fail |
| TC-007 | Back to sign in from forgot password | Login | All | [ ] Pass / [ ] Fail |
| TC-008 | Logout via header menu | Header | All | [ ] Pass / [ ] Fail |
| TC-009 | Session redirect to login | Auth Guard | All | [ ] Pass / [ ] Fail |
| TC-010 | Post-login redirect to intended page | Auth Guard | All | [ ] Pass / [ ] Fail |
| TC-011 | Sidebar navigation items for Admin | Sidebar | Admin | [ ] Pass / [ ] Fail |
| TC-012 | Sidebar navigation items for Operator | Sidebar | Operator | [ ] Pass / [ ] Fail |
| TC-013 | Sidebar navigation items for Partner | Sidebar | Partner | [ ] Pass / [ ] Fail |
| TC-014 | Sidebar navigation items for ReadOnly | Sidebar | ReadOnly | [ ] Pass / [ ] Fail |
| TC-015 | Sidebar active state highlighting | Sidebar | All | [ ] Pass / [ ] Fail |
| TC-016 | Header displays user role chip | Header | All | [ ] Pass / [ ] Fail |
| TC-017 | Header user avatar and menu | Header | All | [ ] Pass / [ ] Fail |
| TC-018 | Dashboard KPI cards display | Dashboard | All | [ ] Pass / [ ] Fail |
| TC-019 | Dashboard date range selector | Dashboard | All | [ ] Pass / [ ] Fail |
| TC-020 | Dashboard score trend chart | Dashboard | All | [ ] Pass / [ ] Fail |
| TC-021 | Dashboard score distribution panel | Dashboard | All | [ ] Pass / [ ] Fail |
| TC-022 | Dashboard query volume chart | Dashboard | All | [ ] Pass / [ ] Fail |
| TC-023 | Score Lookup - Lite search | Score Lookup | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-024 | Score Lookup - Pro search | Score Lookup | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-025 | Score Lookup - tier toggle | Score Lookup | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-026 | Score Lookup - empty ID validation | Score Lookup | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-027 | Score Lookup - error handling | Score Lookup | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-028 | Score Lookup - View Full Details button | Score Lookup | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-029 | Score Detail - score gauges | Score Detail | Admin, Operator, Partner | [ ] Pass / [ ] Fail |
| TC-030 | Score Detail - risk drivers | Score Detail | Admin, Operator, Partner | [ ] Pass / [ ] Fail |
| TC-031 | Score Detail - score history chart | Score Detail | Admin, Operator, Partner | [ ] Pass / [ ] Fail |
| TC-032 | Score Detail - not found state | Score Detail | Admin, Operator, Partner | [ ] Pass / [ ] Fail |
| TC-033 | Customer Management - table display | Customers | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-034 | Customer Management - status filter | Customers | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-035 | Customer Management - tier filter | Customers | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-036 | Customer Management - add customer | Customers | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-037 | Customer Management - API key display after creation | Customers | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-038 | Customer Management - activate customer | Customers | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-039 | Customer Management - configure license | Customers | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-040 | User Management - table display | Users | Admin | [ ] Pass / [ ] Fail |
| TC-041 | User Management - add user | Users | Admin | [ ] Pass / [ ] Fail |
| TC-042 | User Management - edit role | Users | Admin | [ ] Pass / [ ] Fail |
| TC-043 | User Management - deactivate user | Users | Admin | [ ] Pass / [ ] Fail |
| TC-044 | Audit Logs - table display | Audit Logs | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-045 | Audit Logs - search filter | Audit Logs | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-046 | Audit Logs - action filter | Audit Logs | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-047 | Audit Logs - user filter | Audit Logs | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-048 | Audit Logs - row click detail dialog | Audit Logs | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-049 | Audit Logs - export CSV | Audit Logs | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-050 | Settings - profile settings | Settings | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-051 | Settings - API configuration display | Settings | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-052 | Settings - notification preferences | Settings | Admin, Operator | [ ] Pass / [ ] Fail |
| TC-053 | Settings - system settings (Admin only) | Settings | Admin | [ ] Pass / [ ] Fail |
| TC-054 | Settings - system settings hidden for Operator | Settings | Operator | [ ] Pass / [ ] Fail |
| TC-055 | Partner Dashboard - KPI cards | Partner Dashboard | Partner | [ ] Pass / [ ] Fail |
| TC-056 | Partner Dashboard - quota usage bar | Partner Dashboard | Partner | [ ] Pass / [ ] Fail |
| TC-057 | Partner Dashboard - daily query volume chart | Partner Dashboard | Partner | [ ] Pass / [ ] Fail |
| TC-058 | Partner Dashboard - monthly usage trend | Partner Dashboard | Partner | [ ] Pass / [ ] Fail |
| TC-059 | Partner Score Lookup - Lite search | Partner Score Lookup | Partner | [ ] Pass / [ ] Fail |
| TC-060 | Partner Score Lookup - Pro search with risk drivers | Partner Score Lookup | Partner | [ ] Pass / [ ] Fail |
| TC-061 | Partner Usage - month selector | Partner Usage | Partner | [ ] Pass / [ ] Fail |
| TC-062 | Partner Usage - summary cards | Partner Usage | Partner | [ ] Pass / [ ] Fail |
| TC-063 | Partner Usage - billing breakdown table | Partner Usage | Partner | [ ] Pass / [ ] Fail |
| TC-064 | Partner Usage - daily breakdown table | Partner Usage | Partner | [ ] Pass / [ ] Fail |
| TC-065 | Partner Usage - download CSV | Partner Usage | Partner | [ ] Pass / [ ] Fail |
| TC-066 | Partner API Keys - key info display | Partner API Keys | Partner | [ ] Pass / [ ] Fail |
| TC-067 | Partner API Keys - rotate key | Partner API Keys | Partner | [ ] Pass / [ ] Fail |
| TC-068 | Partner API Keys - revoke key | Partner API Keys | Partner | [ ] Pass / [ ] Fail |
| TC-069 | Partner API Keys - copy new key | Partner API Keys | Partner | [ ] Pass / [ ] Fail |
| TC-070 | Partner Embed Config - allowed origins | Embed Config | Partner | [ ] Pass / [ ] Fail |
| TC-071 | Partner Embed Config - theme settings | Embed Config | Partner | [ ] Pass / [ ] Fail |
| TC-072 | Partner Embed Config - widget preview | Embed Config | Partner | [ ] Pass / [ ] Fail |
| TC-073 | Partner Embed Config - embed code copy | Embed Config | Partner | [ ] Pass / [ ] Fail |
| TC-074 | Partner Embed Config - save configuration | Embed Config | Partner | [ ] Pass / [ ] Fail |
| TC-075 | 404 Not Found page | Error Pages | All | [ ] Pass / [ ] Fail |
| TC-076 | 403 Access Denied inline | Role Guard | All | [ ] Pass / [ ] Fail |
| TC-077 | Role guard - Admin accessing Partner pages | Role Guard | Admin | [ ] Pass / [ ] Fail |
| TC-078 | Role guard - Partner accessing Admin pages | Role Guard | Partner | [ ] Pass / [ ] Fail |
| TC-079 | Role guard - ReadOnly access restrictions | Role Guard | ReadOnly | [ ] Pass / [ ] Fail |
| TC-080 | Error boundary - crash recovery | Error Boundary | All | [ ] Pass / [ ] Fail |
| TC-081 | DataTable pagination | Common Components | All | [ ] Pass / [ ] Fail |
| TC-082 | White label - app name in sidebar and login | White Label | All | [ ] Pass / [ ] Fail |
| TC-083 | White label - theme persistence | White Label | All | [ ] Pass / [ ] Fail |
| TC-084 | Responsive - sidebar and layout | Responsive | All | [ ] Pass / [ ] Fail |
| TC-085 | Responsive - score lookup results | Responsive | All | [ ] Pass / [ ] Fail |
| TC-086 | Loading states display | Common Components | All | [ ] Pass / [ ] Fail |
| TC-087 | Score gauge range validation | Charts | All | [ ] Pass / [ ] Fail |
| TC-088 | Security - unauthenticated API redirect | Security | N/A | [ ] Pass / [ ] Fail |
| TC-089 | Security - direct URL access without auth | Security | N/A | [ ] Pass / [ ] Fail |

---

## Test Environment

| Item | Details |
|------|---------|
| **Application URL** | http://localhost:3000 |
| **Supported Browsers** | Chrome (latest), Firefox (latest), Safari (latest), Edge (latest) |
| **Minimum Resolution** | 1280x720 (responsive support for mobile) |
| **Backend API** | http://localhost:8000 (Swagger docs at http://localhost:8000/docs) |
| **Prerequisites** | Backend and frontend servers running; test accounts seeded (see below) |

---

## Test Credentials

All test users are pre-seeded via `backend/scripts/seed_users.py`. Run `python -m scripts.seed_users` from the backend directory if users don't exist.

| Role | Email | Password | Full Name | Organization |
|------|-------|----------|-----------|--------------|
| **Admin** | `admin@vycepay.com` | `Admin@2026` | James Mwangi | VycePay |
| **Operator** | `operator@vycepay.com` | `Operator@2026` | Odhiambo Ochieng | VycePay |
| **Partner** | `partner@equitybank.co.ke` | `Partner@2026` | Wanjiku Kamau | Equity Bank |
| **ReadOnly** | `readonly@kcbgroup.com` | `ReadOnly@2026` | Amina Hassan | KCB Group |

> **Note:** These are development/UAT credentials only. `must_change_password` is set to `false` for testing convenience. Never use these in production.

## Test Data

All test data is seeded via `backend/scripts/seed_test_data.py`. Run `python -m scripts.seed_test_data` from the backend directory.

### Test National IDs (for Score Lookup)

| National ID | Type | VyceScore | NIQ Score | Risk Level | Has Risk Drivers |
|-------------|------|-----------|-----------|------------|------------------|
| `12345678` | Individual | 720 | 78 | Low Risk | Yes (3 drivers) |
| `23456789` | Individual | 540 | 45 | Medium Risk | Yes (3 drivers) |
| `34567890` | Individual | 380 | 22 | High Risk | No |
| `MSME001` | MSME/Business | 650 | 62 | Medium Risk | Yes (3 drivers) |
| `MSME002` | MSME/Business | 810 | 91 | Low Risk | No |

### Test API Keys (for Score API access)

The score endpoints require an `X-API-Key` header. The frontend auto-sets the default API key (Equity Bank Pro) on login in development mode.

| Customer | Tier | API Key | Score Access |
|----------|------|---------|--------------|
| Equity Bank Kenya | Pro | `vyc_test_equity_bank_pro_key_2026` | Lite + Pro |
| KCB Group | Deep Dive | `vyc_test_kcb_group_enterprise_key_2026` | Lite + Pro + Custom |
| Safaricom M-Pesa | Lite | `vyc_test_safaricom_lite_key_2026` | Lite only |

> **Important:** After logging in, clear localStorage and re-login if score lookups fail with auth errors. The API key is automatically stored on first login.

---

## Test Roles

The application defines four roles in `UserRole`: **Admin**, **Operator**, **Partner**, and **ReadOnly**.

### Admin
- Full access to all pages
- Sidebar items: Dashboard, Score Lookup, Customer Management, User Management, Audit Logs, Settings
- Settings page shows the "System Settings" card (Cache TTL, Rate Limit, Maintenance Mode)
- Route access: `/dashboard`, `/scores/lookup`, `/scores/detail/:id`, `/admin/customers`, `/admin/users`, `/admin/audit-logs`, `/settings`

### Operator
- Access to operational pages but not user management
- Sidebar items: Dashboard, Score Lookup, Customer Management, Audit Logs, Settings
- Settings page does NOT show "System Settings" card
- Route access: `/dashboard`, `/scores/lookup`, `/scores/detail/:id`, `/admin/customers`, `/admin/audit-logs`, `/settings`

### Partner
- Access to partner-specific pages and score lookup
- Sidebar items: Dashboard, Partner Dashboard, Score Lookup (partner), Usage & Billing, API Keys, Embed Widget
- Route access: `/dashboard`, `/partner/dashboard`, `/partner/scores`, `/partner/usage`, `/partner/api-keys`, `/partner/embed-config`, `/scores/lookup`, `/scores/detail/:id`

### ReadOnly
- Dashboard only
- Sidebar items: Dashboard
- Route access: `/dashboard`
- All other pages return 403 inline ("403 - Access Denied") via RoleGuard

---

## Test Scenarios

---

### TC-001: Login with valid credentials
**Page:** Login (`/login`)
**Role(s):** All roles
**Prerequisites:** Valid test account credentials
**Steps:**
1. Navigate to `http://localhost:3000/login`
2. Verify the login page displays the app name "VyceScore" (or configured white-label name) and subtitle "Credit Scoring Admin Portal"
3. Verify two text fields are present: "Email" (autofocused) and "Password"
4. Enter a valid email in the "Email" field
5. Enter the correct password in the "Password" field
6. Click the "Sign In" button
7. Observe the button text changes to "Signing in..." while loading

**Expected Result:** User is redirected to `/dashboard`. The sidebar and header appear with the user's avatar initials, role chip, and notification bell icon.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-002: Login with invalid credentials
**Page:** Login (`/login`)
**Role(s):** All roles
**Prerequisites:** None
**Steps:**
1. Navigate to `http://localhost:3000/login`
2. Enter a valid email in the "Email" field
3. Enter an incorrect password in the "Password" field
4. Click the "Sign In" button

**Expected Result:** A red error Alert appears with the message: "Invalid email or password. Please try again."
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-003: Login with empty fields
**Page:** Login (`/login`)
**Role(s):** All roles
**Prerequisites:** None
**Steps:**
1. Navigate to `http://localhost:3000/login`
2. Leave both "Email" and "Password" fields empty
3. Click the "Sign In" button

**Expected Result:** A red error Alert appears with the message: "Please enter both email and password." No API call is made.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-004: Password visibility toggle
**Page:** Login (`/login`)
**Role(s):** All roles
**Prerequisites:** None
**Steps:**
1. Navigate to `http://localhost:3000/login`
2. Enter text in the "Password" field
3. Verify the password is masked (type="password")
4. Click the eye icon (visibility toggle) at the end of the Password field
5. Verify the password text becomes visible (type="text")
6. Click the eye icon again

**Expected Result:** Password toggles between masked and visible. The icon alternates between visibility (eye open) and visibility-off (eye with line) icons.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-005: Forgot password flow
**Page:** Login (`/login`)
**Role(s):** All roles
**Prerequisites:** None
**Steps:**
1. Navigate to `http://localhost:3000/login`
2. Click the "Forgot Password?" link below the Sign In button
3. Verify the view changes to show subtitle "Reset your password" and instructional text: "Enter the email address associated with your account and we will send you a link to reset your password."
4. Enter a valid email in the "Email" field
5. Click the "Send Reset Link" button

**Expected Result:** A green success Alert appears with the message: "A password reset link has been sent to your email address. Please check your inbox." The "Back to Sign In" button remains visible.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-006: Forgot password with empty email
**Page:** Login (`/login`)
**Role(s):** All roles
**Prerequisites:** None
**Steps:**
1. Navigate to `http://localhost:3000/login`
2. Click the "Forgot Password?" link
3. Leave the "Email" field empty
4. Click the "Send Reset Link" button

**Expected Result:** A red error Alert appears with the message: "Please enter your email address."
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-007: Back to sign in from forgot password
**Page:** Login (`/login`)
**Role(s):** All roles
**Prerequisites:** None
**Steps:**
1. Navigate to `http://localhost:3000/login`
2. Click the "Forgot Password?" link
3. Click the "Back to Sign In" button (has an arrow-back icon)

**Expected Result:** The view returns to the login form with "Email" and "Password" fields. Any previous error or success messages are cleared.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-008: Logout via header menu
**Page:** Header (all pages)
**Role(s):** All roles
**Prerequisites:** Logged in as any user
**Steps:**
1. Log in to the application
2. Click the user avatar (circular icon with user initials) in the top-right of the Header
3. Verify a dropdown Menu appears showing the user's name and email (e.g., "James Mwangi (james@vycepay.com)") as a disabled item
4. Click the "Logout" menu item (has a logout icon)

**Expected Result:** User is logged out and redirected to `/login`.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-009: Session redirect to login
**Page:** Auth Guard
**Role(s):** All roles
**Prerequisites:** User is not authenticated (no valid session/token)
**Steps:**
1. Clear browser cookies/storage to ensure no active session
2. Navigate directly to `http://localhost:3000/dashboard`

**Expected Result:** User is redirected to `/login`. A loading spinner with message "Loading your session..." may briefly appear if a stale token exists.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-010: Post-login redirect to intended page
**Page:** Auth Guard / Login
**Role(s):** Admin, Operator
**Prerequisites:** User is not authenticated
**Steps:**
1. Clear session and navigate directly to `http://localhost:3000/admin/customers`
2. Verify redirect to `/login`
3. Log in with valid Admin or Operator credentials

**Expected Result:** After login, user is redirected to `/admin/customers` (the originally intended page), not the default `/dashboard`.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-011: Sidebar navigation items for Admin
**Page:** Sidebar (all pages)
**Role(s):** Admin
**Prerequisites:** Logged in as Admin
**Steps:**
1. Log in as an Admin user
2. Inspect the left sidebar navigation items

**Expected Result:** The sidebar displays exactly these items in order: "Dashboard", "Score Lookup", "Customer Management", "User Management", "Audit Logs", "Settings". The app name "VyceScore" (or white-label name) and a logo/icon appear at the top of the sidebar.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-012: Sidebar navigation items for Operator
**Page:** Sidebar (all pages)
**Role(s):** Operator
**Prerequisites:** Logged in as Operator
**Steps:**
1. Log in as an Operator user
2. Inspect the left sidebar navigation items

**Expected Result:** The sidebar displays: "Dashboard", "Score Lookup", "Customer Management", "Audit Logs", "Settings". "User Management" is NOT visible.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-013: Sidebar navigation items for Partner
**Page:** Sidebar (all pages)
**Role(s):** Partner
**Prerequisites:** Logged in as Partner
**Steps:**
1. Log in as a Partner user
2. Inspect the left sidebar navigation items

**Expected Result:** The sidebar displays: "Dashboard", "Partner Dashboard", "Score Lookup", "Usage & Billing", "API Keys", "Embed Widget". Admin items like "Customer Management", "User Management", "Audit Logs", and "Settings" are NOT visible.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-014: Sidebar navigation items for ReadOnly
**Page:** Sidebar (all pages)
**Role(s):** ReadOnly
**Prerequisites:** Logged in as ReadOnly
**Steps:**
1. Log in as a ReadOnly user
2. Inspect the left sidebar navigation items

**Expected Result:** The sidebar displays ONLY: "Dashboard". No other navigation items are visible.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-015: Sidebar active state highlighting
**Page:** Sidebar (all pages)
**Role(s):** Admin
**Prerequisites:** Logged in as Admin
**Steps:**
1. Click "Dashboard" in the sidebar
2. Observe the visual highlight on the "Dashboard" item
3. Click "Score Lookup" in the sidebar
4. Observe the highlight moves to "Score Lookup"

**Expected Result:** The currently active sidebar item has a visible background highlight (rgba(255,255,255,0.12)) and bolder white text (fontWeight 600). Other items have dimmer text (rgba(255,255,255,0.7)).
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-016: Header displays user role chip
**Page:** Header (all pages)
**Role(s):** All roles
**Prerequisites:** Logged in
**Steps:**
1. Log in as any user
2. Look at the top-right area of the Header bar

**Expected Result:** A small chip/badge displays the user's role (e.g., "Admin", "Operator", "Partner", "ReadOnly") in a primary-colored background with white text.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-017: Header user avatar and menu
**Page:** Header (all pages)
**Role(s):** All roles
**Prerequisites:** Logged in as a user with name "James Mwangi"
**Steps:**
1. Verify the avatar in the top-right shows the user's initials (e.g., "JM" for James Mwangi)
2. Click the avatar
3. Verify the dropdown menu shows: a disabled item with "James Mwangi (james@vycepay.com)" and a clickable "Logout" item

**Expected Result:** Avatar shows correct initials. Menu displays user info and Logout option.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-018: Dashboard KPI cards display
**Page:** Dashboard (`/dashboard`)
**Role(s):** All roles
**Prerequisites:** Logged in
**Steps:**
1. Navigate to `/dashboard`
2. Verify the page heading "Dashboard" is displayed
3. Verify five KPI cards are present with titles: "Total Scores Generated", "Active Partners", "Avg VyceScore", "Model AUC-ROC", "API Uptime"
4. Verify each card shows a numeric value, a subtitle with delta/description, and a colored icon

**Expected Result:** All five KPI cards display with default date range "Last 30 Days". Example values for 30d: Total Scores "12,847", Active Partners "34", Avg VyceScore "654", Model AUC-ROC "0.809", API Uptime "99.97%".
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-019: Dashboard date range selector
**Page:** Dashboard (`/dashboard`)
**Role(s):** All roles
**Prerequisites:** Logged in, on Dashboard page
**Steps:**
1. Locate the date range dropdown (select field) in the top-right of the Dashboard page
2. Verify the default selection is "Last 30 Days"
3. Click the dropdown and select "Last 7 Days"
4. Verify all KPI card values update (e.g., Total Scores changes to "2,147")
5. Select "Last 90 Days" and verify values update again (e.g., Total Scores shows "35,214")
6. Repeat for "Last 6 Months" and "Last Year"

**Expected Result:** All KPI values change to match the selected date range. Available options are: "Last 7 Days", "Last 30 Days", "Last 90 Days", "Last 6 Months", "Last Year".
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-020: Dashboard score trend chart
**Page:** Dashboard (`/dashboard`)
**Role(s):** All roles
**Prerequisites:** Logged in
**Steps:**
1. On the Dashboard, scroll to the charts area
2. Locate the chart titled "Average Score Trend (6 months)"
3. Verify it is a line chart with two lines: "VyceScore" (dark blue) and "NIQ Score" (teal)
4. Verify the Y-axis ranges from 300 to 900
5. Verify horizontal reference lines at 500 ("Medium") and 700 ("Low Risk")
6. Hover over data points to verify tooltips appear

**Expected Result:** Line chart renders with 6 data points, two colored lines, proper axis labels, and interactive tooltips.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-021: Dashboard score distribution panel
**Page:** Dashboard (`/dashboard`)
**Role(s):** All roles
**Prerequisites:** Logged in
**Steps:**
1. On the Dashboard, locate the "Score Distribution" card (right side)
2. Verify three bands are displayed:
   - "High Risk (300-499)" at 18% in red
   - "Medium Risk (500-700)" at 52% in orange
   - "Low Risk (701-900)" at 30% in green
3. Verify each band has a horizontal progress bar matching its percentage

**Expected Result:** Three score distribution bands display with correct labels, percentages, and color-coded progress bars.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-022: Dashboard query volume chart
**Page:** Dashboard (`/dashboard`)
**Role(s):** All roles
**Prerequisites:** Logged in
**Steps:**
1. On the Dashboard, scroll to the bottom chart
2. Locate the chart titled "Daily Query Volume"
3. Verify it is a bar chart with two series: "Lite Queries" (blue) and "Pro Queries" (red/pink)
4. Verify dates appear on the X-axis and query counts on the Y-axis
5. Hover over bars to verify tooltips with values

**Expected Result:** Stacked/grouped bar chart renders with 7 days of data and interactive tooltips.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-023: Score Lookup - Lite search
**Page:** Score Lookup (`/scores/lookup`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in as Admin or Operator; a valid national ID exists in the system
**Steps:**
1. Navigate to `/scores/lookup`
2. Verify the page heading "Score Lookup" is displayed
3. Verify a text field labeled "National ID" with placeholder "Enter national ID number"
4. Verify a toggle button group with "Lite" and "Pro" options (Lite selected by default)
5. Enter a valid national ID in the "National ID" field
6. Click the "Search" button (has a search icon)

**Expected Result:** Results card appears showing: a VyceScore gauge (semi-circle, 300-900 range), a NIQ Score gauge (0-100 range), and detail rows for "National ID", "Score Date", "Model Version", "Cached" (Yes/No), and "Tier" (LITE). The "View Full Details" button is NOT shown for Lite tier.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-024: Score Lookup - Pro search
**Page:** Score Lookup (`/scores/lookup`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in; valid national ID
**Steps:**
1. Navigate to `/scores/lookup`
2. Click the "Pro" toggle button to switch tier
3. Enter a valid national ID
4. Click the "Search" button

**Expected Result:** Results card appears with VyceScore gauge, NIQ Score gauge, score details (Tier shows "PRO"), and a "View Full Details" button.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-025: Score Lookup - tier toggle
**Page:** Score Lookup (`/scores/lookup`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in
**Steps:**
1. Navigate to `/scores/lookup`
2. Verify "Lite" is selected by default in the toggle group
3. Click "Pro" -- verify it becomes selected and "Lite" is deselected
4. Click "Lite" again -- verify it toggles back
5. Try clicking the already-selected toggle -- verify it stays selected (cannot deselect both)

**Expected Result:** Only one toggle can be active at a time. The selection cannot be cleared entirely.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-026: Score Lookup - empty ID validation
**Page:** Score Lookup (`/scores/lookup`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in
**Steps:**
1. Navigate to `/scores/lookup`
2. Leave the "National ID" field empty
3. Observe the "Search" button state

**Expected Result:** The "Search" button is disabled when the National ID field is empty or contains only whitespace.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-027: Score Lookup - error handling
**Page:** Score Lookup (`/scores/lookup`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in
**Steps:**
1. Navigate to `/scores/lookup`
2. Enter a national ID that does not exist in the system (e.g., "0000000000")
3. Click "Search"

**Expected Result:** A red error Alert appears with the message: "Failed to retrieve score. The ID may not exist or the service may be unavailable."
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-028: Score Lookup - View Full Details button
**Page:** Score Lookup (`/scores/lookup`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in; Pro search completed successfully
**Steps:**
1. Perform a successful Pro search (TC-024)
2. Click the "View Full Details" button below the score details

**Expected Result:** User is navigated to `/scores/detail/{nationalId}` where the Score Detail page loads.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-029: Score Detail - score gauges
**Page:** Score Detail (`/scores/detail/:nationalId`)
**Role(s):** Admin, Operator, Partner
**Prerequisites:** Navigate from a Pro score lookup result
**Steps:**
1. Navigate to `/scores/detail/{validNationalId}`
2. Verify the page heading "Score Detail: {nationalId}" is displayed
3. Verify the left column contains a VyceScore gauge (size 240) and a NIQ Score gauge (size 180, range 0-100)
4. Verify "Probability of Default" is shown with a percentage value
5. Verify "Confidence:" text shows a lower and upper interval

**Expected Result:** Both score gauges render correctly with appropriate colors. Probability of Default and confidence interval are displayed below the gauges.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-030: Score Detail - risk drivers
**Page:** Score Detail (`/scores/detail/:nationalId`)
**Role(s):** Admin, Operator, Partner
**Prerequisites:** Valid Pro score data exists
**Steps:**
1. On the Score Detail page, locate the "Top Risk Drivers" section in the right column
2. Verify risk driver cards are displayed, each showing:
   - A directional arrow icon (green up-arrow for positive, red down-arrow for negative)
   - A feature label (bold text)
   - A feature code chip (e.g., "CBLRI", "UTDI") aligned to the right
   - A description text
   - "SHAP impact: {value}" with sign indicator (e.g., "+0.045" or "-0.032")
3. Verify positive-impact cards have green border/background tint
4. Verify negative-impact cards have red border/background tint

**Expected Result:** Risk driver cards are color-coded by impact direction and display all fields: label, feature chip, description, and SHAP value.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-031: Score Detail - score history chart
**Page:** Score Detail (`/scores/detail/:nationalId`)
**Role(s):** Admin, Operator, Partner
**Prerequisites:** Score history data exists for the national ID
**Steps:**
1. On the Score Detail page, scroll to the bottom section
2. Verify a line chart titled "Score History" is displayed
3. Verify it shows VyceScore and NIQ Score lines over time

**Expected Result:** Score history chart renders with historical data points. If no history data is available, the chart area may be empty but should not cause an error.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-032: Score Detail - not found state
**Page:** Score Detail (`/scores/detail/:nationalId`)
**Role(s):** Admin, Operator, Partner
**Prerequisites:** None
**Steps:**
1. Navigate directly to `/scores/detail/INVALID_ID_999999` (a non-existent ID)
2. Wait for the API call to complete

**Expected Result:** The page displays "Score not found" heading and the text "No score data available for the requested national ID."
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-033: Customer Management - table display
**Page:** Customer Management (`/admin/customers`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in as Admin or Operator
**Steps:**
1. Navigate to `/admin/customers`
2. Verify the page heading "Customer Management" is displayed
3. Verify an "Add Customer" button (with + icon) is in the top-right
4. Verify a DataGrid table is displayed with columns: "Customer Name", "Email", "Tier", "Status", "Query Limit", "Used", "Actions"
5. Verify sample customers are shown (e.g., "Equity Bank Kenya", "KCB Group", "Safaricom M-Pesa")
6. Verify Tier column shows colored chips: LITE (primary), PRO (secondary), ENTERPRISE (info)
7. Verify Status column shows outlined chips: pending (warning), active (success), suspended (error)

**Expected Result:** Customer table renders with all columns, colored tier and status chips, and action buttons.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-034: Customer Management - status filter
**Page:** Customer Management (`/admin/customers`)
**Role(s):** Admin, Operator
**Prerequisites:** On Customer Management page
**Steps:**
1. Locate the "Status" dropdown filter above the table
2. Verify default is "All Statuses"
3. Select "Active" from the dropdown
4. Verify only customers with "active" status are shown
5. Select "Pending" -- verify only pending customers appear
6. Select "All Statuses" to reset

**Expected Result:** Table filters correctly by status. Options are: "All Statuses", "Pending", "Active", "Suspended", "Deactivated".
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-035: Customer Management - tier filter
**Page:** Customer Management (`/admin/customers`)
**Role(s):** Admin, Operator
**Prerequisites:** On Customer Management page
**Steps:**
1. Locate the "Tier" dropdown filter
2. Verify default is "All Tiers"
3. Select "Pro" from the dropdown
4. Verify only customers with "pro" tier are shown
5. Select "All Tiers" to reset

**Expected Result:** Table filters by tier. Options are: "All Tiers", "Lite", "Pro", "Enterprise".
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-036: Customer Management - add customer
**Page:** Customer Management (`/admin/customers`)
**Role(s):** Admin, Operator
**Prerequisites:** On Customer Management page
**Steps:**
1. Click the "Add Customer" button
2. Verify a dialog titled "Add New Customer" opens
3. Verify the dialog contains fields: "Customer Name" (required), "Email" (email type, required), "Tier" (dropdown with Lite/Pro/Enterprise), "Query Limit" (number input, min 1000, step 1000)
4. Leave "Customer Name" and "Email" empty -- verify "Create Customer" button is disabled
5. Fill in: Customer Name = "Test Bank", Email = "test@bank.co.ke", Tier = "Pro", Query Limit = 50000
6. Click "Create Customer"

**Expected Result:** Dialog closes. A new "API Key Display" dialog appears titled "Customer Created Successfully" with a warning Alert: "This API key will only be shown once. Please copy it now and store it securely." The generated API key is displayed in monospace font with a copy button. The new customer appears in the table with status "pending".
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-037: Customer Management - API key display after creation
**Page:** Customer Management (`/admin/customers`)
**Role(s):** Admin, Operator
**Prerequisites:** Just created a customer (TC-036)
**Steps:**
1. In the API Key Display dialog, verify the API key format starts with "vs_{tier}_" followed by a 32-character hex string
2. Click the copy icon button next to the API key
3. Verify a snackbar notification appears at the bottom-right: "API key copied to clipboard."
4. Click the "Done" button

**Expected Result:** API key is copied to clipboard. Snackbar confirmation appears. Dialog closes.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-038: Customer Management - activate customer
**Page:** Customer Management (`/admin/customers`)
**Role(s):** Admin, Operator
**Prerequisites:** A customer with status "pending" exists in the table
**Steps:**
1. In the customer table, locate a row with status "pending" (e.g., "Faulu Microfinance")
2. In the Actions column, verify a green checkmark icon button is visible (tooltip: "Activate")
3. Click the Activate button

**Expected Result:** The customer's status changes to "active" (green chip). A snackbar notification appears: "{Customer Name} has been activated." The Activate button disappears from that row.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-039: Customer Management - configure license
**Page:** Customer Management (`/admin/customers`)
**Role(s):** Admin, Operator
**Prerequisites:** On Customer Management page
**Steps:**
1. In the customer table, click the edit (pencil) icon button in the Actions column for any customer (tooltip: "Configure License")
2. Verify a dialog titled "Configure License - {Customer Name}" opens
3. Verify the dialog contains "Tier" (dropdown pre-filled with current tier) and "Query Limit" (number input pre-filled with current limit)
4. Change the Tier to "Enterprise" and Query Limit to 200000
5. Click "Update License"

**Expected Result:** Dialog closes. A snackbar notification appears: "License updated successfully." The customer's Tier and Query Limit values update in the table.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-040: User Management - table display
**Page:** User Management (`/admin/users`)
**Role(s):** Admin
**Prerequisites:** Logged in as Admin
**Steps:**
1. Navigate to `/admin/users`
2. Verify the page heading "User Management" is displayed
3. Verify an "Add User" button (with + icon) is in the top-right
4. Verify a DataGrid table with columns: "Name", "Email", "Role", "Organization", "Status", "Last Login", "Actions"
5. Verify Role column shows colored chips: Admin (primary), Operator (secondary), Partner (info), ReadOnly (default)
6. Verify Status column shows outlined chips: active (success), inactive (default)

**Expected Result:** User table renders with all columns and colored role/status chips.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-041: User Management - add user
**Page:** User Management (`/admin/users`)
**Role(s):** Admin
**Prerequisites:** On User Management page
**Steps:**
1. Click the "Add User" button
2. Verify a dialog titled "Add New User" opens
3. Verify fields: "Full Name" (required), "Email" (email type, required), "Role" (dropdown with Admin/Operator/Partner/Read Only)
4. Verify "Create User" button is disabled when "Full Name" or "Email" is empty
5. Fill in: Full Name = "Test User", Email = "test@example.com", Role = "Operator"
6. Click "Create User"

**Expected Result:** Dialog closes. A snackbar notification appears: "User Test User created successfully." The new user appears in the table with status "active", organization "VycePay", and Last Login "-".
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-042: User Management - edit role
**Page:** User Management (`/admin/users`)
**Role(s):** Admin
**Prerequisites:** Users exist in the table
**Steps:**
1. Click the edit (pencil) icon button for any user (tooltip: "Edit Role")
2. Verify a dialog titled "Edit Role - {User Name}" opens
3. Verify a "Role" dropdown pre-filled with the user's current role
4. Change the role to a different value (e.g., from "Partner" to "ReadOnly")
5. Click "Update Role"

**Expected Result:** Dialog closes. Snackbar: "Role updated for {User Name}." The user's role chip updates in the table.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-043: User Management - deactivate user
**Page:** User Management (`/admin/users`)
**Role(s):** Admin
**Prerequisites:** An active user exists in the table
**Steps:**
1. Locate an active user in the table
2. Click the red block icon button in the Actions column (tooltip: "Deactivate")
3. Verify a confirmation dialog titled "Deactivate User" opens with text: "Are you sure you want to deactivate {User Name}? They will no longer be able to access the system."
4. Click the "Cancel" button -- verify dialog closes, no changes
5. Re-open the dialog and click the red "Deactivate" button

**Expected Result:** Dialog closes. Snackbar: "{User Name} has been deactivated." The user's status changes to "inactive". The Deactivate button disappears from that row's Actions.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-044: Audit Logs - table display
**Page:** Audit Logs (`/admin/audit-logs`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in as Admin or Operator
**Steps:**
1. Navigate to `/admin/audit-logs`
2. Verify the page heading "Audit Logs" is displayed
3. Verify an "Export CSV" button (with download icon) is in the top-right
4. Verify a DataGrid table with columns: "Timestamp", "User", "Action", "Method", "Status", "Time (ms)", "IP Address"
5. Verify Method column shows colored chips: GET (primary/blue), POST (success/green), PUT (warning/orange), DELETE (error/red)
6. Verify Status column shows outlined chips color-coded: 2xx (success), 3xx (info), 4xx (warning), 5xx (error)
7. Verify Action column displays in monospace font

**Expected Result:** Audit log table displays with all columns, color-coded method and status chips, and timestamp formatted in en-KE locale.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-045: Audit Logs - search filter
**Page:** Audit Logs (`/admin/audit-logs`)
**Role(s):** Admin, Operator
**Prerequisites:** On Audit Logs page
**Steps:**
1. Locate the "Search" text field with placeholder "Search logs..."
2. Type "login" in the search field
3. Verify the table filters to show only rows where user name, action, endpoint, or details contain "login"
4. Clear the search field
5. Verify all rows reappear

**Expected Result:** Table dynamically filters as text is entered. Search is case-insensitive and matches across multiple fields.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-046: Audit Logs - action filter
**Page:** Audit Logs (`/admin/audit-logs`)
**Role(s):** Admin, Operator
**Prerequisites:** On Audit Logs page
**Steps:**
1. Locate the "Action" dropdown filter
2. Verify default is "All Actions"
3. Select "auth.login" from the dropdown
4. Verify only rows with action "auth.login" are displayed
5. Select "All Actions" to reset

**Expected Result:** Table filters by the selected action. The dropdown is dynamically populated with all unique actions from the log data.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-047: Audit Logs - user filter
**Page:** Audit Logs (`/admin/audit-logs`)
**Role(s):** Admin, Operator
**Prerequisites:** On Audit Logs page
**Steps:**
1. Locate the "User" dropdown filter
2. Verify default is "All Users"
3. Select a specific user (e.g., "James Mwangi")
4. Verify only rows for that user are shown

**Expected Result:** Table filters by the selected user. "Unknown" users are excluded from the dropdown options.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-048: Audit Logs - row click detail dialog
**Page:** Audit Logs (`/admin/audit-logs`)
**Role(s):** Admin, Operator
**Prerequisites:** On Audit Logs page
**Steps:**
1. Click on any row in the audit logs table (rows should show pointer cursor on hover)
2. Verify a dialog titled "Audit Log Detail" opens
3. Verify the dialog shows a detail table with fields: Timestamp, User (name + ID), Action, Method, Endpoint, Status Code, Response Time, IP Address, User Agent
4. If the selected log has a request body, verify "Request Body" row appears in monospace font
5. If the selected log has details, verify "Details" row appears
6. Click the "Close" button

**Expected Result:** Detail dialog shows all log fields in a structured table format. Dialog closes cleanly.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-049: Audit Logs - export CSV
**Page:** Audit Logs (`/admin/audit-logs`)
**Role(s):** Admin, Operator
**Prerequisites:** On Audit Logs page with data
**Steps:**
1. Optionally apply filters to narrow down results
2. Click the "Export CSV" button in the top-right
3. Verify a CSV file downloads with filename format `audit_logs_YYYY-MM-DD.csv`
4. Open the downloaded CSV and verify headers: Timestamp, User, Action, Method, Endpoint, Status, IP Address, Response Time (ms), Details
5. Verify the CSV contains only the currently filtered/visible logs

**Expected Result:** CSV file downloads with correct headers and filtered data. Values with commas or quotes are properly escaped.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-050: Settings - profile settings
**Page:** Settings (`/settings`)
**Role(s):** Admin, Operator
**Prerequisites:** Logged in as Admin or Operator
**Steps:**
1. Navigate to `/settings`
2. Verify the page heading "Settings" is displayed
3. Locate the "Profile Settings" card
4. Verify the "Full Name" field is editable and pre-filled with the current user's name
5. Verify the "Email" field is disabled with helper text "Contact an administrator to change your email"
6. Verify "Role:" label with a chip showing the current role
7. Verify "Organization:" label with the organization name
8. Verify the "Save Profile" button (with save icon) is disabled when name hasn't changed
9. Modify the "Full Name" field
10. Verify the "Save Profile" button becomes enabled
11. Click "Save Profile"

**Expected Result:** Snackbar notification appears: "Profile settings saved successfully."
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-051: Settings - API configuration display
**Page:** Settings (`/settings`)
**Role(s):** Admin, Operator
**Prerequisites:** On Settings page
**Steps:**
1. Locate the "API Configuration" card
2. Verify "API Base URL" field is disabled and shows the configured URL (e.g., "https://api.vycescore.com/v1") with helper text "Configured via environment variables"
3. Verify a switch labeled "Show API key in dashboard widgets"
4. Verify an info Alert with text mentioning "API keys can be managed from the Partner API Keys page"

**Expected Result:** API configuration section displays read-only URL, toggle switch, and informational alert.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-052: Settings - notification preferences
**Page:** Settings (`/settings`)
**Role(s):** Admin, Operator
**Prerequisites:** On Settings page
**Steps:**
1. Locate the "Notification Preferences" card
2. Verify three toggle switches:
   - "Score threshold alerts" (with description about email notifications for score thresholds)
   - "Usage limit warnings" (with description about 80% and 95% quota notifications)
   - "System maintenance notifications" (with description about scheduled maintenance windows)
3. Toggle each switch on and off
4. Click the "Save Preferences" button

**Expected Result:** Snackbar: "Notification preferences saved successfully." Switches retain their toggled state.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-053: Settings - system settings (Admin only)
**Page:** Settings (`/settings`)
**Role(s):** Admin
**Prerequisites:** Logged in as Admin
**Steps:**
1. On the Settings page, locate the "System Settings" card
2. Verify fields:
   - "Cache TTL (hours)" -- number input with helper text "How long scored results are cached in Redis (1-168 hours)", min 1, max 168
   - "Rate Limit (requests/minute)" -- number input with helper text "Default API rate limit per customer per minute", min 10, max 10000
   - "Maintenance mode" switch (warning color)
3. Toggle "Maintenance mode" ON
4. Verify a warning Alert appears: "Enabling maintenance mode will return 503 responses to all API consumers. The admin portal will remain accessible."
5. Toggle "Maintenance mode" OFF -- verify the warning disappears
6. Click "Save System Settings"

**Expected Result:** Snackbar: "System settings saved successfully." Maintenance mode warning shows/hides based on toggle state.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-054: Settings - system settings hidden for Operator
**Page:** Settings (`/settings`)
**Role(s):** Operator
**Prerequisites:** Logged in as Operator
**Steps:**
1. Navigate to `/settings`
2. Verify the "Profile Settings", "API Configuration", and "Notification Preferences" cards are visible
3. Verify the "System Settings" card is NOT present on the page

**Expected Result:** Only Admin users see the System Settings card. Operators see three cards, not four.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-055: Partner Dashboard - KPI cards
**Page:** Partner Dashboard (`/partner/dashboard`)
**Role(s):** Partner
**Prerequisites:** Logged in as Partner
**Steps:**
1. Navigate to `/partner/dashboard`
2. Verify the page heading "Partner Dashboard" is displayed
3. Verify a tier plan chip is shown in the top-right (e.g., "Pro Plan")
4. Verify four KPI cards: "Total Queries (This Month)", "Lite Queries" (subtitle: "Score pre-screening"), "Pro Queries" (subtitle: "Full underwriting"), "Queries Remaining" (subtitle: "of {limit} monthly limit")

**Expected Result:** All four KPI cards display with correct titles, values, and subtitles. Loading spinner with "Loading partner dashboard..." displays while data loads.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-056: Partner Dashboard - quota usage bar
**Page:** Partner Dashboard (`/partner/dashboard`)
**Role(s):** Partner
**Prerequisites:** On Partner Dashboard
**Steps:**
1. Below the KPI cards, locate the "Monthly Quota Usage" card
2. Verify it shows a percentage value and a progress bar
3. Verify the progress bar color is:
   - Green if usage <= 75%
   - Orange/warning if usage > 75% and <= 90%
   - Red if usage > 90%
4. Verify "{used} used" text on the left and "{limit} limit" text on the right below the bar

**Expected Result:** Quota usage bar renders with dynamic color coding based on percentage.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-057: Partner Dashboard - daily query volume chart
**Page:** Partner Dashboard (`/partner/dashboard`)
**Role(s):** Partner
**Prerequisites:** On Partner Dashboard
**Steps:**
1. Locate the chart titled "Daily Query Volume (Current Month)"
2. Verify it is a bar chart with "Lite Queries" and "Pro Queries" series

**Expected Result:** Bar chart renders with daily data for the current month.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-058: Partner Dashboard - monthly usage trend
**Page:** Partner Dashboard (`/partner/dashboard`)
**Role(s):** Partner
**Prerequisites:** On Partner Dashboard; usage trend data available
**Steps:**
1. Locate the "Monthly Usage Trend" section
2. Verify each month shows: period label (e.g., "2026-02"), a progress bar representing usage relative to the query limit, and a total queries count

**Expected Result:** Monthly trend section shows historical usage bars for up to 6 months.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-059: Partner Score Lookup - Lite search
**Page:** Partner Score Lookup (`/partner/scores`)
**Role(s):** Partner
**Prerequisites:** Logged in as Partner
**Steps:**
1. Navigate to `/partner/scores`
2. Verify the page heading "Score Lookup" is displayed
3. Verify instructional text: "Enter a National ID to retrieve the VyceScore. Choose Lite for rapid pre-screening or Pro for full underwriting with risk drivers."
4. Enter a valid national ID in the "National ID" field (placeholder: "Enter national ID number")
5. Ensure "Lite" is selected in the toggle group
6. Click "Search"

**Expected Result:** Results card shows VyceScore gauge, NIQ Score gauge, and detail rows: National ID, Score Date, Model Version, Cached, Tier (LITE).
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-060: Partner Score Lookup - Pro search with risk drivers
**Page:** Partner Score Lookup (`/partner/scores`)
**Role(s):** Partner
**Prerequisites:** Logged in as Partner; valid national ID with Pro data
**Steps:**
1. Navigate to `/partner/scores`
2. Select "Pro" in the toggle group
3. Enter a valid national ID
4. Click "Search"
5. Verify the results include a "Top Risk Drivers" section below the score details

**Expected Result:** Results card shows score gauges, detail rows (Tier: PRO), and a list of risk drivers. Each risk driver shows: a numbered index (#1, #2, etc.), feature name, and impact with color coding (green for positive, red for negative).
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-061: Partner Usage - month selector
**Page:** Partner Usage (`/partner/usage`)
**Role(s):** Partner
**Prerequisites:** Logged in as Partner
**Steps:**
1. Navigate to `/partner/usage`
2. Verify the page heading "Usage Reports" is displayed
3. Locate the month selector dropdown in the top-right
4. Verify the current month is selected by default
5. Verify up to 12 recent months are available in the dropdown
6. Select a previous month

**Expected Result:** Report data updates to reflect the selected month. Loading spinner with "Loading report..." may briefly appear.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-062: Partner Usage - summary cards
**Page:** Partner Usage (`/partner/usage`)
**Role(s):** Partner
**Prerequisites:** On Partner Usage page with a month selected
**Steps:**
1. Verify four summary cards are displayed: "Total Queries", "Included in Plan", "Overage Queries", "Total Amount"
2. Verify "Overage Queries" value is shown in red if greater than 0
3. Verify "Total Amount" shows currency code (e.g., "KES") and amount, with a status chip (e.g., "PAID" in green, "OVERDUE" in red)

**Expected Result:** All four summary cards display with correct values and conditional styling.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-063: Partner Usage - billing breakdown table
**Page:** Partner Usage (`/partner/usage`)
**Role(s):** Partner
**Prerequisites:** On Partner Usage page with data
**Steps:**
1. Locate the "Billing Breakdown ({month})" card
2. Verify the table shows line items:
   - "Base Fee ({tier})" with amount
   - "Lite Queries ({count} x KES 3)" with amount
   - "Pro Queries ({count} x KES 15)" with amount
   - "Overage ({count} queries)" in red text (only if overage > 0)
   - "Total" row with bold text and top border

**Expected Result:** Billing breakdown table shows all cost line items with correct amounts and formatting.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-064: Partner Usage - daily breakdown table
**Page:** Partner Usage (`/partner/usage`)
**Role(s):** Partner
**Prerequisites:** On Partner Usage page with data
**Steps:**
1. Scroll to the "Daily Breakdown" section
2. Verify a table with column headers: "Date", "Lite", "Pro", "Batch", "Total"
3. Verify each row shows daily query counts with right-aligned numbers

**Expected Result:** Daily breakdown table displays with all columns and formatted numbers.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-065: Partner Usage - download CSV
**Page:** Partner Usage (`/partner/usage`)
**Role(s):** Partner
**Prerequisites:** On Partner Usage page with daily breakdown data
**Steps:**
1. Locate the "Download CSV" button (with download icon) in the "Daily Breakdown" section header
2. Click "Download CSV"
3. Verify a CSV file downloads with filename format `usage-report-YYYY-MM.csv`
4. Open the CSV and verify headers: Date, Lite Queries, Pro Queries, Batch Queries, Total Queries

**Expected Result:** CSV file downloads with correct filename and data matching the daily breakdown table.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-066: Partner API Keys - key info display
**Page:** Partner API Keys (`/partner/api-keys`)
**Role(s):** Partner
**Prerequisites:** Logged in as Partner
**Steps:**
1. Navigate to `/partner/api-keys`
2. Verify the page heading "API Key Management" is displayed
3. Verify a "Current API Key" card with a key icon, title, and description: "Used for authenticating API requests via the X-API-Key header."
4. Verify "Key Prefix:" label with a monospace chip showing the key prefix
5. Verify "Created:" and "Last Used:" dates if available

**Expected Result:** API key info card displays with key prefix, creation date, and last used date.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-067: Partner API Keys - rotate key
**Page:** Partner API Keys (`/partner/api-keys`)
**Role(s):** Partner
**Prerequisites:** On API Keys page
**Steps:**
1. Locate the "Key Actions" card
2. Click the "Rotate Key" button (primary blue, with refresh icon)
3. Verify a confirmation dialog titled "Rotate API Key?" opens with warning text about invalidating the current key
4. Click "Cancel" -- verify dialog closes, no action taken
5. Click "Rotate Key" again, then click "Rotate Key" in the confirmation dialog

**Expected Result:** A success Alert appears: "API key rotated successfully. Copy the new key below -- it will not be shown again." A new card with warning border appears showing the new API key in a read-only text field with a copy button.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-068: Partner API Keys - revoke key
**Page:** Partner API Keys (`/partner/api-keys`)
**Role(s):** Partner
**Prerequisites:** On API Keys page
**Steps:**
1. Click the "Revoke Key" button (outlined red, with delete icon)
2. Verify a confirmation dialog titled "Revoke API Key?" opens with text about permanently revoking and disabling API access
3. Click "Cancel" -- verify dialog closes
4. Click "Revoke Key" again, then click the red "Revoke Key" button in the dialog

**Expected Result:** Success Alert: "API key has been revoked. Contact your administrator to get a new key."
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-069: Partner API Keys - copy new key
**Page:** Partner API Keys (`/partner/api-keys`)
**Role(s):** Partner
**Prerequisites:** Key just rotated (TC-067 completed)
**Steps:**
1. In the new key display card, click the copy icon button
2. Verify the icon changes to a green checkmark (CheckIcon) for approximately 2 seconds
3. Verify the tooltip changes from "Copy to clipboard" to "Copied!"
4. Paste from clipboard to verify the key was actually copied

**Expected Result:** Key is copied to clipboard. Visual confirmation via icon change and tooltip.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-070: Partner Embed Config - allowed origins
**Page:** Partner Embed Config (`/partner/embed-config`)
**Role(s):** Partner
**Prerequisites:** Logged in as Partner
**Steps:**
1. Navigate to `/partner/embed-config`
2. Verify the page heading "Embed Widget" and sub-heading "White-Label Embed Configuration"
3. Locate the "Allowed Origins" card with description: "Domains that are allowed to embed the score lookup widget."
4. Type "https://example.com" in the text field (placeholder: "https://example.com")
5. Click the "Add" button
6. Verify a chip "https://example.com" appears with a delete icon
7. Add another origin "https://test.com"
8. Click the delete icon on the first chip to remove it
9. Verify only "https://test.com" remains
10. When no origins are configured, verify text: "No origins configured (all origins allowed)"

**Expected Result:** Origins can be added via text input + "Add" button, displayed as removable chips. Origins can also be added by pressing Enter.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-071: Partner Embed Config - theme settings
**Page:** Partner Embed Config (`/partner/embed-config`)
**Role(s):** Partner
**Prerequisites:** On Embed Config page
**Steps:**
1. Locate the "Theme Settings" card
2. Verify fields: "App Name" (default "VyceScore"), "Logo URL" (placeholder: "https://example.com/logo.png"), "Primary Color" (color picker, default #1976d2), "Secondary Color" (color picker, default #dc004e)
3. Change "App Name" to "MyBankScore"
4. Change "Primary Color" by clicking the color picker
5. Verify the Widget Preview on the right side updates dynamically

**Expected Result:** Theme settings fields are editable. The widget preview reflects changes in real-time.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-072: Partner Embed Config - widget preview
**Page:** Partner Embed Config (`/partner/embed-config`)
**Role(s):** Partner
**Prerequisites:** On Embed Config page
**Steps:**
1. Locate the "Widget Preview" card on the right side
2. Verify the embedded widget shows: the app name (e.g., "VyceScore - Score Lookup"), a "National ID" text field, and a "Look Up Score" button
3. Locate the "Widget Settings" card and toggle "Show NIQ Score in widget" OFF
4. Verify the preview widget will not show NIQ Score section when a lookup is performed

**Expected Result:** Widget preview renders and reflects configuration changes dynamically.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-073: Partner Embed Config - embed code copy
**Page:** Partner Embed Config (`/partner/embed-config`)
**Role(s):** Partner
**Prerequisites:** On Embed Config page
**Steps:**
1. Locate the "Embed Code" card below the widget preview
2. Verify it contains an iframe code snippet in a `<pre>` block with monospace styling
3. Verify the snippet format includes `src=".../embed/widget?token=..."`, width, height, frameborder, and allow attributes
4. Verify a "postMessage API" section is shown below with JavaScript code examples for VYCE_LOOKUP and VYCE_SCORE_RESULT
5. Click the copy icon button next to the "Embed Code" heading
6. Verify the icon changes to a green checkmark for ~2 seconds

**Expected Result:** Embed snippet is copyable. postMessage API documentation is displayed. Copy confirmation shows via icon change.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-074: Partner Embed Config - save configuration
**Page:** Partner Embed Config (`/partner/embed-config`)
**Role(s):** Partner
**Prerequisites:** On Embed Config page with changes made
**Steps:**
1. Make changes to origins, theme, or widget settings
2. Click the "Save Configuration" button at the bottom-left
3. Verify the button text changes to "Saving..." while loading

**Expected Result:** A success Alert appears: "Embed configuration saved successfully." On failure, an error Alert appears: "Failed to save embed configuration."
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-075: 404 Not Found page
**Page:** Not Found
**Role(s):** All roles (or unauthenticated)
**Prerequisites:** None
**Steps:**
1. Navigate to `http://localhost:3000/nonexistent-page`
2. Verify the page displays:
   - Large "404" text
   - "Page Not Found" heading
   - "The page you're looking for doesn't exist or has been moved." description
   - A "Go to Dashboard" button

3. Click "Go to Dashboard"

**Expected Result:** User is navigated to `/dashboard` (or redirected to `/login` if not authenticated).
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-076: 403 Access Denied inline
**Page:** Role Guard (inline within AppShell)
**Role(s):** Any role accessing unauthorized page
**Prerequisites:** Logged in
**Steps:**
1. Log in as a ReadOnly user
2. Navigate directly to `/admin/customers` via the browser address bar
3. Verify the page displays within the normal layout (sidebar + header still visible):
   - A large block icon in red
   - "403 - Access Denied" heading
   - "You do not have sufficient permissions to access this page. Please contact your administrator if you believe this is an error."
   - A "Go to Dashboard" button

**Expected Result:** The RoleGuard renders the Forbidden component inline (not a full-page redirect). Sidebar and header remain visible.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-077: Role guard - Admin accessing Partner pages
**Page:** Various partner routes
**Role(s):** Admin
**Prerequisites:** Logged in as Admin
**Steps:**
1. Navigate to `/partner/dashboard`
2. Verify the 403 Access Denied inline page is shown
3. Navigate to `/partner/api-keys`
4. Verify 403 again

**Expected Result:** Admin users cannot access Partner-only routes (`/partner/*`). The RoleGuard blocks access with the 403 Forbidden component.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-078: Role guard - Partner accessing Admin pages
**Page:** Various admin routes
**Role(s):** Partner
**Prerequisites:** Logged in as Partner
**Steps:**
1. Navigate to `/admin/customers`
2. Verify the 403 Access Denied inline page is shown
3. Navigate to `/admin/users`
4. Verify 403 again
5. Navigate to `/admin/audit-logs`
6. Verify 403 again
7. Navigate to `/settings`
8. Verify 403 again

**Expected Result:** Partner users cannot access Admin/Operator routes. All four admin routes show 403.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-079: Role guard - ReadOnly access restrictions
**Page:** Multiple pages
**Role(s):** ReadOnly
**Prerequisites:** Logged in as ReadOnly
**Steps:**
1. Verify `/dashboard` is accessible (no 403)
2. Navigate to `/scores/lookup` -- verify 403
3. Navigate to `/admin/customers` -- verify 403
4. Navigate to `/admin/users` -- verify 403
5. Navigate to `/admin/audit-logs` -- verify 403
6. Navigate to `/settings` -- verify 403
7. Navigate to `/partner/dashboard` -- verify 403

**Expected Result:** ReadOnly users can ONLY access `/dashboard`. All other protected routes show 403.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-080: Error boundary - crash recovery
**Page:** Any page (wraps entire app)
**Role(s):** All roles
**Prerequisites:** Application running
**Steps:**
1. Simulate a JavaScript rendering error (this may require a developer to temporarily introduce a crash in a component, or use browser DevTools to trigger an error)
2. Verify the ErrorBoundary catches the error and displays:
   - An error icon (red circle with exclamation)
   - "Something went wrong" heading
   - An error message or "An unexpected error occurred"
   - A "Try Again" button
3. Click "Try Again"

**Expected Result:** The ErrorBoundary resets its state and attempts to re-render the child components. The error screen is replaced with the normal UI (assuming the error was transient).
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-081: DataTable pagination
**Page:** Any page with DataTable (Customers, Users, Audit Logs)
**Role(s):** Admin
**Prerequisites:** Logged in as Admin; enough rows to trigger pagination
**Steps:**
1. Navigate to `/admin/audit-logs` (has 10 sample entries)
2. Verify the table shows pagination controls at the bottom
3. Verify page size options are available: 5, 10, 25, 50
4. Change page size to 5
5. Verify only 5 rows are visible
6. Navigate to page 2
7. Verify the remaining rows are displayed

**Expected Result:** Pagination controls work correctly. Row count and page info update appropriately.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-082: White label - app name in sidebar and login
**Page:** Sidebar, Login
**Role(s):** All roles
**Prerequisites:** Application running with default or custom white-label configuration
**Steps:**
1. Navigate to `/login`
2. Verify the app name displayed matches the WhiteLabel config (default: "VyceScore")
3. Verify either a logo image (if `logoUrl` is configured) or a colored square with the first two letters of the app name is shown
4. Log in and verify the sidebar header shows the same app name and logo

**Expected Result:** App name and logo are consistent between the login page and sidebar. Both use the WhiteLabelContext configuration.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-083: White label - theme persistence
**Page:** All pages
**Role(s):** All roles
**Prerequisites:** Application running
**Steps:**
1. Verify the WhiteLabelProvider reads from localStorage key "whiteLabelConfig" on initialization
2. If a custom config is stored in localStorage (e.g., `{"appName":"CustomApp","primaryColor":"#ff0000"}`), verify the theme reflects those values
3. Clear localStorage and reload -- verify defaults are restored (appName: "VyceScore", primaryColor: "#1976d2")

**Expected Result:** White-label configuration persists across page reloads via localStorage.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-084: Responsive - sidebar and layout
**Page:** All pages
**Role(s):** All roles
**Prerequisites:** Logged in
**Steps:**
1. Open browser DevTools and switch to a mobile viewport (e.g., 375x812)
2. Verify the sidebar is a permanent drawer (260px width) -- on very small screens it may overlap the content
3. Verify the main content area adjusts its width to `calc(100% - 260px)`
4. Resize to a tablet viewport (768px) -- verify layout still renders without horizontal scroll

**Expected Result:** The layout uses a fixed sidebar with the main content area filling the remaining width. Note: The sidebar is a permanent drawer and does not collapse on mobile (this may be a known limitation).
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-085: Responsive - score lookup results
**Page:** Score Lookup
**Role(s):** Admin, Operator
**Prerequisites:** A successful score lookup performed
**Steps:**
1. With score results displayed, resize the browser to a narrow width (< 900px)
2. Verify the score gauges and detail section switch from a horizontal row layout to a vertical stack layout (flex-direction changes from "row" to "column" at the "md" breakpoint)

**Expected Result:** Score result card layout is responsive -- gauges stack vertically on smaller screens.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-086: Loading states display
**Page:** Multiple pages
**Role(s):** All roles
**Prerequisites:** Logged in
**Steps:**
1. Navigate to `/partner/dashboard` as a Partner user
2. Verify a LoadingSpinner appears with message "Loading partner dashboard..." while data loads
3. Navigate to `/partner/api-keys`
4. Verify "Loading API key info..." spinner appears
5. Navigate to `/partner/usage`
6. Verify "Loading usage data..." spinner appears
7. During Auth Guard session loading, verify "Loading your session..." spinner appears

**Expected Result:** Each loading state shows a centered CircularProgress spinner with an appropriate contextual message.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-087: Score gauge range validation
**Page:** Score Lookup, Score Detail
**Role(s):** Admin, Operator, Partner
**Prerequisites:** Score data available
**Steps:**
1. Perform a score lookup
2. Verify the VyceScore gauge displays with range 300 (left) to 900 (right)
3. Verify the NIQ Score gauge displays with range 0 (left) to 100 (right)
4. Verify score values are clamped within their respective ranges (a score below 300 shows 300, above 900 shows 900)
5. Verify the gauge color changes based on score value (red for low, orange for medium, green for high)
6. Verify a text label below the score (e.g., risk category for VyceScore, "X / 100" format for NIQ Score)

**Expected Result:** Gauges render as semi-circle pie charts with correct ranges, colors, and labels.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-088: Security - unauthenticated API redirect
**Page:** Auth Guard
**Role(s):** N/A (unauthenticated)
**Prerequisites:** No active session
**Steps:**
1. Clear all browser storage (localStorage, sessionStorage, cookies)
2. Navigate to any protected route (e.g., `/dashboard`)

**Expected Result:** AuthGuard detects `isAuthenticated === false` and redirects to `/login` with the intended URL preserved in location state for post-login redirect.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

### TC-089: Security - direct URL access without auth
**Page:** Multiple protected routes
**Role(s):** N/A (unauthenticated)
**Prerequisites:** No active session
**Steps:**
1. Directly navigate to each of these URLs without being logged in:
   - `/dashboard`
   - `/scores/lookup`
   - `/admin/customers`
   - `/admin/users`
   - `/admin/audit-logs`
   - `/settings`
   - `/partner/dashboard`
   - `/partner/api-keys`
2. Verify each redirects to `/login`

**Expected Result:** All protected routes redirect unauthenticated users to `/login`. No protected content is visible.
**Status:** [ ] Pass / [ ] Fail
**Notes:** ___

---

## Appendix: Test Data Reference

This appendix documents every piece of seeded data available in the UAT environment.
Testers should reference these tables when executing test cases to know the expected inputs and outputs.

---

### A. Seeded User Accounts

These accounts are created by `backend/scripts/seed_users.py`. All accounts are **Active** with `must_change_password = false`.

| Name | Email | Password | Role | Organization | Status |
|------|-------|----------|------|--------------|--------|
| James Mwangi | admin@vycepay.com | Admin@2026 | Admin | VycePay | Active |
| Odhiambo Ochieng | operator@vycepay.com | Operator@2026 | Operator | VycePay | Active |
| Wanjiku Kamau | partner@equitybank.co.ke | Partner@2026 | Partner | Equity Bank | Active |
| Amina Hassan | readonly@kcbgroup.com | ReadOnly@2026 | ReadOnly | KCB Group | Active |

**Usage notes:**
- Use **Admin** (James Mwangi) for TC-011, TC-018 through TC-033 (Dashboard, Customers, Users, Audit Logs, Score Lookup, Settings).
- Use **Operator** (Odhiambo Ochieng) for TC-012 and operator-scoped tests.
- Use **Partner** (Wanjiku Kamau) for TC-013 and all Partner Dashboard / Partner Score Lookup / Partner Usage / Partner API Keys tests (TC-040 through TC-060).
- Use **ReadOnly** (Amina Hassan) for TC-014, TC-034 through TC-039, and read-only access verification.

---

### B. Seeded Customer Accounts

Customers are created by `backend/scripts/seed_test_data.py`. The frontend Customers Page also includes mock entries for Faulu Microfinance and NCBA Bank.

| Name | Email | Tier | Status | API Key (raw) | Monthly Query Limit |
|------|-------|------|--------|---------------|---------------------|
| Equity Bank Kenya | api@equitybank.co.ke | Pro | Active | `vyc_test_equity_bank_pro_key_2026` | 100,000 |
| KCB Group | integration@kcbgroup.com | Enterprise (Deep Dive) | Active | `vyc_test_kcb_group_enterprise_key_2026` | 500,000 |
| Safaricom M-Pesa | partners@safaricom.co.ke | Lite | Active | `vyc_test_safaricom_lite_key_2026` | 50,000 |
| Faulu Microfinance | tech@faulu.co.ke | Lite | Pending | N/A | 10,000 |
| NCBA Bank | digital@ncbagroup.com | Pro | Suspended | N/A | 75,000 |

**Usage notes:**
- **Equity Bank Kenya** is the customer linked to the Partner user (Wanjiku Kamau). Use its API key for partner-scoped tests.
- **Faulu Microfinance** (Pending) and **NCBA Bank** (Suspended) are useful for testing status-based filtering and activation/suspension flows on the Customers page (TC-024 through TC-027).
- API keys are passed in the `X-API-Key` header for external API calls.

---

### C. Test National IDs for Score Lookup

These subjects and their current scores are seeded by `backend/scripts/seed_test_data.py`. Each subject also has 12 months of historical scores.

| National ID | Type | VyceScore | NIQ Score | Risk Level | Has Risk Drivers | # Risk Drivers | Score Date | Model Version |
|-------------|------|-----------|-----------|------------|------------------|----------------|------------|---------------|
| 12345678 | Individual | 720 | 78 | Low Risk | Yes | 3 | 2026-03-08 | v1.0.0 |
| 23456789 | Individual | 540 | 45 | Medium Risk | Yes | 3 | 2026-03-08 | v1.0.0 |
| 34567890 | Individual | 380 | 22 | High Risk | No | 0 | 2026-03-07 | v1.0.0 |
| MSME001 | Business (MSME) | 650 | 62 | Medium Risk | Yes | 3 | 2026-03-08 | v1.0.0 |
| MSME002 | Business (MSME) | 810 | 91 | Low Risk | No | 0 | 2026-03-08 | v1.0.0 |

**Risk level bands:**
- **High Risk**: 300--499
- **Medium Risk**: 500--700
- **Low Risk**: 701--900

**Usage notes:**
- Use **12345678** for TC-032 (Score Lookup) and TC-036 (Score Detail with risk drivers).
- Use **34567890** for testing high-risk score display and volatile trend charts.
- Use **MSME001** or **MSME002** for testing MSME/business-type score lookups.
- Enter a non-existent ID (e.g., `99999999`) to test "not found" handling.

---

### D. Score Detail Reference

#### D.1 Confidence Intervals

| National ID | VyceScore | Confidence Lower | Confidence Upper |
|-------------|-----------|------------------|------------------|
| 12345678 | 720 | 690 | 750 |
| 23456789 | 540 | 510 | 570 |
| 34567890 | 380 | 350 | 410 |
| MSME001 | 650 | 620 | 680 |
| MSME002 | 810 | 780 | 840 |

#### D.2 Risk Drivers (Pro Score Detail)

Risk drivers are only seeded for national IDs **12345678**, **23456789**, and **MSME001**. National IDs **34567890** and **MSME002** have no risk drivers.

**National ID: 12345678 (VyceScore 720, Low Risk)**

| Rank | Factor Name | Feature | Impact | SHAP Value | Description |
|------|-------------|---------|--------|------------|-------------|
| 1 | Cross-Border Liquidity Resilience | CBLRI | Positive | +0.045 | Consistent international transaction patterns indicate stable cross-border income |
| 2 | Supply Chain Formalization | SCFV | Positive | +0.032 | Growing number of digitized supplier-buyer relationships via VyceTrade |
| 3 | Digital Documentation Compliance | DDC | Negative | -0.018 | Below-average operational task completion rate in the last quarter |

**National ID: 23456789 (VyceScore 540, Medium Risk)**

| Rank | Factor Name | Feature | Impact | SHAP Value | Description |
|------|-------------|---------|--------|------------|-------------|
| 1 | Geographic Operational Stability | GOS | Negative | -0.052 | High variance in transaction endpoint locations suggests operational instability |
| 2 | Network Interdependence Quality | NIQ | Negative | -0.038 | Trading partners have below-average VyceScores |
| 3 | Utility Transactional Diversity | UTDI | Positive | +0.021 | Moderate merchant category diversity in recent quarters |

**National ID: MSME001 (VyceScore 650, Medium Risk)**

| Rank | Factor Name | Feature | Impact | SHAP Value | Description |
|------|-------------|---------|--------|------------|-------------|
| 1 | Supply Chain Formalization | SCFV | Positive | +0.067 | Rapidly growing digitized supplier network |
| 2 | Cross-Border Liquidity Resilience | CBLRI | Positive | +0.041 | Stable cross-border payment patterns |
| 3 | Geographic Operational Stability | GOS | Negative | -0.015 | Minor fluctuations in operational geography |

#### D.3 Feature Values (National ID: 12345678)

Features are only seeded for national ID **12345678** (feature date: 2026-03-08, quality score: 0.95).

| Feature Name | Value | Category | Data Source |
|--------------|-------|----------|-------------|
| CBLRI | 0.82 | Liquidity | VycePay |
| UTDI | 0.65 | Diversity | VycePay |
| SCFV | 0.71 | Supply Chain | VyceTrade |
| DDC | 0.58 | Compliance | VycePay |
| NIQ | 78.00 | Network | VyceScore |
| GOS | 0.88 | Geographic | VycePay |

#### D.4 Score History (12-Month Trends)

Each subject has 12 monthly historical scores plus the current score. Dates run from approximately March 2025 through February 2026, with the current score on March 7 or 8, 2026.

**12345678 -- Improving Individual (620 to 720)**

| Month | VyceScore | NIQ Score | Confidence Lower | Confidence Upper |
|-------|-----------|-----------|------------------|------------------|
| ~Mar 2025 | 620 | 55 | 590 | 650 |
| ~Apr 2025 | 635 | 58 | 605 | 665 |
| ~May 2025 | 640 | 60 | 610 | 670 |
| ~Jun 2025 | 648 | 61 | 618 | 678 |
| ~Jul 2025 | 660 | 63 | 630 | 690 |
| ~Aug 2025 | 665 | 65 | 635 | 695 |
| ~Sep 2025 | 672 | 67 | 642 | 702 |
| ~Oct 2025 | 685 | 69 | 655 | 715 |
| ~Nov 2025 | 690 | 71 | 660 | 720 |
| ~Dec 2025 | 700 | 73 | 670 | 730 |
| ~Jan 2026 | 708 | 75 | 678 | 738 |
| ~Feb 2026 | 715 | 77 | 685 | 745 |
| **Current (2026-03-08)** | **720** | **78** | **690** | **750** |

**23456789 -- Declining Individual (640 to 540)**

| Month | VyceScore | NIQ Score | Confidence Lower | Confidence Upper |
|-------|-----------|-----------|------------------|------------------|
| ~Mar 2025 | 640 | 62 | 610 | 670 |
| ~Apr 2025 | 630 | 60 | 600 | 660 |
| ~May 2025 | 618 | 58 | 588 | 648 |
| ~Jun 2025 | 610 | 56 | 580 | 640 |
| ~Jul 2025 | 600 | 54 | 570 | 630 |
| ~Aug 2025 | 592 | 53 | 562 | 622 |
| ~Sep 2025 | 585 | 51 | 555 | 615 |
| ~Oct 2025 | 575 | 50 | 545 | 605 |
| ~Nov 2025 | 568 | 49 | 538 | 598 |
| ~Dec 2025 | 560 | 48 | 530 | 590 |
| ~Jan 2026 | 552 | 46 | 522 | 582 |
| ~Feb 2026 | 545 | 45 | 515 | 575 |
| **Current (2026-03-08)** | **540** | **45** | **510** | **570** |

**34567890 -- Volatile High-Risk Individual (~380)**

| Month | VyceScore | NIQ Score | Confidence Lower | Confidence Upper |
|-------|-----------|-----------|------------------|------------------|
| ~Mar 2025 | 410 | 28 | 380 | 440 |
| ~Apr 2025 | 395 | 25 | 365 | 425 |
| ~May 2025 | 420 | 30 | 390 | 450 |
| ~Jun 2025 | 385 | 23 | 355 | 415 |
| ~Jul 2025 | 370 | 20 | 340 | 400 |
| ~Aug 2025 | 390 | 24 | 360 | 420 |
| ~Sep 2025 | 365 | 19 | 335 | 395 |
| ~Oct 2025 | 380 | 22 | 350 | 410 |
| ~Nov 2025 | 355 | 18 | 325 | 385 |
| ~Dec 2025 | 370 | 20 | 340 | 400 |
| ~Jan 2026 | 385 | 23 | 355 | 415 |
| ~Feb 2026 | 375 | 21 | 345 | 405 |
| **Current (2026-03-07)** | **380** | **22** | **350** | **410** |

**MSME001 -- Steadily Growing MSME (560 to 650)**

| Month | VyceScore | NIQ Score | Confidence Lower | Confidence Upper |
|-------|-----------|-----------|------------------|------------------|
| ~Mar 2025 | 560 | 42 | 530 | 590 |
| ~Apr 2025 | 572 | 44 | 542 | 602 |
| ~May 2025 | 580 | 46 | 550 | 610 |
| ~Jun 2025 | 588 | 48 | 558 | 618 |
| ~Jul 2025 | 595 | 50 | 565 | 625 |
| ~Aug 2025 | 605 | 52 | 575 | 635 |
| ~Sep 2025 | 612 | 54 | 582 | 642 |
| ~Oct 2025 | 620 | 55 | 590 | 650 |
| ~Nov 2025 | 628 | 57 | 598 | 658 |
| ~Dec 2025 | 635 | 59 | 605 | 665 |
| ~Jan 2026 | 640 | 60 | 610 | 670 |
| ~Feb 2026 | 645 | 61 | 615 | 675 |
| **Current (2026-03-08)** | **650** | **62** | **620** | **680** |

**MSME002 -- High-Performing MSME (750 to 810)**

| Month | VyceScore | NIQ Score | Confidence Lower | Confidence Upper |
|-------|-----------|-----------|------------------|------------------|
| ~Mar 2025 | 750 | 80 | 720 | 780 |
| ~Apr 2025 | 758 | 81 | 728 | 788 |
| ~May 2025 | 765 | 83 | 735 | 795 |
| ~Jun 2025 | 770 | 84 | 740 | 800 |
| ~Jul 2025 | 775 | 85 | 745 | 805 |
| ~Aug 2025 | 780 | 86 | 750 | 810 |
| ~Sep 2025 | 785 | 87 | 755 | 815 |
| ~Oct 2025 | 790 | 88 | 760 | 820 |
| ~Nov 2025 | 795 | 89 | 765 | 825 |
| ~Dec 2025 | 798 | 89 | 768 | 828 |
| ~Jan 2026 | 802 | 90 | 772 | 832 |
| ~Feb 2026 | 808 | 91 | 778 | 838 |
| **Current (2026-03-08)** | **810** | **91** | **780** | **840** |

---

### E. Dashboard KPI Reference Values

The Admin Dashboard displays KPIs that change based on the selected date range. The following are the mock values rendered by the frontend for each date range selector option.

| KPI | 7d | 30d (default) | 90d | 6m | 1y |
|-----|----|---------------|-----|----|----|
| Total Scores Generated | 2,147 | 12,847 | 35,214 | 62,480 | 108,352 |
| Scores Delta | +12.3% from prior week | +8.2% from last month | +15.6% from prior quarter | +22.1% from prior 6 months | +45.3% year over year |
| Active Partners | 34 | 34 | 34 | 34 | 34 |
| Partners Delta | 0 new this week | 3 new this month | 7 new this quarter | 12 new in period | 19 new this year |
| Avg VyceScore | 658 | 654 | 648 | 641 | 635 |
| Avg Score Band | Medium Risk | Medium Risk | Medium Risk | Medium Risk | Medium Risk |
| Model AUC-ROC | 0.812 | 0.809 | 0.805 | 0.798 | 0.791 |
| AUC-ROC Delta | +0.003 from prior week | +0.007 from last month | +0.012 from prior quarter | +0.018 from prior period | +0.031 year over year |
| API Uptime | 100% | 99.97% | 99.94% | 99.91% | 99.88% |
| Query Volume | 8,420 | 34,210 | 98,750 | 187,300 | 342,800 |
| Query Volume Delta | +5.1% from prior week | +6.8% from last month | +11.2% from prior quarter | +18.4% from prior period | +38.7% year over year |

**Score Distribution (displayed in all date ranges):**
| Band | Percentage |
|------|-----------|
| High Risk (300--499) | 18% |
| Medium Risk (500--700) | 52% |
| Low Risk (701--900) | 30% |

**Score Trend Chart (6-month sample data):**
| Date | VyceScore | NIQ Score |
|------|-----------|-----------|
| 2025-10-01 | 620 | 58 |
| 2025-11-01 | 645 | 60 |
| 2025-12-01 | 660 | 62 |
| 2026-01-01 | 680 | 64 |
| 2026-02-01 | 695 | 65 |
| 2026-03-01 | 710 | 67 |

**Daily Query Volume Chart (7-day sample data):**
| Date | Lite Queries | Pro Queries |
|------|-------------|-------------|
| 2026-03-01 | 1,240 | 380 |
| 2026-03-02 | 1,180 | 410 |
| 2026-03-03 | 980 | 290 |
| 2026-03-04 | 1,350 | 420 |
| 2026-03-05 | 1,420 | 460 |
| 2026-03-06 | 1,280 | 395 |
| 2026-03-07 | 1,100 | 340 |

---

### F. Audit Log Sample Data

The Audit Logs page displays 10 seeded entries (defined in `frontend/src/pages/admin/AuditLogsPage.tsx`). Testers should verify filtering, search, CSV export, and detail dialog against these entries.

| # | Timestamp (UTC) | User | Action | Method | Endpoint | Status | IP Address | Response Time | Details |
|---|-----------------|------|--------|--------|----------|--------|------------|---------------|---------|
| 1 | 2026-03-08 10:32:15 | James Mwangi | score.lookup.lite | GET | /v1/scores/lite/12345678 | 200 | 41.204.187.42 | 145ms | Score lookup for national ID 12345678 |
| 2 | 2026-03-08 10:28:03 | James Mwangi | customer.create | POST | /v1/admin/customers | 201 | 41.204.187.42 | 230ms | Created customer Faulu Microfinance with Lite tier |
| 3 | 2026-03-08 09:45:22 | Odhiambo Ochieng | auth.login | POST | /v1/auth/login | 200 | 197.232.45.110 | 89ms | Successful login |
| 4 | 2026-03-08 09:30:11 | Wanjiku Kamau | score.lookup.pro | GET | /v1/scores/pro/87654321 | 200 | 41.89.244.18 | 1120ms | Pro score lookup for national ID 87654321 |
| 5 | 2026-03-07 16:20:45 | James Mwangi | user.role.update | PUT | /v1/admin/users/u4 | 200 | 41.204.187.42 | 156ms | Changed role for Amina Hassan to ReadOnly |
| 6 | 2026-03-07 15:10:33 | Odhiambo Ochieng | customer.license.update | PUT | /v1/admin/customers/2/license | 200 | 197.232.45.110 | 198ms | Updated KCB Group license to Enterprise tier |
| 7 | 2026-03-07 14:15:28 | Wanjiku Kamau | auth.login | POST | /v1/auth/login | 200 | 41.89.244.18 | 95ms | Successful login |
| 8 | 2026-03-07 12:05:19 | Unknown | auth.login | POST | /v1/auth/login | 401 | 102.68.12.55 | 42ms | Failed login attempt - invalid credentials |
| 9 | 2026-03-06 11:42:55 | James Mwangi | batch.submit | POST | /v1/batches | 202 | 41.204.187.42 | 312ms | Submitted batch scoring job with 500 IDs |
| 10 | 2026-03-06 09:18:07 | James Mwangi | customer.activate | POST | /v1/admin/customers/4/activate | 200 | 41.204.187.42 | 178ms | Activated customer Faulu Microfinance |

**Filtering test scenarios:**
- Filter by Action = `auth.login` -- should show entries #3, #7, #8
- Filter by User = James Mwangi -- should show entries #1, #2, #5, #9, #10
- Filter by User = Odhiambo Ochieng -- should show entries #3, #6
- Search for "Faulu" -- should show entries #2, #10
- Entry #8 has status 401 (failed login) -- verify it displays with warning/amber styling
- Entry #2 has status 201 (created) -- verify it displays with success/green styling

---

### G. Partner Dashboard Reference Data

When logged in as the **Partner** user (Wanjiku Kamau / partner@equitybank.co.ke), the Partner Dashboard fetches live data from the `/v1/partner/usage` endpoint for **Equity Bank Kenya**. The expected configuration is:

| Field | Expected Value |
|-------|---------------|
| Customer Name | Equity Bank Kenya |
| Tier | Pro |
| Monthly Query Limit | 100,000 |
| Billing Period | Current month (YYYY-MM format) |

**KPI Cards displayed:**
- **Total Queries (This Month)**: Sum of all Lite + Pro queries for the current billing period
- **Lite Queries**: Count of Lite-tier API calls made this month
- **Pro Queries**: Count of Pro-tier API calls made this month
- **Queries Remaining**: `Monthly Query Limit - Total Queries` (minimum 0)

**Quota Usage Bar:**
- Usage percentage = `(Total Queries / Monthly Query Limit) * 100`
- Color coding: Green if under 75%, Amber if 75--90%, Red if over 90%

**Monthly Usage Trend:**
- Displays up to 6 months of historical billing records showing total queries per month

**Testing notes:**
- Since the partner dashboard uses live API data (not frontend mocks), the actual values depend on how many API requests have been logged in the `api_request_logs` table for Equity Bank Kenya.
- In a freshly seeded environment with no API activity, expect Total Queries = 0, Queries Remaining = 100,000, and Usage Percentage = 0.0%.
- The daily query volume chart will be empty if no API requests have been made.
- Verify the tier chip in the top-right corner shows "Pro Plan".
