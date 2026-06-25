from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from functools import wraps
from io import BytesIO
import os
import json
import random
import re
import csv
import traceback

app = Flask(__name__)

# ============== Configuration ==============
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'digiserve-super-secret-key-2026')
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    MONGO_URI = os.environ.get('MONGO_URI', "mongodb+srv://digiserve_admin:digiserve2324@digiserve-cluster.mrlhjs4.mongodb.net/digiserve?retryWrites=true&w=majority&appName=digiserve-cluster")
    
    UPLOAD_FOLDER = 'uploads/'
    DOCUMENT_FOLDER = 'uploads/documents/'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt'}
    
    ADMIN_PHONE = '9999999999'
    ADMIN_NAME = 'Administrator'
    ADMIN_EMAIL = 'admin@digiserve.com'
    ITEMS_PER_PAGE = 10
    
    COMPANY_NAME = 'DigiServe'
    COMPANY_TAGLINE = 'Your Trusted Digital Service Partner'
    CONTACT_PHONE = '9421456959'
    CONTACT_EMAIL = 'support@digiserve.com'

app.config.from_object(Config)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOCUMENT_FOLDER'], exist_ok=True)

# Initialize MongoDB
mongo = PyMongo(app)
db = mongo.db

print("=" * 60)
print("🚀 DigiServe Portal Initializing...")
print("=" * 60)

# ============== Helper Functions ==============

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_id(user_id):
    try:
        return db.users.find_one({'_id': ObjectId(user_id)})
    except:
        return None

def get_user_by_phone(phone):
    try:
        return db.users.find_one({'phone': phone})
    except:
        return None

def validate_phone(phone):
    return bool(re.match(r'^[6-9]\d{9}$', phone))

def validate_email(email):
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def generate_reference_number():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = random.randint(1000, 9999)
    return f'DS{timestamp}{random_part}'

def create_notification(user_id, request_id, title, message, type='info'):
    try:
        notification = {
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'request_id': str(request_id) if request_id else None,
            'title': title,
            'message': message,
            'type': type,
            'is_read': False,
            'created_at': datetime.now(timezone.utc)
        }
        result = db.notifications.insert_one(notification)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating notification: {e}")
        return None

def get_all_services(limit=None):
    try:
        query = {'is_active': True}
        services = list(db.services.find(query).sort('order', 1))
        if limit:
            services = services[:limit]
        for service in services:
            service['id'] = str(service['_id'])
        return services
    except Exception as e:
        print(f"Error getting services: {e}")
        return []

def get_service_by_slug(slug):
    try:
        return db.services.find_one({'slug': slug, 'is_active': True})
    except:
        return None

def get_service_by_id(service_id):
    try:
        return db.services.find_one({'_id': ObjectId(service_id)})
    except:
        return None

def auto_create_admin_user():
    try:
        existing_admin = db.users.find_one({'phone': Config.ADMIN_PHONE})
        if existing_admin:
            return existing_admin
        
        admin_user = {
            'name': Config.ADMIN_NAME,
            'phone': Config.ADMIN_PHONE,
            'email': Config.ADMIN_EMAIL,
            'role': 'admin',
            'is_active': True,
            'created_at': datetime.now(timezone.utc),
            'last_login': datetime.now(timezone.utc),
            'address': 'Admin Office',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001'
        }
        result = db.users.insert_one(admin_user)
        admin_user['_id'] = result.inserted_id
        print(f"✅ Auto-created admin user: {Config.ADMIN_PHONE}")
        return admin_user
    except Exception as e:
        print(f"Error auto-creating admin: {e}")
        return None

