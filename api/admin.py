from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Pharmacy, Medicine, Category

class UserAdminCustom(UserAdmin):
    list_display = ('email', 'role', 'employee_id', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser')
    search_fields = ('email',)
    ordering = ('email',)

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
    list_filter = ('user__role',)
    list_editable = ('phone_number', 'address')

class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'pharmacy', 'category', 'stock', 'price', 'expiry_date', 'status')
    list_filter = ('category', 'status', 'pharmacy')
    search_fields = ('name', 'manufacturer')
    date_hierarchy = 'expiry_date'
    readonly_fields = ('status',)  # status is automatically calculated

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# Register all models
admin.site.register(User, UserAdminCustom)
admin.site.register(Pharmacy, PharmacyAdmin)
admin.site.register(Medicine, MedicineAdmin)
admin.site.register(Category, CategoryAdmin)
