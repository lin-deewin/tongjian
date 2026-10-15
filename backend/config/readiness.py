import json
from pathlib import Path

REQUIRED_GATES = ['merchant_products', 'price_and_terms', 'email_delivery', 'real_payment_refund',
                  'bill_verified', 'device_matrix', 'cdn_private_cache', 'admin_networks', 'restore_drill', 'support_contact']

def missing_gates(path):
    try:
        gates = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        gates = {}
    if not isinstance(gates, dict):
        gates = {}
    return [key for key in REQUIRED_GATES if not isinstance(gates.get(key), dict) or
            gates[key].get('passed') is not True or not gates[key].get('evidence') or not gates[key].get('verified_by')]
