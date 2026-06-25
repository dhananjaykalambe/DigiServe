# app.py - COMPLETE FIXED VERSION FOR RENDER

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from functools import wraps
import os
import json
import random
import re
import traceback

app = Flask(__name__)

# ============== Configuration ==============
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'digiserve-super-secret-key-2026')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', "mongodb+srv://digiserve_admin:digiserve2324@digiserve-cluster.mrlhjs4.mongodb.net/digiserve?retryWrites=true&w=majority&appName=digiserve-cluster")
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['DOCUMENT_FOLDER'] = 'uploads/documents/'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt'}

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

def format_time_ago(dt):
    """Format time ago with proper timezone handling"""
    if not dt:
        return "Unknown"
    try:
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            # If naive, assume UTC
            dt = dt.replace(tzinfo=timezone.utc)
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
    except:
        return str(dt)

def get_all_services():
    """Get all active services"""
    try:
        services = list(db.services.find({'is_active': True}).sort('order', 1))
        for service in services:
            service['id'] = str(service['_id'])
        return services
    except Exception as e:
        print(f"❌ Error getting services: {e}")
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

# ============== Database Initialization ==============

def init_database():
    """Initialize database with services and admin - CALLED AT STARTUP"""
    print("📦 Initializing database...")
    
    # Check MongoDB connection
    try:
        db.command('ping')
        print("✅ MongoDB Atlas connected successfully!")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False
    
    # Create indexes
    try:
        db.users.create_index('phone', unique=True)
        db.services.create_index('slug', unique=True)
        db.service_requests.create_index('reference_number', unique=True)
        print("✅ Indexes created")
    except Exception as e:
        print(f"⚠️ Index creation warning: {e}")
    
    # Create admin user
    try:
        admin = db.users.find_one({'phone': '9999999999'})
        if not admin:
            admin_user = {
                'name': 'Administrator',
                'phone': '9999999999',
                'email': 'admin@digiserve.com',
                'role': 'admin',
                'is_active': True,
                'created_at': datetime.now(timezone.utc),
                'last_login': datetime.now(timezone.utc)
            }
            db.users.insert_one(admin_user)
            print("✅ Admin user created (Phone: 9999999999)")
        else:
            print("✅ Admin user already exists")
    except Exception as e:
        print(f"⚠️ Admin creation warning: {e}")
    
    # Create services
    try:
        existing_count = db.services.count_documents({})
        if existing_count > 0:
            print(f"✅ Services already exist ({existing_count} services found)")
            return True
        
        print("📦 Creating 24 services...")
        
        services_data = [
            # 1. Scholarship & Education
            {
                'category': 'scholarship',
                'name': 'Scholarship Form Filling',
                'slug': 'scholarship-form-filling',
                'description': 'Expert assistance for filling various scholarship application forms including PMSSS, Post Matric, and more.',
                'icon': 'fas fa-graduation-cap',
                'service_charge': 0,
                'is_active': True,
                'order': 1,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'education',
                'name': 'College Admission Forms',
                'slug': 'college-admission-forms',
                'description': 'Get help with college admission applications, form filling, and document submission.',
                'icon': 'fas fa-university',
                'service_charge': 500,
                'is_active': True,
                'order': 2,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'education',
                'name': 'Government Exam Forms',
                'slug': 'government-exam-forms',
                'description': 'Professional assistance for filling government exam applications like UPSC, SSC, Banking.',
                'icon': 'fas fa-file-alt',
                'service_charge': 800,
                'is_active': True,
                'order': 3,
                'created_at': datetime.now(timezone.utc)
            },
            # 4-6. Career Services
            {
                'category': 'career',
                'name': 'Internship/Job Applications',
                'slug': 'internship-job-applications',
                'description': 'Professional assistance for internship and job applications.',
                'icon': 'fas fa-briefcase',
                'service_charge': 300,
                'is_active': True,
                'order': 4,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'career',
                'name': 'Resume Creation',
                'slug': 'resume-creation',
                'description': 'Professional resume writing with modern templates and ATS-friendly formats.',
                'icon': 'fas fa-file-alt',
                'service_charge': 200,
                'is_active': True,
                'order': 5,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'career',
                'name': 'LinkedIn Profile Setup',
                'slug': 'linkedin-profile-setup',
                'description': 'Complete LinkedIn profile optimization and networking strategies.',
                'icon': 'fab fa-linkedin',
                'service_charge': 250,
                'is_active': True,
                'order': 6,
                'created_at': datetime.now(timezone.utc)
            },
            # 7-9. Bill Payments
            {
                'category': 'bill_payment',
                'name': 'Electricity Bill Payment',
                'slug': 'electricity-bill-payment',
                'description': 'Quick and secure online electricity bill payment for all major providers.',
                'icon': 'fas fa-lightbulb',
                'service_charge': 0,
                'is_active': True,
                'order': 7,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'bill_payment',
                'name': 'Water Bill Payment',
                'slug': 'water-bill-payment',
                'description': 'Pay your water bills online instantly with our secure payment system.',
                'icon': 'fas fa-tint',
                'service_charge': 0,
                'is_active': True,
                'order': 8,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'bill_payment',
                'name': 'Mobile Recharge',
                'slug': 'mobile-recharge',
                'description': 'Instant mobile recharge for all prepaid and postpaid connections.',
                'icon': 'fas fa-mobile-alt',
                'service_charge': 0,
                'is_active': True,
                'order': 9,
                'created_at': datetime.now(timezone.utc)
            },
            # 10-13. Document Services
            {
                'category': 'document',
                'name': 'PAN Card Services',
                'slug': 'pan-card-services',
                'description': 'Apply for new PAN card, update details, or request for reprint.',
                'icon': 'fas fa-id-card',
                'service_charge': 150,
                'is_active': True,
                'order': 10,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'document',
                'name': 'Passport Services',
                'slug': 'passport-services',
                'description': 'Complete assistance for passport application, renewal, and verification.',
                'icon': 'fas fa-passport',
                'service_charge': 350,
                'is_active': True,
                'order': 11,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'document',
                'name': 'Income Certificate',
                'slug': 'income-certificate',
                'description': 'Apply for income certificate for government schemes and scholarships.',
                'icon': 'fas fa-file-invoice-dollar',
                'service_charge': 100,
                'is_active': True,
                'order': 12,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'document',
                'name': 'Caste Certificate',
                'slug': 'caste-certificate',
                'description': 'Apply for caste certificate (SC/ST/OBC) for educational and employment purposes.',
                'icon': 'fas fa-users',
                'service_charge': 100,
                'is_active': True,
                'order': 13,
                'created_at': datetime.now(timezone.utc)
            },
            # 14-16. Printing & Design
            {
                'category': 'printing',
                'name': 'Printing Services',
                'slug': 'printing-services',
                'description': 'High-quality printing services for documents, photos, flyers, and more.',
                'icon': 'fas fa-print',
                'service_charge': 50,
                'is_active': True,
                'order': 14,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'printing',
                'name': 'Scanning Services',
                'slug': 'scanning-services',
                'description': 'Professional document scanning services with high-quality output.',
                'icon': 'fas fa-camera',
                'service_charge': 20,
                'is_active': True,
                'order': 15,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'printing',
                'name': 'Passport Photo Service',
                'slug': 'passport-photo-service',
                'description': 'Professional passport and visa photo services meeting all specification requirements.',
                'icon': 'fas fa-camera-retro',
                'service_charge': 100,
                'is_active': True,
                'order': 16,
                'created_at': datetime.now(timezone.utc)
            },
            # 17-19. Digital Services
            {
                'category': 'digital',
                'name': 'Website Development',
                'slug': 'website-development',
                'description': 'Custom website development with modern design and full functionality.',
                'icon': 'fas fa-laptop-code',
                'service_charge': 5000,
                'is_active': True,
                'order': 17,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'digital',
                'name': 'Data Entry',
                'slug': 'data-entry',
                'description': 'Professional data entry services with accuracy and confidentiality.',
                'icon': 'fas fa-keyboard',
                'service_charge': 200,
                'is_active': True,
                'order': 18,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'digital',
                'name': 'Excel/Data Analytics Service',
                'slug': 'excel-data-analytics',
                'description': 'Professional Excel and data analytics services including reports and dashboards.',
                'icon': 'fas fa-chart-bar',
                'service_charge': 350,
                'is_active': True,
                'order': 19,
                'created_at': datetime.now(timezone.utc)
            },
            # 20-22. Business Services
            {
                'category': 'business',
                'name': 'Travel Booking',
                'slug': 'travel-booking',
                'description': 'Complete travel booking services including flights, hotels, and tour packages.',
                'icon': 'fas fa-plane',
                'service_charge': 200,
                'is_active': True,
                'order': 20,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'business',
                'name': 'GST Registration',
                'slug': 'gst-registration',
                'description': 'Professional assistance for GST registration, filing, and compliance.',
                'icon': 'fas fa-file-invoice',
                'service_charge': 1500,
                'is_active': True,
                'order': 21,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'business',
                'name': 'Business Registration',
                'slug': 'business-registration',
                'description': 'Complete business registration services including sole proprietorship and partnership.',
                'icon': 'fas fa-building',
                'service_charge': 2000,
                'is_active': True,
                'order': 22,
                'created_at': datetime.now(timezone.utc)
            },
            # 23-24. Design Services
            {
                'category': 'design',
                'name': 'Logo Design',
                'slug': 'logo-design',
                'description': 'Professional logo design services with multiple concepts and unlimited revisions.',
                'icon': 'fas fa-paint-brush',
                'service_charge': 800,
                'is_active': True,
                'order': 23,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'design',
                'name': 'Social Media Design',
                'slug': 'social-media-design',
                'description': 'Professional social media designs including posts, covers, and ad creatives.',
                'icon': 'fas fa-hashtag',
                'service_charge': 500,
                'is_active': True,
                'order': 24,
                'created_at': datetime.now(timezone.utc)
            }
        ]
        
        for service in services_data:
            db.services.insert_one(service)
            print(f"  ✅ Added: {service['name']}")
        
        print(f"✅ Successfully created {len(services_data)} services!")
        
    except Exception as e:
        print(f"❌ Error creating services: {e}")
        traceback.print_exc()
        return False
    
    print("=" * 60)
    print("🚀 DigiServe Portal is ready!")
    print(f"📊 Total Services: {db.services.count_documents({})}")
    print("👑 Admin Login: 9999999999")
    print("=" * 60)
    return True

