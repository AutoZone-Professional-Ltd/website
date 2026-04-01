from django.contrib import admin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'featured')
    list_filter = ('featured', 'category')
    list_editable = ('price', 'stock', 'featured')
    search_fields = ('name', 'description', 'category__name')
