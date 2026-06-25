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
import config

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(config.Config)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOCUMENT_FOLDER'], exist_ok=True)

# Initialize MongoDB
mongo = PyMongo(app)
db = mongo.db

# ============== Helper Functions ==============

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash('Admin access required', 'danger')
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

def get_all_services():
    try:
        return list(db.services.find({'is_active': True}).sort('created_at', 1))
    except:
        return []

def get_services_by_category():
    try:
        services = list(db.services.find({'is_active': True}).sort('created_at', 1))
        categorized = {}
        for service in services:
            category = service.get('category', 'other')
            if category not in categorized:
                categorized[category] = []
            service['id'] = str(service['_id'])
            categorized[category].append(service)
        return categorized
    except:
        return {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def create_notification(user_id, title, message, type='info', request_id=None):
    try:
        notification = {
            'user_id': ObjectId(user_id),
            'title': title,
            'message': message,
            'type': type,
            'request_id': str(request_id) if request_id else None,
            'is_read': False,
            'created_at': datetime.now(timezone.utc)
        }
        result = db.notifications.insert_one(notification)
        return str(result.inserted_id)
    except:
        return None

def auto_create_admin():
    """Create admin user if not exists"""
    try:
        existing = db.users.find_one({'phone': app.config['ADMIN_PHONE']})
        if existing:
            return existing
        
        admin = {
            'name': app.config['ADMIN_NAME'],
            'phone': app.config['ADMIN_PHONE'],
            'email': app.config['ADMIN_EMAIL'],
            'role': 'admin',
            'is_active': True,
            'address': 'Admin Office',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001',
            'created_at': datetime.now(timezone.utc),
            'last_login': None
        }
        result = db.users.insert_one(admin)
        admin['_id'] = result.inserted_id
        print(f"✅ Admin user created: {app.config['ADMIN_PHONE']}")
        return admin
    except Exception as e:
        print(f"Error creating admin: {e}")
        return None

def init_db():
    """Initialize database with indexes and default data"""
    print("=" * 60)
    print("📦 Initializing Database...")
    
    try:
        db.command('ping')
        print("✅ MongoDB connected successfully!")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False
    
    try:
        # Create indexes
        db.users.create_index('phone', unique=True)
        db.users.create_index('email', sparse=True)
        db.services.create_index('slug', unique=True)
        db.service_requests.create_index('reference_number', unique=True)
        db.service_requests.create_index('user_id')
        db.service_requests.create_index('status')
        db.notifications.create_index('user_id')
        db.notifications.create_index('created_at')
        db.payment_transactions.create_index('transaction_id', unique=True)
        print("✅ Indexes created")
        
        # Create admin
        auto_create_admin()
        
        # Create default services if none exist
        if db.services.count_documents({}) == 0:
            default_services = [
                {
                    'category': 'scholarship',
                    'name': 'PMSSS Scholarship Application',
                    'description': "Prime Minister's Special Scholarship Scheme for Jammu and Kashmir students.",
                    'eligibility': 'Students who have passed 10+2 examination from J&K board with minimum 60% marks.',
                    'documents_required': '10th Marksheet, 12th Marksheet, Domicile Certificate, Income Certificate',
                    'instructions': 'Ensure all documents are self-attested. Upload clear scanned copies.',
                    'processing_time': '15-20 working days',
                    'service_charge': 0,
                    'convenience_fee_percent': 2,
                    'gst_percent': 18,
                    'icon': 'fas fa-graduation-cap'
                },
                {
                    'category': 'scholarship',
                    'name': 'Post Matric Scholarship',
                    'description': 'Post Matric Scholarship for SC/ST/OBC students.',
                    'eligibility': 'Students belonging to SC/ST/OBC categories with family income less than ₹2.5 LPA.',
                    'documents_required': 'Caste Certificate, Income Certificate, Previous Year Marksheet',
                    'instructions': 'Fill all details carefully. Upload income certificate for verification.',
                    'processing_time': '20-25 working days',
                    'service_charge': 0,
                    'convenience_fee_percent': 2,
                    'gst_percent': 18,
                    'icon': 'fas fa-university'
                },
                {
                    'category': 'education',
                    'name': 'MHT-CET Application Form',
                    'description': 'Maharashtra Common Entrance Test for Engineering and Pharmacy admissions.',
                    'eligibility': 'Indian citizen, passed 10+2 with PCM/PCB from recognized board.',
                    'documents_required': '10th Marksheet, 12th Marksheet, Domicile Certificate, Photo, Signature',
                    'instructions': 'Fill the form carefully. Double-check all entered information.',
                    'processing_time': 'Same day processing',
                    'service_charge': 800,
                    'convenience_fee_percent': 2,
                    'gst_percent': 18,
                    'icon': 'fas fa-file-alt'
                },
                {
                    'category': 'document',
                    'name': 'PAN Card Application',
                    'description': 'Apply for new PAN card or request for reprint.',
                    'eligibility': 'Indian citizen with valid address proof and identity proof.',
                    'documents_required': 'Aadhar Card, Address Proof, Passport Size Photo',
                    'instructions': 'Use clear photograph with white background.',
                    'processing_time': '15-20 working days',
                    'service_charge': 150,
                    'convenience_fee_percent': 2,
                    'gst_percent': 18,
                    'icon': 'fas fa-id-card'
                },
                {
                    'category': 'bill_payment',
                    'name': 'Electricity Bill Payment',
                    'description': 'Pay your electricity bill online instantly.',
                    'eligibility': 'Valid electricity consumer number',
                    'documents_required': 'Consumer Number',
                    'instructions': 'Enter correct consumer number as shown on your bill.',
                    'processing_time': 'Instant',
                    'service_charge': 0,
                    'convenience_fee_percent': 0,
                    'gst_percent': 0,
                    'icon': 'fas fa-lightbulb'
                },
                {
                    'category': 'exams',
                    'name': 'UPSC Civil Services Form',
                    'description': 'UPSC Civil Services Examination application form filling assistance.',
                    'eligibility': 'Graduate in any discipline from recognized university',
                    'documents_required': 'Graduation Certificate, Date of Birth Proof, Photo, Signature',
                    'instructions': 'Fill DAF carefully. Upload photo as per specifications.',
                    'processing_time': '2-3 working days',
                    'service_charge': 500,
                    'convenience_fee_percent': 2,
                    'gst_percent': 18,
                    'icon': 'fas fa-landmark'
                },
                {
                    'category': 'eseva',
                    'name': 'Birth Certificate Application',
                    'description': 'Apply for new birth certificate online.',
                    'eligibility': 'Birth registered within 21 days of occurrence',
                    'documents_required': 'Hospital Discharge Certificate, Parents ID Proof',
                    'instructions': 'Provide correct hospital name and date of birth.',
                    'processing_time': '7-10 working days',
                    'service_charge': 200,
                    'convenience_fee_percent': 2,
                    'gst_percent': 18,
                    'icon': 'fas fa-baby-carriage'
                },
                {
                    'category': 'eseva',
                    'name': 'Income Certificate Application',
                    'description': 'Apply for income certificate for scholarships and government schemes.',
                    'eligibility': 'Resident of the state with valid address proof.',
                    'documents_required': 'Aadhar Card, Address Proof, Previous Income Certificate',
                    'instructions': 'Provide correct income details from all sources.',
                    'processing_time': '10-15 working days',
                    'service_charge': 100,
                    'convenience_fee_percent': 2,
                    'gst_percent': 18,
                    'icon': 'fas fa-file-invoice-dollar'
                }
            ]
            
            for service_data in default_services:
                # Generate slug
                slug = service_data['name'].lower().strip()
                slug = re.sub(r'[^a-z0-9]+', '-', slug)
                slug = slug.strip('-')
                service_data['slug'] = slug
                service_data['is_active'] = True
                service_data['created_at'] = datetime.now(timezone.utc)
                db.services.insert_one(service_data)
                print(f"✅ Added service: {service_data['name']}")
        
        print("=" * 60)
        print("🚀 DigiServe Portal is ready!")
        print(f"👑 Admin Login: {app.config['ADMIN_PHONE']}")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        traceback.print_exc()
        return False

# ============== Routes ==============

@app.route('/')
def index():
    """Home page"""
    try:
        services = get_all_services()[:6]
        stats = {
            'total_users': db.users.count_documents({'role': 'user'}),
            'total_applications': db.service_requests.count_documents({}),
            'total_services': db.services.count_documents({'is_active': True})
        }
        return render_template('index.html', services=services, stats=stats)
    except Exception as e:
        print(f"Index error: {e}")
        return render_template('index.html', services=[], stats={'total_users': 0, 'total_applications': 0, 'total_services': 0})

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        
        if not phone or not re.match(r'^[6-9]\d{9}$', phone):
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
                return redirect(url_for('services_dashboard'))
            
            else:
                # Check if it's the admin number
                if phone == app.config['ADMIN_PHONE']:
                    admin = auto_create_admin()
                    if admin:
                        session['user_id'] = str(admin['_id'])
                        session['user_name'] = admin['name']
                        session['user_role'] = 'admin'
                        session['user_phone'] = admin['phone']
                        session.permanent = True
                        flash('Welcome, Administrator!', 'success')
                        return redirect(url_for('admin_panel'))
                
                flash('New number detected! Please complete registration.', 'info')
                return redirect(url_for('register', phone=phone))
                
        except Exception as e:
            print(f"Login error: {e}")
            traceback.print_exc()
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    phone = request.args.get('phone', '')
    
    if phone == app.config['ADMIN_PHONE']:
        flash('This is an administrator number. Please use admin login.', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip() or None
        address = request.form.get('address', '').strip() or None
        city = request.form.get('city', '').strip() or None
        state = request.form.get('state', '').strip() or None
        pincode = request.form.get('pincode', '').strip() or None
        
        if not name or len(name) < 2:
            flash('Please enter a valid name', 'danger')
            return redirect(url_for('register', phone=phone))
        
        if not phone or not re.match(r'^[6-9]\d{9}$', phone):
            flash('Please enter a valid mobile number', 'danger')
            return redirect(url_for('register', phone=phone))
        
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash('Please enter a valid email address', 'danger')
            return redirect(url_for('register', phone=phone))
        
        if pincode and not re.match(r'^\d{6}$', pincode):
            flash('Pincode must be 6 digits', 'danger')
            return redirect(url_for('register', phone=phone))
        
        try:
            existing = get_user_by_phone(phone)
            if existing:
                flash('Mobile number already registered. Please login.', 'info')
                return redirect(url_for('login'))
            
            new_user = {
                'name': name.title(),
                'phone': phone,
                'email': email,
                'role': 'user',
                'is_active': True,
                'address': address,
                'city': city,
                'state': state,
                'pincode': pincode,
                'created_at': datetime.now(timezone.utc),
                'last_login': datetime.now(timezone.utc)
            }
            result = db.users.insert_one(new_user)
            
            session['user_id'] = str(result.inserted_id)
            session['user_name'] = name
            session['user_role'] = 'user'
            session['user_phone'] = phone
            session.permanent = True
            
            create_notification(
                result.inserted_id,
                'Welcome to DigiServe! 🎉',
                f'Welcome {name}! Thank you for registering with DigiServe.',
                'success'
            )
            
            flash(f'Welcome to DigiServe, {name}!', 'success')
            return redirect(url_for('services_dashboard'))
            
        except Exception as e:
            print(f"Registration error: {e}")
            traceback.print_exc()
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('register', phone=phone))
    
    return render_template('register.html', phone=phone)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/services-dashboard')
@login_required
def services_dashboard():
    """Services dashboard for users"""
    try:
        user = get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('login'))
        
        services_by_category = get_services_by_category()
        
        # Get counts
        recent_count = db.service_requests.count_documents({
            'user_id': ObjectId(session['user_id'])
        })
        
        completed_count = db.service_requests.count_documents({
            'user_id': ObjectId(session['user_id']),
            'status': 'completed'
        })
        
        pending_count = db.service_requests.count_documents({
            'user_id': ObjectId(session['user_id']),
            'status': {'$in': ['pending', 'in_progress']}
        })
        
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        })
        
        return render_template('services_dashboard.html',
                             user=user,
                             services=services_by_category,
                             recent_count=recent_count,
                             completed_count=completed_count,
                             pending_count=pending_count,
                             unread_count=unread_count)
    except Exception as e:
        print(f"Dashboard error: {e}")
        flash('Unable to load dashboard. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/service/<slug>')
