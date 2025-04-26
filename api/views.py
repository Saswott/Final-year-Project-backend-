from rest_framework import generics, status, permissions, viewsets, filters
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import action, api_view, permission_classes
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta, datetime
import json
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import serializers
from django.db import transaction, models
from django.http import HttpResponse
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from datetime import datetime
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from rest_framework.response import Response
from .models import User, Medicine, Category, Pharmacy, Prescription, Invoice, RecentActivity, Message
from .serializers import MessageSerializer, MessageCreateSerializer, RecentActivitySerializer
from .serializers import (
    PharmacyRegistrationSerializer,
    UserSerializer,
    MedicineSerializer,
    CategorySerializer,
    EmployeeRegistrationSerializer,
    PrescriptionSerializer,
    InvoiceSerializer,
    MessageSerializer,  # Added import for MessageSerializer
)
# ------------------ CONSTANTS ------------------
ERROR_NOT_AN_EMPLOYEE = "This user is not an employee"
# ------------------ PHARMACY REGISTRATION ------------------
class PharmacyRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = PharmacyRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)
# ------------------ USER DETAILS ------------------
class UserMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        user = request.user
        data = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'role': user.role,
            'is_active': user.is_active,
            'is_verified': user.is_verified,
            'pharmacy': user.pharmacy.pharmacy_name if user.pharmacy else None,
        }
        return Response(data, status=status.HTTP_200_OK)
