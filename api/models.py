from django.db import models
from django.db.models import JSONField
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone


# ========================
# User Manager
# ========================
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


# ========================
# Custom User Model
# ========================
class User(AbstractUser):
    ROLE_CHOICES = (
        ('employee', 'Employee'),
        ('pharmacy', 'Pharmacy'),
    )

    username = None
    email = models.EmailField(unique=True)
    employee_id = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='pharmacy')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    pharmacy = models.ForeignKey(
        'Pharmacy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff'
    )

    phone_number = models.CharField(max_length=20, blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    citizenship_document = models.FileField(upload_to='citizenship_documents/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='api_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='api_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    @property
    def pharmacy_profile(self):
        try:
            return self.pharmacy
        except Pharmacy.DoesNotExist:
            return None


# ========================
# Pharmacy Model
# ========================
class Pharmacy(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pharmacy_profile')
    pharmacy_name = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=20)
    address = models.TextField()


# ========================
# Category Model
# ========================
class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

# ========================
# Prescription Model
# ========================
class Prescription(models.Model):
    PENDING = 'Pending'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'

    STATUS_CHOICES = (
        (PENDING, PENDING),
        (COMPLETED, COMPLETED),
        (CANCELLED, CANCELLED),
    )

    patient = models.CharField(max_length=100)
    date = models.DateField()
    medications = models.JSONField()  # Stores list of medications
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    doctor = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription for {self.patient} - {self.date}"


# ========================
# Medicine Model
# ========================
class Medicine(models.Model):
    IN_STOCK = 'In Stock'
    LOW_STOCK = 'Low Stock'
    OUT_OF_STOCK = 'Out of Stock'
    

    STATUS_CHOICES = (
        (IN_STOCK, IN_STOCK),
        (LOW_STOCK, LOW_STOCK),
        (OUT_OF_STOCK, OUT_OF_STOCK),
    )

    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='medicines')
    stock = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField()
    manufacturer = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=IN_STOCK)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.stock <= 0:
            self.status = self.OUT_OF_STOCK
        elif self.stock <= 200:
            self.status = self.LOW_STOCK
        else:
            self.status = self.IN_STOCK
        super().save(*args, **kwargs)
    
    def has_sufficient_stock(self, quantity):
        return self.stock >= quantity

    def reduce_stock(self, quantity):
        if self.has_sufficient_stock(quantity):
            self.stock -= quantity
            self.save()
            return True
        return False

# ========================
# Invoice/Billing Model
# ========================
class Invoice(models.Model):
    PENDING = 'Pending'
    PAID = 'Paid'
    CANCELLED = 'Cancelled'

    STATUS_CHOICES = (
        (PENDING, PENDING),
        (PAID, PAID),
        (CANCELLED, CANCELLED),
    )

    PAYMENT_METHODS = (
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('Online', 'Online Payment'),
    )

    invoice_number = models.CharField(max_length=20, unique=True)
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=15,)
    doctor_name = models.CharField(max_length=100,)
    items = JSONField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='Cash')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PAID)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='invoices')
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            today = timezone.now().date()
            last_invoice = Invoice.objects.filter(
                created_at__date=today
            ).order_by('-invoice_number').first()
            
            if last_invoice:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
                
            self.invoice_number = f"INV-{today.strftime('%Y%m%d')}-{new_num:04d}"
        
        # Calculate discount based on subtotal
        if not self.subtotal:
            self.subtotal = self.total_amount
            
        # Apply discount rules
        if self.subtotal > 10000:
            self.discount_percentage = 20
        elif self.subtotal > 5000:
            self.discount_percentage = 10
        elif self.subtotal > 2500:
            self.discount_percentage = 5
        else:
            self.discount_percentage = 0
            
        self.discount_amount = (self.subtotal * self.discount_percentage) / 100
        self.total_amount = self.subtotal - self.discount_amount
        
        # Ensure pharmacy is set if not provided
        if not self.pharmacy_id and self.created_by and self.created_by.pharmacy:
            self.pharmacy = self.created_by.pharmacy
        
        super().save(*args, **kwargs)




       # ========================  RecentActivity# ========================  

class RecentActivity(models.Model):
    ACTIVITY_TYPES = (
        ('new_medicine', 'New Medicine Added'),
        ('stock_update', 'Stock Updated'),
        ('price_change', 'Price Changed'),
        ('out_of_stock', 'Medicine Out of Stock'),
        ('low_stock', 'Low Stock Warning'),
        ('new_invoice', 'New Invoice Created'),
        ('prescription', 'Prescription Filled'),
    )

    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    prescription = models.ForeignKey(Prescription, on_delete=models.SET_NULL, null=True, blank=True)
    old_value = models.CharField(max_length=100, blank=True, null=True)
    new_value = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='activities')

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Recent Activities'

    def __str__(self):
        return f"{self.get_activity_type_display()} at {self.timestamp}"
    

    # message

# In your Message model
class Message(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    pharmacy = models.ForeignKey(
        Pharmacy, 
        on_delete=models.CASCADE, 
        related_name='received_messages',
        null=True,  # Add this to make optional
        blank=True  # Add this to allow blank in forms
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)