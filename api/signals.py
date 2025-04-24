from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Medicine, Invoice, Prescription, RecentActivity

@receiver(post_save, sender=Medicine)
def track_medicine_changes(sender, instance, created, **kwargs):
    if created:
        # New medicine added
        RecentActivity.objects.create(
            activity_type='new_medicine',
            medicine=instance,
            new_value=f"{instance.name} (Stock: {instance.stock})",
            pharmacy=instance.pharmacy
        )
    else:
        # Check for stock changes
        if 'stock' in kwargs.get('update_fields', []):
            RecentActivity.objects.create(
                activity_type='stock_update',
                medicine=instance,
                old_value=f"Stock: {instance.stock - 1 if instance.stock > 0 else 0}",  # This is simplified
                new_value=f"Stock: {instance.stock}",
                pharmacy=instance.pharmacy
            )
        
        # Check for price changes
        if 'price' in kwargs.get('update_fields', []):
            RecentActivity.objects.create(
                activity_type='price_change',
                medicine=instance,
                old_value=f"Price: {instance.price}",  # This would need the old price from somewhere
                new_value=f"New Price: {instance.price}",
                pharmacy=instance.pharmacy
            )

@receiver(post_save, sender=Invoice)
def track_new_invoices(sender, instance, created, **kwargs):
    if created:
        RecentActivity.objects.create(
            activity_type='new_invoice',
            invoice=instance,
            new_value=f"Invoice #{instance.invoice_number} for ₹{instance.total_amount}",
            pharmacy=instance.pharmacy
        )

@receiver(post_save, sender=Prescription)
def track_prescriptions(sender, instance, created, **kwargs):
    if created:
        RecentActivity.objects.create(
            activity_type='prescription',
            prescription=instance,
            new_value=f"Prescription for {instance.patient}",
            pharmacy=instance.pharmacy
        )