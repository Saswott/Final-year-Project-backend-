from rest_framework import serializers
from .models import User, Pharmacy, Medicine, Category
from django.contrib.auth.password_validation import validate_password


# 🏥 Pharmacy Serializer
class PharmacySerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = ['pharmacy_name', 'license_number', 'phone_number', 'address']


# 👤 Basic User Serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'role']


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
        user = User.objects.create_user(**validated_data)
        Pharmacy.objects.create(user=user, **pharmacy_data)
        return user


# 🧪 Category Serializer
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


# 💊 Medicine Serializer
class MedicineSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    pharmacy_name = serializers.SerializerMethodField()
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())

    class Meta:
        model = Medicine
        fields = [
            'id', 'name', 'category', 'category_name', 'stock', 'price',
            'expiry_date', 'manufacturer', 'status', 'pharmacy', 'pharmacy_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'created_at', 'updated_at']

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_pharmacy_name(self, obj):
        return obj.pharmacy.pharmacy_name if obj.pharmacy else None

    def create(self, validated_data):
        request = self.context.get('request')
        if request and not validated_data.get('pharmacy'):
            user = request.user
            if hasattr(user, 'pharmacy'):
                validated_data['pharmacy'] = user.pharmacy

        stock = validated_data.get('stock', 0)
        if stock <= 0:
            validated_data['status'] = Medicine.OUT_OF_STOCK
        elif stock <= 200:
            validated_data['status'] = Medicine.LOW_STOCK
        else:
            validated_data['status'] = Medicine.IN_STOCK

        return super().create(validated_data)


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
            role='employee'
        )
        return user
