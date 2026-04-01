from unittest.mock import patch

from django.test import TestCase, override_settings

from website.erpnext import get_catalog_data


class ERPNextCatalogTests(TestCase):
    @override_settings(
        ERPNEXT_BASE_URL='https://erp.example.com',
        ERPNEXT_AUTH_TOKEN='token test:test',
        ERPNEXT_ITEM_MODEL_FIELD='item_group',
        ERPNEXT_CATALOG_CACHE_TIMEOUT=1,
    )
    @patch('website.erpnext._fetch_prices')
    @patch('website.erpnext._fetch_items')
    def test_catalog_groups_by_model_and_brand(self, mock_items, mock_prices):
        mock_items.return_value = [
            {
                'item_group': 'Hilux',
                'brand': 'Toyota',
                'item_name': 'Brake Pad Front',
                'item_code': 'BP-001',
                'description': 'Front brake pad',
                'stock_uom': 'Nos',
            },
            {
                'item_group': 'Hilux',
                'brand': 'Toyota',
                'item_name': 'Oil Filter',
                'item_code': 'OF-002',
                'description': 'Oil filter',
                'stock_uom': 'Nos',
            },
            {
                'item_group': 'Ranger',
                'brand': 'Ford',
                'item_name': 'Air Filter',
                'item_code': 'AF-003',
                'description': 'Air filter',
                'stock_uom': 'Nos',
            },
        ]
        mock_prices.return_value = {
            'BP-001': {'price_list_rate': 120000, 'currency': 'UGX', 'price_list': 'Standard Selling'},
            'OF-002': {'price_list_rate': 45000, 'currency': 'UGX', 'price_list': 'Standard Selling'},
            'AF-003': {'price_list_rate': 68000, 'currency': 'UGX', 'price_list': 'Standard Selling'},
        }

        payload = get_catalog_data(force_refresh=True)

        self.assertEqual(payload['total_models'], 2)
        self.assertEqual(payload['total_brands'], 2)
        self.assertEqual(payload['total_items'], 3)
        self.assertEqual(payload['catalog_groups'][0]['name'], 'Hilux')
        self.assertEqual(payload['catalog_groups'][0]['brands'][0]['name'], 'Toyota')
        self.assertEqual(payload['catalog_groups'][0]['brands'][0]['items'][0]['item_code'], 'BP-001')
