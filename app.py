# app.py - COMPLETE UPGRADED VERSION

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
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Increased to 100MB for multiple documents
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt'}
app.config['MAX_DOCUMENTS'] = 10  # Maximum documents per application

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
    if not dt:
        return "Unknown"
    try:
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
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

# ============== Database Initialization with Enhanced Services ==============

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
    
    # Create services with enhanced form fields
    try:
        existing_count = db.services.count_documents({})
        if existing_count > 0:
            print(f"✅ Services already exist ({existing_count} services found)")
            return True
        
        print("📦 Creating 24 services with custom form fields...")
        
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
                'form_fields': [
                    {'name': 'student_name', 'label': 'Student Name', 'type': 'text', 'required': True},
                    {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
                    {'name': 'mother_name', 'label': "Mother's Name", 'type': 'text', 'required': True},
                    {'name': 'date_of_birth', 'label': 'Date of Birth', 'type': 'date', 'required': True},
                    {'name': 'gender', 'label': 'Gender', 'type': 'select', 'options': ['Male', 'Female', 'Other'], 'required': True},
                    {'name': 'caste_category', 'label': 'Caste Category', 'type': 'select', 'options': ['General', 'SC', 'ST', 'OBC', 'EWS'], 'required': True},
                    {'name': 'annual_income', 'label': 'Annual Family Income (₹)', 'type': 'number', 'required': True},
                    {'name': 'education_level', 'label': 'Education Level', 'type': 'select', 'options': ['Class 10', 'Class 12', 'Graduate', 'Post Graduate', 'PhD'], 'required': True},
                    {'name': 'institution_name', 'label': 'Institution Name', 'type': 'text', 'required': True},
                    {'name': 'course_name', 'label': 'Course Name', 'type': 'text', 'required': True},
                    {'name': 'academic_year', 'label': 'Academic Year', 'type': 'text', 'required': True},
                    {'name': 'previous_marks', 'label': 'Previous Marks (%)', 'type': 'number', 'required': True},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': True},
                    {'name': 'bank_account_number', 'label': 'Bank Account Number', 'type': 'text', 'required': True},
                    {'name': 'ifsc_code', 'label': 'IFSC Code', 'type': 'text', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'student_name', 'label': 'Student Name', 'type': 'text', 'required': True},
                    {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
                    {'name': 'date_of_birth', 'label': 'Date of Birth', 'type': 'date', 'required': True},
                    {'name': 'gender', 'label': 'Gender', 'type': 'select', 'options': ['Male', 'Female', 'Other'], 'required': True},
                    {'name': 'admission_quota', 'label': 'Admission Quota', 'type': 'select', 'options': ['General', 'SC', 'ST', 'OBC', 'EWS', 'Sports', 'NRI'], 'required': True},
                    {'name': 'preferred_course', 'label': 'Preferred Course', 'type': 'text', 'required': True},
                    {'name': 'previous_education', 'label': 'Previous Education', 'type': 'text', 'required': True},
                    {'name': 'percentage_obtained', 'label': 'Percentage Obtained', 'type': 'number', 'required': True},
                    {'name': 'entrance_exam_score', 'label': 'Entrance Exam Score (if any)', 'type': 'text'},
                    {'name': 'college_name', 'label': 'College Name', 'type': 'text', 'required': True},
                    {'name': 'course_duration', 'label': 'Course Duration', 'type': 'text', 'required': True},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'candidate_name', 'label': 'Candidate Name', 'type': 'text', 'required': True},
                    {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
                    {'name': 'date_of_birth', 'label': 'Date of Birth', 'type': 'date', 'required': True},
                    {'name': 'gender', 'label': 'Gender', 'type': 'select', 'options': ['Male', 'Female', 'Other'], 'required': True},
                    {'name': 'exam_name', 'label': 'Exam Name', 'type': 'select', 'options': ['UPSC Civil Services', 'SSC CGL', 'SSC CHSL', 'Bank PO', 'Bank Clerk', 'Railway Group D', 'State PSC'], 'required': True},
                    {'name': 'exam_center_preference', 'label': 'Exam Center Preference', 'type': 'text', 'required': True},
                    {'name': 'educational_qualification', 'label': 'Educational Qualification', 'type': 'text', 'required': True},
                    {'name': 'percentage', 'label': 'Percentage', 'type': 'number', 'required': True},
                    {'name': 'category', 'label': 'Category', 'type': 'select', 'options': ['General', 'SC', 'ST', 'OBC', 'EWS'], 'required': True},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': True},
                    {'name': 'voter_id', 'label': 'Voter ID Number', 'type': 'text'},
                ],
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
                'form_fields': [
                    {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                    {'name': 'current_role', 'label': 'Current Role/Position', 'type': 'text', 'required': True},
                    {'name': 'experience_years', 'label': 'Years of Experience', 'type': 'number', 'required': True},
                    {'name': 'skill_set', 'label': 'Skills (comma separated)', 'type': 'text', 'required': True},
                    {'name': 'preferred_industry', 'label': 'Preferred Industry', 'type': 'select', 'options': ['Technology', 'Healthcare', 'Education', 'Finance', 'Retail', 'Manufacturing', 'Other'], 'required': True},
                    {'name': 'preferred_role', 'label': 'Preferred Role', 'type': 'text', 'required': True},
                    {'name': 'expected_salary', 'label': 'Expected Salary', 'type': 'text'},
                    {'name': 'notice_period', 'label': 'Notice Period', 'type': 'select', 'options': ['Immediate', '15 Days', '30 Days', '45 Days', '60 Days'], 'required': True},
                    {'name': 'linkedin_profile', 'label': 'LinkedIn Profile URL', 'type': 'url'},
                    {'name': 'portfolio_url', 'label': 'Portfolio URL', 'type': 'url'},
                ],
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
                'form_fields': [
                    {'name': 'full_name', 'label': 'Full Name', 'type': 'text', 'required': True},
                    {'name': 'current_designation', 'label': 'Current Designation', 'type': 'text', 'required': True},
                    {'name': 'total_experience', 'label': 'Total Experience (years)', 'type': 'number', 'required': True},
                    {'name': 'key_skills', 'label': 'Key Skills (comma separated)', 'type': 'text', 'required': True},
                    {'name': 'resume_template', 'label': 'Resume Template', 'type': 'select', 'options': ['Modern', 'Classic', 'Creative', 'Minimal', 'Executive'], 'required': True},
                    {'name': 'industry_sector', 'label': 'Industry Sector', 'type': 'select', 'options': ['IT/Software', 'Finance', 'Healthcare', 'Education', 'Marketing', 'Sales', 'Other'], 'required': True},
                    {'name': 'career_objective', 'label': 'Career Objective', 'type': 'textarea', 'required': True},
                    {'name': 'achievements', 'label': 'Key Achievements', 'type': 'textarea'},
                    {'name': 'languages_known', 'label': 'Languages Known', 'type': 'text', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'full_name', 'label': 'Full Name', 'type': 'text', 'required': True},
                    {'name': 'current_headline', 'label': 'Current Headline (e.g., Software Engineer @ Google)', 'type': 'text', 'required': True},
                    {'name': 'current_company', 'label': 'Current Company', 'type': 'text', 'required': True},
                    {'name': 'current_role', 'label': 'Current Role', 'type': 'text', 'required': True},
                    {'name': 'industry', 'label': 'Industry', 'type': 'select', 'options': ['Technology', 'Healthcare', 'Education', 'Finance', 'Retail', 'Manufacturing', 'Other'], 'required': True},
                    {'name': 'linkedin_url', 'label': 'LinkedIn Profile URL', 'type': 'url', 'required': True},
                    {'name': 'target_audience', 'label': 'Target Audience', 'type': 'text', 'required': True},
                    {'name': 'specializations', 'label': 'Specializations', 'type': 'text'},
                    {'name': 'content_preferences', 'label': 'Content Preferences', 'type': 'textarea'},
                ],
                'created_at': datetime.now(timezone.utc)
            },
            # 7-9. Bill Payments - Minimal fields
            {
                'category': 'bill_payment',
                'name': 'Electricity Bill Payment',
                'slug': 'electricity-bill-payment',
                'description': 'Quick and secure online electricity bill payment for all major providers.',
                'icon': 'fas fa-lightbulb',
                'service_charge': 0,
                'is_active': True,
                'order': 7,
                'form_fields': [
                    {'name': 'consumer_name', 'label': 'Consumer Name', 'type': 'text', 'required': True},
                    {'name': 'consumer_number', 'label': 'Consumer Number', 'type': 'text', 'required': True},
                    {'name': 'bill_amount', 'label': 'Bill Amount', 'type': 'number', 'required': True},
                    {'name': 'due_date', 'label': 'Due Date', 'type': 'date', 'required': True},
                    {'name': 'provider_name', 'label': 'Service Provider', 'type': 'select', 'options': ['Tata Power', 'Adani Electricity', 'BSES', 'CESC', 'State Electricity Board', 'Other'], 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'consumer_name', 'label': 'Consumer Name', 'type': 'text', 'required': True},
                    {'name': 'consumer_number', 'label': 'Consumer Number', 'type': 'text', 'required': True},
                    {'name': 'bill_amount', 'label': 'Bill Amount', 'type': 'number', 'required': True},
                    {'name': 'due_date', 'label': 'Due Date', 'type': 'date', 'required': True},
                    {'name': 'property_address', 'label': 'Property Address', 'type': 'textarea', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'mobile_number', 'label': 'Mobile Number', 'type': 'text', 'required': True},
                    {'name': 'operator', 'label': 'Operator', 'type': 'select', 'options': ['Airtel', 'Jio', 'Vi', 'BSNL', 'MTNL'], 'required': True},
                    {'name': 'plan_type', 'label': 'Plan Type', 'type': 'select', 'options': ['Prepaid', 'Postpaid'], 'required': True},
                    {'name': 'recharge_amount', 'label': 'Recharge Amount (₹)', 'type': 'number', 'required': True},
                    {'name': 'validity_days', 'label': 'Validity (Days)', 'type': 'number', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                    {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
                    {'name': 'date_of_birth', 'label': 'Date of Birth', 'type': 'date', 'required': True},
                    {'name': 'pan_type', 'label': 'Service Type', 'type': 'select', 'options': ['New PAN Card', 'Reprint', 'Update Details'], 'required': True},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': True},
                    {'name': 'address_proof', 'label': 'Address Proof', 'type': 'text', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                    {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
                    {'name': 'mother_name', 'label': "Mother's Name", 'type': 'text', 'required': True},
                    {'name': 'date_of_birth', 'label': 'Date of Birth', 'type': 'date', 'required': True},
                    {'name': 'passport_type', 'label': 'Passport Type', 'type': 'select', 'options': ['New Passport', 'Renewal', 'Reissue'], 'required': True},
                    {'name': 'marital_status', 'label': 'Marital Status', 'type': 'select', 'options': ['Single', 'Married', 'Divorced', 'Widowed'], 'required': True},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': True},
                    {'name': 'pan_number', 'label': 'PAN Number', 'type': 'text'},
                    {'name': 'passport_number', 'label': 'Old Passport Number (for renewal)', 'type': 'text'},
                ],
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
                'form_fields': [
                    {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                    {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
                    {'name': 'address', 'label': 'Residential Address', 'type': 'textarea', 'required': True},
                    {'name': 'annual_income', 'label': 'Annual Income (₹)', 'type': 'number', 'required': True},
                    {'name': 'income_source', 'label': 'Income Source', 'type': 'select', 'options': ['Salary', 'Business', 'Agriculture', 'Pension', 'Other'], 'required': True},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': True},
                    {'name': 'ration_card_number', 'label': 'Ration Card Number', 'type': 'text'},
                ],
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
                'form_fields': [
                    {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                    {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
                    {'name': 'mother_name', 'label': "Mother's Name", 'type': 'text', 'required': True},
                    {'name': 'caste_category', 'label': 'Caste Category', 'type': 'select', 'options': ['SC', 'ST', 'OBC', 'General'], 'required': True},
                    {'name': 'sub_caste', 'label': 'Sub-Caste', 'type': 'text'},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': True},
                    {'name': 'permanent_address', 'label': 'Permanent Address', 'type': 'textarea', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'print_type', 'label': 'Print Type', 'type': 'select', 'options': ['Document Printing', 'Photo Printing', 'Flyer/Brochure', 'Poster', 'Business Card', 'Other'], 'required': True},
                    {'name': 'color_option', 'label': 'Color Option', 'type': 'select', 'options': ['Black & White', 'Color'], 'required': True},
                    {'name': 'page_count', 'label': 'Number of Pages', 'type': 'number', 'required': True},
                    {'name': 'print_quantity', 'label': 'Quantity', 'type': 'number', 'required': True},
                    {'name': 'paper_size', 'label': 'Paper Size', 'type': 'select', 'options': ['A4', 'A5', 'Letter', 'Legal', 'Custom'], 'required': True},
                    {'name': 'delivery_option', 'label': 'Delivery Option', 'type': 'select', 'options': ['Pickup', 'Delivery'], 'required': True},
                    {'name': 'special_instructions', 'label': 'Special Instructions', 'type': 'textarea'},
                ],
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
                'form_fields': [
                    {'name': 'document_type', 'label': 'Document Type', 'type': 'select', 'options': ['Documents', 'Photos', 'Books', 'Legal Papers', 'Other'], 'required': True},
                    {'name': 'scan_quality', 'label': 'Scan Quality', 'type': 'select', 'options': ['Standard (300 DPI)', 'High (600 DPI)', 'Archival (1200 DPI)'], 'required': True},
                    {'name': 'page_count', 'label': 'Number of Pages', 'type': 'number', 'required': True},
                    {'name': 'color_option', 'label': 'Color Option', 'type': 'select', 'options': ['Black & White', 'Color'], 'required': True},
                    {'name': 'output_format', 'label': 'Output Format', 'type': 'select', 'options': ['PDF', 'JPEG', 'PNG', 'TIFF'], 'required': True},
                    {'name': 'document_size', 'label': 'Document Size', 'type': 'select', 'options': ['A4', 'A3', 'Legal', 'Letter'], 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                    {'name': 'photo_purpose', 'label': 'Photo Purpose', 'type': 'select', 'options': ['Passport', 'Visa', 'ID Card', 'Driving License', 'Other'], 'required': True},
                    {'name': 'country_of_application', 'label': 'Country of Application', 'type': 'text', 'required': True},
                    {'name': 'photo_quantity', 'label': 'Number of Photos', 'type': 'number', 'required': True},
                    {'name': 'photo_size', 'label': 'Photo Size', 'type': 'select', 'options': ['2x2 inch (Passport)', '1x1 inch', '2x3 inch', 'Custom'], 'required': True},
                    {'name': 'background_color', 'label': 'Background Color', 'type': 'select', 'options': ['White', 'Light Grey', 'Light Blue', 'Other'], 'required': True},
                    {'name': 'delivery_option', 'label': 'Delivery Option', 'type': 'select', 'options': ['Pickup', 'Digital Delivery', 'Shipping'], 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'business_name', 'label': 'Business/Project Name', 'type': 'text', 'required': True},
                    {'name': 'website_type', 'label': 'Website Type', 'type': 'select', 'options': ['Business Website', 'E-Commerce', 'Portfolio', 'Blog', 'Landing Page', 'Web Application'], 'required': True},
                    {'name': 'industry', 'label': 'Industry', 'type': 'select', 'options': ['Technology', 'Healthcare', 'Education', 'Finance', 'Retail', 'Manufacturing', 'Other'], 'required': True},
                    {'name': 'features', 'label': 'Features Needed', 'type': 'textarea', 'required': True},
                    {'name': 'pages_required', 'label': 'Number of Pages', 'type': 'number', 'required': True},
                    {'name': 'design_style', 'label': 'Design Style Preference', 'type': 'text', 'required': True},
                    {'name': 'target_audience', 'label': 'Target Audience', 'type': 'text', 'required': True},
                    {'name': 'color_preference', 'label': 'Color Preference', 'type': 'text'},
                    {'name': 'deadline', 'label': 'Expected Deadline', 'type': 'date', 'required': True},
                    {'name': 'budget_range', 'label': 'Budget Range', 'type': 'text', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'project_name', 'label': 'Project Name', 'type': 'text', 'required': True},
                    {'name': 'data_type', 'label': 'Type of Data', 'type': 'select', 'options': ['Text', 'Numerical', 'Form Data', 'Excel/Spreadsheet', 'Image Data', 'PDF Data'], 'required': True},
                    {'name': 'data_volume', 'label': 'Approximate Data Volume', 'type': 'text', 'required': True},
                    {'name': 'deadline', 'label': 'Deadline', 'type': 'date', 'required': True},
                    {'name': 'preferred_format', 'label': 'Preferred Output Format', 'type': 'select', 'options': ['Excel', 'CSV', 'Word', 'PDF', 'Google Sheets'], 'required': True},
                    {'name': 'special_instructions', 'label': 'Special Instructions', 'type': 'textarea'},
                ],
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
                'form_fields': [
                    {'name': 'project_name', 'label': 'Project Name', 'type': 'text', 'required': True},
                    {'name': 'service_type', 'label': 'Service Type', 'type': 'select', 'options': ['Excel Automation', 'Data Analysis', 'Dashboard Creation', 'Report Generation', 'VBA Macros'], 'required': True},
                    {'name': 'data_source', 'label': 'Data Source', 'type': 'text', 'required': True},
                    {'name': 'analysis_goal', 'label': 'Analysis Goal', 'type': 'textarea', 'required': True},
                    {'name': 'deliverable', 'label': 'Deliverable', 'type': 'select', 'options': ['Excel File', 'PowerPoint Presentation', 'Dashboard', 'Report'], 'required': True},
                    {'name': 'deadline', 'label': 'Deadline', 'type': 'date', 'required': True},
                    {'name': 'special_requirements', 'label': 'Special Requirements', 'type': 'textarea'},
                ],
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
                'form_fields': [
                    {'name': 'traveler_name', 'label': 'Traveler Name', 'type': 'text', 'required': True},
                    {'name': 'trip_type', 'label': 'Trip Type', 'type': 'select', 'options': ['Domestic', 'International'], 'required': True},
                    {'name': 'destination', 'label': 'Destination', 'type': 'text', 'required': True},
                    {'name': 'source', 'label': 'Departure City', 'type': 'text', 'required': True},
                    {'name': 'departure_date', 'label': 'Departure Date', 'type': 'date', 'required': True},
                    {'name': 'return_date', 'label': 'Return Date', 'type': 'date'},
                    {'name': 'preferred_airline', 'label': 'Preferred Airline', 'type': 'text'},
                    {'name': 'preferred_hotel', 'label': 'Preferred Hotel', 'type': 'text'},
                    {'name': 'budget_range', 'label': 'Budget Range', 'type': 'select', 'options': ['Economy', 'Mid-Range', 'Luxury', 'Custom'], 'required': True},
                    {'name': 'number_of_travelers', 'label': 'Number of Travelers', 'type': 'number', 'required': True},
                    {'name': 'special_requests', 'label': 'Special Requests', 'type': 'textarea'},
                    {'name': 'passport_number', 'label': 'Passport Number (for international)', 'type': 'text'},
                ],
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
                'form_fields': [
                    {'name': 'business_name', 'label': 'Business Name', 'type': 'text', 'required': True},
                    {'name': 'business_type', 'label': 'Business Type', 'type': 'select', 'options': ['Sole Proprietorship', 'Partnership', 'LLP', 'Private Limited Company', 'Public Limited Company'], 'required': True},
                    {'name': 'pan_number', 'label': 'PAN Number', 'type': 'text', 'required': True},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number (Proprietor/Director)', 'type': 'text', 'required': True},
                    {'name': 'business_address', 'label': 'Business Address', 'type': 'textarea', 'required': True},
                    {'name': 'business_activity', 'label': 'Nature of Business', 'type': 'text', 'required': True},
                    {'name': 'annual_turnover', 'label': 'Estimated Annual Turnover (₹)', 'type': 'number', 'required': True},
                    {'name': 'registration_type', 'label': 'Registration Type', 'type': 'select', 'options': ['Normal Registration', 'Composition Scheme', 'Voluntary Registration'], 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'business_name', 'label': 'Business Name', 'type': 'text', 'required': True},
                    {'name': 'business_type', 'label': 'Business Type', 'type': 'select', 'options': ['Sole Proprietorship', 'Partnership', 'LLP', 'Private Limited Company', 'One Person Company'], 'required': True},
                    {'name': 'owner_name', 'label': 'Owner/Director Name', 'type': 'text', 'required': True},
                    {'name': 'pan_number', 'label': 'PAN Number', 'type': 'text', 'required': True},
                    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': True},
                    {'name': 'business_address', 'label': 'Business Address', 'type': 'textarea', 'required': True},
                    {'name': 'business_activity', 'label': 'Nature of Business', 'type': 'text', 'required': True},
                    {'name': 'partners_directors', 'label': 'Partners/Directors Details (if any)', 'type': 'textarea'},
                    {'name': 'authorized_capital', 'label': 'Authorized Capital', 'type': 'text', 'required': True},
                ],
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
                'form_fields': [
                    {'name': 'business_name', 'label': 'Business/Project Name', 'type': 'text', 'required': True},
                    {'name': 'industry', 'label': 'Industry', 'type': 'select', 'options': ['Technology', 'Healthcare', 'Education', 'Finance', 'Retail', 'Manufacturing', 'Other'], 'required': True},
                    {'name': 'design_style', 'label': 'Design Style Preference', 'type': 'select', 'options': ['Modern', 'Minimalist', 'Classic', 'Creative', 'Corporate', 'Playful'], 'required': True},
                    {'name': 'colors', 'label': 'Preferred Colors', 'type': 'text', 'required': True},
                    {'name': 'concepts_required', 'label': 'Number of Concepts', 'type': 'select', 'options': ['3 Concepts', '5 Concepts', '10 Concepts'], 'required': True},
                    {'name': 'target_audience', 'label': 'Target Audience', 'type': 'text', 'required': True},
                    {'name': 'revisions', 'label': 'Revisions Included', 'type': 'select', 'options': ['2 Revisions', '5 Revisions', 'Unlimited'], 'required': True},
                    {'name': 'deliverables', 'label': 'Deliverables Needed', 'type': 'text', 'required': True},
                    {'name': 'inspiration', 'label': 'Inspiration/Reference Links', 'type': 'url'},
                    {'name': 'special_instructions', 'label': 'Special Instructions', 'type': 'textarea'},
                ],
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
                'form_fields': [
                    {'name': 'project_name', 'label': 'Project Name', 'type': 'text', 'required': True},
                    {'name': 'platform', 'label': 'Platform', 'type': 'select', 'options': ['Facebook', 'Instagram', 'Twitter', 'LinkedIn', 'YouTube', 'All Platforms'], 'required': True},
                    {'name': 'design_type', 'label': 'Design Type', 'type': 'select', 'options': ['Post Design', 'Cover Photo', 'Story Design', 'Ad Creative', 'Profile Picture', 'Video Thumbnail'], 'required': True},
                    {'name': 'quantity', 'label': 'Number of Designs', 'type': 'number', 'required': True},
                    {'name': 'design_style', 'label': 'Design Style', 'type': 'text', 'required': True},
                    {'name': 'colors', 'label': 'Preferred Colors', 'type': 'text', 'required': True},
                    {'name': 'brand_guidelines', 'label': 'Brand Guidelines', 'type': 'textarea'},
                    {'name': 'content_to_include', 'label': 'Content to Include', 'type': 'textarea', 'required': True},
                    {'name': 'deadline', 'label': 'Deadline', 'type': 'date', 'required': True},
                    {'name': 'special_instructions', 'label': 'Special Instructions', 'type': 'textarea'},
                ],
                'created_at': datetime.now(timezone.utc)
            }
        ]
        
        for service in services_data:
            db.services.insert_one(service)
            print(f"  ✅ Added: {service['name']}")
        
        print(f"✅ Successfully created {len(services_data)} services with custom forms!")
        
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
        
        # Get form fields from service
        form_fields = service.get('form_fields', [])
        
        return render_template('service_detail.html', service=service, user=user, form_fields=form_fields)
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
        
        # Get common fields
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        
        if not all([full_name, phone, address, city, state, pincode]):
            return jsonify({'success': False, 'message': 'Please fill all required common fields'}), 400
        
        # Get dynamic form fields
        dynamic_fields = {}
        form_fields = service.get('form_fields', [])
        for field in form_fields:
            field_name = field.get('name')
            field_value = request.form.get(field_name, '').strip()
            if field.get('required') and not field_value:
                return jsonify({'success': False, 'message': f'Please fill {field.get("label")}'}), 400
            if field_value:
                dynamic_fields[field_name] = field_value
        
        # Handle document uploads
        uploaded_files = []
        if 'documents' in request.files:
            files = request.files.getlist('documents')
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    filepath = os.path.join(app.config['DOCUMENT_FOLDER'], unique_filename)
                    file.save(filepath)
                    
                    # Get file size
                    file_size = os.path.getsize(filepath)
                    
                    uploaded_files.append({
                        'filename': unique_filename,
                        'original_filename': filename,
                        'file_size': file_size,
                        'uploaded_at': datetime.now(timezone.utc)
                    })
        
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
            'dynamic_fields': dynamic_fields,
            'documents': uploaded_files,
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
        
        # Create notification
        create_notification(
            session['user_id'],
            str(result.inserted_id),
            'Application Submitted',
            f'Your application for {service["name"]} has been submitted. Reference: {ref_number}',
            'success'
        )
        
        return jsonify({
            'success': True,
            'message': 'Application submitted successfully',
            'reference_number': ref_number,
            'amount': service.get('service_charge', 0),
            'requires_payment': service.get('service_charge', 0) > 0,
            'documents_uploaded': len(uploaded_files)
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
                {'service_name': {'$regex': search, '$options': 'i'}}
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
                'applicant_name': req.get('applicant_name', 'N/A'),
                'documents_count': len(req.get('documents', []))
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

# ============== Admin Routes ==============

# app.py - Add these routes to your existing app.py

# ============== Admin Dashboard Routes ==============

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Main admin dashboard with statistics"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Get statistics
        total_services = db.services.count_documents({})
        active_services = db.services.count_documents({'is_active': True})
        total_requests = db.service_requests.count_documents({})
        pending_requests = db.service_requests.count_documents({'status': 'pending'})
        completed_requests = db.service_requests.count_documents({'status': 'completed'})
        total_users = db.users.count_documents({'role': 'user'})
        
        # Recent applications
        recent_applications = list(db.service_requests.find()
                                   .sort('submitted_at', -1)
                                   .limit(5))
        
        # Recent users
        recent_users = list(db.users.find()
                           .sort('created_at', -1)
                           .limit(5))
        
        # Service-wise application count
        service_stats = []
        pipeline = [
            {'$group': {'_id': '$service_name', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': 10}
        ]
        service_stats = list(db.service_requests.aggregate(pipeline))
        
        # Monthly applications
        monthly_stats = []
        pipeline = [
            {
                '$group': {
                    '_id': {
                        'year': {'$year': '$submitted_at'},
                        'month': {'$month': '$submitted_at'}
                    },
                    'count': {'$sum': 1}
                }
            },
            {'$sort': {'_id.year': -1, '_id.month': -1}},
            {'$limit': 6}
        ]
        monthly_stats = list(db.service_requests.aggregate(pipeline))
        
        stats = {
            'total_services': total_services,
            'active_services': active_services,
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'completed_requests': completed_requests,
            'total_users': total_users
        }
        
        return render_template('admin_dashboard.html',
                             stats=stats,
                             recent_applications=recent_applications,
                             recent_users=recent_users,
                             service_stats=service_stats,
                             monthly_stats=monthly_stats)
    except Exception as e:
        print(f"Error loading admin dashboard: {e}")
        flash('Unable to load dashboard.', 'danger')
        return redirect(url_for('index'))

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
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/service/create', methods=['GET', 'POST'])
@login_required
def admin_create_service():
    """Create a new service with custom fields"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Get basic service data
            name = request.form.get('name', '').strip()
            slug = request.form.get('slug', '').strip()
            category = request.form.get('category', '').strip()
            description = request.form.get('description', '').strip()
            service_charge = float(request.form.get('service_charge', 0))
            processing_time = request.form.get('processing_time', '').strip()
            icon = request.form.get('icon', 'fas fa-cog').strip()
            is_active = request.form.get('is_active') == 'on'
            
            # Validate required fields
            if not name or not slug or not category:
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('admin_create_service'))
            
            # Check if slug exists
            existing = db.services.find_one({'slug': slug})
            if existing:
                flash('Service with this slug already exists. Please use a different slug.', 'danger')
                return redirect(url_for('admin_create_service'))
            
            # Get custom form fields from JSON
            form_fields_json = request.form.get('form_fields_json', '[]')
            try:
                form_fields = json.loads(form_fields_json)
            except:
                form_fields = []
            
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
                'form_fields': form_fields,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            result = db.services.insert_one(service_data)
            
            # Create notification for admin
            create_notification(
                session['user_id'],
                str(result.inserted_id),
                'Service Created',
                f'Service "{name}" has been created successfully.',
                'success'
            )
            
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
    """Edit an existing service with custom fields"""
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
            # Get basic service data
            name = request.form.get('name', '').strip()
            slug = request.form.get('slug', '').strip()
            category = request.form.get('category', '').strip()
            description = request.form.get('description', '').strip()
            service_charge = float(request.form.get('service_charge', 0))
            processing_time = request.form.get('processing_time', '').strip()
            icon = request.form.get('icon', 'fas fa-cog').strip()
            is_active = request.form.get('is_active') == 'on'
            order = int(request.form.get('order', 0))
            
            # Validate required fields
            if not name or not slug or not category:
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('admin_edit_service', service_id=service_id))
            
            # Check if slug exists (excluding current service)
            existing = db.services.find_one({'slug': slug, '_id': {'$ne': ObjectId(service_id)}})
            if existing:
                flash('Service with this slug already exists. Please use a different slug.', 'danger')
                return redirect(url_for('admin_edit_service', service_id=service_id))
            
            # Get custom form fields from JSON
            form_fields_json = request.form.get('form_fields_json', '[]')
            try:
                form_fields = json.loads(form_fields_json)
            except:
                form_fields = []
            
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
                'form_fields': form_fields,
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
        form_fields_json = json.dumps(service.get('form_fields', []))
        
        return render_template('admin_service_form.html', 
                             service=service,
                             categories=categories,
                             form_fields_json=form_fields_json,
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
            return jsonify({
                'success': False, 
                'message': f'Cannot delete service with {app_count} applications. Archive it instead.'
            }), 400
        
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

@app.route('/admin/service/fields/<service_id>', methods=['GET'])
@login_required
def admin_get_service_fields(service_id):
    """Get service fields for AJAX"""
    user = get_user_by_id(session['user_id'])
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        service = db.services.find_one({'_id': ObjectId(service_id)})
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        return jsonify({
            'success': True,
            'fields': service.get('form_fields', [])
        })
    except Exception as e:
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
print("🚀 Running database initialization...")
init_database()
print("✅ Application ready!")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)