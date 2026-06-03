from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from bson.errors import InvalidId
import os
import json
import random
import re
import qrcode
from io import BytesIO
import base64
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import threading
import time
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'digiserve-secret-key-2026')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# MongoDB Configuration - from environment variable
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/digiserve')
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['DOCUMENT_FOLDER'] = 'uploads/documents/'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Initialize MongoDB
mongo = PyMongo(app)
db = mongo.db

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOCUMENT_FOLDER'], exist_ok=True)

# ============== Helper Functions ==============

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def validate_aadhar(number):
    return bool(re.match(r'^[2-9]{1}[0-9]{3}[0-9]{4}[0-9]{4}$', number))

def validate_pan(number):
    return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', number))

def generate_qr_code(data):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()

def calculate_fees(service_charge, convenience_fee_percent=2, gst_percent=18):
    convenience_fee = (service_charge * convenience_fee_percent) / 100
    subtotal = service_charge + convenience_fee
    gst = (subtotal * gst_percent) / 100
    total = subtotal + gst
    return {
        'service_charge': round(service_charge, 2),
        'convenience_fee': round(convenience_fee, 2),
        'subtotal': round(subtotal, 2),
        'gst': round(gst, 2),
        'total': round(total, 2)
    }

def get_user_by_phone(phone):
    try:
        return db.users.find_one({'phone': phone})
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_user_by_id(user_id):
    try:
        return db.users.find_one({'_id': ObjectId(user_id)})
    except:
        return None

def get_service_by_id(service_id):
    try:
        return db.services.find_one({'_id': ObjectId(service_id)})
    except:
        return None

def get_service_by_slug(slug):
    try:
        return db.services.find_one({'slug': slug, 'is_active': True})
    except:
        return None

def get_services_by_category():
    try:
        services = list(db.services.find({'is_active': True}))
        categorized = {}
        for service in services:
            category = service.get('category', 'other')
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(service)
        return categorized
    except:
        return {}

def create_notification(user_id, request_id, title, message, type='info'):
    try:
        notification = {
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'request_id': request_id,
            'title': title,
            'message': message,
            'type': type,
            'is_read': False,
            'created_at': datetime.now(timezone.utc)
        }
        result = db.notifications.insert_one(notification)
        return result.inserted_id
    except Exception as e:
        print(f"Error creating notification: {e}")
        return None

def format_time_ago(dt):
    if dt is None:
        return "Unknown"
    now = datetime.now(timezone.utc)
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    diff = now - dt
    if diff.days > 365:
        return f"{diff.days // 365} year(s) ago"
    elif diff.days > 30:
        return f"{diff.days // 30} month(s) ago"
    elif diff.days > 0:
        return f"{diff.days} day(s) ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hour(s) ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minute(s) ago"
    else:
        return "Just now"

def generate_reference_number():
    return f'DS{datetime.now().strftime("%Y%m%d%H%M%S")}{random.randint(1000, 9999)}'

def check_mongodb_connection():
    try:
        db.command('ping')
        return True
    except:
        return False

# ============== Initialize Database ==============

