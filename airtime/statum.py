"""Statum airtime disbursement client (POST /api/v2/airtime, Basic Auth)."""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 30


class StatumError(Exception):
    pass


def send_airtime(phone_number, amount):
    """Queue an airtime top-up. Returns Statum's request_id; raises StatumError on failure."""
    try:
        response = requests.post(
            settings.STATUM_AIRTIME_URL,
            json={'phone_number': phone_number, 'amount': str(int(amount))},
            auth=(settings.STATUM_CONSUMER_KEY, settings.STATUM_CONSUMER_SECRET),
            timeout=TIMEOUT,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise StatumError(f'Statum request failed: {exc}') from exc

    if int(data.get('status_code', response.status_code)) != 200 or not data.get('request_id'):
        raise StatumError(f"Statum rejected top-up: {data.get('description') or response.text}")
    logger.info('Statum accepted KES %s to %s: %s', amount, phone_number, data['request_id'])
    return data['request_id']
