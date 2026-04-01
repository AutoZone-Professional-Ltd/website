from django.shortcuts import redirect, render
from django.conf import settings
from django.templatetags.static import static
import os

from .erpnext import get_catalog_data, _erp_get, resolve_erp_image
from .erpnext_chat import AutoZoneChatbot
from .models import Category, Product


def get_erp_stats():
    """Get stats from ERPNext API."""
    try:
        chatbot = AutoZoneChatbot()
        stats = chatbot.get_full_stats()
        return {
            'items': stats.get('total_items', 0),
            'customers': stats.get('total_customers', 0),
            'brands': stats.get('total_brands', 0),
            'territories': stats.get('total_territories', 0),
            'total_sales': stats.get('total_sales', 0),
            'invoices': stats.get('total_invoices', 0),
        }
    except Exception:
        return {
            'items': 0,
            'customers': 0,
            'brands': 0,
            'territories': 0,
            'total_sales': 0,
            'invoices': 0,
        }


def get_top_products(limit=12):
    """Get top selling products from historical data."""
    try:
        chatbot = AutoZoneChatbot()
        top = chatbot.hist.get_top_products(limit)
        return top
    except Exception:
        return []


def get_featured_items(limit=12):
    """Get items with images from ERPNext, resolved to local/static path when possible."""
    try:
        items = _erp_get('resource/Item', {
            'fields': '["item_code", "item_name", "description", "brand", "image", "item_group"]',
            'filters': '[ ["image", "!=", ""], ["disabled", "=", 0]]',
            'limit_page_length': limit,
        })

        resolved = []
        for item in items:
            img = resolve_erp_image(item.get('image', ''))
            if not img:
                img = static('img/Logo.png')
            item['image'] = img
            resolved.append(item)

        return resolved[:limit]
    except Exception:
        return []


def get_all_brands():
    """Get all brands with item counts."""
    try:
        items = _erp_get('resource/Item', {
            'fields': '["brand", "item_name", "image"]',
            'filters': '[["disabled", "=", 0]]',
            'limit_page_length': 5000,
        })
        
        brand_data = {}
        for item in items:
            brand = item.get('brand') or 'Other'
            image_val = resolve_erp_image(item.get('image', ''))
            if not image_val:
                image_val = static('img/Logo.png')

            if brand not in brand_data:
                brand_data[brand] = {'count': 0, 'name': brand, 'image': image_val}
            brand_data[brand]['count'] += 1
        
        return sorted(brand_data.values(), key=lambda x: -x['count'])
    except Exception:
        return []


def get_local_gallery_images(limit=24):
    """Read local static product images for extra gallery coverage."""
    img_dir = os.path.join(settings.BASE_DIR, 'static', 'img')
    if not os.path.isdir(img_dir):
        return []

    files = sorted(
        [f for f in os.listdir(img_dir)
         if os.path.isfile(os.path.join(img_dir, f))
         and f.lower().split('.')[-1] in ['jpg', 'jpeg', 'png', 'webp']
         and f.lower() != 'logo.png']
    )
    urls = [static(f'img/{f}') for f in files[:limit]]
    return urls


def home(request):
    """Home page with real data from database."""
    stats = get_erp_stats()
    top_products = get_top_products(12)
    featured_items = get_featured_items(20)
    brands = get_all_brands()[:15]
    local_gallery_images = get_local_gallery_images(24)
    
    context = {
        'stats': stats,
        'top_products': top_products,
        'featured_items': featured_items,
        'brands': brands,
        'featured_count': len(featured_items),
        'local_gallery_images': local_gallery_images,
    }
    return render(request, 'index.html', context)


def about(request):
    """About page with real stats."""
    stats = get_erp_stats()
    top_products = get_top_products(10)
    
    context = {
        'stats': stats,
        'top_products': top_products,
    }
    return render(request, 'about.html', context)


def services(request):
    """Services page."""
    stats = get_erp_stats()
    brands = get_all_brands()[:10]
    
    context = {
        'stats': stats,
        'brands': brands,
    }
    return render(request, 'services.html', context)


def products(request):
    """Products page with live ERPNext catalog."""
    context = {
        'catalog_groups': [],
        'total_items': 0,
        'total_models': 0,
        'total_brands': 0,
        'catalog_error': '',
        'catalog_source': 'erpnext',
    }

    try:
        data = get_catalog_data()
        data['catalog_groups'] = [g for g in data['catalog_groups'] if g['name'] != 'Non-stock']
        data['total_models'] = len(data['catalog_groups'])
        data['total_items'] = sum(g['count'] for g in data['catalog_groups'])
        data['total_brands'] = sum(len(g['brands']) for g in data['catalog_groups'])
        context.update(data)
    except Exception as exc:
        context['catalog_error'] = str(exc)

    return render(request, 'products.html', context)


def contact(request):
    """Contact page."""
    stats = get_erp_stats()
    return render(request, 'contact.html', {'stats': stats})


def privacy_policy(request):
    return render(request, 'privacy_policy.html')


def terms_of_service(request):
    return render(request, 'terms_of_service.html')


def subscribe(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        # Process the subscription here
        return render(request, 'subscription_success.html')
    return redirect('home')