def init_db():
    print("=" * 50)
    print("Initializing DigiServe Database...")
    
    if not check_mongodb_connection():
        print("❌ MongoDB connection failed!")
        return False
    
    print("✅ MongoDB connected successfully!")
    
    try:
        # Create indexes
        db.users.create_index('phone', unique=True)
        db.services.create_index('slug', unique=True)
        db.service_requests.create_index('reference_number', unique=True)
        db.service_requests.create_index('user_id')
        db.service_requests.create_index('status')
        db.notifications.create_index('user_id')
        db.notifications.create_index('created_at')
        
        # Create admin user if not exists
        if not db.users.find_one({'phone': '9999999999'}):
            admin = {
                'name': 'Admin User',
                'phone': '9999999999',
                'role': 'admin',
                'is_active': True,
                'created_at': datetime.now(timezone.utc),
                'last_login': None,
                'address': None,
                'city': None,
                'state': None,
                'pincode': None
            }
            db.users.insert_one(admin)
            print("✅ Admin user created!")
        
        # Create default services
        default_services = [
            {
                'category': 'scholarship',
                'name': 'PMSSS Scholarship Application',
                'slug': 'pmsss-scholarship',
                'description': 'Prime Minister\'s Special Scholarship Scheme for Jammu and Kashmir students.',
                'eligibility': 'Students who have passed 10+2 examination from J&K board.',
                'documents_required': '10th Marksheet, 12th Marksheet, Domicile Certificate, Income Certificate',
                'instructions': 'Fill all details carefully.',
                'processing_time': '15-20 working days',
                'service_charge': 0,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-graduation-cap',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'education',
                'name': 'MHT-CET Application Form',
                'slug': 'mht-cet-application',
                'description': 'Maharashtra Common Entrance Test.',
                'eligibility': 'Indian citizen, passed 10+2 with PCM/PCB',
                'documents_required': '10th Marksheet, 12th Marksheet, Domicile Certificate',
                'instructions': 'Fill the form carefully.',
                'processing_time': 'Same day processing',
                'service_charge': 800,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-file-alt',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'document',
                'name': 'PAN Card Application',
                'slug': 'pan-card-application',
                'description': 'Apply for new PAN card.',
                'eligibility': 'Indian citizen with valid address proof.',
                'documents_required': 'Aadhar Card, Address Proof, Photo',
                'instructions': 'Use clear photograph.',
                'processing_time': '15-20 working days',
                'service_charge': 150,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-id-card',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'bill_payment',
                'name': 'Electricity Bill Payment',
                'slug': 'electricity-bill-payment',
                'description': 'Pay your electricity bill online.',
                'eligibility': 'Valid electricity consumer number.',
                'documents_required': 'Consumer Number',
                'instructions': 'Enter correct consumer number.',
                'processing_time': 'Instant',
                'service_charge': 0,
                'convenience_fee_percent': 0,
                'gst_percent': 0,
                'is_active': True,
                'icon': 'fas fa-lightbulb',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'exams',
                'name': 'UPSC Civil Services Form',
                'slug': 'upsc-civil-services',
                'description': 'UPSC Civil Services Examination.',
                'eligibility': 'Graduate in any discipline.',
                'documents_required': 'Graduation Certificate, DOB Proof, Photo',
                'instructions': 'Fill DAF carefully.',
                'processing_time': '2-3 working days',
                'service_charge': 500,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-landmark',
                'created_at': datetime.now(timezone.utc)
            }
        ]
        
        for service in default_services:
            if not db.services.find_one({'slug': service['slug']}):
                db.services.insert_one(service)
        
        print("=" * 50)
        print("🚀 DigiServe eSeva Portal is ready!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

# ============== Routes ==============

@app.route('/')
def index():
    try:
        services = list(db.services.find({'is_active': True}).limit(6))
        return render_template('index.html', services=services)
    except:
        return render_template('index.html', services=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        
        if not phone or len(phone) != 10 or not phone.isdigit():
            flash('Please enter a valid 10-digit mobile number', 'danger')
            return redirect(url_for('login'))
        
        try:
            user = get_user_by_phone(phone)
            
            if user:
                session['user_id'] = str(user['_id'])
                session['user_name'] = user['name']
                session['user_role'] = user['role']
                session['user_phone'] = user['phone']
                session.permanent = True
                
                db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'last_login': datetime.now(timezone.utc)}}
                )
                
                flash(f'Welcome back, {user["name"]}!', 'success')
                
                if user['role'] == 'admin':
                    return redirect(url_for('admin_panel'))
                else:
                    return redirect(url_for('services_dashboard'))
            else:
                flash('New mobile number! Please complete registration.', 'info')
                return redirect(url_for('register', phone=phone))
        except Exception as e:
            print(f"Error in login: {e}")
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    phone = request.args.get('phone', '')
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip() or None
        city = request.form.get('city', '').strip() or None
        state = request.form.get('state', '').strip() or None
        pincode = request.form.get('pincode', '').strip() or None
        
        if not name or not phone:
            flash('Name and mobile number are required', 'danger')
            return redirect(url_for('register', phone=phone))
        
        try:
            existing_user = get_user_by_phone(phone)
            if existing_user:
                flash('Mobile number already registered. Please login.', 'info')
                return redirect(url_for('login'))
            
            new_user = {
                'name': name,
                'phone': phone,
                'role': 'user',
                'is_active': True,
                'created_at': datetime.now(timezone.utc),
                'last_login': None,
                'address': address,
                'city': city,
                'state': state,
                'pincode': pincode
            }
            result = db.users.insert_one(new_user)
            
            session['user_id'] = str(result.inserted_id)
            session['user_name'] = name
            session['user_role'] = 'user'
            session['user_phone'] = phone
            session.permanent = True
            
            create_notification(
                result.inserted_id,
                None,
                'Welcome to DigiServe!',
                f'Welcome {name}! Thank you for registering.',
                'success'
            )
            
            flash('Registration successful! Welcome to DigiServe!', 'success')
            return redirect(url_for('services_dashboard'))
        except Exception as e:
            print(f"Error in registration: {e}")
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('register', phone=phone))
    
    return render_template('register.html', phone=phone)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/services-dashboard')
