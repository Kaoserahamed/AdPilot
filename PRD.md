# Product Requirements Document (PRD)

## Product Name

**AdPilot**
*AI-Powered Multi-Platform Advertising Management Platform*

> Working name. The final product name can be changed without affecting the architecture.

---

# 1. Product Overview

AdPilot is a web-based advertising management platform that allows businesses and marketers to create, adapt, publish, and monitor advertising campaigns across multiple advertising platforms from a single interface.

Instead of manually creating separate campaigns in Facebook/Instagram, Google/YouTube, TikTok, and other advertising platforms, users can provide one campaign brief and let the platform generate platform-specific advertising content and configurations.

The platform will combine:

* Campaign management
* AI-powered ad content generation
* Creative asset management
* Multi-platform advertising integrations
* Campaign publishing
* Unified analytics
* AI-assisted performance analysis
* Secure OAuth-based platform connections

The initial MVP will focus on **Meta Ads and Google Ads/YouTube**, with the architecture designed to support additional advertising platforms later.

---

# 2. Problem Statement

Advertising across multiple platforms currently requires marketers to work with different dashboards, APIs, campaign structures, creative requirements, targeting systems, and analytics interfaces.

A marketer may need to:

1. Create a campaign strategy.
2. Write advertising copy.
3. Prepare images/videos in different formats.
4. Configure campaigns separately on each platform.
5. Monitor campaign performance independently.
6. Compare results manually.
7. Generate performance reports.

This creates duplicated work and makes campaign management difficult for small businesses, startups, and individual marketers.

AdPilot aims to provide a centralized workflow:

```text
Campaign Idea
      ↓
AI Campaign Generation
      ↓
Platform-Specific Adaptation
      ↓
User Review
      ↓
Multi-Platform Publishing
      ↓
Unified Analytics
      ↓
AI Performance Analysis
```

---

# 3. Product Vision

Build a platform where a user can describe an advertising goal once and manage the resulting advertising campaign across multiple platforms from one dashboard.

The long-term vision is to provide an **AI advertising copilot** that assists with campaign planning, creative generation, campaign configuration, publishing, monitoring, and analysis while keeping final publishing and spending decisions under user control.

---

# 4. Goals

## 4.1 Primary Goals

The MVP must allow users to:

* Create an account.
* Create advertising campaigns.
* Upload advertising creatives.
* Connect supported advertising accounts.
* Generate advertising content using AI.
* Generate platform-specific versions of advertisements.
* Review generated advertisements before publishing.
* Create/submit campaigns through supported advertising APIs.
* Track campaign publishing status.
* Retrieve campaign performance metrics.
* View multiple platform results from one dashboard.
* Receive AI-generated factual performance summaries.

## 4.2 Technical Goals

The application should:

* Use a modular architecture.
* Separate platform-specific API logic from core business logic.
* Support additional advertising platforms without major architectural changes.
* Validate all AI-generated structured data.
* Secure OAuth credentials and API tokens.
* Support asynchronous background jobs.
* Provide automated testing.
* Provide CI/CD.
* Be containerized.
* Be deployable to cloud infrastructure.
* Provide production logging and health monitoring.

---

# 5. Non-Goals for MVP

The following features are outside the initial MVP:

* Fully autonomous advertising without user approval.
* Automatic unlimited budget allocation.
* Automatic financial transactions.
* Building a new advertising network.
* Guaranteeing campaign approval by external platforms.
* Bypassing advertising platform policies.
* Supporting every advertising platform from the beginning.
* Advanced autonomous campaign optimization.
* Enterprise-grade multi-organization billing.
* Complex attribution modeling.

These may be considered in future versions.

---

# 6. Target Users

## 6.1 Small Businesses

Businesses that want to advertise products/services without managing several advertising dashboards.

## 6.2 Startups

Startups running campaigns across multiple platforms with limited marketing resources.

## 6.3 Digital Marketers

Marketing professionals who need centralized campaign creation and monitoring.

## 6.4 Agencies

Future versions may support agencies managing multiple clients and advertising accounts.

## 6.5 Individual Creators / Entrepreneurs

Users who want to promote products, services, events, courses, applications, or websites.

---

# 7. Core User Journey

