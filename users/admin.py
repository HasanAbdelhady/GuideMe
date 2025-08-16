from django.contrib import admin

from .models import CustomUser, Interest

admin.site.register(CustomUser)


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
