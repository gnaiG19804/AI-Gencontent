from tortoise import fields, models

class PriceSyncLog(models.Model):
    """
    Log entity for Price Synchronization events.
    Records every time a product is analyzed and updated.
    """
    id = fields.IntField(pk=True)
    product_id = fields.CharField(max_length=50, index=True)
    variant_id = fields.CharField(max_length=50, null=True)
    product_title = fields.CharField(max_length=255, null=True)
    
    # Prices
    old_price = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    new_price = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    competitor_price = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    cost = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    # Decision
    action = fields.CharField(max_length=20)  # UPDATE, SKIP, ERROR
    status = fields.CharField(max_length=20, default="PENDING") # SUCCESS, FAILED, PENDING
    reason = fields.TextField(null=True)
    
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "price_sync_logs"