def init_db():
    print("📦 Initializing database...")
    
    try:
        db.command('ping')
        print("✅ MongoDB Atlas connected successfully!")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False
    
    try:
        db.users.create_index('phone', unique=True)
        db.users.create_index('email', sparse=True)
        db.services.create_index('slug', unique=True)
        db.services.create_index('category')
        db.service_requests.create_index('reference_number', unique=True)
        db.service_requests.create_index('user_id')
        db.service_requests.create_index('status')
        db.service_requests.create_index('submitted_at')
        db.notifications.create_index('user_id')
        db.notifications.create_index('created_at')
        print("✅ Indexes created successfully")
        
        auto_create_admin_user()
        
        if db.services.count_documents({}) == 0:
            default_services = [
                {
                    'category': 'scholarship',
                    'name': 'PMSSS Scholarship',
                    'slug': 'pmsss-scholarship',
                    'description': "Prime Minister's Special Scholarship Scheme for Jammu & Kashmir students.",
                    'icon': 'fas fa-graduation-cap',
                    'service_charge': 0,
                    'is_active': True,
                    'order': 1,
                    'created_at': datetime.now(timezone.utc)
                },
                {
                    'category': 'scholarship',
                    'name': 'Post Matric Scholarship',
                    'slug': 'post-matric-scholarship',
                    'description': 'Post Matric Scholarship for SC/ST/OBC students.',
                    'icon': 'fas fa-university',
                    'service_charge': 0,
                    'is_active': True,
                    'order': 2,
                    'created_at': datetime.now(timezone.utc)
                },
                {
                    'category': 'education',
                    'name': 'MHT-CET Application',
                    'slug': 'mht-cet-application',
                    'description': 'Maharashtra Common Entrance Test form filling assistance.',
                    'icon': 'fas fa-file-alt',
                    'service_charge': 800,
                    'is_active': True,
                    'order': 3,
                    'created_at': datetime.now(timezone.utc)
                },
                {
                    'category': 'document',
                    'name': 'PAN Card Application',
                    'slug': 'pan-card-application',
                    'description': 'Apply for new PAN card or request for reprint.',
                    'icon': 'fas fa-id-card',
                    'service_charge': 150,
                    'is_active': True,
                    'order': 4,
                    'created_at': datetime.now(timezone.utc)
                },
                {
                    'category': 'bill_payment',
                    'name': 'Electricity Bill Payment',
                    'slug': 'electricity-bill-payment',
                    'description': 'Pay your electricity bill online instantly.',
                    'icon': 'fas fa-lightbulb',
                    'service_charge': 0,
                    'is_active': True,
                    'order': 5,
                    'created_at': datetime.now(timezone.utc)
                },
                {
                    'category': 'exams',
                    'name': 'UPSC Civil Services Form',
                    'slug': 'upsc-civil-services',
                    'description': 'UPSC Civil Services Examination form filling assistance.',
                    'icon': 'fas fa-landmark',
                    'service_charge': 500,
                    'is_active': True,
                    'order': 6,
                    'created_at': datetime.now(timezone.utc)
                },
                {
                    'category': 'eseva',
                    'name': 'Birth Certificate',
                    'slug': 'birth-certificate',
                    'description': 'Apply for new birth certificate online.',
                    'icon': 'fas fa-baby-carriage',
                    'service_charge': 200,
                    'is_active': True,
                    'order': 7,
                    'created_at': datetime.now(timezone.utc)
                },
                {
                    'category': 'eseva',
                    'name': 'Income Certificate',
                    'slug': 'income-certificate',
                    'description': 'Apply for income certificate for government schemes.',
                    'icon': 'fas fa-file-invoice-dollar',
                    'service_charge': 100,
                    'is_active': True,
                    'order': 8,
                    'created_at': datetime.now(timezone.utc)
                }
            ]
            
            for service in default_services:
                db.services.insert_one(service)
                print(f"✅ Added service: {service['name']}")
        
        print("=" * 60)
        print("🚀 DigiServe Portal is ready!")
        print("📍 MongoDB Atlas: Connected")
        print("👑 Admin Login: 9999999999")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        traceback.print_exc()
        return False

# ============== Routes ==============

