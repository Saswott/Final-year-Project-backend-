from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

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
    
    # Direct reference to pharmacy
    pharmacy = models.ForeignKey('Pharmacy', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')

    # New fields for employee registration
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    citizenship_document = models.FileField(upload_to='citizenship_documents/', blank=True, null=True)

    # is_active is used to track employee verification status
    # This field is already part of AbstractUser, so we're just documenting its use
    # When is_active=False for an employee, they are pending verification

    # Add related_name to avoid clashes
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

class Pharmacy(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pharmacy_profile')
    pharmacy_name = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=20)
    address = models.TextField()

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Medicine(models.Model):
    IN_STOCK = 'In Stock'
    LOW_STOCK = 'Low Stock'
    OUT_OF_STOCK = 'Out of Stock'
    
    STATUS_CHOICES = (
        (IN_STOCK, IN_STOCK),
        (LOW_STOCK, LOW_STOCK),
        (OUT_OF_STOCK, OUT_OF_STOCK),
    )
    
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='medicines')
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='medicines')
    stock = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField()
    manufacturer = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='In Stock')
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
    
    def __str__(self):
        return f"{self.name} - {self.pharmacy.pharmacy_name}"