# ------------------ CATEGORY VIEWSET ------------------
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
# ------------------ MEDICINE VIEWSET ------------------
class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all().select_related('category')
    serializer_class = MedicineSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status']
    search_fields = ['name', 'manufacturer']
    ordering_fields = ['name', 'price', 'stock', 'expiry_date']
    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        three_months_later = timezone.now().date() + timedelta(days=90)
        expiring_soon = queryset.filter(expiry_date__lte=three_months_later).count()
        return Response({
            'total_items': queryset.count(),
            'low_stock': queryset.filter(stock__lte=200).count(),
            'out_of_stock': queryset.filter(stock=0).count(),
            'expiring_soon': expiring_soon,
        })
    
    @action(detail=False, methods=['get'])
    def check_availability(self, request):
        name = request.query_params.get('name', '')
        quantity = int(request.query_params.get('quantity', 0))
        
        if not name or quantity <= 0:
            return Response(
                {"error": "Both name and positive quantity are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            medicine = Medicine.objects.get(name__iexact=name)
            return Response({
                "available": medicine.has_sufficient_stock(quantity),
                "stock": medicine.stock,
                "medicine": MedicineSerializer(medicine).data
            })
        except Medicine.DoesNotExist:
            return Response({
                "available": False,
                "error": "Medicine not found"
            }, status=status.HTTP_404_NOT_FOUND)
    
# ------------------ EMPLOYEE REGISTRATION ------------------
class EmployeeRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = EmployeeRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]  # Changed from AllowAny
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get the current user (pharmacy owner)
        pharmacy_owner = request.user
        
        # Create the employee user
        user = serializer.save()
        
        # Associate the employee with the pharmacy
        if pharmacy_owner.pharmacy:
            user.pharmacy = pharmacy_owner.pharmacy
            user.save()
        
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)
# ------------------ EMPLOYEE MANAGEMENT VIEWSET ------------------
class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'pharmacy':
            # Return employees belonging to this pharmacy
            return User.objects.filter(pharmacy=user.pharmacy, role='employee')
        elif user.role == 'admin':
            # Admin can see all employees
            return User.objects.filter(role='employee')
        elif user.role == 'employee':
            # Employees can see other employees in their pharmacy
            if user.pharmacy:
                return User.objects.filter(pharmacy=user.pharmacy, role='employee')
        
        return User.objects.none()
    @action(detail=True, methods=['patch'])
    def verify(self, request, pk=None):
        employee = self.get_object()
        is_verified = request.data.get('is_verified', False)
        if employee.role != 'employee':
            return Response({"error": ERROR_NOT_AN_EMPLOYEE}, status=status.HTTP_400_BAD_REQUEST)
        # Set both is_active and is_verified to the same value
        employee.is_active = is_verified
        employee.is_verified = is_verified
        employee.save()
        return Response({
            "message": f"Employee {employee.email} verification status updated",
            "is_verified": is_verified,
            "is_active": is_verified,
            "employee": UserSerializer(employee).data
        })
    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        employee = self.get_object()
        if employee.role != 'employee':
            return Response({"error": ERROR_NOT_AN_EMPLOYEE}, status=status.HTTP_400_BAD_REQUEST)
        document = request.FILES.get('document')
        if not document:
            return Response({"error": "No document provided"}, status=status.HTTP_400_BAD_REQUEST)
        document_type = request.data.get('document_type', 'citizenship')
        if document_type == 'citizenship':
            employee.citizenship_document = document
            employee.save()
            return Response({"message": "Citizenship document uploaded successfully"})
        else:
            return Response({"error": "Invalid document type"}, status=status.HTTP_400_BAD_REQUEST)
    @action(detail=True, methods=['post'])
    def upload_profile_picture(self, request, pk=None):
        employee = self.get_object()
        if employee.role != 'employee':
            return Response({"error": ERROR_NOT_AN_EMPLOYEE}, status=status.HTTP_400_BAD_REQUEST)
        profile_picture = request.FILES.get('profile_picture')
        if not profile_picture:
            return Response({"error": "No profile picture provided"}, status=status.HTTP_400_BAD_REQUEST)
        employee.profile_picture = profile_picture
        employee.save()
        return Response({"message": "Profile picture uploaded successfully"})
    @action(detail=False, methods=['get'])
    def pending(self, request):
        queryset = self.get_queryset().filter(is_active=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
# ------------------ CUSTOM TOKEN VIEWS ------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(required=False)
    employee_id = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)
    def validate(self, attrs):
        # For debugging purposes
        print(f"Received login attempt with data: {attrs}")
        
        email = attrs.get('email', '')
        employee_id = attrs.get('employee_id', '')
        password = attrs.get('password', '')
        
        if not email and not employee_id:
            raise serializers.ValidationError({"error": "Either email or employee_id must be provided"})
        # Find the user
        user = None
        if email:
            try:
                user = User.objects.get(email=email)
                print(f"User found with email: {email}, is_active: {user.is_active}")
            except User.DoesNotExist:
                print(f"No user found with email: {email}")
        elif employee_id:
            try:
                user = User.objects.get(employee_id=employee_id)
                print(f"User found with employee_id: {employee_id}, is_active: {user.is_active}")
            except User.DoesNotExist:
                print(f"No user found with employee_id: {employee_id}")
        if not user:
            raise serializers.ValidationError({"error": "No user found with the provided credentials"})
        if not user.is_active:
            print(f"User {user.email} is not active, activation status: {user.is_active}")
            raise serializers.ValidationError({"error": "This account is not active. Please wait for admin approval."})
        # Check password
        if not user.check_password(password):
            print(f"Invalid password for user: {user.email}")
            raise serializers.ValidationError({"error": "Invalid password"})
        # Get the token
        refresh = self.get_token(user)
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'is_verified': getattr(user, 'is_verified', False)
            }
        }
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
# ------------------ pescription ------------------
class PrescriptionViewSet(viewsets.ModelViewSet):
    serializer_class = PrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['patient', 'doctor']
    ordering_fields = ['date', 'created_at']
    def get_queryset(self):
        user = self.request.user
        # For pharmacy owners and employees, show all prescriptions
        if user.role in ['pharmacy', 'employee']:
            return Prescription.objects.all().order_by('-created_at')
        return Prescription.objects.none()
    def perform_create(self, serializer):
        # Automatically set the doctor to current user's name or email
        doctor_name = self.request.user.get_full_name() or self.request.user.email
        serializer.save(doctor=doctor_name)
    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        today = timezone.now().date()
        
        return Response({
            'total': queryset.count(),
            'pending': queryset.filter(status='Pending').count(),
            'completed': queryset.filter(status='Completed').count(),
            'today': queryset.filter(date=today).count(),
        })
    