# ============== Routes ==============

@app.route('/')
def index():
    try:
        services = get_all_services()
        print(f"📊 Rendering index with {len(services)} services")
        
        total_users = db.users.count_documents({'role': 'user'}) if hasattr(db, 'users') else 0
        total_applications = db.service_requests.count_documents({}) if hasattr(db, 'service_requests') else 0
        
        return render_template('index.html', 
                             services=services,
                             total_users=total_users,
                             total_applications=total_applications)
    except Exception as e:
        print(f"❌ Error loading index: {e}")
        traceback.print_exc()
        return render_template('index.html', services=[])

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
                return redirect(url_for('index'))
            else:
                session['registration_phone'] = phone
                flash('New user! Please complete registration.', 'info')
                return redirect(url_for('register'))
                
        except Exception as e:
            print(f"Login error: {e}")
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
                'last_login': datetime.now(timezone.utc)
            }
            result = db.users.insert_one(new_user)
            
            session['user_id'] = str(result.inserted_id)
            session['user_name'] = name
            session['user_role'] = 'user'
            session['user_phone'] = phone
            session.permanent = True
            session.pop('registration_phone', None)
            
            flash(f'Welcome to DigiServe, {name}!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            print(f"Registration error: {e}")
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
        
        if not all([full_name, phone, address, city, state, pincode]):
            return jsonify({'success': False, 'message': 'Please fill all required fields'}), 400
        
        ref_number = generate_reference_number()
        
        request_data = {
            'user_id': ObjectId(session['user_id']),
            'service_id': ObjectId(service_id),
            'service_type': service['category'],
            'service_name': service['name'],
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
        
        return jsonify({
            'success': True,
            'message': 'Application submitted successfully',
            'reference_number': ref_number,
            'amount': service.get('service_charge', 0),
            'requires_payment': service.get('service_charge', 0) > 0
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
        
        query = {'user_id': ObjectId(session['user_id'])}
        if status != 'all':
            query['status'] = status
        
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
            
            if app_data.get('applicant_phone') != phone:
                flash('Phone number does not match this application.', 'danger')
                return redirect(url_for('track_application'))
            
            return render_template('track_result.html', application=app_data)
            
        except Exception as e:
            print(f"Error tracking application: {e}")
            flash('Error tracking application. Please try again.', 'danger')
            return redirect(url_for('track_application'))
    
    return render_template('track_application.html')

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
        completed_requests = db.service_requests.count_documents({'status': 'completed'})
        
        all_requests = list(db.service_requests.find().sort('submitted_at', -1))
        for req in all_requests:
            req['_id'] = str(req['_id'])
        
        users = list(db.users.find())
        for u in users:
            u['_id'] = str(u['_id'])
        
        services = list(db.services.find())
        for s in services:
            s['_id'] = str(s['_id'])
        
        stats = {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'completed_requests': completed_requests,
            'total_users': db.users.count_documents({'role': 'user'}),
            'total_services': db.services.count_documents({'is_active': True})
        }
        
        return render_template('admin.html',
                             requests=all_requests,
                             users=users,
                             services=services,
                             stats=stats)
    except Exception as e:
        print(f"Error loading admin panel: {e}")
        flash('Unable to load admin panel.', 'danger')
        return redirect(url_for('index'))

# ============== Admin - Service Management Routes ==============

@app.route('/admin/services')
@login_required
def admin_services():
    """Admin page for managing services"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    try:
        services = list(db.services.find().sort('order', 1))
        for s in services:
            s['id'] = str(s['_id'])
        
        return render_template('admin_services.html', services=services)
    except Exception as e:
        print(f"Error loading admin services: {e}")
        flash('Unable to load services.', 'danger')
        return redirect(url_for('admin_panel'))

@app.route('/admin/service/create', methods=['GET', 'POST'])
@login_required
def admin_create_service():
    """Create a new service"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            slug = request.form.get('slug', '').strip()
            category = request.form.get('category', '').strip()
            description = request.form.get('description', '').strip()
            service_charge = float(request.form.get('service_charge', 0))
            processing_time = request.form.get('processing_time', '').strip()
            icon = request.form.get('icon', 'fas fa-cog').strip()
            is_active = request.form.get('is_active') == 'on'
            
            # Validate
            if not name or not slug or not category:
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('admin_create_service'))
            
            # Check if slug exists
            existing = db.services.find_one({'slug': slug})
            if existing:
                flash('Service with this slug already exists. Please use a different slug.', 'danger')
                return redirect(url_for('admin_create_service'))
            
            # Get fields from form (comma separated)
            fields_str = request.form.get('fields', '').strip()
            fields = [f.strip() for f in fields_str.split(',') if f.strip()]
            
            # Get max order
            max_order = db.services.count_documents({})
            
            service_data = {
                'name': name,
                'slug': slug,
                'category': category,
                'description': description,
                'service_charge': service_charge,
                'processing_time': processing_time or '3-5 working days',
                'icon': icon,
                'is_active': is_active,
                'order': max_order + 1,
                'fields': fields,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            db.services.insert_one(service_data)
            flash(f'Service "{name}" created successfully!', 'success')
            return redirect(url_for('admin_services'))
            
        except Exception as e:
            print(f"Error creating service: {e}")
            flash(f'Error creating service: {str(e)}', 'danger')
            return redirect(url_for('admin_create_service'))
    
    # GET - Show create form
    categories = db.services.distinct('category')
    return render_template('admin_service_form.html', 
                         service=None, 
                         categories=categories,
                         form_title='Create New Service',
                         form_action='/admin/service/create')

@app.route('/admin/service/edit/<service_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_service(service_id):
    """Edit an existing service"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    try:
        service = db.services.find_one({'_id': ObjectId(service_id)})
        if not service:
            flash('Service not found', 'danger')
            return redirect(url_for('admin_services'))
        
        if request.method == 'POST':
            # Get form data
            name = request.form.get('name', '').strip()
            slug = request.form.get('slug', '').strip()
            category = request.form.get('category', '').strip()
            description = request.form.get('description', '').strip()
            service_charge = float(request.form.get('service_charge', 0))
            processing_time = request.form.get('processing_time', '').strip()
            icon = request.form.get('icon', 'fas fa-cog').strip()
            is_active = request.form.get('is_active') == 'on'
            order = int(request.form.get('order', 0))
            
            # Validate
            if not name or not slug or not category:
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('admin_edit_service', service_id=service_id))
            
            # Check if slug exists (excluding current service)
            existing = db.services.find_one({'slug': slug, '_id': {'$ne': ObjectId(service_id)}})
            if existing:
                flash('Service with this slug already exists. Please use a different slug.', 'danger')
                return redirect(url_for('admin_edit_service', service_id=service_id))
            
            # Get fields from form (comma separated)
            fields_str = request.form.get('fields', '').strip()
            fields = [f.strip() for f in fields_str.split(',') if f.strip()]
            
            update_data = {
                'name': name,
                'slug': slug,
                'category': category,
                'description': description,
                'service_charge': service_charge,
                'processing_time': processing_time or '3-5 working days',
                'icon': icon,
                'is_active': is_active,
                'order': order,
                'fields': fields,
                'updated_at': datetime.now(timezone.utc)
            }
            
            db.services.update_one(
                {'_id': ObjectId(service_id)},
                {'$set': update_data}
            )
            
            flash(f'Service "{name}" updated successfully!', 'success')
            return redirect(url_for('admin_services'))
        
        # GET - Show edit form
        service['id'] = str(service['_id'])
        categories = db.services.distinct('category')
        fields_str = ', '.join(service.get('fields', []))
        
        return render_template('admin_service_form.html', 
                             service=service,
                             fields_str=fields_str,
                             categories=categories,
                             form_title='Edit Service',
                             form_action=f'/admin/service/edit/{service_id}')
                             
    except Exception as e:
        print(f"Error editing service: {e}")
        flash(f'Error editing service: {str(e)}', 'danger')
        return redirect(url_for('admin_services'))

@app.route('/admin/service/delete/<service_id>', methods=['POST'])
@login_required
def admin_delete_service(service_id):
    """Delete a service"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        service = db.services.find_one({'_id': ObjectId(service_id)})
        if not service:
            return jsonify({'success': False, 'message': 'Service not found'}), 404
        
        # Check if service has applications
        app_count = db.service_requests.count_documents({'service_id': ObjectId(service_id)})
        if app_count > 0:
            return jsonify({'success': False, 'message': f'Cannot delete service with {app_count} applications. Archive it instead.'}), 400
        
        db.services.delete_one({'_id': ObjectId(service_id)})
        return jsonify({'success': True, 'message': 'Service deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting service: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/service/toggle-status/<service_id>', methods=['POST'])
@login_required
def admin_toggle_service_status(service_id):
    """Toggle service active/inactive status"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        service = db.services.find_one({'_id': ObjectId(service_id)})
        if not service:
            return jsonify({'success': False, 'message': 'Service not found'}), 404
        
        new_status = not service.get('is_active', True)
        db.services.update_one(
            {'_id': ObjectId(service_id)},
            {'$set': {'is_active': new_status, 'updated_at': datetime.now(timezone.utc)}}
        )
        
        return jsonify({
            'success': True, 
            'is_active': new_status,
            'message': f'Service {"activated" if new_status else "deactivated"} successfully'
        })
        
    except Exception as e:
        print(f"Error toggling service status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/service/reorder', methods=['POST'])
@login_required
def admin_reorder_services():
    """Reorder services"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        service_ids = data.get('service_ids', [])
        
        for index, service_id in enumerate(service_ids, 1):
            db.services.update_one(
                {'_id': ObjectId(service_id)},
                {'$set': {'order': index, 'updated_at': datetime.now(timezone.utc)}}
            )
        
        return jsonify({'success': True, 'message': 'Services reordered successfully'})
        
    except Exception as e:
        print(f"Error reordering services: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
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
        
        db.service_requests.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {
                'status': status,
                'admin_remarks': remarks,
                'processed_at': datetime.now(timezone.utc)
            }}
        )
        
        return jsonify({'success': True})
    except Exception as e:
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
            'timeline': service_request.get('timeline', [])
        }
        
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
        'services_count': db.services.count_documents({}),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html', error_message=str(error)), 500

# ============== INITIALIZE DATABASE AT STARTUP ==============
# This runs when the app starts with gunicorn
print("🚀 Running database initialization...")
init_database()
print("✅ Application ready!")

# ============== Application Entry Point ==============

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)