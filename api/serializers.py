from rest_framework import serializers
from .models import User, Pharmacy, Medicine, Category, Prescription, Invoice, RecentActivity, Message
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from decimal import Decimal
from django.db import transaction
import json


# 🏥 Pharmacy Serializer
class PharmacySerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = ['pharmacy_name', 'license_number', 'phone_number', 'address']


# 👤 Basic User Serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone_number',
            'role', 'is_active', 'is_verified', 'date_joined'
        ]
        read_only_fields = ['is_active', 'is_verified', 'date_joined']


# 🏥 Pharmacy Registration Serializer
class PharmacyRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)
    pharmacy = PharmacySerializer()

    class Meta:
        model = User
        fields = ['email', 'password', 'confirm_password', 'pharmacy', 'role']
        extra_kwargs = {
            'role': {'read_only': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Passwords don't match"})
        return attrs

    def create(self, validated_data):
        pharmacy_data = validated_data.pop('pharmacy')

        validated_data['role'] = 'pharmacy'
        validated_data['is_active'] = True
        validated_data['is_verified'] = True

        user = User.objects.create_user(**validated_data)
        pharmacy = Pharmacy.objects.create(user=user, **pharmacy_data)

        user.pharmacy = pharmacy
        user.save()

        return user


# 🧪 Category Serializer
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


# 💊 Medicine Serializer
class MedicineSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    expiry_date = serializers.DateField(format='%Y-%m-%d', input_formats=['%Y-%m-%d'])

    class Meta:
        model = Medicine
        fields = [
            'id', 'name', 'category', 'category_name', 'stock', 'price',
            'expiry_date', 'manufacturer', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'created_at', 'updated_at']

    def validate_category(self, value):
        if not value:
            raise serializers.ValidationError("Category is required")
        return value

    def validate(self, data):
        if 'stock' in data and data['stock'] < 0:
            raise serializers.ValidationError({"stock": "Stock cannot be negative"})
        if 'price' in data and data['price'] <= 0:
            raise serializers.ValidationError({"price": "Price must be positive"})
        if 'expiry_date' in data and data['expiry_date'] < timezone.now().date():
            raise serializers.ValidationError({"expiry_date": "Expiry date must be in the future"})
        return data

    def create(self, validated_data):
        return Medicine.objects.create(**validated_data)


# 👨‍💼 Employee Registration Serializer
class EmployeeRegistrationSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, required=True)
    citizenship_document = serializers.FileField(required=True)

    class Meta:
        model = User
        fields = [
            'email', 'password', 'confirm_password', 'first_name', 'last_name',
            'phone_number', 'age', 'address', 'citizenship_document'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'validators': [validate_password]},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'phone_number': {'required': True},
            'age': {'required': True},
            'address': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone_number=validated_data['phone_number'],
            age=validated_data['age'],
            address=validated_data['address'],
            citizenship_document=validated_data['citizenship_document'],
            role='employee',
            is_active=False,
            is_verified=False,
        )
        
        # Associate with pharmacy if the request user is a pharmacy owner
        request = self.context.get('request')
        if request and request.user.pharmacy:
            user.pharmacy = request.user.pharmacy
            user.save()
            
        return user


# 👨‍💼 Employee Detail Serializer
class EmployeeDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone_number',
            'age', 'address', 'role', 'is_active', 'is_verified', 'date_joined'
        ]
        read_only_fields = ['id', 'email', 'date_joined']


