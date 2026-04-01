import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_http_methods(["POST"])
def chatbot_api(request):
    """Main chatbot API endpoint - uses local AI engine."""
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        
        if not question:
            return JsonResponse({'error': 'No question provided'}, status=400)
        
        if len(question) > 500:
            return JsonResponse({'error': 'Question too long'}, status=400)
        
        from .erpnext_chat import answer_question
        result = answer_question(question)
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({
            'answer': f'Sorry, I encountered an error: {str(e)}',
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def chatbot_health(request):
    """Health check endpoint."""
    try:
        from .erpnext_chat import AutoZoneChatbot
        
        chatbot = AutoZoneChatbot()
        brands = chatbot.get_brands()
        territories = chatbot.get_territories()
        item_count = chatbot.get_item_count()
        customer_count = chatbot.get_customer_count()
        
        return JsonResponse({
            'status': 'healthy',
            'database': 'connected',
            'ai_engine': 'local',
            'stats': {
                'brands': len(brands),
                'territories': len(territories),
                'items': item_count,
                'customers': customer_count
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        })
