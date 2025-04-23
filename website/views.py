from django.shortcuts import redirect, render

def home(request):
    return render(request, 'index.html')

def about(request):
    return render(request, 'about.html')

def services(request):
    return render(request, 'services.html')

def products(request):
    return render(request, 'products.html')

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