```text
User
 ↓
Register / Login
 ↓
Dashboard
 ↓
Create Campaign
 ↓
Enter Campaign Brief
 ↓
Upload Creative
 ↓
Select Platforms
 ↓
AI Generates Campaign Content
 ↓
User Reviews
 ↓
Platform Validation
 ↓
Connect Advertising Accounts
 ↓
Prepare Campaign
 ↓
User Confirms
 ↓
Publish
 ↓
Platform Review / Active Status
 ↓
Metrics Synchronization
 ↓
Unified Analytics
 ↓
AI Performance Summary
```

---

# 8. Functional Requirements

# 8.1 Authentication

The system shall support:

* User registration.
* User login.
* User logout.
* Password hashing.
* Session/token management.
* Protected routes.
* Password reset.
* Email verification if enabled.
* Authentication error handling.

### Acceptance Criteria

* Unauthenticated users cannot access protected application pages.
* Passwords are never stored in plaintext.
* Invalid credentials return appropriate errors.
* Expired authentication credentials are handled securely.

---

# 8.2 User Dashboard

The dashboard shall display:

* Active campaigns.
* Draft campaigns.
* Campaigns pending review.
* Recent campaigns.
* Total campaign spend.
* Impressions.
* Clicks.
* Conversions where available.
* Connected platforms.
* Recent activity.

Example:

```text
Dashboard

Campaigns
----------------------------------
Active              4
Draft               3
Pending Review      2

Performance
----------------------------------
Spend               $427
Impressions         284K
Clicks              8,421
Conversions         327
```

Metrics must clearly identify their source and reporting period.

---

# 8.3 Campaign Creation

Users shall be able to create a campaign using a campaign brief.

Required information:

* Campaign name.
* Product/service.
* Description.
* Advertising objective.
* Target location.
* Target audience.
* Budget.
* Campaign duration.
* Landing page.
* Preferred tone.
* Offer/discount if applicable.
* Desired platforms.

Optional information:

* Brand guidelines.
* Existing advertising copy.
* Competitor/reference information.
* Additional campaign instructions.

---

# 8.4 Campaign Objectives

The initial system should support configurable objectives such as:

* Traffic.
* Leads.
* Sales/conversions.
* Brand awareness.
* Engagement.

The available objectives must be mapped to what the selected advertising platforms actually support.

---

# 8.5 Creative Management

Users shall be able to upload and manage:

* Images.
* Videos.
* Logos.

Each creative should store metadata:

```text
Creative
--------
ID
User ID
File URL
File Type
File Size
Width
Height
Duration
Created At
```

The system shall validate:

* File type.
* File size.
* File dimensions where required.
* Platform compatibility.

---

# 8.6 Creative Library

Users shall have a centralized creative library.

Capabilities:

* Upload.
* Preview.
* Search.
* Filter.
* Attach to campaigns.
* Delete.
* View metadata.

Example:

```text
My Creatives

[ Image ] [ Image ] [ Video ]
[ Logo  ] [ Image ] [ Video ]
```

---

# 8.7 AI Campaign Generation

The AI service shall transform a campaign brief into structured advertising content.

Input:

```text
Product
Description
Audience
Location
Objective
Budget
Tone
Offer
Landing Page
Platforms
```

Output should include:

```json
{
  "strategy": {},
  "audience": {},
  "messaging": {},
  "platform_ads": []
}
```

The AI system must not return uncontrolled free-form data where structured information is required.

All structured AI responses must be validated using backend schemas.

---

# 8.8 Platform-Specific Ad Generation

The AI service shall adapt campaign messaging for each supported platform.

Example output:

### Meta

```text
Primary Text
Headline
Description
CTA
```

### Google/YouTube

```text
Headline
Long Headline
Description
Video Hook
Video Script
CTA
```

Additional platforms may have different fields.

The system must maintain separate platform schemas.

---

# 8.9 AI Content Editing

Users shall be able to request modifications such as:

* Regenerate.
* Shorten.
* Expand.
* Change tone.
* Make more professional.
* Make more casual.
* Change CTA.
* Rewrite headline.
* Generate alternative versions.

AI modifications must remain associated with the campaign and platform.

---

# 8.10 Human Review

No campaign should be automatically published solely because AI generated it.

The user must have a review stage:

```text
AI Generated
     ↓
User Review
     ↓
User Confirmation
     ↓
Publish
```

The review screen should show:

