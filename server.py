import os
import json
import sqlite3
import hmac
import hashlib
import requests
import sys
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file
from lipana import Lipana

app = Flask(__name__, static_folder='.')

# Initialize Lipana SDK
api_key = os.environ.get('LIPANA_API_KEY', '')
print(f"LIPANA_API_KEY present: {bool(api_key)}", file=sys.stderr)
print(f"LIPANA_API_KEY length: {len(api_key)}", file=sys.stderr)
if api_key:
    print(f"LIPANA_API_KEY prefix: {api_key[:15]}..." if len(api_key) > 15 else f"LIPANA_API_KEY: {api_key}", file=sys.stderr)

# Determine environment based on key prefix
if api_key.startswith('lip_sk_test_') or api_key.startswith('lip_pk_test_'):
    lipana_env = 'sandbox'
else:
    lipana_env = 'production'  # Default to production (sandbox not always available)

print(f"Lipana environment: {lipana_env}", file=sys.stderr)

# Initialize Lipana client
lipana_client = None
if api_key:
    try:
        lipana_client = Lipana(api_key=api_key, environment=lipana_env)
        print("Lipana SDK initialized successfully", file=sys.stderr)
    except Exception as e:
        print(f"Failed to initialize Lipana SDK: {str(e)}", file=sys.stderr)

DATABASE_PATH = 'payments.db'

PACKAGES = {
    'standard': {
        'name': 'Standard Package',
        'price': 99,
        'features': {
            'credit_score': True,
            'crb_status': True,
            'basic_report': True,
            'loan_eligibility': True,
            'credit_history': False,
            'detailed_analysis': False,
            'lender_recommendations': False,
            'credit_improvement_tips': False,
            'dispute_assistance': False,
            'priority_support': False
        },
        'description': 'Basic CRB check with credit score and status'
    },
    'premium': {
        'name': 'Premium Package',
        'price': 299,
        'features': {
            'credit_score': True,
            'crb_status': True,
            'basic_report': True,
            'loan_eligibility': True,
            'credit_history': True,
            'detailed_analysis': True,
            'lender_recommendations': True,
            'credit_improvement_tips': True,
            'dispute_assistance': False,
            'priority_support': False
        },
        'description': 'Comprehensive CRB report with detailed analysis'
    },
    'golden': {
        'name': 'Golden Premium Package',
        'price': 499,
        'features': {
            'credit_score': True,
            'crb_status': True,
            'basic_report': True,
            'loan_eligibility': True,
            'credit_history': True,
            'detailed_analysis': True,
            'lender_recommendations': True,
            'credit_improvement_tips': True,
            'dispute_assistance': True,
            'priority_support': True,
            'download_report': True,
            'direct_lenders': True
        },
        'description': 'Complete CRB solution with priority support and dispute assistance'
    }
}

DIRECT_LENDERS = {
    'mshwari': {
        'name': 'M-Shwari',
        'type': 'Instant Mobile Loans',
        'max_amount': 50000,
        'interest_rate': '7.5% per month',
        'contact': '+254700000001',
        'badge': 'Pre-approved',
        'color': 'green'
    },
    'tala': {
        'name': 'Tala Kenya',
        'type': 'Fast Approval Loans',
        'max_amount': 50000,
        'interest_rate': '15% per month',
        'contact': '+254700000002',
        'badge': 'Verified Partner',
        'color': 'blue'
    },
    'branch': {
        'name': 'Branch Kenya',
        'type': 'Flexible Repayment',
        'max_amount': 70000,
        'interest_rate': '1-3% per day',
        'contact': '+254700000003',
        'badge': 'Trusted',
        'color': 'purple'
    },
    'kcb': {
        'name': 'KCB M-Pesa',
        'type': 'Bank-backed Loans',
        'max_amount': 1000000,
        'interest_rate': '1.083% per month',
        'contact': '+254700000004',
        'badge': 'Official Bank',
        'color': 'orange'
    },
    'zenka': {
        'name': 'Zenka Finance',
        'type': 'Quick Cash Loans',
        'max_amount': 30000,
        'interest_rate': '9% per month',
        'contact': '+254700000005',
        'badge': 'Fast Approval',
        'color': 'teal'
    },
    'opesa': {
        'name': 'OPesa Loans',
        'type': 'Emergency Loans',
        'max_amount': 25000,
        'interest_rate': '8% per month',
        'contact': '+254700000006',
        'badge': 'Quick Access',
        'color': 'cyan'
    },
    'fuliza': {
        'name': 'Fuliza by Safaricom',
        'type': 'Overdraft Facility',
        'max_amount': 100000,
        'interest_rate': '1% per day',
        'contact': '+254700000007',
        'badge': 'Official M-Pesa',
        'color': 'green'
    },
    'equity': {
        'name': 'Equity Bank EazzyLoan',
        'type': 'Bank Loans',
        'max_amount': 500000,
        'interest_rate': '1.25% per month',
        'contact': '+254700000008',
        'badge': 'Premium Bank',
        'color': 'red'
    }
}

