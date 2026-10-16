import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import handle_stk_callback

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def mpesa_callback(request):
    try:
        body = json.loads(request.body)
    except ValueError:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'}, status=400)

    logger.info('M-Pesa callback: %s', body)
    handle_stk_callback(body)
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