* Campaign configuration.
* Platform.
* Creative.
* Generated copy.
* Budget.
* Targeting.
* Estimated platform requirements.
* Validation errors/warnings.

---

# 8.11 Platform Adapter System

Advertising platform integrations shall use a common adapter architecture.

Example:

```text
AdPlatformAdapter
├── MetaAdapter
├── GoogleAdsAdapter
└── TikTokAdapter
```

The base abstraction should support operations such as:

```text
connect_account()
get_accounts()
validate_campaign()
upload_creative()
create_campaign()
create_ad()
publish_campaign()
pause_campaign()
get_campaign_status()
get_metrics()
```

Individual platforms may implement only the operations supported by their APIs.

---

# 8.12 Connected Accounts

Users shall be able to connect advertising accounts using OAuth.

Example:

```text
Connected Accounts

Meta
    Connected ✓

Google Ads
    Connected ✓

TikTok
    Not Connected
```

The frontend must never receive sensitive platform access tokens unless strictly required by the OAuth architecture.

Tokens should be stored securely on the backend.

---

# 8.13 Meta Integration

The MVP shall integrate with the Meta advertising ecosystem where supported by the applicable API and account permissions.

Capabilities should include:

* OAuth connection.
* Account discovery.
* Campaign creation.
* Creative handling.
* Ad creation.
* Campaign submission.
* Status retrieval.
* Metrics retrieval.

The implementation must account for platform-specific permissions, API limitations, review requirements, and campaign policies.

---

# 8.14 Google Ads / YouTube Integration

The MVP shall integrate with Google Ads APIs for supported advertising workflows.

Capabilities should include:

* OAuth.
* Account discovery.
* Campaign creation/configuration.
* Supported YouTube advertising workflow.
* Campaign submission.
* Status retrieval.
* Metrics retrieval.

The implementation must respect Google Ads API requirements and account permissions.

---

# 8.15 Campaign Validation

Before publishing, the backend shall validate:

### General

* Required fields.
* Budget.
* Dates.
* Creative.
* Landing page.
* Targeting.

### Platform-specific

* Supported creative format.
* Required campaign fields.
* Text limits.
* Media requirements.
* Platform-specific configuration.

Example:

```text
Campaign Validation

Meta       ✓ Ready
Google     ✓ Ready
TikTok     ✗ Creative format unsupported
```

---

# 8.16 Campaign Publishing

Publishing shall be asynchronous.

Workflow:

```text
User clicks Publish
        ↓
Backend validates campaign
        ↓
Create publishing job
        ↓
Queue
        ↓
Worker
        ↓
Platform API
        ↓
Update campaign status
```

Possible statuses:

```text
DRAFT
GENERATING
READY
VALIDATION_FAILED
PUBLISHING
PENDING_REVIEW
ACTIVE
PAUSED
REJECTED
FAILED
```

---

# 8.17 Background Processing

Long-running operations shall use background workers.

Examples:

* AI generation.
* Video processing.
* Creative uploads.
* Campaign publishing.
* Metric synchronization.
* Status synchronization.

Technology for MVP:

```text
Redis
+
Celery
```

The architecture should allow replacement with another queue system later.

---

# 8.18 Campaign Analytics

The platform shall collect available metrics from supported platforms.

Potential metrics:

* Spend.
* Impressions.
* Reach.
* Clicks.
* CTR.
* CPC.
* Conversions.
* CPA.
* Revenue where available.
* ROAS where available.

Every metric must retain:

```text
Platform
Campaign
Metric
Value
Currency
Timestamp / Reporting Period
Source
```

---

# 8.19 Unified Analytics Dashboard

Users shall be able to view:

```text
All Campaigns
      ↓
Platform Metrics
      ↓
Campaign Metrics
      ↓
Time-Based Metrics
```

Visualizations:

* Spend over time.
* Impressions.
* Clicks.
* Conversions.
* Campaign status.
* Platform breakdown.

The dashboard must clearly distinguish metrics that come directly from external platforms from metrics calculated by AdPilot.

---

# 8.20 AI Analytics Assistant

Users shall be able to ask questions about their campaign data.

Examples:

> "Summarize this campaign."

> "What happened during the last 7 days?"

> "Compare the campaign metrics between platforms."

The AI must only use retrieved campaign data as its factual source.

It must not invent missing metrics.

Example:

