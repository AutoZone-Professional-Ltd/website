# Auto Zone Professional Website

## ERPNext Catalog Setup

The products catalog can read items directly from ERPNext and group them as:

1. Item model
2. Brand
3. Item name, item code, description, and selling price

Add these values to your `.env` file:

```env
ERPNEXT_BASE_URL=https://your-erp-domain.com
ERPNEXT_AUTH_TOKEN=token api_key:api_secret
# Or use these two instead of ERPNEXT_AUTH_TOKEN:
# ERPNEXT_API_KEY=your_api_key
# ERPNEXT_API_SECRET=your_api_secret

ERPNEXT_ITEM_MODEL_FIELD=item_group
ERPNEXT_ITEM_PRICE_LIST=Standard Selling
ERPNEXT_CATALOG_CACHE_TIMEOUT=300
```

Notes:

- `ERPNEXT_ITEM_MODEL_FIELD` can point to your ERPNext item model field. If your system uses a custom field such as `custom_item_model`, set that here.
- If ERPNext is not configured or unavailable, the page falls back to local website products.
