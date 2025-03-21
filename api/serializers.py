from rest_framework import serializers
from .models import User, Pharmacy
from django.contrib.auth.password_validation import validate_password

class PharmacySerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = ['pharmacy_name', 'license_number', 'phone_number', 'address']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'role']

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