```text
Campaign Summary

Reporting period:
September 18–24, 2026

Impressions:
42,821

Clicks:
1,283

Conversions:
47

Conversion rate:
3.66%
```

---

# 8.21 Campaign Activity Log

Every important action should be recorded.

Example:

```text
Activity

19:20 Campaign created
19:22 AI copy generated
19:25 Creative uploaded
19:27 Meta account connected
19:30 Campaign submitted
19:31 Meta status changed to PENDING_REVIEW
```

This is useful for debugging and auditing.

---

# 9. Data Model

Initial entities:

```text
User
Campaign
Creative
CampaignCreative
Platform
ConnectedAccount
PlatformCampaign
Advertisement
CampaignMetric
AIRequest
PublishingJob
ActivityLog
```

Possible relationships:

```text
User
 │
 ├── Campaign
 │      ├── Creative
 │      ├── Advertisement
 │      ├── PlatformCampaign
 │      └── CampaignMetric
 │
 ├── ConnectedAccount
 │
 └── ActivityLog
```

---

# 10. API Requirements

Initial API structure:

```text
/api/v1/auth
/api/v1/users
/api/v1/campaigns
/api/v1/creatives
/api/v1/ai
/api/v1/platforms
/api/v1/accounts
/api/v1/publishing
/api/v1/analytics
/api/v1/activity
```

Example:

```text
POST   /api/v1/campaigns
GET    /api/v1/campaigns
GET    /api/v1/campaigns/{id}
PUT    /api/v1/campaigns/{id}
DELETE /api/v1/campaigns/{id}
```

AI:

```text
POST /api/v1/ai/generate-campaign
POST /api/v1/ai/regenerate
POST /api/v1/ai/analyze
```

Publishing:

```text
POST /api/v1/campaigns/{id}/validate
POST /api/v1/campaigns/{id}/publish
GET  /api/v1/campaigns/{id}/status
```

Analytics:

```text
GET /api/v1/analytics/overview
GET /api/v1/analytics/campaigns/{id}
GET /api/v1/analytics/platforms
```

---

# 11. Non-Functional Requirements

## 11.1 Security

The system must:

* Hash passwords securely.
* Encrypt sensitive credentials at rest.
* Protect OAuth credentials.
* Never expose secrets in frontend code.
* Validate all incoming requests.
* Apply rate limiting.
* Use HTTPS in production.
* Restrict CORS.
* Implement secure file handling.
* Maintain audit logs.
* Follow least-privilege access.

---

# 11.2 Performance

Target:

* Normal API responses: preferably under 500 ms excluding external APIs.
* Dashboard initial load: preferably under 2–3 seconds under normal conditions.
* Long-running operations must be asynchronous.
* External API failures must not block unrelated users.

Performance targets should be measured under documented test conditions.

---

# 11.3 Reliability

The system should:

* Retry transient external API failures.
* Avoid duplicate campaign creation.
* Use idempotency where applicable.
* Track failed jobs.
* Provide health checks.
* Provide structured logs.
* Support database backups.

---

# 11.4 Scalability

The architecture should allow independent scaling of:

```text
Frontend
Backend API
Workers
Database
Redis
Storage
```

The application should be stateless at the API layer where practical.

---

# 12. Security Architecture

Sensitive credentials must follow:

```text
Browser
   ↓
Backend
   ↓
Encrypted Credential Store
   ↓
Platform API
```

Never:

```text
Browser
   ↓
Platform Secret
```

Secrets must be supplied through environment variables or a production secret-management system.

---

# 13. AI Architecture

Use an abstraction:

```text
AIProvider
├── GeminiProvider
└── OpenAIProvider
```

AI requests should contain:

```text
System Instructions
+
Campaign Context
+
Platform Requirements
+
User Request
```

AI output should be:

```text
Model
 ↓
Structured JSON
 ↓
Schema Validation
 ↓
Business Validation
 ↓
Database
```

Never directly send unchecked AI output to an advertising API.

---

# 14. Error Handling

The system must provide meaningful errors.

Example:

```text
Campaign could not be published.

Reason:
Google Ads rejected the campaign configuration because
a required field is missing.

Action:
Review the highlighted field and try again.
```

Errors should have:

```text
User-friendly message
Internal error code
Request ID
Timestamp
```

Sensitive internal information must not be exposed to users.

