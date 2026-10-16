import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Customer
from accounts.phone import normalize_msisdn

from . import menu
from .models import UssdSession

logger = logging.getLogger(__name__)

ERROR_TEXT = 'Sorry, we could not process your request. Please try again.'


def _is_authorized(request):
    secrets = settings.BRILIO_CALLBACK_SECRETS
    if not secrets:
        # Allow unauthenticated local testing only.
        if settings.DEBUG:
            return True
        logger.error('BRILIO_CALLBACK_SECRETS is not set; rejecting USSD request')
        return False
    supplied = request.headers.get('Authentication', '').encode()
    # Check every secret so the comparison time doesn't reveal which one matched.
    matches = [hmac.compare_digest(supplied, secret.encode()) for secret in secrets]
    return any(matches)


def _reply(text, end):
    if len(text) > menu.MAX_TEXT_LENGTH:
        logger.warning('USSD text over %s chars, truncating: %r', menu.MAX_TEXT_LENGTH, text)
        text = text[:menu.MAX_TEXT_LENGTH]
    return JsonResponse({'text': text, 'responseType': 'END' if end else 'CON'})


@csrf_exempt
@require_POST
def brilio_callback(request):
    if not _is_authorized(request):
        return JsonResponse({'detail': 'Unauthorized'}, status=401)
    try:
        payload = json.loads(request.body)
    except ValueError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    session_id = str(payload.get('sessionId', ''))
    text = str(payload.get('text') or '')
    network = str(payload.get('network') or '')
    msisdn = normalize_msisdn(payload.get('msisdn'))
    if not session_id:
        return JsonResponse({'detail': 'sessionId is required'}, status=400)
    if msisdn is None:
        return _reply('Sorry, QuickTop is only available for Kenyan mobile numbers.', end=True)

    ctx = menu.Context(
        msisdn=msisdn,
        session_id=session_id,
        min_amount=settings.AIRTIME_MIN_AMOUNT,
        max_amount=settings.AIRTIME_MAX_AMOUNT,
    )
    try:
        response = menu.handle(text, ctx)
        if response.action:
            response.action()
    except Exception:
        logger.exception('USSD session %s failed on text %r', session_id, text)
        response = menu.Response(ERROR_TEXT, end=True)

    try:
        Customer.objects.update_or_create(phone_number=msisdn, defaults={'network': network})
        UssdSession.objects.update_or_create(
            session_id=session_id,
            defaults={
                'msisdn': msisdn,
                'network': network,
                'service_code': str(payload.get('code') or ''),
                'text': text,
                'last_response': response.text,
                'ended': response.end,
            },
        )
    except Exception:
        # Logging must never break the subscriber's session.
        logger.exception('Could not record USSD session %s', session_id)

    return _reply(response.text, response.end)