@app.route('/')
def index():
    try:
        services = get_all_services()
        featured_services = services[:6] if services else []
        
        total_users = db.users.count_documents({'role': 'user'})
        total_applications = db.service_requests.count_documents({})
        total_services = db.services.count_documents({'is_active': True})
        
        return render_template('index.html', 
                             services=featured_services,
                             all_services=services,
                             total_users=total_users,
                             total_applications=total_applications,
                             total_services=total_services)
    except Exception as e:
        print(f"Error loading index: {e}")
        return render_template('index.html', services=[], all_services=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        
        if not phone or not validate_phone(phone):
            flash('Please enter a valid 10-digit mobile number', 'danger')
            return redirect(url_for('login'))
        
        try:
            user = get_user_by_phone(phone)
            
            if user:
                session['user_id'] = str(user['_id'])
                session['user_name'] = user['name']
                session['user_role'] = user.get('role', 'user')
                session['user_phone'] = user['phone']
                session.permanent = True
                
                db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'last_login': datetime.now(timezone.utc)}}
                )
                
                flash(f'Welcome back, {user["name"]}!', 'success')
                
                if user.get('role') == 'admin':
                    return redirect(url_for('admin_panel'))
                
                redirect_service = session.pop('redirect_service', None)
                if redirect_service:
                    return redirect(url_for('service_detail', slug=redirect_service))
                return redirect(url_for('index'))
            
            else:
                session['registration_phone'] = phone
                flash('New user! Please complete registration.', 'info')
                return redirect(url_for('register'))
                
        except Exception as e:
            print(f"Login error: {e}")
            traceback.print_exc()
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    phone = session.get('registration_phone', '')
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip() or None
        
        if not name or len(name) < 2:
            flash('Please enter a valid name', 'danger')
            return redirect(url_for('register'))
        
        if not phone or not validate_phone(phone):
            flash('Please enter a valid 10-digit mobile number', 'danger')
            return redirect(url_for('register'))
        
        if email and not validate_email(email):
            flash('Please enter a valid email address', 'danger')
            return redirect(url_for('register'))
        
        try:
            existing_user = get_user_by_phone(phone)
            if existing_user:
                flash('Mobile number already registered. Please login.', 'info')
                return redirect(url_for('login'))
            
            new_user = {
                'name': name.title(),
                'phone': phone,
                'email': email,
                'role': 'user',
                'is_active': True,
                'created_at': datetime.now(timezone.utc),
                'last_login': datetime.now(timezone.utc),
                'address': request.form.get('address', '').strip() or None,
                'city': request.form.get('city', '').strip() or None,
                'state': request.form.get('state', '').strip() or None,
                'pincode': request.form.get('pincode', '').strip() or None
            }
            result = db.users.insert_one(new_user)
            
            session['user_id'] = str(result.inserted_id)
            session['user_name'] = name
            session['user_role'] = 'user'
            session['user_phone'] = phone
            session.permanent = True
            session.pop('registration_phone', None)
            
            create_notification(
                result.inserted_id,
                None,
                'Welcome to DigiServe! 🎉',
                f'Welcome {name}! Start exploring our services.',
                'success'
            )
            
            flash(f'Welcome to DigiServe, {name}!', 'success')
            
            redirect_service = session.pop('redirect_service', None)
            if redirect_service:
                return redirect(url_for('service_detail', slug=redirect_service))
            return redirect(url_for('index'))
            
        except Exception as e:
            print(f"Registration error: {e}")
            traceback.print_exc()
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('register'))
    
    return render_template('register.html', phone=phone)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/service/<slug>')
@login_required
def service_detail(slug):
    try:
        service = get_service_by_slug(slug)
        if not service:
            flash('Service not found', 'danger')
            return redirect(url_for('index'))
        
        service['id'] = str(service['_id'])
        user = get_user_by_id(session['user_id'])
        
        return render_template('service_detail.html', service=service, user=user)
    except Exception as e:
        print(f"Error loading service: {e}")
        flash('Unable to load service details.', 'danger')
        return redirect(url_for('index'))

