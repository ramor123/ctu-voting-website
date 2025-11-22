from django.utils.deprecation import MiddlewareMixin
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages


class AccountCheckMiddleWare(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):

        modulename = view_func.__module__
        user = request.user

        # -----------------------------------------------------------
        # 0. ALLOW LANDING PAGE WITHOUT LOGIN
        # -----------------------------------------------------------
        try:
            if request.path == reverse('landing'):  # name="landing" in urls.py
                return None
        except:
            pass

        # -----------------------------------------------------------
        # 1. USER IS LOGGED IN
        # -----------------------------------------------------------
        if user.is_authenticated:

            # ------------------ ADMIN AREA ACCESS -------------------
            if user.user_type == '1':  # Admin
                if modulename == 'voting.views':
                    if request.path == reverse('fetch_ballot'):
                        return None
                    messages.error(request, "You do not have access to this resource")
                    return redirect(reverse('adminDashboard'))

            # ------------------ VOTER AREA ACCESS -------------------
            elif user.user_type == '2':  # Voter
                if modulename == 'administrator.views':
                    messages.error(request, "You do not have access to this resource")
                    return redirect(reverse('voterDashboard'))

            # ------------------ UNKNOWN USER TYPE -------------------
            else:
                return redirect(reverse('account_login'))

            return None

        # -----------------------------------------------------------
        # 2. USER NOT LOGGED IN — CHECK ALLOWED PAGES
        # -----------------------------------------------------------
        else:

            # Allowed no-login pages
            allowed_paths = [
                reverse('account_login'),
                reverse('account_register'),
            ]

            if request.path in allowed_paths:
                return None

            # Allow Django's own auth views
            if modulename == "django.contrib.auth.views":
                return None

            # Trying to access ADMIN or VOTER pages while not logged in
            if modulename == "administrator.views" or modulename == "voting.views":
                messages.error(request, "You need to be logged in to perform this operation")
                return redirect(reverse('account_login'))

            # Everything else → redirect to login
            return redirect(reverse('account_login'))
