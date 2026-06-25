from datetime import datetime, timezone
from bson import ObjectId
import random
import json
import re

class BaseModel:
    """Base model with common utilities"""
    
    @staticmethod
    def to_dict(doc):
        """Convert MongoDB document to dict with string ID"""
        if not doc:
            return None
        doc_dict = dict(doc)
        if '_id' in doc_dict:
            doc_dict['id'] = str(doc_dict.pop('_id'))
        
        # Format datetime fields
        for field in ['created_at', 'last_login', 'processed_at', 'submitted_at', 'uploaded_at']:
            if field in doc_dict and doc_dict[field]:
                if isinstance(doc_dict[field], datetime):
                    doc_dict[field] = doc_dict[field].strftime('%Y-%m-%d %H:%M:%S')
        
        return doc_dict

class User(BaseModel):
    """User model"""
    COLLECTION = 'users'
    
    @staticmethod
    def create(name, phone, email=None, role='user', address=None, city=None, state=None, pincode=None):
        return {
            'name': name.strip().title(),
            'phone': phone,
            'email': email,
            'role': role,
            'is_active': True,
            'address': address,
            'city': city,
            'state': state,
            'pincode': pincode,
            'created_at': datetime.now(timezone.utc),
            'last_login': None
        }
    
    @staticmethod
    def validate_phone(phone):
        return bool(re.match(r'^[6-9]\d{9}$', phone))
    
    @staticmethod
    def validate_email(email):
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))
    
    @staticmethod
    def validate_pincode(pincode):
        return bool(re.match(r'^\d{6}$', pincode))

class Service(BaseModel):
    """Service model"""
    COLLECTION = 'services'
    
    @staticmethod
    def create(category, name, description, eligibility=None, documents_required=None,
               instructions=None, processing_time=None, service_charge=0,
               convenience_fee_percent=2, gst_percent=18, icon='fas fa-file-alt'):
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        
        return {
            'category': category,
            'name': name.strip(),
            'slug': slug,
            'description': description.strip(),
            'eligibility': eligibility,
            'documents_required': documents_required,
            'instructions': instructions,
            'processing_time': processing_time or '7-10 working days',
            'service_charge': float(service_charge),
            'convenience_fee_percent': float(convenience_fee_percent),
            'gst_percent': float(gst_percent),
            'is_active': True,
            'icon': icon,
            'created_at': datetime.now(timezone.utc)
        }

class ServiceRequest(BaseModel):
    """Service Request model"""
    COLLECTION = 'service_requests'
    
    @staticmethod
    def generate_reference():
        return f'DS{datetime.now().strftime("%Y%m%d%H%M%S")}{random.randint(1000, 9999)}'
    
    @staticmethod
    def create(user_id, service_id, service_name, service_type, details, amount=0):
        return {
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'service_id': ObjectId(service_id) if isinstance(service_id, str) else service_id,
            'service_name': service_name,
            'service_type': service_type,
            'details': details,
            'amount': float(amount),
            'reference_number': ServiceRequest.generate_reference(),
            'status': 'pending',
            'payment_status': 'pending',
            'submitted_at': datetime.now(timezone.utc),
            'processed_at': None,
            'admin_remarks': None,
            'timeline': [
                {
                    'title': 'Application Submitted',
                    'description': 'Your application has been submitted successfully.',
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'completed': True
                }
            ]
        }

class PaymentTransaction(BaseModel):
    """Payment model"""
    COLLECTION = 'payment_transactions'
    
    @staticmethod
    def generate_transaction_id():
        return f'TXN{datetime.now().strftime("%Y%m%d%H%M%S")}{random.randint(10000, 99999)}'
    
    @staticmethod
    def create(user_id, request_id, amount, payment_method='online'):
        return {
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'request_id': ObjectId(request_id) if isinstance(request_id, str) else request_id,
            'transaction_id': PaymentTransaction.generate_transaction_id(),
            'amount': float(amount),
            'payment_method': payment_method,
            'status': 'completed',
            'created_at': datetime.now(timezone.utc)
        }

class Notification(BaseModel):
    """Notification model"""
    COLLECTION = 'notifications'
    
    @staticmethod
    def create(user_id, title, message, type='info', request_id=None):
        return {
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'title': title,
            'message': message,
            'type': type,
            'request_id': str(request_id) if request_id else None,
            'is_read': False,
            'created_at': datetime.now(timezone.utc)
        }

class RequestDocument(BaseModel):
    """Document model"""
    COLLECTION = 'request_documents'
    
    @staticmethod
    def create(request_id, original_filename, stored_filename, file_path, file_size):
        return {
            'request_id': ObjectId(request_id) if isinstance(request_id, str) else request_id,
            'original_filename': original_filename,
            'stored_filename': stored_filename,
            'file_path': file_path,
            'file_size': file_size,
            'uploaded_at': datetime.now(timezone.utc)
        }

def calculate_fees(service_charge, convenience_fee_percent=2, gst_percent=18):
    """Calculate total fees with taxes"""
    convenience_fee = (service_charge * convenience_fee_percent) / 100
    subtotal = service_charge + convenience_fee
    gst = (subtotal * gst_percent) / 100
    total = subtotal + gst
    
    return {
        'service_charge': round(service_charge, 2),
        'convenience_fee': round(convenience_fee, 2),
        'convenience_fee_percent': convenience_fee_percent,
        'subtotal': round(subtotal, 2),
        'gst': round(gst, 2),
        'gst_percent': gst_percent,
        'total': round(total, 2)
    }