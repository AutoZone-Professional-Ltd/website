from django.shortcuts import redirect, render

from .erpnext import ERPNextCatalogError, get_catalog_data
from .models import Category, Product

def home(request):
    featured_products = Product.objects.filter(featured=True).select_related('category')[:6]
    categories = Category.objects.all()[:6]
    context = {
        'featured_products': featured_products,
        'categories': categories,
        'category_count': Category.objects.count(),
        'product_count': Product.objects.count(),
    }
    return render(request, 'index.html', context)

def about(request):
    return render(request, 'about.html')

def services(request):
    return render(request, 'services.html')

def products(request):
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
    except ERPNextCatalogError as exc:
        fallback_products = Product.objects.select_related('category').all()
        fallback_group = {
            'name': 'Local Catalog',
            'count': fallback_products.count(),
            'brands': [
                {
                    'name': 'Website Products',
                    'count': fallback_products.count(),
                    'items': [
                        {
                            'item_name': product.name,
                            'item_code': f'LOCAL-{product.id}',
                            'description': product.description,
                            'price': product.price,
                            'currency': 'USD',
                            'price_list': 'Website',
                            'stock_uom': '',
                        }
                        for product in fallback_products
                    ],
                }
            ],
        }
        if fallback_group['count']:
            context['catalog_groups'] = [fallback_group]
            context['total_items'] = fallback_group['count']
            context['total_models'] = 1
            context['total_brands'] = 1
            context['catalog_source'] = 'local'
        context['catalog_error'] = str(exc)

    return render(request, 'products.html', context)

def contact(request):
    return render(request, 'contact.html')

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