@app.route('/submit-application', methods=['POST'])
@login_required
def submit_application():
    try:
        service_id = request.form.get('service_id')
        service = get_service_by_id(service_id)
        
        if not service:
            return jsonify({'success': False, 'message': 'Service not found'}), 404
        
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        dob = request.form.get('dob', '')
        gender = request.form.get('gender', '')
        category = request.form.get('category', '')
        additional_details = request.form.get('additional_details', '').strip()
        
        if not all([full_name, phone, address, city, state, pincode]):
            return jsonify({'success': False, 'message': 'Please fill all required fields'}), 400
        
        details_json = {
            'full_name': full_name,
            'phone': phone,
            'email': email,
            'address': address,
            'city': city,
            'state': state,
            'pincode': pincode,
            'dob': dob,
            'gender': gender,
            'category': category,
            'additional_details': additional_details,
            'submitted_by': session['user_name'],
            'submitted_phone': session['user_phone'],
            'submitted_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        details = json.dumps(details_json, indent=2)
        ref_number = generate_reference_number()
        
        request_data = {
            'user_id': ObjectId(session['user_id']),
            'service_id': ObjectId(service_id),
            'service_type': service['category'],
            'service_name': service['name'],
            'details': details,
            'amount': service.get('service_charge', 0),
            'payment_status': 'pending' if service.get('service_charge', 0) > 0 else 'completed',
            'status': 'pending',
            'reference_number': ref_number,
            'submitted_at': datetime.now(timezone.utc),
            'processed_at': None,
            'admin_remarks': None,
            'applicant_name': full_name,
            'applicant_phone': phone,
            'applicant_email': email,
            'applicant_address': address,
            'applicant_city': city,
            'applicant_state': state,
            'applicant_pincode': pincode,
            'additional_details': additional_details,
            'timeline': [
                {
                    'title': 'Application Submitted',
                    'description': f'Your application for {service["name"]} has been submitted successfully.',
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'completed': True
                }
            ]
        }
        
        result = db.service_requests.insert_one(request_data)
        request_id = result.inserted_id
        
        uploaded_docs = []
        files = request.files.getlist('documents')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
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
                uploaded_docs.append(original_filename)
        
        create_notification(
            ObjectId(session['user_id']),
            str(request_id),
            'Application Submitted ✅',
            f'Your application for {service["name"]} has been submitted. Reference: {ref_number}',
            'success'
        )
        
        admins = list(db.users.find({'role': 'admin'}))
        for admin in admins:
            create_notification(
                admin['_id'],
                str(request_id),
                'New Application Received 🆕',
                f'New application from {full_name} for {service["name"]}. Ref: {ref_number}',
                'info'
            )
        
        return jsonify({
            'success': True,
            'message': 'Application submitted successfully',
            'reference_number': ref_number,
            'amount': service.get('service_charge', 0),
            'requires_payment': service.get('service_charge', 0) > 0,
            'documents_uploaded': len(uploaded_docs)
        })
        
    except Exception as e:
        print(f"Error submitting request: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/my-applications')
@login_required
def my_applications():
    try:
        user = get_user_by_id(session['user_id'])
        return render_template('my_applications.html', user=user)
    except Exception as e:
        print(f"Error loading applications: {e}")
        flash('Unable to load your applications.', 'danger')
        return redirect(url_for('index'))

@app.route('/api/my-applications')
@login_required
def api_my_applications():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        status = request.args.get('status', 'all')
        search = request.args.get('search', '').strip()
        
        query = {'user_id': ObjectId(session['user_id'])}
        if status != 'all':
            query['status'] = status
        if search:
            query['$or'] = [
                {'reference_number': {'$regex': search, '$options': 'i'}},
                {'service_name': {'$regex': search, '$options': 'i'}},
                {'applicant_name': {'$regex': search, '$options': 'i'}}
            ]
        
        total = db.service_requests.count_documents(query)
        skip = (page - 1) * per_page
        
        requests_list = list(db.service_requests.find(query)
                           .sort('submitted_at', -1)
                           .skip(skip)
                           .limit(per_page))
        
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
                'applicant_name': req.get('applicant_name', 'N/A')
            })
        
        return jsonify({
            'applications': data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if per_page > 0 else 1
        })
    except Exception as e:
        print(f"Error fetching applications: {e}")
        return jsonify({'error': 'Unable to fetch applications'}), 500

