# MetroCheck CRB Checker

## Overview

MetroCheck CRB Checker is a Kenya-focused credit reference bureau (CRB) status verification platform. The application enables users to check their credit status, view credit scores, verify loan eligibility, and access borrowing opportunities from lending institutions. The system integrates M-Pesa payment processing via Lipana.dev API for monetizing CRB check services through bundle purchases.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Single Page Application (SPA) Pattern**
- Built with React and TypeScript for type safety and component-based development
- Uses React Router for client-side routing with fallback to index.html for all routes
- Bundled JavaScript and CSS assets served statically
- Responsive design with Tailwind CSS for mobile-first approach targeting Kenyan users

**Rationale**: SPA provides fast, app-like experience crucial for financial services where users expect instant feedback. React's ecosystem and TypeScript improve maintainability and reduce runtime errors in production.

### Backend Architecture

**Flask API Server (Python)**
- RESTful API endpoints for payment processing
- SQLite database for storing payment transactions
- Stateless request handling for scalability

**Payment Processing Flow**:
1. Frontend collects user phone number, amount, and bundle selection
2. Flask API validates and formats Kenyan phone numbers (254 prefix)
3. Integration with Lipana.dev API (https://api.lipana.dev/v1/transactions/push-stk) triggers M-Pesa STK push
4. Stores transaction in SQLite database with status tracking
5. Returns transaction ID and checkout request ID for tracking
6. Callback endpoint receives payment confirmations from Lipana webhooks

**API Endpoints**:
- `POST /api/payment/initiate` - Initiate M-Pesa STK push payment
- `POST /api/payment/callback` - Receive Lipana webhook notifications
- `GET /api/payment/status/<checkout_id>` - Check payment status
- `GET /api/payments` - List all payment transactions

### Database Schema

**payments table (SQLite)**
- id: Primary key
- phone_number: Customer phone number (254XXXXXXXXX format)
- amount: Payment amount in KES
- bundle_name: Selected package/bundle name
- checkout_request_id: Lipana checkout request identifier
- transaction_id: Lipana transaction identifier
- mpesa_receipt_number: M-Pesa receipt after successful payment
- status: pending | processing | completed | failed
- result_code: M-Pesa result code
- result_description: Result message from M-Pesa
- created_at: Timestamp
- updated_at: Timestamp

### Data Validation Layer

**Phone Number Normalization**
- Accepts multiple formats: 0712345678, +254712345678, 254712345678
- Validates against Kenyan mobile patterns (254[17]xxxxxxxx)
- Regex validation ensures only Safaricom/Airtel numbers compatible with M-Pesa

**Payment Validation**:
- Minimum amount: KES 1
- Required fields enforcement (phone, amount)
- Early validation reduces failed API calls and improves UX

### SEO and Discoverability

**Search Engine Optimization**
- Comprehensive meta tags for social sharing (Open Graph, Twitter Cards)
- Canonical URL specification
- Robots.txt configured to allow all major crawlers
- Semantic HTML with proper document structure

**Rationale**: As a B2C service in Kenya, organic discovery through search and social shares is critical for user acquisition.

## External Dependencies

### Payment Gateway
- **Lipana.dev API**: M-Pesa payment processing service
  - Base URL: https://api.lipana.dev/v1
  - STK Push endpoint: /transactions/push-stk
  - Handles STK push notifications
  - Provides transaction tracking via checkout request IDs
  - Requires API key authentication (LIPANA_API_KEY environment variable)
  - Webhook notifications for payment status updates
  - No direct M-Pesa integration needed; Lipana abstracts complexity

### Backend Infrastructure
- **Flask**: Python web framework for API endpoints
- **SQLite**: Local file-based database for transaction storage
- **Python Requests**: HTTP client for Lipana API calls

### Frontend Libraries
- **React 18**: UI library with modern hooks and concurrent features
- **React Router**: Client-side routing for SPA navigation
- **Tailwind CSS**: Utility-first CSS framework for responsive design
- **TypeScript**: Type safety and improved developer experience

### Development/Deployment
- **Python 3.11**: Flask server for API and static file serving
- **Gunicorn**: Production WSGI server (available)

### Third-Party Services
- **Domain**: metropolcrbchecker.co.ke
- **CDN/Hosting**: Lovable.dev (OpenGraph image hosting)
- **Mobile Money**: M-Pesa (via Lipana.dev proxy)

## Environment Variables

### Required Secrets
- `LIPANA_API_KEY`: API key from Lipana.dev dashboard for M-Pesa integration

### Optional Configuration
- `CALLBACK_URL`: Custom callback URL for payment notifications (auto-generated from REPLIT_DEV_DOMAIN if not set)

## Recent Changes

### December 3, 2024 (Latest)
- **Fixed Payment Integration**
  - Fixed Lipana.dev STK push payment issue (LIPANA_API_KEY was not being loaded properly)
  - Payments now working correctly with Lipana SDK
  - STK push sends payment prompt to user's phone
  
- **Enhanced Locked Features UI**
  - All locked sections now clickable with visual upgrade prompts
  - Download Report button shows lock icon and "Upgrade to Download Report" for non-Golden users
  - Clicking locked features triggers Golden upgrade modal with feature-specific messaging
  - Added upgrade buttons inside locked sections for better UX
  - Visual border highlighting on locked sidebar features
  - handleFeatureClick() function for sidebar feature interactions

- **Premium Features with Golden Package Subscription**
  - Added 8 direct loan lender partners (M-Shwari, Fuliza, KCB M-Pesa, Equity EazzyLoan, Tala, Branch, Zenka, OPesa)
  - Direct lenders section locked behind Golden Package (KES 499)
  - Report download feature locked behind Golden Package
  - Users can click on locked features to trigger upgrade modal
  - Upgrade modal shows subscription price and initiates M-Pesa payment
  
- **Enhanced Dashboard Features**
  - Updated Direct Loan Lenders section with 8 verified partners
  - Each lender shows name, type, loan limits, and interest rates
  - Connect Now buttons for Golden Package subscribers
  - Beautiful locked overlay for non-Golden users with upgrade prompt
  
- **PDF Report Generation**
  - Full CRB report downloadable as PDF for Golden Package users
  - PDF includes credit score, CRB status, loan eligibility, credit history, and lender recommendations
  - Non-Golden users see subscription prompt when clicking download
  
- **Package Tiers**
  - Standard Package (KES 99): Basic CRB check, credit score, status
  - Premium Package (KES 299): + Credit history, detailed analysis, lender recommendations
  - Golden Package (KES 499): + PDF download, direct lender connections, dispute assistance

- Added dynamic counter for "Kenyans who checked CRB status" on homepage
  - Counter starts at 10,000 on every Sunday midnight (Kenya time UTC+3)
  - Increases by 100 every hour automatically
  - API endpoint: GET /api/stats/counter returns formatted counter value
- Updated homepage text from "Kenyans checked their CRB status this week" to "Kenyans checked their CRB status this week and recommend the website"

### December 2024 (Earlier)
- Removed Supabase Edge Functions - now using direct Flask API for payments
- Integrated Lipana.dev payment gateway for M-Pesa STK Push payments
- SQLite database for local payment transaction storage
- Callback endpoint for receiving Lipana.dev webhook notifications
- Payment status checking and transaction listing endpoints
- Clean API structure: /api/payment/initiate, /api/payment/callback, /api/payment/status

## Premium Features API Endpoints

- `POST /api/crb/download-report` - Download full CRB report as PDF (Golden Package only)
- `POST /api/lender/connect` - Connect user to a direct lender (Golden Package only)
- `POST /api/upgrade/initiate` - Initiate package upgrade payment
- `POST /api/user/access` - Check user's access level and available features
- `POST /api/crb/report` - Get CRB report based on user's package level
- `GET /api/packages` - Get available packages and pricing
