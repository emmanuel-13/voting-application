from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from .models import Vote


@admin.action(description="Approve selected accounts")
def approve_accounts(modeladmin, request, queryset):
	approved_count = queryset.filter(is_active=False).update(is_active=True)
	modeladmin.message_user(
		request,
		f"{approved_count} account(s) approved.",
		messages.SUCCESS,
	)


class VotingUserAdmin(UserAdmin):
	list_display = (
		"username",
		"email",
		"first_name",
		"last_name",
		"is_active",
		"is_staff",
	)
	list_filter = ("is_active", "is_staff", "is_superuser", "groups")
	actions = (approve_accounts,)


User = get_user_model()
admin.site.unregister(User)
admin.site.register(User, VotingUserAdmin)
admin.site.register(Vote)