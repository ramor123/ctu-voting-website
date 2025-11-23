from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from .email_backend import EmailBackend
from .forms import CustomUserForm
from account.models import CustomUser
from voting.forms import VoterForm
from voting.models import Voter


# ---------------------------
# LOGIN VIEW
# ---------------------------
def account_login(request):
    if request.user.is_authenticated:
        if request.user.user_type == '1':
            return redirect("adminDashboard")
        else:
            return redirect("account_confirm")

    if request.method == 'POST':
        user = EmailBackend.authenticate(
            request,
            username=request.POST.get("email"),
            password=request.POST.get("password")
        )

        if user is not None:
            login(request, user)

            if user.user_type == '1':
                return redirect("adminDashboard")
            else:
                return redirect("account_confirm")
        else:
            messages.error(request, "Invalid login details")
            return redirect("account_login")

    return render(request, "voting/login.html")


# ---------------------------
# REGISTER VIEW
# ---------------------------
def account_register(request):
    userForm = CustomUserForm(request.POST or None)
    voterForm = VoterForm(request.POST or None)

    if request.method == "POST":
        if userForm.is_valid() and voterForm.is_valid():
            user = userForm.save(commit=False)
            voter = voterForm.save(commit=False)

            voter.admin = user
            user.save()
            voter.save()

            messages.success(request, "Account created. You can now log in.")
            return redirect("account_login")
        else:
            messages.error(request, "Provided data failed validation")

    return render(
        request,
        "voting/reg.html",
        {"form1": userForm, "form2": voterForm}
    )


# ---------------------------
# LOGOUT VIEW (FINAL WORKING)
# ---------------------------
def account_logout(request):
    logout(request)
    messages.success(request, "Thank you for visiting us!")
    return redirect("account_login")


# ---------------------------
# VOTER CONFIRMATION PAGE
# ---------------------------
def account_confirm(request):
    if not request.user.is_authenticated:
        return redirect("account_login")

    voter = Voter.objects.filter(admin=request.user).first()

    context = {
        "full_name": f"{request.user.first_name} {request.user.last_name}",
        "course": voter.course if voter else "",
        "year_section": voter.year_section if voter else "",
        "year_level": voter.year_level if voter else "",
    }

    return render(request, "voting/confirmation.html", context)


# ---------------------------
# IDENTITY CONFIRMATION
# ---------------------------
def confirm_identity(request):
    user = request.user

    if user.user_type != "2":
        return redirect("adminDashboard")

    try:
        voter = Voter.objects.get(admin=user)
    except Voter.DoesNotExist:
        return redirect("account_login")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "yes":
            return redirect("ballot")
        elif action == "no":
            logout(request)
            return redirect("account_login")

    context = {
        "full_name": f"{user.first_name} {user.last_name}",
        "email": user.email,
        "phone": voter.phone,
        "verified": voter.verified,
    }

    return render(request, "voting/confirm_identity.html", context)