# ------------------ INVOICE VIEWSET ------------------

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method']
    search_fields = ['customer_name', 'customer_email', 'invoice_number']
    ordering_fields = ['created_at', 'total_amount']

    def get_pharmacy(self):
        """Get the pharmacy for the current user or system's single pharmacy"""
        # For pharmacy users, use their own pharmacy
        if hasattr(self.request.user, 'pharmacy') and self.request.user.pharmacy:
            return self.request.user.pharmacy
        
        # For superusers/employees, get the first pharmacy (single pharmacy system)
        return Pharmacy.objects.first()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # For pharmacy users, filter by their pharmacy
        if user.role == 'pharmacy' and hasattr(user, 'pharmacy'):
            queryset = queryset.filter(pharmacy=user.pharmacy)
        
        # For employees, filter by created_by
        elif user.role == 'employee':
            queryset = queryset.filter(created_by=user)
            
        return queryset.select_related('pharmacy', 'created_by')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Get the pharmacy (either user's pharmacy or system's single pharmacy)
            pharmacy = self.get_pharmacy()
            if not pharmacy:
                return Response(
                    {"error": "No pharmacy is available to associate with this invoice"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Inventory validation
            items = serializer.validated_data.get('items', [])
            inventory_errors = []
            
            for item in items:
                medicine_name = item.get('name')
                quantity = item.get('quantity', 0)
                
                try:
                    medicine = Medicine.objects.get(name__iexact=medicine_name)
                    if not medicine.has_sufficient_stock(quantity):
                        inventory_errors.append({
                            'name': medicine_name,
                            'error': f"Insufficient stock. Available: {medicine.stock}, Requested: {quantity}"
                        })
                except Medicine.DoesNotExist:
                    inventory_errors.append({
                        'name': medicine_name,
                        'error': "Medicine not found"
                    })
                except Medicine.MultipleObjectsReturned:
                    inventory_errors.append({
                        'name': medicine_name,
                        'error': "Multiple medicines with same name. Please use exact name."
                    })

            if inventory_errors:
                return Response({
                    'error': 'Stock validation failed',
                    'inventory_errors': inventory_errors
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create invoice
            invoice = serializer.save(
                created_by=request.user,
                pharmacy=pharmacy
            )

            # Update stock
            for item in items:
                medicine = Medicine.objects.get(name__iexact=item['name'])
                medicine.reduce_stock(item['quantity'])
                medicine.save()

            return Response({
                'success': True,
                'invoice': InvoiceSerializer(invoice).data,
                'message': 'Invoice created successfully'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        invoice = self.get_object()
        # Generate PDF or return data for frontend to generate
        return Response({
            'invoice_number': invoice.invoice_number,
            'customer_name': invoice.customer_name,
            'items': invoice.items,
            'subtotal': invoice.subtotal,
            'discount_percentage': invoice.discount_percentage,
            'discount_amount': invoice.discount_amount,
            'total_amount': invoice.total_amount,
            'created_at': invoice.created_at,
            # Add other fields as needed
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        user = request.user
        if not user.pharmacy:
            return Response({'error': 'User has no associated pharmacy'}, status=400)
            
        queryset = self.get_queryset().filter(pharmacy=user.pharmacy)
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        totals = queryset.aggregate(
            total_count=Count('id'),
            total_amount=Sum('total_amount'),
            today_count=Count('id', filter=models.Q(created_at__date=today)),
            yesterday_count=Count('id', filter=models.Q(created_at__date=yesterday)),
            pending_count=Count('id', filter=models.Q(status='Pending'))
        )
        
        return Response({
            'total': totals['total_count'] or 0,
            'today': totals['today_count'] or 0,
            'yesterday': totals['yesterday_count'] or 0,
            'total_amount': float(totals['total_amount']) if totals['total_amount'] else 0,
            'pending': totals['pending_count'] or 0,
            'paid': totals['total_count'] - totals['pending_count']
        })
    
class InvoicePDFView(APIView):
    def get(self, request, pk):
        try:
            invoice = Invoice.objects.get(pk=pk)
            
            # Create PDF buffer
            buffer = BytesIO()
            
            # Create the PDF document with custom margins
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=36,  # Smaller margins for more space
                leftMargin=36,
                topMargin=36,
                bottomMargin=36
            )
            
            # Container for elements
            elements = []
            
            # Get default styles and add custom ones
            styles = getSampleStyleSheet()
            
            # Add custom styles
            styles.add(ParagraphStyle(
                name='InvoiceTitle',
                fontSize=16,
                alignment=1,  # Center aligned
                spaceAfter=20,
                textColor=colors.HexColor('#2c3e50'),
                fontName='Helvetica-Bold'
            ))
            
            styles.add(ParagraphStyle(
                name='SectionHeader',
                fontSize=12,
                spaceAfter=10,
                textColor=colors.HexColor('#3498db'),
                fontName='Helvetica-Bold'
            ))
            
            styles.add(ParagraphStyle(
                name='NormalBold',
                fontSize=10,
                fontName='Helvetica-Bold'
            ))
            
            styles.add(ParagraphStyle(
                name='NormalRight',
                fontSize=10,
                alignment=2  # Right aligned
            ))
            
            styles.add(ParagraphStyle(
                name='TotalStyle',
                fontSize=12,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#e74c3c')
            ))
            
            # 1. Header Section
            # Add pharmacy logo if available (uncomment and modify if you have a logo)
            # logo_path = "path/to/your/logo.png"
            # if os.path.exists(logo_path):
            #     logo = Image(logo_path, width=1.5*inch, height=0.75*inch)
            #     elements.append(logo)
            #     elements.append(Spacer(1, 0.25*inch))
            
            # Invoice title
            elements.append(Paragraph("TAX INVOICE", styles['InvoiceTitle']))
            
            # 2. Pharmacy and Invoice Info (Two columns)
            pharmacy_data = []
            if invoice.pharmacy:
                pharmacy_data = [
                    [Paragraph("<b>Pharmacy:</b>", styles['NormalBold']), Paragraph(invoice.pharmacy.pharmacy_name, styles['Normal'])],
                    [Paragraph("<b>Address:</b>", styles['NormalBold']), Paragraph(invoice.pharmacy.address, styles['Normal'])],
                    [Paragraph("<b>Phone:</b>", styles['NormalBold']), Paragraph(invoice.pharmacy.phone_number, styles['Normal'])],
                ]
            
            invoice_data = [
                [Paragraph("<b>Invoice #:</b>", styles['NormalBold']), Paragraph(invoice.invoice_number, styles['Normal'])],
                [Paragraph("<b>Date:</b>", styles['NormalBold']), Paragraph(invoice.created_at.strftime('%d-%b-%Y'), styles['Normal'])],
                [Paragraph("<b>Status:</b>", styles['NormalBold']), Paragraph(invoice.status, styles['Normal'])],
                [Paragraph("<b>Payment Method:</b>", styles['NormalBold']), Paragraph(invoice.payment_method, styles['Normal'])],
            ]
            
            # Create a table with two columns
            info_table = Table([
                [
                    Table(pharmacy_data, colWidths=[1.5*inch, 3*inch]) if pharmacy_data else Paragraph("", styles['Normal']),
                    Table(invoice_data, colWidths=[1.5*inch, 3*inch])
                ]
            ], colWidths=[4*inch, 4*inch])
            
            elements.append(info_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # 3. Customer Details Section
            elements.append(Paragraph("Customer Details", styles['SectionHeader']))
            
            customer_data = [
                [Paragraph("<b>Name:</b>", styles['NormalBold']), Paragraph(invoice.customer_name, styles['Normal'])],
                [Paragraph("<b>Email:</b>", styles['NormalBold']), Paragraph(invoice.customer_email or "Not provided", styles['Normal'])],
                [Paragraph("<b>Phone:</b>", styles['NormalBold']), Paragraph(invoice.customer_phone, styles['Normal'])],
                [Paragraph("<b>Doctor Name:</b>", styles['NormalBold']), Paragraph(invoice.doctor_name or "Not provided", styles['Normal'])],
            ]
            
            customer_table = Table(customer_data, colWidths=[1.5*inch, 4*inch])
            elements.append(customer_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # 4. Items Table
            elements.append(Paragraph("Items", styles['SectionHeader']))
            
            # Process items
            try:
                items = json.loads(invoice.items) if isinstance(invoice.items, str) else invoice.items
            except:
                items = []
            
            # Prepare table data
            table_data = [
                [
                    Paragraph("<b>Item</b>", styles['NormalBold']),
                    Paragraph("<b>Qty</b>", styles['NormalBold']),
                    Paragraph("<b>Unit Price</b>", styles['NormalBold']),
                    Paragraph("<b>Total</b>", styles['NormalBold'])
                ]
            ]
            
            for item in items:
                table_data.append([
                    Paragraph(item.get('name', ''), styles['Normal']),
                    Paragraph(str(item.get('quantity', 0)), styles['Normal']),
                    Paragraph(f"Rs {float(item.get('total', 0)):.2f}", styles['NormalRight']),
                    Paragraph(f"Rs {float(item.get('total', 0)):.2f}", styles['NormalRight'])
                ])
            
            # Create items table
            items_table = Table(table_data, colWidths=[3*inch, 0.75*inch, inch, inch])
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#212529')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.white),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
            ]))
            
            elements.append(items_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # 5. Totals Section
            total_data = [
                [Paragraph("<b>Subtotal:</b>", styles['NormalBold']), Paragraph(f"Rs {invoice.subtotal:.2f}", styles['NormalRight'])],
            ]
            # Add discount row if applicable
            if invoice.discount_percentage > 0:
                total_data.append([
                    Paragraph(f"<b>Discount ({invoice.discount_percentage}%):</b>", styles['NormalBold']), 
                    Paragraph(f"- Rs {invoice.discount_amount:.2f}", styles['NormalRight'])
                ])
            total_data.append([
                Paragraph("<b>Total Amount:</b>", styles['TotalStyle']), 
                Paragraph(f"Rs {invoice.total_amount:.2f}", styles['TotalStyle'])
            ])
            
            total_table = Table(total_data, colWidths=[4*inch, 2*inch])
            elements.append(total_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # 6. Footer Section
            footer = [
                Paragraph("<b>Notes:</b>", styles['NormalBold']),
                Paragraph("1. Goods once sold cannot be returned or exchanged.", styles['Normal']),
                Paragraph("2. Please retain this invoice for warranty claims.", styles['Normal']),
                Paragraph("3. For any queries, please contact our pharmacy.", styles['Normal']),
                Spacer(1, 0.25*inch),
                Paragraph("Thank you for your business!", styles['NormalBold']),
                Spacer(1, 0.5*inch),
                Paragraph("<b>Authorized Signature</b>", styles['NormalBold']),
                Spacer(1, 0.5*inch),
                Paragraph("_________________________", styles['Normal']),
            ]
            
            for item in footer:
                elements.append(item)
            
            # Build the PDF
            doc.build(elements)
            
            # Get PDF value from buffer
            pdf = buffer.getvalue()
            buffer.close()
            
            # Create HTTP response
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Invoice_{invoice.invoice_number}.pdf"'
            return response
            
        except Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
class RecentActivityView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get the user's pharmacy
        if not hasattr(request.user, 'pharmacy'):
            return Response(
                {"error": "User is not associated with a pharmacy"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get recent activities for the pharmacy
        activities = RecentActivity.objects.filter(
            pharmacy=request.user.pharmacy
        ).order_by('-timestamp')[:50]
        
        serializer = RecentActivitySerializer(activities, many=True)
        return Response(serializer.data)
    


#message
class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'pharmacy':
            return Message.objects.filter(
                pharmacy=user.pharmacy
            ).select_related('employee').order_by('-created_at')
        return Message.objects.none()

    def get_serializer_class(self):
        if self.action == 'create':
            return MessageCreateSerializer
        return MessageSerializer

    def perform_create(self, serializer):
        if self.request.user.role != 'employee':
            raise PermissionDenied("Only employees can send messages")
        serializer.save(
            employee=self.request.user, 
            pharmacy=self.request.user.pharmacy
        )


    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        message = self.get_object()
        if request.user.role != 'pharmacy':
            raise PermissionDenied("Only pharmacy can mark messages as read")
        message.is_read = True
        message.save()
        return Response({'status': 'message marked as read'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        if request.user.role != 'pharmacy':
            raise PermissionDenied("Only pharmacy can check unread count")
        count = Message.objects.filter(
            pharmacy=request.user.pharmacy,
            is_read=False
        ).count()
        return Response({'unread_count': count})
    


# ------------------ ANALYTICS VIEW ------------------

class AnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get the user's pharmacy
        user = request.user
        if not hasattr(user, 'pharmacy'):
            return Response(
                {"error": "User is not associated with a pharmacy"},
                status=status.HTTP_400_BAD_REQUEST
            )
        pharmacy = user.pharmacy
        
        # Calculate date ranges for the last 7 days (including today)
        today = timezone.now().date()
        date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]  # Last 6 days + today
        
        # 1. Weekly Sales Data (for bar chart)
        weekly_sales_data = []
        for date in date_range:
            daily_sales = Invoice.objects.filter(
                pharmacy=pharmacy,
                created_at__date=date
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            weekly_sales_data.append({
                'day': date.strftime('%a'),  # Short day name (Mon, Tue, etc.)
                'value': float(daily_sales),
                'name': 'Sales'
            })
        
        # 2. Category Distribution Data
        category_data = []
        categories = Category.objects.all()
        for category in categories:
            # Get total sales for this category
            category_sales = Invoice.objects.filter(
                pharmacy=pharmacy,
                items__contains=[{"name": category.name}]
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # Calculate percentage (placeholder logic - you might want different calculation)
            percentage = min(90, max(65, (category_sales / 1000) * 100)) if category_sales > 0 else 0
            
            category_data.append({
                'category': category.name,
                'percentage': round(percentage),
                'sales': float(category_sales)
            })
        
        # 3. Stats Cards Data
        # Weekly Sales
        weekly_sales = sum(item['value'] for item in weekly_sales_data)
        
        # Top Medicine
        top_medicine = Medicine.objects.filter(
            invoice__pharmacy=pharmacy
        ).annotate(
            total_sold=Sum('invoice__items__quantity')
        ).order_by('-total_sold').first()
        
        # Frequent Buyer
        frequent_buyer = Invoice.objects.filter(
            pharmacy=pharmacy
        ).values('customer_name').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-count').first()
        
        response_data = {
            'pharmacy_name': pharmacy.pharmacy_name,
            'weekly_sales_data': weekly_sales_data,
            'category_data': category_data,
            'stats': {
                'weekly_sales': {
                    'value': weekly_sales,
                    'percentage': 20  # Placeholder for percentage change
                },
                'top_medicine': {
                    'name': top_medicine.name if top_medicine else 'Paracetamol',
                    'count': top_medicine.total_sold if top_medicine else 5987
                },
                'frequent_buyer': {
                    'name': frequent_buyer['customer_name'] if frequent_buyer else 'Dr. Smith',
                    'count': frequent_buyer['count'] if frequent_buyer else 2457
                }
            }
        }
        
        return Response(response_data)
    
# ------------------ PDF GENERATION ------------------

class AnalyticsPDFView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            # Get the analytics data
            analytics_response = AnalyticsView().get(request)
            if analytics_response.status_code != 200:
                return analytics_response
                
            data = analytics_response.data
            
            # Create PDF buffer
            buffer = BytesIO()
            
            # Create the PDF document with custom margins
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=36,
                leftMargin=36,
                topMargin=36,
                bottomMargin=36
            )
            
            # Container for elements
            elements = []
            styles = getSampleStyleSheet()
            
            # Add custom styles
            styles.add(ParagraphStyle(
                name='Title',
                fontSize=18,
                alignment=1,
                spaceAfter=20,
                textColor=colors.HexColor('#2c3e50'),
                fontName='Helvetica-Bold'
            ))
            
            styles.add(ParagraphStyle(
                name='Header',
                fontSize=14,
                spaceAfter=10,
                textColor=colors.HexColor('#3498db'),
                fontName='Helvetica-Bold'
            ))
            
            styles.add(ParagraphStyle(
                name='NormalBold',
                fontSize=10,
                fontName='Helvetica-Bold'
            ))
            
            # 1. Title
            elements.append(Paragraph("Pharmacy Analytics Report", styles['Title']))
            elements.append(Paragraph(f"Pharmacy: {data['pharmacy_name']}", styles['Normal']))
            elements.append(Paragraph(f"Date: {timezone.now().date().strftime('%Y-%m-%d')}", styles['Normal']))
            elements.append(Spacer(1, 0.5*inch))
            
            # 2. Key Stats
            elements.append(Paragraph("Key Statistics", styles['Header']))
            
            stats_data = [
                ["Weekly Sales", f"₹{data['stats']['weekly_sales']['value']:,.2f}", f"{data['stats']['weekly_sales']['percentage']}%"],
                ["Top Medicine", data['stats']['top_medicine']['name'], f"{data['stats']['top_medicine']['count']} sold"],
                ["Frequent Buyer", data['stats']['frequent_buyer']['name'], f"{data['stats']['frequent_buyer']['count']} purchases"],
            ]
            
            stats_table = Table(stats_data, colWidths=[2*inch, 2*inch, 2*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#212529')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.white),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
            ]))
            
            elements.append(stats_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # 3. Weekly Sales Chart (as a table)
            elements.append(Paragraph("Weekly Sales", styles['Header']))
            
            sales_data = [["Day", "Sales (₹)"]] + [
                [item['day'], f"{item['value']:,.2f}"] 
                for item in data['weekly_sales_data']
            ]
            
            sales_table = Table(sales_data, colWidths=[1*inch, 2*inch])
            sales_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#212529')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('ALIGN', (1,0), (1,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.white),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
            ]))
            
            elements.append(sales_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # 4. Category Distribution
            elements.append(Paragraph("Medicine Categories Distribution", styles['Header']))
            
            category_data = [["Category", "Percentage", "Sales (₹)"]] + [
                [item['category'], f"{item['percentage']}%", f"{item['sales']:,.2f}"] 
                for item in data['category_data']
            ]
            
            category_table = Table(category_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
            category_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#212529')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('ALIGN', (1,0), (2,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.white),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
            ]))
            
            elements.append(category_table)
            
            # Build the PDF
            doc.build(elements)
            
            # Get PDF value from buffer
            pdf = buffer.getvalue()
            buffer.close()
            
            # Create HTTP response
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="pharmacy_analytics_report.pdf"'
            return response
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