FEATURE_LABELS = {
    'credit_score': 'Credit Score Check',
    'crb_status': 'CRB Status Verification',
    'basic_report': 'Basic CRB Report',
    'loan_eligibility': 'Loan Eligibility Check',
    'credit_history': 'Full Credit History (12 months)',
    'detailed_analysis': 'Detailed Credit Analysis',
    'lender_recommendations': 'Lender Recommendations',
    'credit_improvement_tips': 'Credit Score Improvement Tips',
    'dispute_assistance': 'CRB Dispute Assistance',
    'priority_support': '24/7 Priority Support'
}

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            amount REAL NOT NULL,
            bundle_name TEXT NOT NULL,
            checkout_request_id TEXT,
            merchant_request_id TEXT,
            transaction_id TEXT,
            mpesa_receipt_number TEXT,
            status TEXT DEFAULT 'pending',
            result_code INTEGER,
            result_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            package_type TEXT NOT NULL,
            payment_id INTEGER,
            is_active INTEGER DEFAULT 1,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (payment_id) REFERENCES payments(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crb_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            credit_score INTEGER,
            crb_status TEXT,
            loan_eligibility TEXT,
            credit_history TEXT,
            detailed_analysis TEXT,
            lender_recommendations TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_package(phone_number):
    """Get the user's active package type"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT package_type FROM user_access 
        WHERE phone_number = ? AND is_active = 1
        ORDER BY created_at DESC LIMIT 1
    ''', (phone_number,))
    result = cursor.fetchone()
    conn.close()
    return result['package_type'] if result else None

def grant_user_access(phone_number, package_type, payment_id):
    """Grant user access to a package"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_access (phone_number, package_type, payment_id, is_active)
        VALUES (?, ?, ?, 1)
    ''', (phone_number, package_type, payment_id))
    conn.commit()
    conn.close()

def generate_crb_report(phone_number):
    """Generate or retrieve CRB report for user"""
    import random
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM crb_reports WHERE phone_number = ?
        ORDER BY created_at DESC LIMIT 1
    ''', (phone_number,))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return dict(existing)
    
    credit_score = random.randint(300, 850)
    
    if credit_score >= 700:
        crb_status = 'Good Standing'
        loan_eligibility = 'Eligible for premium loans up to KES 500,000'
    elif credit_score >= 550:
        crb_status = 'Fair Standing'
        loan_eligibility = 'Eligible for standard loans up to KES 200,000'
    elif credit_score >= 400:
        crb_status = 'Needs Improvement'
        loan_eligibility = 'Limited eligibility - small loans up to KES 50,000'
    else:
        crb_status = 'Poor Standing'
        loan_eligibility = 'Not currently eligible - work on improving score'
    
    credit_history = json.dumps([
        {'month': 'Nov 2024', 'score': credit_score - random.randint(-20, 30)},
        {'month': 'Oct 2024', 'score': credit_score - random.randint(-20, 40)},
        {'month': 'Sep 2024', 'score': credit_score - random.randint(-20, 50)},
        {'month': 'Aug 2024', 'score': credit_score - random.randint(-20, 60)},
        {'month': 'Jul 2024', 'score': credit_score - random.randint(-20, 70)},
        {'month': 'Jun 2024', 'score': credit_score - random.randint(-20, 80)},
    ])
    
    detailed_analysis = json.dumps({
        'payment_history': random.randint(60, 100),
        'credit_utilization': random.randint(10, 90),
        'credit_age': random.randint(1, 15),
        'credit_mix': random.randint(50, 100),
        'recent_inquiries': random.randint(0, 10)
    })
    
    lender_recommendations = json.dumps([
        {'name': 'KCB Bank', 'max_loan': 300000, 'rate': '13.5%'},
        {'name': 'Equity Bank', 'max_loan': 250000, 'rate': '14.0%'},
        {'name': 'M-Shwari', 'max_loan': 50000, 'rate': '7.5%'},
        {'name': 'Tala', 'max_loan': 30000, 'rate': '15.0%'},
        {'name': 'Branch', 'max_loan': 70000, 'rate': '12.0%'}
    ])
    
    cursor.execute('''
        INSERT INTO crb_reports (phone_number, credit_score, crb_status, loan_eligibility, 
                                  credit_history, detailed_analysis, lender_recommendations)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (phone_number, credit_score, crb_status, loan_eligibility, 
          credit_history, detailed_analysis, lender_recommendations))
    conn.commit()
    
    cursor.execute('SELECT * FROM crb_reports WHERE id = ?', (cursor.lastrowid,))
    report = dict(cursor.fetchone())
    conn.close()
    
    return report

def format_phone_number(phone):
    cleaned = ''.join(filter(str.isdigit, phone.replace('+', '')))
    
    if cleaned.startswith('254'):
        pass
    elif cleaned.startswith('0'):
        cleaned = '254' + cleaned[1:]
    elif cleaned.startswith('7') or cleaned.startswith('1'):
        cleaned = '254' + cleaned
    
    import re
    if not re.match(r'^254[17]\d{8}$', cleaned):
        return None
    
    return cleaned

@app.route('/api/payment/initiate', methods=['POST', 'OPTIONS'])
def initiate_payment():
    if request.method == 'OPTIONS':
        return jsonify({})
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        phone = data.get('phone')
        amount = data.get('amount')
        bundle_name = data.get('bundleName', 'CRB Check')
        
        if not phone or amount is None:
            return jsonify({
                'success': False, 
                'error': 'Missing required fields: phone and amount'
            }), 400
        
        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            return jsonify({
                'success': False,
                'error': 'Invalid phone number format. Use 254XXXXXXXXX, 0XXXXXXXXX, or +254XXXXXXXXX'
            }), 400
        
        try:
            amount = float(amount)
            if amount < 10:
                return jsonify({'success': False, 'error': 'Minimum amount is KES 10'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        if not lipana_client:
            return jsonify({
                'success': False, 
                'error': 'Payment service not configured. Please contact support.'
            }), 500
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO payments (phone_number, amount, bundle_name, status)
            VALUES (?, ?, ?, 'pending')
        ''', (formatted_phone, amount, bundle_name))
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        phone_with_plus = f'+{formatted_phone}'
        print(f"Initiating STK push via SDK for {phone_with_plus}, amount: {int(amount)}", file=sys.stderr)
        
        try:
            stk_response = lipana_client.transactions.initiate_stk_push(
                phone=phone_with_plus,
                amount=int(amount)
            )
            print(f"SDK STK push response: {stk_response}", file=sys.stderr)
            
            checkout_id = stk_response.get('checkoutRequestID') or stk_response.get('checkoutRequestId')
            transaction_id = stk_response.get('transactionId')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payments 
                SET checkout_request_id = ?, transaction_id = ?, status = 'processing', updated_at = ?
                WHERE id = ?
            ''', (checkout_id, transaction_id, datetime.now().isoformat(), payment_id))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'STK push sent successfully. Check your phone to complete payment.',
                'paymentId': payment_id,
                'checkoutRequestId': checkout_id
            })
            
        except Exception as sdk_error:
            error_msg = str(sdk_error)
            print(f"SDK STK push error: {error_msg}", file=sys.stderr)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payments SET status = 'failed', result_description = ?, updated_at = ?
                WHERE id = ?
            ''', (error_msg, datetime.now().isoformat(), payment_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': False, 'error': error_msg}), 400
            
    except Exception as e:
        print(f"Payment error: {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'error': 'An error occurred. Please try again.'}), 500

@app.route('/functions/v1/initiate-payment', methods=['POST', 'OPTIONS'])
def supabase_compat_initiate_payment():
    if request.method == 'OPTIONS':
        return jsonify({})
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        phone = data.get('phone')
        amount = data.get('amount')
        bundle_name = data.get('bundleName', 'CRB Check')
        
        if not phone or amount is None:
            return jsonify({
                'success': False, 
                'error': 'Missing required fields: phone and amount'
            }), 400
        
        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            return jsonify({
                'success': False,
                'error': 'Invalid phone number format. Use 254XXXXXXXXX, 0XXXXXXXXX, or +254XXXXXXXXX'
            }), 400
        
        try:
            amount = float(amount)
            if amount < 10:
                return jsonify({'success': False, 'error': 'Minimum amount is KES 10'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        if not lipana_client:
            return jsonify({
                'success': False, 
                'error': 'Payment service not configured. Please contact support.'
            }), 500
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO payments (phone_number, amount, bundle_name, status)
            VALUES (?, ?, ?, 'pending')
        ''', (formatted_phone, amount, bundle_name))
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        phone_with_plus = f'+{formatted_phone}'
        print(f"Initiating STK push via SDK for {phone_with_plus}, amount: {int(amount)}", file=sys.stderr)
        
        try:
            stk_response = lipana_client.transactions.initiate_stk_push(
                phone=phone_with_plus,
                amount=int(amount)
            )
            print(f"SDK STK push response: {stk_response}", file=sys.stderr)
            
            checkout_id = stk_response.get('checkoutRequestID') or stk_response.get('checkoutRequestId')
            transaction_id = stk_response.get('transactionId')
            
            if stk_response.get('data'):
                data_obj = stk_response.get('data', {})
                checkout_id = checkout_id or data_obj.get('checkoutRequestID') or data_obj.get('checkoutRequestId')
                transaction_id = transaction_id or data_obj.get('transactionId')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payments 
                SET checkout_request_id = ?, transaction_id = ?, status = 'processing', updated_at = ?
                WHERE id = ?
            ''', (checkout_id, transaction_id, datetime.now().isoformat(), payment_id))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'STK push sent successfully. Check your phone to complete payment.',
                'transactionId': transaction_id,
                'checkoutRequestID': checkout_id
            })
            
        except Exception as sdk_error:
            error_msg = str(sdk_error)
            print(f"SDK STK push error: {error_msg}", file=sys.stderr)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payments SET status = 'failed', result_description = ?, updated_at = ?
                WHERE id = ?
            ''', (error_msg, datetime.now().isoformat(), payment_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': False, 'error': error_msg}), 400
            
    except Exception as e:
        print(f"Payment error: {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'error': 'An error occurred. Please try again.'}), 500

def determine_package_type(bundle_name, amount):
    """Determine the package type from bundle name or amount"""
    if bundle_name:
        bundle_lower = bundle_name.lower()
        if 'golden' in bundle_lower or 'gold' in bundle_lower:
            return 'golden'
        elif 'premium' in bundle_lower:
            return 'premium'
        elif 'standard' in bundle_lower:
            return 'standard'
    
    if amount:
        amount = float(amount)
        if amount >= 499:
            return 'golden'
        elif amount >= 299:
            return 'premium'
        else:
            return 'standard'
    
    return 'standard'

def grant_access_for_payment(payment_id, phone_number, bundle_name, amount):
    """Grant user access for a completed payment"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM user_access 
        WHERE payment_id = ?
    ''', (payment_id,))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return False
    
    package_type = determine_package_type(bundle_name, amount)
    
    cursor.execute('''
        INSERT INTO user_access (phone_number, package_type, payment_id, is_active)
        VALUES (?, ?, ?, 1)
    ''', (phone_number, package_type, payment_id))
    conn.commit()
    conn.close()
    
    print(f"ACCESS GRANTED: {phone_number} -> {package_type} package (Payment ID: {payment_id})", file=sys.stderr)
    return True