# 📝 Prescription Serializer  
class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = ['id', 'patient', 'date', 'medications', 'status', 'doctor', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'doctor']

    def validate_medications(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one medication is required")
        return value

    def validate(self, data):
        # Ensure date is not in the past
        if 'date' in data and data['date'] < timezone.now().date():
            raise serializers.ValidationError({"date": "Date cannot be in the past"})
        return data


# 💵 Invoice Serializer
class InvoiceSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    pharmacy = PharmacySerializer(read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        coerce_to_string=True
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'customer_name', 'customer_email', 
            'customer_phone', 'doctor_name', 'items', 'subtotal',
            'discount_percentage', 'discount_amount', 'total_amount', 
            'payment_method', 'status', 'created_by', 'pharmacy', 
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice_number', 'created_by', 'pharmacy', 
            'created_at', 'updated_at', 'total_amount', 'subtotal',
            'discount_percentage', 'discount_amount'
        ]

    def to_representation(self, instance):
        """Convert Decimal fields to strings in the response"""
        ret = super().to_representation(instance)
        ret['total_amount'] = str(ret['total_amount'])
        ret['subtotal'] = str(ret['subtotal'])
        ret['discount_amount'] = str(ret['discount_amount'])
        
        if 'items' in ret:
            if isinstance(ret['items'], str):
                try:
                    ret['items'] = json.loads(ret['items'])
                except json.JSONDecodeError:
                    ret['items'] = []
            
            for item in ret['items']:
                if 'price' in item:
                    item['price'] = str(item['price'])
                if 'total' in item:
                    item['total'] = str(item['total'])
        
        return ret

    def validate(self, data):
        if not data.get('customer_name'):
            raise serializers.ValidationError({"customer_name": "Customer name is required"})
        
        if not data.get('customer_phone'):
            data['customer_phone'] = '0000000000'
        
        items = data.get('items', [])
        if not items or len(items) == 0:
            raise serializers.ValidationError({"items": "At least one item is required"})
        
        for item in items:
            if not all(k in item for k in ['name', 'quantity']):
                raise serializers.ValidationError({
                    "items": "Each item must have name and quantity"
                })
            if item['quantity'] <= 0:
                raise serializers.ValidationError({
                    "items": "Quantity must be greater than 0"
                })
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        
        if not hasattr(user, 'pharmacy'):
            raise serializers.ValidationError(
                {"pharmacy": "User is not associated with any pharmacy"}
            )

        items = validated_data['items']
        subtotal = Decimal('0')
        updated_items = []
        
        for item in items:
            try:
                medicine = Medicine.objects.get(name__iexact=item['name'])
                item_price = Decimal(str(medicine.price))
                item_total = item['quantity'] * item_price
                subtotal += item_total
                
                updated_items.append({
                    'name': item['name'],
                    'quantity': item['quantity'],
                    'price': str(item_price),
                    'total': str(item_total)
                })
                
                if medicine.stock < item['quantity']:
                    raise serializers.ValidationError({
                        "items": f"Insufficient stock for {item['name']}. Available: {medicine.stock}"
                    })
                    
            except Medicine.DoesNotExist:
                raise serializers.ValidationError({
                    "items": f"Medicine {item['name']} not found in inventory"
                })
        
        validated_data['items'] = updated_items
        validated_data['subtotal'] = subtotal
        
        invoice = Invoice.objects.create(**validated_data)
        
        for item in items:
            medicine = Medicine.objects.get(name__iexact=item['name'])
            medicine.stock -= item['quantity']
            medicine.save()
        
        return invoice


# 🕒 Recent Activity Serializer
class RecentActivitySerializer(serializers.ModelSerializer):
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    medicine_name = serializers.CharField(source='medicine.name', read_only=True)
    timestamp = serializers.DateTimeField(format='%H:%M')
    
    class Meta:
        model = RecentActivity
        fields = [
            'id', 
            'activity_type', 
            'activity_type_display',
            'medicine_name',
            'old_value', 
            'new_value', 
            'timestamp'
        ]


# 📩 Message Serializer
class MessageSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format='%b %d, %Y %I:%M %p')
    
    class Meta:
        model = Message
        fields = [
            'id', 
            'employee', 
            'employee_name', 
            'pharmacy', 
            'message', 
            'created_at', 
            'is_read'
        ]
        read_only_fields = [
            'id', 
            'employee', 
            'pharmacy', 
            'created_at', 
            'is_read'
        ]
    
    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['message']
        extra_kwargs = {
            'message': {'required': True}
        }

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated")
        
        if request.user.role != 'employee':
            raise serializers.ValidationError("Only employees can send messages")
        
        if not hasattr(request.user, 'pharmacy'):
            raise serializers.ValidationError("Employee must be associated with a pharmacy")
        
        return Message.objects.create(
            employee=request.user,
            pharmacy=request.user.pharmacy,
            message=validated_data['message']
        )
    
    