@login_required
def service_detail(slug):
    """Service detail page"""
    try:
        service = get_service_by_slug(slug)
        if not service:
            flash('Service not found', 'danger')
            return redirect(url_for('services_dashboard'))
        
        service['id'] = str(service['_id'])
        user = get_user_by_id(session['user_id'])
        
        return render_template('service_detail.html', service=service, user=user)
    except Exception as e:
        print(f"Service detail error: {e}")
        flash('Unable to load service details.', 'danger')
        return redirect(url_for('services_dashboard'))

@app.route('/submit-service-request', methods=['POST'])
@login_required
def submit_service_request():
    """Submit a service request"""
    try:
        service_id = request.form.get('service_id')
        if not service_id:
            return jsonify({'success': False, 'message': 'Service ID required'}), 400
        
        service = get_service_by_id(service_id)
        if not service:
            return jsonify({'success': False, 'message': 'Service not found'}), 404
        
        # Get form data
        full_name = request.form.get('full_name', '').strip()
        dob = request.form.get('dob', '')
        gender = request.form.get('gender', '')
        category = request.form.get('category', '')
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        email = request.form.get('email', '').strip()
        aadhar = request.form.get('aadhar_number', '').strip()
        pan = request.form.get('pan_number', '').strip()
        qualification = request.form.get('qualification', '')
        institute = request.form.get('institute_name', '')
        course = request.form.get('course_name', '')
        passing_year = request.form.get('passing_year', '')
        percentage = request.form.get('percentage', '')
        additional = request.form.get('additional_details', '').strip()
        
        # Validate required fields
        required = [full_name, dob, gender, category, address, city, state, pincode]
        if not all(required):
            return jsonify({'success': False, 'message': 'Please fill all required fields'}), 400
        
        if pincode and not re.match(r'^\d{6}$', pincode):
            return jsonify({'success': False, 'message': 'Invalid pincode'}), 400
        
        # Calculate fees
        service_charge = service.get('service_charge', 0)
        conv_fee = service.get('convenience_fee_percent', 2)
        gst = service.get('gst_percent', 18)
        
        convenience_fee = (service_charge * conv_fee) / 100
        subtotal = service_charge + convenience_fee
        gst_amount = (subtotal * gst) / 100
        total = subtotal + gst_amount
        
        fee_details = {
            'service_charge': round(service_charge, 2),
            'convenience_fee': round(convenience_fee, 2),
            'convenience_fee_percent': conv_fee,
            'subtotal': round(subtotal, 2),
            'gst': round(gst_amount, 2),
            'gst_percent': gst,
            'total': round(total, 2)
        }
        
        # Build details JSON
        details = {
            'full_name': full_name,
            'dob': dob,
            'gender': gender,
            'category': category,
            'address': address,
            'city': city,
            'state': state,
            'pincode': pincode,
            'email': email,
            'aadhar_number': aadhar,
            'pan_number': pan,
            'qualification': qualification,
            'institute_name': institute,
            'course_name': course,
            'passing_year': passing_year,
            'percentage': percentage,
            'additional_details': additional,
            'fee_details': fee_details,
            'submitted_by': session['user_name'],
            'submitted_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Create request
        request_data = {
            'user_id': ObjectId(session['user_id']),
            'service_id': ObjectId(service_id),
            'service_name': service['name'],
            'service_type': service['category'],
            'details': json.dumps(details),
            'amount': total,
            'payment_status': 'pending' if total > 0 else 'completed',
            'status': 'pending',
            'reference_number': f'DS{datetime.now().strftime("%Y%m%d%H%M%S")}{random.randint(1000, 9999)}',
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
            'applicant_email': email,
            'qualification': qualification,
            'institute_name': institute,
            'course_name': course,
            'passing_year': passing_year,
            'percentage': percentage,
            'additional_details': additional,
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
        
        # Handle file uploads
        uploaded_files = []
        files = request.files.getlist('documents')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                original = secure_filename(file.filename)
                ext = original.rsplit('.', 1)[1].lower() if '.' in original else 'pdf'
                stored = f"{request_data['reference_number']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}.{ext}"
                path = os.path.join(app.config['DOCUMENT_FOLDER'], stored)
                file.save(path)
                
                doc_data = {
                    'request_id': request_id,
                    'original_filename': original,
                    'stored_filename': stored,
                    'file_path': path,
                    'file_size': os.path.getsize(path),
                    'uploaded_at': datetime.now(timezone.utc)
                }
                db.request_documents.insert_one(doc_data)
                uploaded_files.append(original)
        
        # Notify user
        create_notification(
            session['user_id'],
            'Application Submitted ✅',
            f'Your application for {service["name"]} has been submitted. Reference: {request_data["reference_number"]}',
            'success',
            str(request_id)
        )
        
        # Notify admins
        admins = list(db.users.find({'role': 'admin'}))
        for admin in admins:
            create_notification(
                str(admin['_id']),
                'New Application Received 🆕',
                f'New application from {full_name} for {service["name"]}. Ref: {request_data["reference_number"]}',
                'info',
                str(request_id)
            )
        
        return jsonify({
            'success': True,
            'message': 'Application submitted successfully',
            'reference_number': request_data['reference_number'],
            'amount': total,
            'fee_details': fee_details,
            'requires_payment': total > 0,
            'documents_uploaded': len(uploaded_files)
        })
        
    except Exception as e:
        print(f"Submit error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/my-requests')
@login_required
def my_requests_page():
    """My requests page"""
    try:
        user = get_user_by_id(session['user_id'])
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        })
        return render_template('my_requests.html', user=user, unread_count=unread_count)
    except Exception as e:
        print(f"My requests error: {e}")
        flash('Unable to load your requests.', 'danger')
        return redirect(url_for('services_dashboard'))

@app.route('/api/my-requests')
@login_required
def api_my_requests():
    """API endpoint for my requests"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        status = request.args.get('status', 'all')
        payment = request.args.get('payment', 'all')
        search = request.args.get('search', '').strip()
        
        query = {'user_id': ObjectId(session['user_id'])}
        if status != 'all':
            query['status'] = status
        if payment != 'all':
            query['payment_status'] = payment
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
                'submitted_at': req['submitted_at'].strftime('%Y-%m-%d %H:%M') if isinstance(req['submitted_at'], datetime) else str(req['submitted_at']),
                'documents_count': db.request_documents.count_documents({'request_id': req['_id']}),
                'applicant_name': req.get('applicant_name', 'N/A')
            })
        
        return jsonify({
            'requests': data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if per_page > 0 else 1
        })
    except Exception as e:
        print(f"API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/request-details/<request_id>')
@login_required
def request_details(request_id):
    """Get request details"""
    try:
        req = db.service_requests.find_one({'_id': ObjectId(request_id)})
        if not req:
            return jsonify({'error': 'Request not found'}), 404
        
        if str(req['user_id']) != session['user_id'] and session.get('user_role') != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        documents = list(db.request_documents.find({'request_id': ObjectId(request_id)}))
        for doc in documents:
            doc['id'] = str(doc['_id'])
            if isinstance(doc.get('uploaded_at'), datetime):
                doc['uploaded_at'] = doc['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        request_dict = {
            'id': str(req['_id']),
            'reference_number': req['reference_number'],
            'service_name': req['service_name'],
            'status': req['status'],
            'payment_status': req['payment_status'],
            'amount': req['amount'],
            'submitted_at': req['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(req['submitted_at'], datetime) else str(req['submitted_at']),
            'processed_at': req['processed_at'].strftime('%Y-%m-%d %H:%M:%S') if req.get('processed_at') and isinstance(req['processed_at'], datetime) else None,
            'admin_remarks': req.get('admin_remarks', ''),
            'applicant_name': req.get('applicant_name', ''),
            'applicant_dob': req.get('applicant_dob', ''),
            'applicant_gender': req.get('applicant_gender', ''),
            'applicant_category': req.get('applicant_category', ''),
            'applicant_address': req.get('applicant_address', ''),
            'applicant_city': req.get('applicant_city', ''),
            'applicant_state': req.get('applicant_state', ''),
            'applicant_pincode': req.get('applicant_pincode', ''),
            'applicant_email': req.get('applicant_email', ''),
            'qualification': req.get('qualification', ''),
            'institute_name': req.get('institute_name', ''),
            'course_name': req.get('course_name', ''),
            'passing_year': req.get('passing_year', ''),
            'percentage': req.get('percentage', ''),
            'additional_details': req.get('additional_details', ''),
            'timeline': req.get('timeline', [])
        }
        
        return jsonify({
            'request': request_dict,
            'documents': documents
        })
    except Exception as e:
        print(f"Request details error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/initiate-payment/<ref_number>', methods=['POST'])
@login_required
def initiate_payment(ref_number):
    """Initiate payment for a request"""
    try:
        req = db.service_requests.find_one({
            'reference_number': ref_number,
            'user_id': ObjectId(session['user_id'])
        })
        
        if not req:
            return jsonify({'success': False, 'message': 'Request not found'}), 404
        
        if req['payment_status'] == 'completed':
            return jsonify({'success': False, 'message': 'Payment already completed'}), 400
        
        # Create payment record
        transaction_id = f'TXN{datetime.now().strftime("%Y%m%d%H%M%S")}{random.randint(10000, 99999)}'
        
        payment = {
            'user_id': ObjectId(session['user_id']),
            'request_id': req['_id'],
            'transaction_id': transaction_id,
            'amount': req['amount'],
            'payment_method': 'online',
            'status': 'completed',
            'created_at': datetime.now(timezone.utc)
        }
        db.payment_transactions.insert_one(payment)
        
        # Update request
        db.service_requests.update_one(
            {'_id': req['_id']},
            {'$set': {
                'payment_status': 'completed',
                'status': 'in_progress'
            }}
        )
        
        # Add timeline entry
        db.service_requests.update_one(
            {'_id': req['_id']},
            {'$push': {
                'timeline': {
                    'title': 'Payment Completed',
                    'description': f'Payment of ₹{req["amount"]} has been received. Transaction ID: {transaction_id}',
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'completed': True
                }
            }}
        )
        
        create_notification(
            session['user_id'],
            'Payment Successful 💰',
            f'Payment of ₹{req["amount"]} completed. Transaction ID: {transaction_id}',
            'success',
            str(req['_id'])
        )
        
        return jsonify({
            'success': True,
            'message': 'Payment successful!',
            'transaction_id': transaction_id
        })
    except Exception as e:
        print(f"Payment error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/notifications')
@login_required
def get_notifications():
    """Get user notifications"""
    try:
        notifications = list(db.notifications.find(
            {'user_id': ObjectId(session['user_id'])}
        ).sort('created_at', -1).limit(50))
        
        result = []
        for n in notifications:
            created_at = n['created_at']
            if isinstance(created_at, datetime):
                time_ago = 'Just now'
                diff = datetime.now(timezone.utc) - created_at
                if diff.days > 365:
                    time_ago = f"{diff.days // 365} year(s) ago"
                elif diff.days > 30:
                    time_ago = f"{diff.days // 30} month(s) ago"
                elif diff.days > 0:
                    time_ago = f"{diff.days} day(s) ago"
                elif diff.seconds > 3600:
                    time_ago = f"{diff.seconds // 3600} hour(s) ago"
                elif diff.seconds > 60:
                    time_ago = f"{diff.seconds // 60} minute(s) ago"
                created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_ago = 'Unknown'
                created_at_str = str(created_at)
            
            result.append({
                'id': str(n['_id']),
                'title': n['title'],
                'message': n['message'],
                'type': n['type'],
                'is_read': n['is_read'],
                'request_id': n.get('request_id'),
                'created_at': created_at_str,
                'time_ago': time_ago
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"Notifications error: {e}")
        return jsonify([])

@app.route('/notifications/mark-read/<notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        result = db.notifications.update_one(
            {'_id': ObjectId(notification_id), 'user_id': ObjectId(session['user_id'])},
            {'$set': {'is_read': True}}
        )
        return jsonify({'success': result.modified_count > 0})
    except Exception as e:
        print(f"Mark read error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    try:
        db.notifications.update_many(
            {'user_id': ObjectId(session['user_id']), 'is_read': False},
            {'$set': {'is_read': True}}
        )
        return jsonify({'success': True})
    except Exception as e:
        print(f"Mark all read error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/user-profile')
@login_required
def get_user_profile():
    """Get user profile"""
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
            'pincode': user.get('pincode', ''),
            'created_at': user['created_at'].strftime('%Y-%m-%d') if isinstance(user['created_at'], datetime) else str(user['created_at'])
        })
    except Exception as e:
        print(f"Profile error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    try:
        data = request.get_json()
        
        update_data = {}
        if 'email' in data:
            if data['email'] and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data['email']):
                return jsonify({'success': False, 'message': 'Invalid email'}), 400
            update_data['email'] = data['email'] or None
        if 'address' in data:
            update_data['address'] = data['address'] or None
        if 'city' in data:
            update_data['city'] = data['city'] or None
        if 'state' in data:
            update_data['state'] = data['state'] or None
        if 'pincode' in data:
            if data['pincode'] and not re.match(r'^\d{6}$', data['pincode']):
                return jsonify({'success': False, 'message': 'Invalid pincode'}), 400
            update_data['pincode'] = data['pincode'] or None
        
        if update_data:
            db.users.update_one(
                {'_id': ObjectId(session['user_id'])},
                {'$set': update_data}
            )
        
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        print(f"Update profile error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============== Admin Routes ==============

@app.route('/admin')
@admin_required
def admin_panel():
    """Admin dashboard"""
    try:
        total_requests = db.service_requests.count_documents({})
        pending_requests = db.service_requests.count_documents({'status': 'pending'})
        in_progress_requests = db.service_requests.count_documents({'status': 'in_progress'})
        completed_requests = db.service_requests.count_documents({'status': 'completed'})
        rejected_requests = db.service_requests.count_documents({'status': 'rejected'})
        
        total_users = db.users.count_documents({'role': 'user'})
        total_services = db.services.count_documents({'is_active': True})
        
        # Total revenue
        revenue_result = list(db.payment_transactions.aggregate([
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ]))
        total_revenue = revenue_result[0]['total'] if revenue_result else 0
        
        # Monthly trends
        monthly_trends = list(db.service_requests.aggregate([
            {'$group': {
                '_id': {
                    'year': {'$year': '$submitted_at'},
                    'month': {'$month': '$submitted_at'}
                },
                'count': {'$sum': 1}
            }},
            {'$sort': {'_id.year': 1, '_id.month': 1}},
            {'$limit': 6}
        ]))
        
        # Service distribution
        service_dist = list(db.service_requests.aggregate([
            {'$group': {'_id': '$service_type', 'count': {'$sum': 1}}}
        ]))
        
        # Status distribution
        status_dist = list(db.service_requests.aggregate([
            {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
        ]))
        
        # Get all requests with user info
        all_requests = list(db.service_requests.find().sort('submitted_at', -1).limit(50))
        for req in all_requests:
            req['_id'] = str(req['_id'])
            user = get_user_by_id(req['user_id'])
            req['user'] = {'name': user['name'], 'phone': user['phone']} if user else None
            req['applicant_name'] = req.get('applicant_name', req.get('user', {}).get('name', 'N/A'))
        
        users = list(db.users.find().sort('created_at', -1))
        for user in users:
            user['_id'] = str(user['_id'])
            user['request_count'] = db.service_requests.count_documents({'user_id': ObjectId(user['_id'])})
        
        payments = list(db.payment_transactions.find().sort('created_at', -1).limit(50))
        for payment in payments:
            payment['_id'] = str(payment['_id'])
            user = get_user_by_id(payment['user_id'])
            req = db.service_requests.find_one({'_id': payment['request_id']})
            payment['user_name'] = user['name'] if user else 'N/A'
            payment['service_name'] = req['service_name'] if req else 'N/A'
        
        services = list(db.services.find())
        for service in services:
            service['_id'] = str(service['_id'])
        
        service_names = list(set([req.get('service_name') for req in all_requests if req.get('service_name')]))
        
        stats = {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'in_progress_requests': in_progress_requests,
            'completed_requests': completed_requests,
            'rejected_requests': rejected_requests,
            'total_users': total_users,
            'total_revenue': total_revenue,
            'total_services': total_services,
            'monthly_trends': monthly_trends,
            'service_distribution': service_dist,
            'status_distribution': status_dist
        }
        
        return render_template('admin.html',
                             requests=all_requests,
                             users=users,
                             payments=payments,
                             services=services,
                             stats=stats,
                             service_names=service_names,
                             filters={})
    except Exception as e:
        print(f"Admin error: {e}")
        traceback.print_exc()
        flash('Unable to load admin panel.', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/update-status/<request_id>', methods=['POST'])
@admin_required
def update_status(request_id):
    """Update request status"""
    try:
        data = request.get_json()
        status = data.get('status')
        remarks = data.get('remarks', '')
        
        req = db.service_requests.find_one({'_id': ObjectId(request_id)})
        if not req:
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
            'in_progress': 'Your application is being processed by our team.',
            'completed': 'Your application has been approved and processed successfully!',
            'rejected': 'Your application has been reviewed. Please check the remarks.'
        }
        
        title = status_titles.get(status, f'Status Updated: {status}')
        message = status_messages.get(status, f'Your application status has been updated to {status}')
        if remarks:
            message += f'\n\nRemarks: {remarks}'
        
        # Add timeline entry
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
            str(req['user_id']),
            title,
            message,
            'success' if status == 'completed' else 'info',
            request_id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Update status error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/add-service', methods=['POST'])
@admin_required
def add_service():
    """Add a new service"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': 'Service name required'}), 400
        
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        
        if db.services.find_one({'slug': slug}):
            return jsonify({'success': False, 'message': 'Service with similar name already exists'}), 400
        
        service = {
            'category': data.get('category'),
            'name': name,
            'slug': slug,
            'description': data.get('description', '').strip(),
            'eligibility': data.get('eligibility', '').strip(),
            'documents_required': data.get('documents_required', '').strip(),
            'instructions': data.get('instructions', '').strip(),
            'processing_time': data.get('processing_time', '7-10 working days'),
            'service_charge': float(data.get('service_charge', 0)),
            'convenience_fee_percent': float(data.get('convenience_fee_percent', 2)),
            'gst_percent': float(data.get('gst_percent', 18)),
            'is_active': True,
            'icon': data.get('icon', 'fas fa-file-alt'),
            'created_at': datetime.now(timezone.utc)
        }
        
        db.services.insert_one(service)
        
        # Notify all users about new service
        users = list(db.users.find({'role': 'user'}))
        for user in users:
            create_notification(
                str(user['_id']),
                'New Service Added! 🎉',
                f'A new service "{name}" has been added to our platform.',
                'info'
            )
        
        return jsonify({'success': True, 'message': 'Service added successfully'})
    except Exception as e:
        print(f"Add service error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/get-pending-count')
@admin_required
def get_pending_count():
    """Get pending requests count"""
    try:
        count = db.service_requests.count_documents({'status': 'pending'})
        return jsonify({'count': count})
    except:
        return jsonify({'count': 0})

@app.route('/admin/request-details/<request_id>')
@admin_required
def admin_request_details(request_id):
    """Get request details for admin"""
    try:
        req = db.service_requests.find_one({'_id': ObjectId(request_id)})
        if not req:
            return jsonify({'error': 'Request not found'}), 404
        
        documents = list(db.request_documents.find({'request_id': ObjectId(request_id)}))
        for doc in documents:
            doc['_id'] = str(doc['_id'])
            if isinstance(doc.get('uploaded_at'), datetime):
                doc['uploaded_at'] = doc['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        user = get_user_by_id(req['user_id'])
        
        request_dict = {
            'id': str(req['_id']),
            'reference_number': req['reference_number'],
            'service_name': req['service_name'],
            'service_type': req['service_type'],
            'status': req['status'],
            'payment_status': req['payment_status'],
            'amount': req['amount'],
            'submitted_at': req['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(req['submitted_at'], datetime) else str(req['submitted_at']),
            'processed_at': req['processed_at'].strftime('%Y-%m-%d %H:%M:%S') if req.get('processed_at') and isinstance(req['processed_at'], datetime) else None,
            'admin_remarks': req.get('admin_remarks', ''),
            'applicant_name': req.get('applicant_name', 'N/A'),
            'applicant_dob': req.get('applicant_dob', ''),
            'applicant_gender': req.get('applicant_gender', ''),
            'applicant_category': req.get('applicant_category', ''),
            'applicant_address': req.get('applicant_address', ''),
            'applicant_city': req.get('applicant_city', ''),
            'applicant_state': req.get('applicant_state', ''),
            'applicant_pincode': req.get('applicant_pincode', ''),
            'applicant_email': req.get('applicant_email', ''),
            'qualification': req.get('qualification', ''),
            'institute_name': req.get('institute_name', ''),
            'course_name': req.get('course_name', ''),
            'passing_year': req.get('passing_year', ''),
            'percentage': req.get('percentage', ''),
            'additional_details': req.get('additional_details', ''),
            'timeline': req.get('timeline', [])
        }
        
        return jsonify({
            'request': request_dict,
            'documents': documents,
            'user': {
                'name': user['name'] if user else 'N/A',
                'phone': user['phone'] if user else 'N/A',
                'email': user.get('email', 'N/A') if user else 'N/A'
            }
        })
    except Exception as e:
        print(f"Admin request details error: {e}")
        return jsonify({'error': str(e)}), 500

# ============== Export Routes ==============

@app.route('/export/applications/csv')
@admin_required
def export_applications_csv():
    """Export applications to CSV"""
    try:
        apps = list(db.service_requests.find().sort('submitted_at', -1))
        
        output = BytesIO()
        writer = csv.writer(output)
        writer.writerow(['Reference', 'Applicant', 'Service', 'Status', 'Payment', 'Amount', 'Date', 'Phone'])
        
        for app in apps:
            user = get_user_by_id(app['user_id'])
            writer.writerow([
                app['reference_number'],
                app.get('applicant_name', 'N/A'),
                app['service_name'],
                app['status'],
                app['payment_status'],
                app['amount'],
                app['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(app['submitted_at'], datetime) else str(app['submitted_at']),
                user['phone'] if user else ''
            ])
        
        output.seek(0)
        return send_file(
            output,
            download_name=f'applications_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            as_attachment=True,
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/revenue/csv')
@admin_required
def export_revenue_csv():
    """Export revenue to CSV"""
    try:
        payments = list(db.payment_transactions.find().sort('created_at', -1))
        
        output = BytesIO()
        writer = csv.writer(output)
        writer.writerow(['Transaction ID', 'User', 'Service', 'Amount', 'Method', 'Date'])
        
        for payment in payments:
            user = get_user_by_id(payment['user_id'])
            req = db.service_requests.find_one({'_id': payment['request_id']})
            writer.writerow([
                payment['transaction_id'],
                user['name'] if user else '',
                req['service_name'] if req else '',
                payment['amount'],
                payment['payment_method'],
                payment['created_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(payment['created_at'], datetime) else str(payment['created_at'])
            ])
        
        output.seek(0)
        return send_file(
            output,
            download_name=f'revenue_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            as_attachment=True,
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/users/csv')
@admin_required
def export_users_csv():
    """Export users to CSV"""
    try:
        users = list(db.users.find())
        
        output = BytesIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Phone', 'Email', 'Role', 'Applications', 'Joined'])
        
        for user in users:
            count = db.service_requests.count_documents({'user_id': user['_id']})
            writer.writerow([
                user['name'],
                user['phone'],
                user.get('email', ''),
                user['role'],
                count,
                user['created_at'].strftime('%Y-%m-%d') if isinstance(user['created_at'], datetime) else str(user['created_at'])
            ])
        
        output.seek(0)
        return send_file(
            output,
            download_name=f'users_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            as_attachment=True,
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============== Error Handlers ==============

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html', error_message=str(error)), 500

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

# ============== Application Entry Point ==============

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 DigiServe eSeva Portal - Professional Edition")
    print("=" * 60)
    
    init_db()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"\n✅ Application started on port {port}!")
    print(f"🌐 Visit: http://localhost:{port}")
    print("=" * 60 + "\n")
    app.run(debug=debug, host='0.0.0.0', port=port)