@app.route('/functions/v1/check-payment-status', methods=['POST', 'OPTIONS'])
def supabase_compat_check_status():
    if request.method == 'OPTIONS':
        return jsonify({})
    
    try:
        data = request.get_json() or {}
        
        print(f"Full check-status request body: {json.dumps(data)}", file=sys.stderr)
        
        checkout_id = data.get('checkoutRequestID') or data.get('checkoutRequestId') or data.get('checkout_request_id')
        transaction_id = data.get('transactionId') or data.get('transaction_id')
        phone = data.get('phone') or data.get('phoneNumber') or data.get('phone_number')
        payment_id = data.get('paymentId') or data.get('payment_id')
        
        print(f"Check status request - checkout_id: {checkout_id}, transaction_id: {transaction_id}, phone: {phone}, payment_id: {payment_id}", file=sys.stderr)
        
        def is_valid(val):
            return val and val not in ['null', 'undefined', 'None', '']
        
        has_identifier = is_valid(checkout_id) or is_valid(transaction_id) or is_valid(phone) or is_valid(payment_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        payment = None
        
        if is_valid(payment_id):
            cursor.execute('''
                SELECT id, phone_number, amount, bundle_name, status, transaction_id,
                       mpesa_receipt_number, result_description, created_at
                FROM payments 
                WHERE id = ?
            ''', (payment_id,))
            payment = cursor.fetchone()
        
        if not payment and is_valid(checkout_id):
            cursor.execute('''
                SELECT id, phone_number, amount, bundle_name, status, transaction_id,
                       mpesa_receipt_number, result_description, created_at
                FROM payments 
                WHERE checkout_request_id = ?
            ''', (checkout_id,))
            payment = cursor.fetchone()
        
        if not payment and is_valid(transaction_id):
            cursor.execute('''
                SELECT id, phone_number, amount, bundle_name, status, transaction_id,
                       mpesa_receipt_number, result_description, created_at
                FROM payments 
                WHERE transaction_id = ?
            ''', (transaction_id,))
            payment = cursor.fetchone()
        
        if not payment and is_valid(phone):
            formatted_phone = format_phone_number(phone)
            if formatted_phone:
                cursor.execute('''
                    SELECT id, phone_number, amount, bundle_name, status, transaction_id,
                           mpesa_receipt_number, result_description, created_at
                    FROM payments 
                    WHERE phone_number = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (formatted_phone,))
                payment = cursor.fetchone()
        
        if not payment and not has_identifier:
            print("No identifier provided, falling back to most recent payment", file=sys.stderr)
            cursor.execute('''
                SELECT id, phone_number, amount, bundle_name, status, transaction_id,
                       mpesa_receipt_number, result_description, created_at
                FROM payments 
                WHERE status IN ('pending', 'processing', 'completed')
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            payment = cursor.fetchone()
            if payment:
                print(f"Found fallback payment: ID={payment['id']}, status={payment['status']}", file=sys.stderr)
        
        if not payment:
            conn.close()
            return jsonify({'success': False, 'error': 'Payment not found'}), 404
        
        current_status = payment['status']
        db_transaction_id = payment['transaction_id']
        
        if current_status in ['pending', 'processing'] and db_transaction_id:
            new_status = None
            mpesa_receipt = None
            
            if lipana_client:
                try:
                    print(f"Querying Lipana SDK for transaction status: {db_transaction_id}", file=sys.stderr)
                    status_response = lipana_client.transactions.retrieve(db_transaction_id)
                    print(f"Lipana SDK response: {status_response}", file=sys.stderr)
                    
                    lipana_status = status_response.get('status', '').lower()
                    mpesa_receipt = status_response.get('mpesaReceiptNumber') or status_response.get('receipt')
                    
                    if lipana_status == 'success' or lipana_status == 'completed':
                        new_status = 'completed'
                    elif lipana_status == 'failed' or lipana_status == 'cancelled':
                        new_status = 'failed'
                        
                except Exception as sdk_error:
                    print(f"SDK error, trying direct API: {str(sdk_error)}", file=sys.stderr)
            
            if not new_status and api_key:
                try:
                    print(f"Querying Lipana transactions list for: {db_transaction_id}", file=sys.stderr)
                    headers = {
                        'x-api-key': api_key,
                        'Content-Type': 'application/json'
                    }
                    api_url = "https://api.lipana.dev/v1/transactions"
                    response = requests.get(api_url, headers=headers, timeout=15)
                    print(f"Lipana API response status: {response.status_code}", file=sys.stderr)
                    
                    if response.status_code == 200:
                        api_response = response.json()
                        transactions = api_response.get('data', [])
                        
                        for txn in transactions:
                            if txn.get('transactionId') == db_transaction_id:
                                print(f"Found transaction in list: {txn}", file=sys.stderr)
                                lipana_status = txn.get('status', '').lower()
                                metadata = txn.get('metadata', {})
                                mpesa_receipt = metadata.get('mpesaReceiptNumber') or txn.get('mpesaReceiptNumber')
                                
                                if lipana_status == 'success' or lipana_status == 'completed':
                                    new_status = 'completed'
                                elif lipana_status == 'failed' or lipana_status == 'cancelled':
                                    new_status = 'failed'
                                break
                except Exception as api_error:
                    print(f"Direct API error: {str(api_error)}", file=sys.stderr)
            
            if new_status and new_status != current_status:
                cursor.execute('''
                    UPDATE payments 
                    SET status = ?, mpesa_receipt_number = ?, updated_at = ?
                    WHERE id = ?
                ''', (new_status, mpesa_receipt, datetime.now().isoformat(), payment['id']))
                conn.commit()
                current_status = new_status
                print(f"Payment status updated to: {new_status}", file=sys.stderr)
                
                if new_status == 'completed':
                    grant_access_for_payment(
                        payment['id'],
                        payment['phone_number'],
                        payment['bundle_name'],
                        payment['amount']
                    )
        
        cursor.execute('''
            SELECT id, phone_number, amount, bundle_name, status, 
                   mpesa_receipt_number, result_description, created_at
            FROM payments 
            WHERE id = ?
        ''', (payment['id'],))
        updated_payment = cursor.fetchone()
        
        has_access = False
        package_type = None
        if updated_payment['status'] == 'completed':
            package_type = get_user_package(updated_payment['phone_number'])
            has_access = package_type is not None
        
        conn.close()
        
        return jsonify({
            'success': True,
            'payment': {
                'id': updated_payment['id'],
                'phone': updated_payment['phone_number'],
                'amount': updated_payment['amount'],
                'bundleName': updated_payment['bundle_name'],
                'status': updated_payment['status'],
                'mpesaReceiptNumber': updated_payment['mpesa_receipt_number'],
                'resultDesc': updated_payment['result_description'],
                'createdAt': updated_payment['created_at']
            },
            'access': {
                'granted': has_access,
                'packageType': package_type
            }
        })
        
    except Exception as e:
        print(f"Check status error: {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'error': str(e)}), 500

def verify_lipana_signature(payload, signature):
    webhook_secret = os.environ.get('LIPANA_WEBHOOK_SECRET', '')
    if not webhook_secret:
        print("WARNING: LIPANA_WEBHOOK_SECRET is not configured. Webhook signature verification disabled.")
        print("For production, please set LIPANA_WEBHOOK_SECRET to enable signature verification.")
        return True
    
    if not signature:
        print("ERROR: No signature provided in webhook request")
        return False
    
    try:
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            print(f"ERROR: Webhook signature mismatch")
        return is_valid
    except Exception as e:
        print(f"ERROR: Signature verification failed: {str(e)}")
        return False

@app.route('/api/payment/callback', methods=['POST'])
def payment_callback():
    try:
        signature = request.headers.get('X-Lipana-Signature', '')
        raw_payload = request.get_data()
        
        if not verify_lipana_signature(raw_payload, signature):
            print("Webhook signature verification failed")
            return jsonify({'status': 'error', 'message': 'Invalid signature'}), 401
        
        data = request.get_json()
        print(f"Callback received: {json.dumps(data, indent=2)}")
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        event_type = data.get('event', '')
        payment_data = data.get('data', data)
        
        transaction_id = payment_data.get('transactionId') or payment_data.get('transaction_id')
        checkout_request_id = payment_data.get('checkoutRequestID') or payment_data.get('checkoutRequestId') or payment_data.get('checkout_request_id')
        payment_status = payment_data.get('status', '')
        amount = payment_data.get('amount')
        phone = payment_data.get('phone')
        
        print(f"Webhook event: {event_type}, transaction_id: {transaction_id}, status: {payment_status}", file=sys.stderr)
        
        body = data.get('Body', {})
        stk_callback = body.get('stkCallback', {})
        if stk_callback:
            checkout_request_id = checkout_request_id or stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc', '')
            
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])
            
            mpesa_receipt = None
            for item in items:
                name = item.get('Name', '')
                value = item.get('Value')
                if name == 'MpesaReceiptNumber':
                    mpesa_receipt = value
            
            db_status = 'completed' if result_code == 0 else 'failed'
        else:
            mpesa_receipt = None
            result_desc = ''
            
            if event_type in ['payment.success', 'transaction.success'] or payment_status == 'success':
                db_status = 'completed'
            elif event_type in ['payment.failed', 'transaction.failed'] or payment_status == 'failed':
                db_status = 'failed'
            elif event_type == 'payout.initiated':
                return jsonify({'status': 'success', 'message': 'Payout event ignored'})
            else:
                db_status = 'pending'
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        payment_record = None
        if checkout_request_id:
            cursor.execute('''
                UPDATE payments 
                SET status = ?, result_description = ?, 
                    mpesa_receipt_number = ?, updated_at = ?
                WHERE checkout_request_id = ?
            ''', (db_status, result_desc, mpesa_receipt, 
                  datetime.now().isoformat(), checkout_request_id))
            cursor.execute('SELECT id, phone_number, bundle_name FROM payments WHERE checkout_request_id = ?', (checkout_request_id,))
            payment_record = cursor.fetchone()
        elif transaction_id:
            cursor.execute('''
                UPDATE payments 
                SET status = ?, result_description = ?, 
                    mpesa_receipt_number = ?, updated_at = ?
                WHERE transaction_id = ?
            ''', (db_status, result_desc, mpesa_receipt, 
                  datetime.now().isoformat(), transaction_id))
            cursor.execute('SELECT id, phone_number, bundle_name FROM payments WHERE transaction_id = ?', (transaction_id,))
            payment_record = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        if db_status == 'completed' and payment_record:
            conn2 = get_db_connection()
            cursor2 = conn2.cursor()
            cursor2.execute('SELECT amount FROM payments WHERE id = ?', (payment_record['id'],))
            payment_amount = cursor2.fetchone()
            conn2.close()
            
            grant_access_for_payment(
                payment_record['id'],
                payment_record['phone_number'],
                payment_record['bundle_name'],
                payment_amount['amount'] if payment_amount else None
            )
        
        print(f"Payment updated to {db_status}", file=sys.stderr)
        
        return jsonify({'status': 'success', 'message': 'Callback processed'})
        
    except Exception as e:
        print(f"Callback error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/payment/status/<checkout_id>', methods=['GET'])
def check_payment_status(checkout_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, phone_number, amount, bundle_name, status, 
                   mpesa_receipt_number, result_description, created_at
            FROM payments 
            WHERE checkout_request_id = ?
        ''', (checkout_id,))
        
        payment = cursor.fetchone()
        conn.close()
        
        if not payment:
            return jsonify({'success': False, 'error': 'Payment not found'}), 404
        
        return jsonify({
            'success': True,
            'payment': {
                'id': payment['id'],
                'phone': payment['phone_number'],
                'amount': payment['amount'],
                'bundleName': payment['bundle_name'],
                'status': payment['status'],
                'receipt': payment['mpesa_receipt_number'],
                'message': payment['result_description'],
                'createdAt': payment['created_at']
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/payments', methods=['GET'])
def get_all_payments():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, phone_number, amount, bundle_name, status, 
                   mpesa_receipt_number, checkout_request_id, created_at
            FROM payments 
            ORDER BY created_at DESC
            LIMIT 100
        ''')
        
        payments = cursor.fetchall()
        conn.close()
        
        payment_list = []
        for p in payments:
            payment_list.append({
                'id': p['id'],
                'phone': p['phone_number'],
                'amount': p['amount'],
                'bundleName': p['bundle_name'],
                'status': p['status'],
                'receipt': p['mpesa_receipt_number'],
                'checkoutId': p['checkout_request_id'],
                'createdAt': p['created_at']
            })
        
        return jsonify({'success': True, 'payments': payment_list})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/packages', methods=['GET'])
def get_packages():
    """Get all available packages with their features"""
    packages_list = []
    for pkg_id, pkg_data in PACKAGES.items():
        packages_list.append({
            'id': pkg_id,
            'name': pkg_data['name'],
            'price': pkg_data['price'],
            'description': pkg_data['description'],
            'features': [
                {
                    'key': key,
                    'label': FEATURE_LABELS.get(key, key),
                    'included': value
                }
                for key, value in pkg_data['features'].items()
            ]
        })
    return jsonify({'success': True, 'packages': packages_list})

@app.route('/api/user/access', methods=['POST'])
def check_user_access():
    """Check user's access level and available features"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        
        if not phone:
            return jsonify({'success': False, 'error': 'Phone number required'}), 400
        
        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            return jsonify({'success': False, 'error': 'Invalid phone number'}), 400
        
        package_type = get_user_package(formatted_phone)
        
        if not package_type:
            return jsonify({
                'success': True,
                'hasAccess': False,
                'message': 'No active package found. Please purchase a package to access CRB reports.'
            })
        
        package = PACKAGES.get(package_type, PACKAGES['standard'])
        
        features_list = [
            {
                'key': key,
                'label': FEATURE_LABELS.get(key, key),
                'unlocked': value,
                'upgradeRequired': not value
            }
            for key, value in package['features'].items()
        ]
        
        upgrade_options = []
        if package_type == 'standard':
            upgrade_options = [
                {
                    'packageId': 'premium',
                    'name': PACKAGES['premium']['name'],
                    'price': PACKAGES['premium']['price'],
                    'upgradeCost': PACKAGES['premium']['price'] - package['price']
                },
                {
                    'packageId': 'golden',
                    'name': PACKAGES['golden']['name'],
                    'price': PACKAGES['golden']['price'],
                    'upgradeCost': PACKAGES['golden']['price'] - package['price']
                }
            ]
        elif package_type == 'premium':
            upgrade_options = [
                {
                    'packageId': 'golden',
                    'name': PACKAGES['golden']['name'],
                    'price': PACKAGES['golden']['price'],
                    'upgradeCost': PACKAGES['golden']['price'] - package['price']
                }
            ]
        
        return jsonify({
            'success': True,
            'hasAccess': True,
            'package': {
                'id': package_type,
                'name': package['name'],
                'description': package['description']
            },
            'features': features_list,
            'upgradeOptions': upgrade_options
        })
        
    except Exception as e:
        print(f"Access check error: {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/crb/report', methods=['POST'])
def get_crb_report():
    """Get CRB report based on user's package level"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        
        if not phone:
            return jsonify({'success': False, 'error': 'Phone number required'}), 400
        
        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            return jsonify({'success': False, 'error': 'Invalid phone number'}), 400
        
        package_type = get_user_package(formatted_phone)
        
        if not package_type:
            return jsonify({
                'success': False,
                'error': 'No active package. Please purchase a package to view your CRB report.'
            }), 403
        
        report = generate_crb_report(formatted_phone)
        package = PACKAGES.get(package_type, PACKAGES['standard'])
        features = package['features']
        
        response_data = {
            'success': True,
            'package': {
                'id': package_type,
                'name': package['name']
            },
            'report': {
                'phone': formatted_phone,
                'generatedAt': report.get('created_at')
            }
        }
        
        if features.get('credit_score'):
            response_data['report']['creditScore'] = report.get('credit_score')
        
        if features.get('crb_status'):
            response_data['report']['crbStatus'] = report.get('crb_status')
        
        if features.get('loan_eligibility'):
            response_data['report']['loanEligibility'] = report.get('loan_eligibility')
        
        if features.get('credit_history'):
            response_data['report']['creditHistory'] = json.loads(report.get('credit_history', '[]'))
        else:
            response_data['report']['creditHistory'] = None
            response_data['report']['creditHistoryLocked'] = True
        
        if features.get('detailed_analysis'):
            response_data['report']['detailedAnalysis'] = json.loads(report.get('detailed_analysis', '{}'))
        else:
            response_data['report']['detailedAnalysis'] = None
            response_data['report']['detailedAnalysisLocked'] = True
        
        if features.get('lender_recommendations'):
            response_data['report']['lenderRecommendations'] = json.loads(report.get('lender_recommendations', '[]'))
        else:
            response_data['report']['lenderRecommendations'] = None
            response_data['report']['lenderRecommendationsLocked'] = True
        
        response_data['report']['creditImprovementTipsLocked'] = not features.get('credit_improvement_tips')
        response_data['report']['disputeAssistanceLocked'] = not features.get('dispute_assistance')
        response_data['report']['prioritySupportLocked'] = not features.get('priority_support')
        response_data['report']['downloadReportLocked'] = not features.get('download_report')
        response_data['report']['directLendersLocked'] = not features.get('direct_lenders')
        
        upgrade_options = []
        if package_type == 'standard':
            upgrade_options = [
                {
                    'packageId': 'premium',
                    'name': PACKAGES['premium']['name'],
                    'price': PACKAGES['premium']['price'],
                    'upgradeCost': PACKAGES['premium']['price'] - package['price']
                },
                {
                    'packageId': 'golden',
                    'name': PACKAGES['golden']['name'],
                    'price': PACKAGES['golden']['price'],
                    'upgradeCost': PACKAGES['golden']['price'] - package['price']
                }
            ]
        elif package_type == 'premium':
            upgrade_options = [
                {
                    'packageId': 'golden',
                    'name': PACKAGES['golden']['name'],
                    'price': PACKAGES['golden']['price'],
                    'upgradeCost': PACKAGES['golden']['price'] - package['price']
                }
            ]
        
        response_data['upgradeOptions'] = upgrade_options
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"CRB report error: {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upgrade/initiate', methods=['POST', 'OPTIONS'])
def initiate_upgrade():
    """Initiate upgrade payment to a higher package"""
    if request.method == 'OPTIONS':
        return jsonify({})
    
    try:
        data = request.get_json()
        phone = data.get('phone')
        target_package = data.get('targetPackage')
        
        if not phone or not target_package:
            return jsonify({'success': False, 'error': 'Phone and target package required'}), 400
        
        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            return jsonify({'success': False, 'error': 'Invalid phone number'}), 400
        
        if target_package not in PACKAGES:
            return jsonify({'success': False, 'error': 'Invalid package'}), 400
        
        current_package = get_user_package(formatted_phone)
        target_pkg = PACKAGES[target_package]
        
        if current_package:
            current_pkg = PACKAGES.get(current_package, PACKAGES['standard'])
            amount = target_pkg['price'] - current_pkg['price']
            if amount <= 0:
                return jsonify({'success': False, 'error': 'Cannot downgrade package'}), 400
        else:
            amount = target_pkg['price']
        
        if not lipana_client:
            return jsonify({
                'success': False, 
                'error': 'Payment service not configured.'
            }), 500
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO payments (phone_number, amount, bundle_name, status)
            VALUES (?, ?, ?, 'pending')
        ''', (formatted_phone, amount, target_package))
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        phone_with_plus = f'+{formatted_phone}'
        
        try:
            stk_response = lipana_client.transactions.initiate_stk_push(
                phone=phone_with_plus,
                amount=int(amount)
            )
            
            checkout_id = stk_response.get('checkoutRequestID') or stk_response.get('checkoutRequestId')
            transaction_id = stk_response.get('transactionId')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payments 
                SET checkout_request_id = ?, transaction_id = ?, status = 'processing', updated_at = ?
                WHERE id = ?
            ''', (checkout_id, transaction_id, datetime.now().isoformat(), payment_id))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Upgrade to {target_pkg["name"]} initiated. Check your phone to complete payment of KES {amount}.',
                'paymentId': payment_id,
                'checkoutRequestId': checkout_id,
                'amount': amount,
                'targetPackage': target_package
            })
            
        except Exception as sdk_error:
            error_msg = str(sdk_error)
            print(f"Upgrade payment error: {error_msg}", file=sys.stderr)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payments SET status = 'failed', result_description = ?, updated_at = ?
                WHERE id = ?
            ''', (error_msg, datetime.now().isoformat(), payment_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': False, 'error': error_msg}), 400
            
    except Exception as e:
        print(f"Upgrade error: {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

@app.route('/api/stats/counter')
def get_stats_counter():
    """
    Returns the dynamic Kenyans counter that:
    - Starts at 10,000 every Sunday midnight (Kenya time)
    - Increases by 100 every hour
    """
    from datetime import timezone, timedelta
    
    # Kenya is UTC+3
    kenya_tz = timezone(timedelta(hours=3))
    now_kenya = datetime.now(kenya_tz)
    
    # Find last Sunday midnight in Kenya time
    days_since_sunday = now_kenya.weekday() + 1  # Monday=0, so we add 1 to get days since Sunday
    if days_since_sunday == 7:  # If today is Sunday
        days_since_sunday = 0
    
    last_sunday_midnight = now_kenya.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_sunday)
    
    # Calculate hours since last Sunday midnight
    time_diff = now_kenya - last_sunday_midnight
    hours_elapsed = int(time_diff.total_seconds() / 3600)
    
    # Calculate counter: starts at 10,000, increases by 100 every hour
    counter = 10000 + (hours_elapsed * 100)
    
    return jsonify({
        'success': True,
        'counter': counter,
        'formatted': f"{counter:,}+"
    })

@app.route('/favicon.ico')
def serve_favicon():
    return send_file('favicon.ico')

@app.route('/robots.txt')
def serve_robots():
    return send_file('robots.txt')

@app.route('/placeholder.svg')
def serve_placeholder():
    return send_file('placeholder.svg')

@app.route('/api/crb/download-report', methods=['POST'])
def download_crb_report():
    """Generate and download CRB report as PDF (Golden package only)"""
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        
        if not phone:
            return jsonify({'success': False, 'error': 'Phone number is required'}), 400
        
        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            return jsonify({'success': False, 'error': 'Invalid phone number'}), 400
        
        package_type = get_user_package(formatted_phone)
        if package_type != 'golden':
            return jsonify({'success': False, 'error': 'Golden package required to download reports'}), 403
        
        report_data = generate_crb_report(formatted_phone)
        
        from io import BytesIO
        from datetime import datetime
        
        pdf_content = generate_pdf_report(formatted_phone, report_data)
        
        buffer = BytesIO(pdf_content)
        buffer.seek(0)
        
        filename = f"CRB_Report_{formatted_phone}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Download report error: {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_pdf_report(phone, report_data):
    """Generate a simple PDF report"""
    from datetime import datetime
    
    credit_score = report_data.get('credit_score', 'N/A')
    crb_status = report_data.get('crb_status', 'N/A')
    loan_eligibility = report_data.get('loan_eligibility', 'N/A')
    credit_history_str = report_data.get('credit_history', '[]')
    detailed_analysis_str = report_data.get('detailed_analysis', '{}')
    lender_recs_str = report_data.get('lender_recommendations', '[]')
    
    try:
        credit_history = json.loads(credit_history_str) if isinstance(credit_history_str, str) else credit_history_str
    except:
        credit_history = []
    
    try:
        detailed_analysis = json.loads(detailed_analysis_str) if isinstance(detailed_analysis_str, str) else detailed_analysis_str
    except:
        detailed_analysis = {}
    
    try:
        lender_recommendations = json.loads(lender_recs_str) if isinstance(lender_recs_str, str) else lender_recs_str
    except:
        lender_recommendations = []
    
    pdf_lines = []
    pdf_lines.append("%PDF-1.4")
    pdf_lines.append("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    pdf_lines.append("2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
    pdf_lines.append("3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj")
    
    content_lines = [
        f"BT /F1 24 Tf 50 750 Td (MetroCheck CRB Report - Golden Package) Tj ET",
        f"BT /F1 12 Tf 50 720 Td (Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}) Tj ET",
        f"BT /F1 12 Tf 50 700 Td (Phone: {phone}) Tj ET",
        f"BT /F1 18 Tf 50 665 Td (Credit Score: {credit_score}) Tj ET",
        f"BT /F1 12 Tf 50 640 Td (CRB Status: {crb_status}) Tj ET",
        f"BT /F1 12 Tf 50 615 Td (Loan Eligibility: {loan_eligibility}) Tj ET",
        "BT /F1 14 Tf 50 580 Td (Credit Score History) Tj ET"
    ]
    
    y_pos = 555
    for item in credit_history[:6]:
        month = item.get('month', '')
        score = item.get('score', 0)
        line = f"BT /F1 10 Tf 50 {y_pos} Td ({month}: Score {score}) Tj ET"
        content_lines.append(line)
        y_pos -= 18
    
    content_lines.append(f"BT /F1 14 Tf 50 {y_pos - 15} Td (Detailed Credit Analysis) Tj ET")
    y_pos -= 35
    
    for key, value in detailed_analysis.items():
        label = key.replace('_', ' ').title()
        if key in ['payment_history', 'credit_utilization', 'credit_mix']:
            value = f"{value}%"
        elif key == 'credit_age':
            value = f"{value} years"
        elif key == 'recent_inquiries':
            value = f"{value} inquiries"
        line = f"BT /F1 10 Tf 50 {y_pos} Td ({label}: {value}) Tj ET"
        content_lines.append(line)
        y_pos -= 18
    
    content_lines.append(f"BT /F1 14 Tf 50 {y_pos - 15} Td (Recommended Lenders) Tj ET")
    y_pos -= 35
    
    for lender in lender_recommendations[:5]:
        name = lender.get('name', '')
        max_loan = lender.get('max_loan', 0)
        rate = lender.get('rate', '')
        line = f"BT /F1 10 Tf 50 {y_pos} Td ({name} - Up to KES {max_loan:,} at {rate}) Tj ET"
        content_lines.append(line)
        y_pos -= 18
    
    content_lines.append(f"BT /F1 10 Tf 50 100 Td (This report is provided by MetroCheck CRB Checker - Golden Premium Package) Tj ET")
    content_lines.append(f"BT /F1 8 Tf 50 80 Td (For disputes or inquiries, contact support@metrocheck.co.ke) Tj ET")
    
    stream_content = " ".join(content_lines)
    stream_length = len(stream_content)
    
    pdf_lines.append(f"4 0 obj << /Length {stream_length} >> stream")
    pdf_lines.append(stream_content)
    pdf_lines.append("endstream endobj")
    pdf_lines.append("5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    
    xref_pos = sum(len(line) + 1 for line in pdf_lines)
    pdf_lines.append("xref")
    pdf_lines.append("0 6")
    pdf_lines.append("0000000000 65535 f ")
    pdf_lines.append("0000000009 00000 n ")
    pdf_lines.append("0000000058 00000 n ")
    pdf_lines.append("0000000115 00000 n ")
    pdf_lines.append("0000000270 00000 n ")
    pdf_lines.append("0000000400 00000 n ")
    pdf_lines.append("trailer << /Size 6 /Root 1 0 R >>")
    pdf_lines.append("startxref")
    pdf_lines.append(str(xref_pos))
    pdf_lines.append("%%EOF")
    
    return "\n".join(pdf_lines).encode('latin-1')

@app.route('/api/lender/connect', methods=['POST'])
def connect_to_lender():
    """Connect user to a direct lender (Golden package only)"""
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        lender_id = data.get('lenderId', '').strip()
        
        if not phone or not lender_id:
            return jsonify({'success': False, 'error': 'Phone and lender ID are required'}), 400
        
        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            return jsonify({'success': False, 'error': 'Invalid phone number'}), 400
        
        package_type = get_user_package(formatted_phone)
        if package_type != 'golden':
            return jsonify({'success': False, 'error': 'Golden package required to connect with lenders'}), 403
        
        if lender_id not in DIRECT_LENDERS:
            return jsonify({'success': False, 'error': 'Invalid lender ID'}), 400
        
        lender = DIRECT_LENDERS[lender_id]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lender_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                lender_id TEXT NOT NULL,
                lender_name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT INTO lender_connections (phone_number, lender_id, lender_name)
            VALUES (?, ?, ?)
        ''', (formatted_phone, lender_id, lender['name']))
        
        conn.commit()
        conn.close()
        
        print(f"Lender connection: {formatted_phone} -> {lender['name']}", file=sys.stderr)
        
        return jsonify({
            'success': True,
            'message': f"Successfully connected to {lender['name']}. You will receive contact within 24 hours.",
            'lender': {
                'name': lender['name'],
                'type': lender['type'],
                'maxAmount': lender['max_amount'],
                'interestRate': lender['interest_rate']
            }
        })
        
    except Exception as e:
        print(f"Lender connection error: {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard')
def serve_dashboard():
    return send_file('dashboard.html')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    return send_file('index.html')

@app.after_request
def add_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    if request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
