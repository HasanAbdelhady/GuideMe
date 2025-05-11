from django.conf import settings

def media_context(request):
    """
    Add MEDIA_URL to the template context for all templates.
    """
    return {
        'MEDIA_URL': settings.MEDIA_URL
    } 