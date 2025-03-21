from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Pharmacy

class UserAdminCustom(UserAdmin):
    # Display fields in the admin list view
    list_display = ('email', 'role', 'employee_id', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser')
    search_fields = ('email',)
    ordering = ('email',)

    # Customize the form fields for the user
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'employee_id', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'password1', 'password2')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'employee_id', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    filter_horizontal = ('groups', 'user_permissions')

class PharmacyAdmin(admin.ModelAdmin):
    list_display = ('pharmacy_name', 'user', 'license_number', 'phone_number', 'address')
    search_fields = ('pharmacy_name', 'license_number', 'phone_number')
    list_filter = ('user__role',)  # Filter pharmacies by user role (e.g., employee or pharmacy)
    
    # Allow quick editing of certain fields directly in the list view
    list_editable = ('phone_number', 'address')

# Register the models with the admin site
admin.site.register(User, UserAdminCustom)
admin.site.register(Pharmacy, PharmacyAdmin)