---

# 15. Testing Requirements

## Unit Testing

Test:

* Business logic.
* Schemas.
* Services.
* Platform adapters.
* AI response validation.

## Integration Testing

Test:

* Database.
* Authentication.
* API.
* Queue.
* External service abstractions.

## End-to-End Testing

Primary flow:

```text
Register
 ↓
Login
 ↓
Create Campaign
 ↓
Upload Creative
 ↓
Generate AI Campaign
 ↓
Review
 ↓
Connect Platform
 ↓
Validate
 ↓
Publish
 ↓
Retrieve Metrics
 ↓
View Dashboard
```

---

# 16. CI/CD Requirements

Every pull request should execute:

```text
Lint
 ↓
Type Check
 ↓
Unit Tests
 ↓
Integration Tests
 ↓
Build
 ↓
Security Scan
```

Deployment pipeline:

```text
Git Push
 ↓
GitHub Actions
 ↓
Test
 ↓
Build
 ↓
Docker Image
 ↓
Deploy
```

---

# 17. Git Development Requirements

Development must be incremental.

For **every feature**:

```text
1. Implement
2. Run tests
3. Fix failures
4. Verify manually when appropriate
5. Review changes
6. Commit
7. Push
8. Move to next feature
```

Commit examples:

```text
feat: add authentication
feat: add campaign management
feat: add creative library
feat: add AI campaign generation
feat: add Meta integration
feat: add Google Ads integration
feat: add analytics dashboard
test: add campaign integration tests
security: harden OAuth credential handling
docs: add deployment documentation
```

Do not accumulate unrelated features into one large commit.

---

# 18. Environment Configuration

Development:

```text
.env
```

Production:

```text
Managed secrets
```

Example:

```text
DATABASE_URL=
REDIS_URL=

JWT_SECRET=

AI_API_KEY=

META_CLIENT_ID=
META_CLIENT_SECRET=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

`.env` files containing secrets must never be committed.

Provide:

```text
.env.example
```

with placeholder values.

---

# 19. Deployment Architecture

Recommended initial deployment:

```text
                    Internet
                       │
                       ▼
                  Next.js
                  Vercel
                       │
                       ▼
                  FastAPI API
                  Azure/AWS
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      PostgreSQL     Redis       Storage
          │            │
          │            ▼
          │          Workers
          │            │
          └────────────┼────────────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
          Meta API          Google API
```

The exact cloud provider can be selected during implementation.

---

# 20. Observability

Production system should provide:

* Application logs.
* API request logs.
* Worker logs.
* External API error logs.
* Authentication events.
* Campaign publishing events.
* Health checks.
* Database monitoring.
* Queue monitoring.

Recommended endpoints:

```text
GET /api/health
GET /api/ready
```

---

# 21. MVP Release Criteria

The MVP is considered complete when a new user can:

```text
✓ Register
✓ Login
✓ Create campaign
✓ Upload creative
✓ Generate AI advertising content
✓ Edit AI content
✓ Connect Meta account
✓ Connect Google Ads account
✓ Validate campaign
✓ Review campaign
✓ Confirm publishing
✓ Submit campaign through supported APIs
✓ See campaign status
✓ Retrieve available metrics
✓ View unified analytics
✓ Ask AI to summarize campaign performance
```

Additionally:

```text
✓ Automated tests pass
✓ CI pipeline passes
✓ Production deployment works
✓ Secrets are secured
✓ Documentation is complete
✓ Error handling is implemented
✓ Database backup strategy exists
```

---

# 22. MVP Success Metrics

Technical/product metrics to track:

* Campaign creation completion rate.
* AI generation success rate.
* Campaign validation failure rate.
* Publishing success/failure rate.
* External API error rate.
* Average AI generation latency.
* Average campaign publishing latency.
* Dashboard load time.
* Background job failure rate.
* User retention.
* Number of connected advertising accounts.

These metrics describe product operation and adoption; they should not be treated as guarantees of advertising performance.

---

# 23. Future Roadmap

## Version 1.1

* TikTok integration.
* LinkedIn integration.
* More creative formats.
* Campaign duplication.
* Scheduled publishing.
* Advanced filters.

## Version 1.2

* A/B campaign variants.
* More detailed reporting.
* Export reports to PDF/CSV.
* Email reports.
* Custom dashboards.

## Version 2.0

Multi-tenant organization support:

```text
Organization
 ├── Members
 ├── Clients
 ├── Campaigns
 ├── Advertising Accounts
 └── Reports
