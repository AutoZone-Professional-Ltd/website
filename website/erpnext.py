import json
import logging
from collections import OrderedDict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning
from django.conf import settings
from django.core.cache import cache

# Silence insecure-cert warning for self-signed / internal ERPNext hosts
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)

_retry = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
_adapter = HTTPAdapter(max_retries=_retry)
_session = requests.Session()
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
_session.verify = False


class ERPNextCatalogError(Exception):
    pass


def _get_auth_headers():
    if settings.ERPNEXT_AUTH_TOKEN:
        token = settings.ERPNEXT_AUTH_TOKEN.strip()
        if token.lower().startswith('token '):
            return {'Accept': 'application/json', 'Authorization': token}
        return {'Accept': 'application/json', 'Authorization': f'token {token}'}

    if settings.ERPNEXT_API_KEY and settings.ERPNEXT_API_SECRET:
        return {
            'Accept': 'application/json',
            'Authorization': f"token {settings.ERPNEXT_API_KEY.strip()}:{settings.ERPNEXT_API_SECRET.strip()}"
        }

    raise ERPNextCatalogError('ERPNext credentials are not configured. Set ERPNEXT_AUTH_TOKEN or ERPNEXT_API_KEY + ERPNEXT_API_SECRET.')


def _erp_get(path, params=None):
    if not settings.ERPNEXT_BASE_URL:
        raise ERPNextCatalogError('ERPNext base URL is not configured.')

    base_url = settings.ERPNEXT_BASE_URL.rstrip('/')
    if path.startswith('/'): 
        path = path[1:]

    url = f"{base_url}/api/{path}"
    headers = _get_auth_headers()

    logger.debug('ERPNext GET %s ; headers=%s ; params=%s', url, {k: ('***' if k=='Authorization' else v) for k,v in headers.items()}, params)

    try:
        response = _session.get(
            url,
            headers=headers,
            params=params,
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.error('ERPNext network error: %s', exc)
        raise ERPNextCatalogError(f'Unable to reach ERPNext. {exc}') from exc

    if response.status_code == 401:
        logger.error('ERPNext auth failed 401: %s', response.text[:300])
        raise ERPNextCatalogError('ERPNext request failed (401). AuthenticationError')

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.error('ERPNext request failed %s: %s', response.status_code, response.text[:300])
        raise ERPNextCatalogError(f'ERPNext request failed ({response.status_code}). {response.text}') from exc

    payload = response.json()
    return payload.get('data', [])


def _fetch_paginated_resource(doctype, fields, filters=None, order_by=None, page_length=500):
    all_rows = []
    limit_start = 0

    while True:
        params = {'fields': json.dumps(fields), 'limit_page_length': page_length, 'limit_start': limit_start}
        if filters:
            params['filters'] = json.dumps(filters)
        if order_by:
            params['order_by'] = order_by

        batch = _erp_get(f'resource/{doctype}', params=params)
        all_rows.extend(batch)

        if len(batch) < page_length:
            break
        limit_start += page_length

    return all_rows


def _fetch_items():
    model_field = settings.ERPNEXT_ITEM_MODEL_FIELD or 'item_group'
    requested_fields = ['item_code', 'item_name', 'description', 'brand', 'item_group', 'stock_uom', model_field]
    fields = list(OrderedDict.fromkeys(requested_fields))
    filters = [['disabled', '=', 0]]

    try:
        return _fetch_paginated_resource('Item', fields=fields, filters=filters, order_by='modified desc')
    except ERPNextCatalogError:
        if model_field == 'item_group':
            raise
        fallback_fields = ['item_code', 'item_name', 'description', 'brand', 'item_group', 'stock_uom']
        return _fetch_paginated_resource('Item', fields=fallback_fields, filters=filters, order_by='modified desc')


def _fetch_prices():
    filters = [['selling', '=', 1]]
    if settings.ERPNEXT_ITEM_PRICE_LIST:
        filters.append(['price_list', '=', settings.ERPNEXT_ITEM_PRICE_LIST])

    rows = _fetch_paginated_resource('Item Price', fields=['item_code', 'price_list_rate', 'currency', 'price_list', 'modified'], filters=filters, order_by='modified desc')

    prices_by_code = {}
    for row in rows:
        item_code = row.get('item_code')
        if item_code and item_code not in prices_by_code:
            prices_by_code[item_code] = row
    return prices_by_code


def _group_items(items, prices_by_code):
    model_field = settings.ERPNEXT_ITEM_MODEL_FIELD or 'item_group'
    grouped = OrderedDict()

    for item in items:
        item_code = item.get('item_code') or 'Unknown code'
        item_name = item.get('item_name') or item_code
        brand = item.get('brand') or 'Unbranded'
        model = item.get(model_field) or item.get('item_group') or 'General'
        description = item.get('description') or 'Description coming soon.'
        price = prices_by_code.get(item_code, {})

        model_group = grouped.setdefault(model, OrderedDict())
        brand_group = model_group.setdefault(brand, [])
        brand_group.append({
            'item_name': item_name,
            'item_code': item_code,
            'description': description,
            'price': price.get('price_list_rate'),
            'currency': price.get('currency', ''),
            'price_list': price.get('price_list', ''),
            'stock_uom': item.get('stock_uom') or '',
        })

    catalog = []
    for model_name, brands in grouped.items():
        brand_entries = []
        model_item_count = 0
        for brand_name, brand_items in brands.items():
            model_item_count += len(brand_items)
            brand_entries.append({'name': brand_name, 'items': brand_items, 'count': len(brand_items)})
        catalog.append({'name': model_name, 'brands': brand_entries, 'count': model_item_count})

    return catalog


def get_catalog_data(force_refresh=False):
    cache_key = 'erpnext_catalog_v1'
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    items = _fetch_items()
    prices_by_code = _fetch_prices()
    catalog = _group_items(items, prices_by_code)
    payload = {
        'catalog_groups': catalog,
        'total_items': sum(group['count'] for group in catalog),
        'total_models': len(catalog),
        'total_brands': sum(len(group['brands']) for group in catalog),
    }
    cache.set(cache_key, payload, timeout=settings.ERPNEXT_CATALOG_CACHE_TIMEOUT)
    return payload
