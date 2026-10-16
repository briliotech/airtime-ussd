"""Safaricom Daraja client for Lipa na M-Pesa Online (STK push)."""

import base64
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

BASE_URLS = {
    'sandbox': 'https://sandbox.safaricom.co.ke',
    'production': 'https://api.safaricom.co.ke',
}
TIMEOUT = 30


class MpesaError(Exception):
    pass


def _base_url():
    return BASE_URLS.get(settings.MPESA_ENV, BASE_URLS['sandbox'])


def get_access_token():
    cache_key = f'mpesa-token-{settings.MPESA_ENV}'
    token = cache.get(cache_key)
    if token:
        return token
    try:
        response = requests.get(
            f'{_base_url()}/oauth/v1/generate',
            params={'grant_type': 'client_credentials'},
            auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MpesaError(f'Could not get Daraja access token: {exc}') from exc
    token = data['access_token']
    # Tokens last ~3599s; refresh a minute early.
    cache.set(cache_key, token, max(int(data.get('expires_in', 3599)) - 60, 60))
    return token


def stk_push(phone_number, amount, account_reference, description, callback_url):
    """Send an STK push. Returns Daraja's JSON on success, raises MpesaError otherwise."""
    timestamp = datetime.now(ZoneInfo('Africa/Nairobi')).strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(
        f'{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}'.encode()
    ).decode()
    payload = {
        'BusinessShortCode': settings.MPESA_SHORTCODE,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': settings.MPESA_TRANSACTION_TYPE,
        'Amount': int(amount),
        'PartyA': phone_number,
        'PartyB': settings.MPESA_PARTY_B,
        'PhoneNumber': phone_number,
        'CallBackURL': callback_url,
        'AccountReference': account_reference[:12],
        'TransactionDesc': description[:13],
    }
    try:
        response = requests.post(
            f'{_base_url()}/mpesa/stkpush/v1/processrequest',
            json=payload,
            headers={'Authorization': f'Bearer {get_access_token()}'},
            timeout=TIMEOUT,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MpesaError(f'STK push request failed: {exc}') from exc

    if response.status_code != 200 or str(data.get('ResponseCode')) != '0':
        message = data.get('errorMessage') or data.get('ResponseDescription') or response.text
        raise MpesaError(f'STK push rejected: {message}')
    logger.info('STK push sent to %s: %s', phone_number, data.get('CheckoutRequestID'))
    return data


def parse_callback_metadata(stk_callback):
    """Flatten CallbackMetadata.Item into a dict, e.g. {'MpesaReceiptNumber': 'QK...'}."""
    items = (stk_callback.get('CallbackMetadata') or {}).get('Item') or []
    return {item.get('Name'): item.get('Value') for item in items}