def services_dashboard():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    try:
        user = get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('login'))
        
        categorized_services = get_services_by_category()
        
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        })
        
        return render_template('services_dashboard.html', 
                             user=user, 
                             services=categorized_services, 
                             unread_count=unread_count)
    except Exception as e:
        print(f"Error: {e}")
        flash('Unable to load services.', 'danger')
        return redirect(url_for('index'))

@app.route('/service/<slug>')
def service_detail(slug):
    if 'user_id' not in session:
        session['redirect_after_login'] = url_for('service_detail', slug=slug)
        flash('Please login to access this service', 'warning')
        return redirect(url_for('login'))
    
    try:
        service = get_service_by_slug(slug)
        if not service:
            flash('Service not found', 'danger')
            return redirect(url_for('services_dashboard'))
        
        user = get_user_by_id(session['user_id'])
        
        return render_template('service_detail.html', service=service, user=user)
    except Exception as e:
        print(f"Error: {e}")
        flash('Unable to load service details.', 'danger')
        return redirect(url_for('services_dashboard'))

@app.route('/calculate-fees', methods=['POST'])
def calculate_fees_api():
    try:
        data = request.get_json()
        service_charge = float(data.get('service_charge', 0))
        convenience_fee_percent = float(data.get('convenience_fee_percent', 2))
        gst_percent = float(data.get('gst_percent', 18))
        
        result = calculate_fees(service_charge, convenience_fee_percent, gst_percent)
        return jsonify({'success': True, 'fees': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/submit-service-request', methods=['POST'])
def submit_service_request():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login'}), 401
    
    try:
        service_id = request.form.get('service_id')
        user = get_user_by_id(session['user_id'])
        service = get_service_by_id(service_id)
        
        if not service:
            return jsonify({'success': False, 'message': 'Service not found'}), 404
        
        full_name = request.form.get('full_name', '')
        dob = request.form.get('dob', '')
        gender = request.form.get('gender', '')
        category = request.form.get('category', '')
        address = request.form.get('address', '')
        city = request.form.get('city', '')
        state = request.form.get('state', '')
        pincode = request.form.get('pincode', '')
        additional_details = request.form.get('additional_details', '')
        
        service_charge = service.get('service_charge', 0)
        convenience_fee_percent = service.get('convenience_fee_percent', 2)
        gst_percent = service.get('gst_percent', 18)
        fee_details = calculate_fees(service_charge, convenience_fee_percent, gst_percent)
        
        details_json = {
            'full_name': full_name,
            'dob': dob,
            'gender': gender,
            'category': category,
            'address': address,
            'city': city,
            'state': state,
            'pincode': pincode,
            'additional_details': additional_details,
            'fee_details': fee_details,
            'submitted_by': user['name'],
            'submitted_phone': user['phone'],
            'submitted_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        details = json.dumps(details_json, indent=2)
        ref_number = generate_reference_number()
        
        request_data = {
            'user_id': ObjectId(session['user_id']),
            'service_id': ObjectId(service_id),
            'service_type': service['category'],
            'service_name': service['name'],
            'sub_service': None,
            'details': details,
            'amount': fee_details['total'],
            'payment_status': 'pending',
            'status': 'pending',
            'reference_number': ref_number,
            'submitted_at': datetime.now(timezone.utc),
            'processed_at': None,
            'admin_remarks': None,
            'applicant_name': full_name,
            'applicant_dob': dob,
            'applicant_gender': gender,
            'applicant_category': category,
            'applicant_address': address,
            'applicant_city': city,
            'applicant_state': state,
            'applicant_pincode': pincode,
            'additional_details': additional_details
        }
        
        result = db.service_requests.insert_one(request_data)
        request_id = result.inserted_id
        
        # Handle document uploads
        if 'documents' in request.files:
            files = request.files.getlist('documents')
            for file in files:
                if file and file.filename:
                    original_filename = secure_filename(file.filename)
                    file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'pdf'
                    stored_filename = f"{ref_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}.{file_ext}"
                    file_path = os.path.join(app.config['DOCUMENT_FOLDER'], stored_filename)
                    file.save(file_path)
                    
                    doc = {
                        'request_id': request_id,
                        'document_type': 'general',
                        'original_filename': original_filename,
                        'stored_filename': stored_filename,
                        'file_path': file_path,
                        'file_size': os.path.getsize(file_path),
                        'uploaded_at': datetime.now(timezone.utc)
                    }
                    db.request_documents.insert_one(doc)
        
        create_notification(
            ObjectId(session['user_id']),
            request_id,
            '✅ Application Submitted!',
            f'Your application for {service["name"]} has been submitted. Reference: {ref_number}',
            'success'
        )
        
        admins = list(db.users.find({'role': 'admin'}))
        for admin in admins:
            create_notification(
                admin['_id'],
                request_id,
                '🆕 New Application',
                f'New application from {full_name} for {service["name"]}',
                'info'
            )
        
        return jsonify({
            'success': True,
            'message': 'Application submitted successfully',
            'reference_number': ref_number,
            'amount': fee_details['total'],
            'fee_details': fee_details,
            'requires_payment': fee_details['total'] > 0
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/my-requests')
def my_requests_page():
    if 'user_id' not in session:
        flash('Please login to view your requests', 'warning')
        return redirect(url_for('login'))
    
    try:
        user = get_user_by_id(session['user_id'])
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        })
        
        return render_template('my_requests.html', user=user, unread_count=unread_count)
    except Exception as e:
        print(f"Error: {e}")
        flash('Unable to load your requests.', 'danger')
        return redirect(url_for('services_dashboard'))

@app.route('/api/my-requests')
def api_my_requests():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login'}), 401
    
    try:
        requests_list = list(db.service_requests.find(
            {'user_id': ObjectId(session['user_id'])}
        ).sort('submitted_at', -1))
        
        data = []
        for req in requests_list:
            data.append({
                'id': str(req['_id']),
                'reference': req['reference_number'],
                'service_name': req['service_name'],
                'status': req['status'],
                'payment_status': req['payment_status'],
                'amount': req['amount'],
                'submitted_at': req['submitted_at'].strftime('%Y-%m-%d %H:%M'),
                'documents_count': db.request_documents.count_documents({'request_id': req['_id']}),
                'applicant_name': req.get('applicant_name', '')
            })
        
        return jsonify(data)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Unable to fetch requests'}), 500

@app.route('/initiate-payment/<ref_number>', methods=['POST'])
def initiate_payment(ref_number):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login'}), 401
    
    try:
        service_request = db.service_requests.find_one({
            'reference_number': ref_number,
            'user_id': ObjectId(session['user_id'])
        })
        
        if not service_request:
            return jsonify({'success': False, 'message': 'Request not found'}), 404
        
        transaction_id = f'TXN{datetime.now().strftime("%Y%m%d%H%M%S")}{random.randint(1000,9999)}'
        
        payment = {
            'user_id': ObjectId(session['user_id']),
            'request_id': service_request['_id'],
            'transaction_id': transaction_id,
            'amount': service_request['amount'],
            'payment_method': 'online',
            'status': 'completed',
            'created_at': datetime.now(timezone.utc)
        }
        
        db.payment_transactions.insert_one(payment)
        db.service_requests.update_one(
            {'_id': service_request['_id']},
            {'$set': {
                'payment_status': 'completed',
                'status': 'in_progress'
            }}
        )
        
        create_notification(
            ObjectId(session['user_id']),
            service_request['_id'],
            '💰 Payment Successful!',
            f'Payment of ₹{service_request["amount"]} completed.',
            'success'
        )
        
        return jsonify({
            'success': True,
            'message': 'Payment successful!',
            'transaction_id': transaction_id
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': 'Payment failed.'}), 500

@app.route('/notifications')
def get_notifications():
    if 'user_id' not in session:
        return jsonify([])
    
    try:
        notifications = list(db.notifications.find(
            {'user_id': ObjectId(session['user_id'])}
        ).sort('created_at', -1).limit(50))
        
        result = []
        for n in notifications:
            result.append({
                'id': str(n['_id']),
                'title': n['title'],
                'message': n['message'],
                'type': n['type'],
                'is_read': n['is_read'],
                'request_id': str(n['request_id']) if n.get('request_id') else None,
                'created_at': n['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'time_ago': format_time_ago(n.get('created_at'))
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify([])

@app.route('/notifications/mark-read/<notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Please login'}), 401
    
    try:
        notification = db.notifications.find_one({'_id': ObjectId(notification_id)})
        if notification and notification['user_id'] == ObjectId(session['user_id']):
            db.notifications.update_one(
                {'_id': ObjectId(notification_id)},
                {'$set': {'is_read': True}}
            )
            return jsonify({'success': True})
        
        return jsonify({'error': 'Unauthorized'}), 403
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Unable to mark notification as read'}), 500

@app.route('/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login'}), 401
    
    try:
        db.notifications.update_many(
            {'user_id': ObjectId(session['user_id']), 'is_read': False},
            {'$set': {'is_read': True}}
        )
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Unable to mark notifications as read'}), 500

@app.route('/unread-count')
def unread_count():
    if 'user_id' not in session:
        return jsonify({'count': 0})
    
    try:
        count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        })
        return jsonify({'count': count})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'count': 0})

# ============== Admin Routes ==============

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    try:
        all_requests = list(db.service_requests.find().sort('submitted_at', -1))
        users = list(db.users.find())
        payments = list(db.payment_transactions.find().sort('created_at', -1))
        services = list(db.services.find())
        
        total_requests = db.service_requests.count_documents({})
        pending_requests = db.service_requests.count_documents({'status': 'pending'})
        completed_requests = db.service_requests.count_documents({'status': 'completed'})
        total_users = db.users.count_documents({'role': 'user'})
        
        revenue_pipeline = [
            {'$match': {'status': 'completed'}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ]
        revenue_result = list(db.payment_transactions.aggregate(revenue_pipeline))
        total_revenue = revenue_result[0]['total'] if revenue_result else 0
        
        admin_notifications = list(db.notifications.find(
            {'user_id': ObjectId(session['user_id'])}
        ).sort('created_at', -1).limit(20))
        
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        })
        
        stats = {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'completed_requests': completed_requests,
            'total_users': total_users,
            'total_revenue': total_revenue
        }
        
        return render_template('admin.html',
                             requests=all_requests,
                             users=users,
                             payments=payments,
                             services=services,
                             stats=stats,
                             notifications=admin_notifications,
                             unread_count=unread_count)
    except Exception as e:
        print(f"Error: {e}")
        flash('Unable to load admin panel.', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/update-status/<request_id>', methods=['POST'])
@admin_required
def update_status(request_id):
    try:
        data = request.get_json()
        status = data.get('status')
        remarks = data.get('remarks', '')
        
        service_request = db.service_requests.find_one({'_id': ObjectId(request_id)})
        
        if not service_request:
            return jsonify({'success': False, 'message': 'Request not found'}), 404
        
        db.service_requests.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {
                'status': status,
                'admin_remarks': remarks,
                'processed_at': datetime.now(timezone.utc)
            }}
        )
        
        status_messages = {
            'in_progress': 'Your application is now being processed.',
            'completed': 'Your application has been completed successfully!',
            'rejected': 'Your application has been reviewed.'
        }
        
        message = status_messages.get(status, f'Status updated to {status}')
        
        create_notification(
            service_request['user_id'],
            ObjectId(request_id),
            f'Status Updated: {status.upper()}',
            f'{message}\nReference: {service_request["reference_number"]}',
            'success' if status == 'completed' else 'info'
        )
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/request-details/<request_id>')
@admin_required
def admin_request_details(request_id):
    try:
        service_request = db.service_requests.find_one({'_id': ObjectId(request_id)})
        if not service_request:
            return jsonify({'error': 'Request not found'}), 404
        
        documents = list(db.request_documents.find({'request_id': ObjectId(request_id)}))
        user = get_user_by_id(service_request['user_id'])
        
        service_request['_id'] = str(service_request['_id'])
        if isinstance(service_request.get('submitted_at'), datetime):
            service_request['submitted_at'] = service_request['submitted_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            details_data = json.loads(service_request.get('details', '{}'))
        except:
            details_data = {}
        
        return jsonify({
            'request': service_request,
            'documents': documents,
            'user': user,
            'details_data': details_data
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/add-service', methods=['POST'])
@admin_required
def add_service():
    try:
        data = request.get_json()
        
        slug = data.get('name', '').lower().replace(' ', '-')
        slug = re.sub(r'[^a-z0-9-]', '', slug)
        
        service = {
            'category': data.get('category'),
            'name': data.get('name'),
            'slug': slug,
            'description': data.get('description'),
            'eligibility': data.get('eligibility'),
            'documents_required': data.get('documents_required'),
            'instructions': data.get('instructions'),
            'processing_time': data.get('processing_time'),
            'service_charge': float(data.get('service_charge', 0)),
            'convenience_fee_percent': float(data.get('convenience_fee_percent', 2)),
            'gst_percent': float(data.get('gst_percent', 18)),
            'is_active': True,
            'icon': data.get('icon', 'fas fa-file-alt'),
            'created_at': datetime.now(timezone.utc)
        }
        
        db.services.insert_one(service)
        
        users = list(db.users.find({'role': 'user'}))
        for user in users:
            create_notification(
                user['_id'],
                None,
                '🆕 New Service Added!',
                f'A new service "{data.get("name")}" has been added.',
                'info'
            )
        
        return jsonify({'success': True, 'message': 'Service added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/get-pending-count')
@admin_required
def get_pending_count():
    try:
        count = db.service_requests.count_documents({'status': 'pending'})
        return jsonify({'count': count})
    except:
        return jsonify({'count': 0})

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("DIGISERVE ESEVA PORTAL")
    print("=" * 60)
    
    if init_db():
        port = int(os.environ.get('PORT', 5000))
        print(f"\n✅ Application started successfully on port {port}!")
        print("=" * 60 + "\n")
        app.run(debug=False, host='0.0.0.0', port=port)
    else:
        print("\n❌ Failed to start application.")