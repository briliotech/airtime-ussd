import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import handle_statum_callback

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def statum_callback(request):
    try:
        payload = json.loads(request.body)
    except ValueError:
        return JsonResponse({'status': 'invalid json'}, status=400)

    logger.info('Statum callback: %s', payload)
    handle_statum_callback(payload)
    return JsonResponse({'status': 'acknowledged'})
