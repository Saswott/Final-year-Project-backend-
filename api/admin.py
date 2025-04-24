from django.contrib import admin
from .models import Medicine, Category

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'stock', 'price', 'expiry_date', 'status')
    list_filter = ('category', 'status')  # Removed pharmacy__pharmacy_name
    search_fields = ('name', 'manufacturer')
    ordering = ('name',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)