from django.http import JsonResponse


def health(request):
    """Simple health-check endpoint returning hola mundo."""
    return JsonResponse({"message": "hola mundo"})