@app.route('/application-details/<request_id>')
@login_required
def application_details(request_id):
    try:
        service_request = db.service_requests.find_one({'_id': ObjectId(request_id)})
        if not service_request:
            return jsonify({'error': 'Application not found'}), 404
        
        if str(service_request['user_id']) != session['user_id'] and session.get('user_role') != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        documents = list(db.request_documents.find({'request_id': ObjectId(request_id)}))
        
        for doc in documents:
            doc['id'] = str(doc['_id'])
            if isinstance(doc.get('uploaded_at'), datetime):
                doc['uploaded_at'] = doc['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        request_dict = {
            'id': str(service_request['_id']),
            'reference_number': service_request['reference_number'],
            'service_name': service_request['service_name'],
            'status': service_request['status'],
            'payment_status': service_request['payment_status'],
            'amount': service_request['amount'],
            'submitted_at': service_request['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(service_request['submitted_at'], datetime) else str(service_request['submitted_at']),
            'processed_at': service_request['processed_at'].strftime('%Y-%m-%d %H:%M:%S') if service_request.get('processed_at') and isinstance(service_request['processed_at'], datetime) else None,
            'admin_remarks': service_request.get('admin_remarks', ''),
            'applicant_name': service_request.get('applicant_name', ''),
            'applicant_phone': service_request.get('applicant_phone', ''),
            'applicant_email': service_request.get('applicant_email', ''),
            'applicant_address': service_request.get('applicant_address', ''),
            'applicant_city': service_request.get('applicant_city', ''),
            'applicant_state': service_request.get('applicant_state', ''),
            'applicant_pincode': service_request.get('applicant_pincode', ''),
            'additional_details': service_request.get('additional_details', ''),
            'timeline': service_request.get('timeline', [])
        }
        
        if service_request.get('details'):
            try:
                details_data = json.loads(service_request['details'])
                request_dict['details_data'] = details_data
            except:
                pass
        
        return jsonify({
            'application': request_dict,
            'documents': documents
        })
    except Exception as e:
        print(f"Error fetching application details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/track-application', methods=['GET', 'POST'])
def track_application():
    if request.method == 'POST':
        reference = request.form.get('reference', '').strip().upper()
        phone = request.form.get('phone', '').strip()
        
        if not reference or not phone:
            flash('Please enter both Reference Number and Phone Number', 'danger')
            return redirect(url_for('track_application'))
        
        try:
            app_data = db.service_requests.find_one({'reference_number': reference})
            if not app_data:
                flash('Application not found. Please check your reference number.', 'danger')
                return redirect(url_for('track_application'))
            
            if app_data.get('applicant_phone') != phone and str(app_data.get('user_id')) != session.get('user_id', ''):
                flash('Phone number does not match this application.', 'danger')
                return redirect(url_for('track_application'))
            
            return render_template('track_result.html', application=app_data)
            
        except Exception as e:
            print(f"Error tracking application: {e}")
            flash('Error tracking application. Please try again.', 'danger')
            return redirect(url_for('track_application'))
    
    return render_template('track_application.html')

@app.route('/check-status', methods=['POST'])
def check_status():
    try:
        data = request.get_json()
        reference = data.get('reference', '').strip().upper()
        phone = data.get('phone', '').strip()
        
        if not reference or not phone:
            return jsonify({'success': False, 'message': 'Please provide both reference number and phone'})
        
        app_data = db.service_requests.find_one({'reference_number': reference})
        if not app_data:
            return jsonify({'success': False, 'message': 'Application not found'})
        
        if app_data.get('applicant_phone') != phone:
            return jsonify({'success': False, 'message': 'Phone number does not match'})
        
        return jsonify({
            'success': True,
            'status': app_data['status'],
            'service_name': app_data['service_name'],
            'reference': app_data['reference_number'],
            'submitted_at': app_data['submitted_at'].strftime('%Y-%m-%d %H:%M') if isinstance(app_data['submitted_at'], datetime) else str(app_data['submitted_at'])
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
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
                'request_id': n.get('request_id'),
                'created_at': n['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'time_ago': format_time_ago(n.get('created_at'))
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return jsonify([])

def format_time_ago(dt):
    if not dt:
        return "Unknown"
    if isinstance(dt, datetime):
        now = datetime.now(timezone.utc)
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
    return str(dt)

@app.route('/notifications/mark-read/<notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    try:
        notification = db.notifications.find_one({'_id': ObjectId(notification_id)})
        if notification and str(notification['user_id']) == session['user_id']:
            db.notifications.update_one(
                {'_id': ObjectId(notification_id)},
                {'$set': {'is_read': True}}
            )
            return jsonify({'success': True})
        return jsonify({'error': 'Unauthorized'}), 403
    except Exception as e:
        print(f"Error marking notification: {e}")
        return jsonify({'error': 'Unable to mark notification as read'}), 500

@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    try:
        db.notifications.update_many(
            {'user_id': ObjectId(session['user_id']), 'is_read': False},
            {'$set': {'is_read': True}}
        )
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error marking all notifications: {e}")
        return jsonify({'error': 'Unable to mark notifications as read'}), 500

@app.route('/unread-count', methods=['GET'])
@login_required
def get_unread_count():
    try:
        count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        })
        return jsonify({'count': count})
    except:
        return jsonify({'count': 0})

@app.route('/user-profile', methods=['GET'])
@login_required
def get_user_profile():
    try:
        user = get_user_by_id(session['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({
            'name': user['name'],
            'phone': user['phone'],
            'email': user.get('email', ''),
            'address': user.get('address', ''),
            'city': user.get('city', ''),
            'state': user.get('state', ''),
            'pincode': user.get('pincode', '')
        })
    except Exception as e:
        return jsonify({'error': 'Unable to fetch profile'}), 500

@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.get_json()
        update_data = {}
        
        if 'email' in data:
            if data['email'] and not validate_email(data['email']):
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400
            update_data['email'] = data['email'] or None
        if 'address' in data:
            update_data['address'] = data['address'] or None
        if 'city' in data:
            update_data['city'] = data['city'] or None
        if 'state' in data:
            update_data['state'] = data['state'] or None
        if 'pincode' in data:
            update_data['pincode'] = data['pincode'] or None
        
        if update_data:
            db.users.update_one(
                {'_id': ObjectId(session['user_id'])},
                {'$set': update_data}
            )
        
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': 'Unable to update profile'}), 500

# ============== Admin Routes ==============

@app.route('/admin')
@login_required
def admin_panel():
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    try:
        total_requests = db.service_requests.count_documents({})
        pending_requests = db.service_requests.count_documents({'status': 'pending'})
        in_progress_requests = db.service_requests.count_documents({'status': 'in_progress'})
        completed_requests = db.service_requests.count_documents({'status': 'completed'})
        rejected_requests = db.service_requests.count_documents({'status': 'rejected'})
        
        total_users = db.users.count_documents({'role': 'user'})
        total_services = db.services.count_documents({'is_active': True})
        
        all_requests = list(db.service_requests.find().sort('submitted_at', -1))
        for req in all_requests:
            req['_id'] = str(req['_id'])
            user_data = get_user_by_id(req['user_id'])
            req['user'] = {'name': user_data['name'], 'phone': user_data['phone']} if user_data else None
        
        users = list(db.users.find())
        for u in users:
            u['_id'] = str(u['_id'])
        
        services = list(db.services.find())
        for s in services:
            s['_id'] = str(s['_id'])
        
        stats = {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'in_progress_requests': in_progress_requests,
            'completed_requests': completed_requests,
            'rejected_requests': rejected_requests,
            'total_users': total_users,
            'total_services': total_services
        }
        
        notifications = list(db.notifications.find(
            {'user_id': ObjectId(session['user_id'])}
        ).sort('created_at', -1).limit(20))
        
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        })
        
        return render_template('admin.html',
                             requests=all_requests,
                             users=users,
                             services=services,
                             stats=stats,
                             notifications=notifications,
                             unread_count=unread_count)
    except Exception as e:
        print(f"Error loading admin panel: {e}")
        traceback.print_exc()
        flash('Unable to load admin panel.', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/update-status/<request_id>', methods=['POST'])
@login_required
def update_status(request_id):
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
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
        
        status_titles = {
            'in_progress': 'Application Under Review',
            'completed': 'Application Approved ✅',
            'rejected': 'Application Update'
        }
        
        status_messages = {
            'in_progress': 'Your application has been received and is being processed.',
            'completed': 'Your application has been approved and processed successfully!',
            'rejected': 'Your application has been reviewed. Please check the remarks.'
        }
        
        title = status_titles.get(status, f'Status Updated: {status}')
        message = status_messages.get(status, f'Your application status has been updated to {status}')
        if remarks:
            message += f'\n\nRemarks: {remarks}'
        
        db.service_requests.update_one(
            {'_id': ObjectId(request_id)},
            {'$push': {
                'timeline': {
                    'title': title,
                    'description': message,
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'completed': status == 'completed'
                }
            }}
        )
        
        create_notification(
            service_request['user_id'],
            request_id,
            title,
            message,
            'success' if status == 'completed' else 'info'
        )
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/application-details/<request_id>')
@login_required
def admin_application_details(request_id):
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        service_request = db.service_requests.find_one({'_id': ObjectId(request_id)})
        if not service_request:
            return jsonify({'error': 'Application not found'}), 404
        
        documents = list(db.request_documents.find({'request_id': ObjectId(request_id)}))
        for doc in documents:
            doc['_id'] = str(doc['_id'])
            if isinstance(doc.get('uploaded_at'), datetime):
                doc['uploaded_at'] = doc['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        user_data = get_user_by_id(service_request['user_id'])
        
        request_dict = {
            'id': str(service_request['_id']),
            'reference_number': service_request['reference_number'],
            'service_name': service_request['service_name'],
            'service_type': service_request['service_type'],
            'status': service_request['status'],
            'payment_status': service_request['payment_status'],
            'amount': service_request['amount'],
            'submitted_at': service_request['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(service_request['submitted_at'], datetime) else str(service_request['submitted_at']),
            'processed_at': service_request['processed_at'].strftime('%Y-%m-%d %H:%M:%S') if service_request.get('processed_at') and isinstance(service_request['processed_at'], datetime) else None,
            'admin_remarks': service_request.get('admin_remarks', ''),
            'applicant_name': service_request.get('applicant_name', ''),
            'applicant_phone': service_request.get('applicant_phone', ''),
            'applicant_email': service_request.get('applicant_email', ''),
            'applicant_address': service_request.get('applicant_address', ''),
            'applicant_city': service_request.get('applicant_city', ''),
            'applicant_state': service_request.get('applicant_state', ''),
            'applicant_pincode': service_request.get('applicant_pincode', ''),
            'additional_details': service_request.get('additional_details', ''),
            'timeline': service_request.get('timeline', [])
        }
        
        if service_request.get('details'):
            try:
                details_data = json.loads(service_request['details'])
                request_dict['details_data'] = details_data
            except:
                pass
        
        return jsonify({
            'application': request_dict,
            'documents': documents,
            'user': {
                'name': user_data['name'] if user_data else 'N/A',
                'phone': user_data['phone'] if user_data else 'N/A',
                'email': user_data.get('email', 'N/A') if user_data else 'N/A'
            }
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

# ============== Health Check ==============

@app.route('/health')
def health_check():
    try:
        db.command('ping')
        db_status = 'connected'
    except:
        db_status = 'disconnected'
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# ============== Error Handlers ==============

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html', error_message=str(error)), 500

# ============== Application Entry Point ==============

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("DIGISERVE PORTAL")
    print("=" * 60)
    
    init_db()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"\n✅ Application started on port {port}!")
    print("=" * 60 + "\n")
    app.run(debug=debug, host='0.0.0.0', port=port)