```

## Version 2.1

AI campaign assistant:

```text
User:
"Create a campaign for my new product."

AI:
Campaign strategy
Creative suggestions
Audience configuration
Platform configurations
Budget proposal

User:
"Review it."

AI:
Validation + explanations

User:
"Publish."

System:
Submit campaigns to selected platforms.
```

---

# 24. Future Multi-Agent Architecture

A future version may use specialized agents:

```text
                 Campaign Manager Agent
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    Research Agent   Creative Agent   Analytics Agent
          │              │              │
          ▼              ▼              ▼
     Audience        Copy/Image       Performance
     Research        Generation        Analysis
                         │
                         ▼
                  Platform Agents
                  ┌──────┼──────┐
                  ▼      ▼      ▼
                Meta   Google  TikTok
```

However, the MVP should use conventional service architecture first. Agentic behavior should be introduced only where it provides clear value.

---

# 25. Recommended Development Order

The implementation must follow this order:

```text
1. Repository Setup
2. Frontend Foundation
3. Backend Foundation
4. Authentication
5. Campaign Management
6. Creative Management
7. AI Campaign Generator
8. Platform Adapter Architecture
9. Meta Integration
10. Google Ads Integration
11. Campaign Validation
12. Publishing Workflow
13. Background Workers
14. Unified Analytics
15. AI Analytics Assistant
16. Security Hardening
17. Automated Testing
18. CI/CD
19. Dockerization
20. Production Deployment
21. Monitoring
22. Documentation
23. End-to-End Validation
24. MVP Release
```

Each stage must follow:

```text
Implement
   ↓
Test
   ↓
Fix
   ↓
Review
   ↓
Commit
   ↓
Push
   ↓
Next Task
```

---

# 26. Definition of Done

A feature is **Done** only when:

* Implementation is complete.
* Relevant tests are written.
* Tests pass.
* Error handling exists.
* Security implications are reviewed.
* UI is responsive where applicable.
* Documentation is updated where necessary.
* No secrets are committed.
* Git status is clean except for intentional work.
* A meaningful commit has been created.
* The commit has been pushed to the remote repository.

No feature should be marked complete merely because the code compiles.

---

# 27. Product Principle

The platform should follow one central principle:

> **AI assists with advertising; the user remains in control of campaign approval and spending.**

The system should make multi-platform advertising simpler without hiding important configuration, costs, platform restrictions, or campaign status from the user.

---

# 28. Final Product Concept

The completed product should provide this experience:

```text
┌────────────────────────────────────────────────────┐
│                    ADPILOT                         │
├────────────────────────────────────────────────────┤
│                                                    │
│  "I want to promote my new tour package."          │
│                                                    │
│  Product: Bangladesh Tour Package                  │
│  Budget: $100                                      │
│  Duration: 7 days                                  │
│  Audience: University students                    │
│                                                    │
│              [ Generate Campaign ]                 │
│                                                    │
├────────────────────────────────────────────────────┤
│                                                    │
│  AI Generated Campaign                             │
│                                                    │
│  ✓ Facebook                                        │
│  ✓ Instagram                                       │
│  ✓ YouTube                                         │
│                                                    │
│  Creative     Copy       Audience      Budget      │
│                                                    │
│              [ Review Campaign ]                   │
│                                                    │
├────────────────────────────────────────────────────┤
│                                                    │
│  Connected Platforms                               │
│                                                    │
│  Facebook    ✓                                     │
│  Google      ✓                                     │
│                                                    │
│              [ Publish Campaign ]                  │
│                                                    │
├────────────────────────────────────────────────────┤
│                                                    │
│  Campaign Analytics                                │
│                                                    │
│  Spend       Impressions      Clicks   Conversions│
│  $427          284K           8,421       327      │
│                                                    │
│  [ Ask AI About Performance ]                      │
│                                                    │
└────────────────────────────────────────────────────┘
```

**The MVP objective is not to replace Meta Ads Manager or Google Ads. It is to provide a unified workflow on top of their APIs: create once, adapt for each platform, review once, publish through the appropriate platform APIs, and monitor the resulting campaigns from one application.**
