from django.shortcuts import render, redirect, reverse
from account.views import account_login
from .models import Position, Candidate, Voter, Votes
from django.http import JsonResponse
from django.utils.text import slugify
from django.contrib import messages
from django.conf import settings
import requests
import json


# ---------------------------
# Basic pages / login
# ---------------------------
def login_view(request):
    """Render the login page (located at voting/templates/voting/login.html)."""
    return render(request, "voting/login.html")


def landing(request):
    return render(request, "landing.html")


def index(request):
    """Root index for voting app: if not authenticated show login, else go to confirmation."""
    if not request.user.is_authenticated:
        return account_login(request)
    # direct to the confirmation page (name in urls.py is 'confirmation_page')
    return redirect(reverse("confirmation_page"))


# ========================================
#       VOTER CONFIRMATION (used by urls)
# ========================================
def confirmation_page(request):
    """
    Show the voter their details and ask to confirm.
    POST 'yes' -> ballot_page
    POST 'no'  -> login page in voting app
    """
    user = request.user

    if not user.is_authenticated:
        return redirect("votingLogin")

    try:
        voter = Voter.objects.get(admin=user)
    except Voter.DoesNotExist:
        messages.error(request, "No voter profile found.")
        return redirect("votingLogin")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "yes":
            # open the voting ballot page (renders the ballot)
            return redirect("show_ballot")
        elif action == "no":
            messages.info(request, "Please login again.")
            return redirect("votingLogin")

    context = {
        "full_name": f"{user.first_name} {user.last_name}",
        "email": user.email,
        "phone": voter.phone,
        "verified": "Yes" if voter.verified else "No",
    }

    return render(request, "voting/voter/confirmation.html", context)


# ========================================
#           BALLOT GENERATION
# ========================================
def generate_ballot(display_controls=False):
    positions = Position.objects.order_by('priority').all()
    output = ""
    num = 1

    for position in positions:
        name = position.name
        position_name = slugify(name)
        candidates = Candidate.objects.filter(position=position)
        candidates_data = ""

        # Build candidate list
        for candidate in candidates:

            # Instruction + Input Selector (NEW minimal-green style)
            if position.max_vote > 1:
                instruction = f"You may select up to {position.max_vote} candidates"
                input_box = f'''
                    <input type="checkbox" value="{candidate.id}"
                           class="minimal-green {position_name}"
                           name="{position_name}[]">
                '''
            else:
                instruction = "Select only one candidate"
                input_box = f'''
                    <input type="radio" value="{candidate.id}"
                           class="minimal-green {position_name}"
                           name="{position_name}">
                '''

            image_url = candidate.photo.url if candidate.photo else ""

            candidates_data += f"""
                <li style="margin-bottom:20px;">
                    {input_box}
                    <button type="button" class="btn btn-primary btn-sm btn-flat platform"
                        data-fullname="{candidate.fullname}"
                        data-bio="{candidate.bio}">
                        <i class="fa fa-search"></i> Platform
                    </button>

                    <img src="{image_url}" height="100" width="100" class="clist" style="margin-left:10px; border-radius:6px;">

                    <span class="cname clist" style="font-size:20px; margin-left:10px;">
                        {candidate.fullname}
                    </span>
                </li>
            """

        # Up / Down Buttons
        up = "disabled" if position.priority == 1 else ""
        down = "disabled" if position.priority == positions.count() else ""

        output += f"""
        <div class="row">
        <div class="col-xs-12">
        <div class="box box-solid" id="{position.id}">
        
            <div class="box-header with-border">
                <h3 class="box-title"><b>{name}</b></h3>
        """

        if display_controls:
            output += f"""
                <div class="pull-right box-tools">
                    <button type="button" class="btn btn-default btn-sm moveup" data-id="{position.id}" {up}>
                        <i class="fa fa-arrow-up"></i>
                    </button>
                    <button type="button" class="btn btn-default btn-sm movedown" data-id="{position.id}" {down}>
                        <i class="fa fa-arrow-down"></i>
                    </button>
                </div>
            """

        output += f"""
            </div>

            <div class="box-body">
                <p>{instruction}
                    <span class="pull-right">
                        <button type="button" class="btn btn-success btn-sm btn-flat reset"
                            data-desc="{position_name}">
                            <i class="fa fa-refresh"></i> Reset
                        </button>
                    </span>
                </p>

                <div id="candidate_list">
                    <ul style="list-style-type:none; padding-left:0;">
                        {candidates_data}
                    </ul>
                </div>
            </div>

        </div>
        </div>
        </div>
        """

        # Fix ordering
        position.priority = num
        position.save()
        num += 1

    return output



def fetch_ballot(request):
    return JsonResponse(generate_ballot(True), safe=False)


# ========================================
#             OTP SYSTEM
# ========================================
def generate_otp():
    import random as r
    otp = ""
    for i in range(r.randint(5, 8)):
        otp += str(r.randint(1, 9))
    return otp


def dashboard(request):
    user = request.user
    if not user.is_authenticated:
        return redirect("votingLogin")
    return redirect(reverse("confirmation_page"))


def voter_dashboard(request):
    user = request.user
    if user.voter.otp is None or user.voter.verified is False:
        if not settings.SEND_OTP:
            msg = bypass_otp()
            messages.success(request, msg)
            return redirect(reverse("show_ballot"))
        return redirect(reverse("voterVerify"))

    if user.voter.voted:
        context = {"my_votes": Votes.objects.filter(voter=user.voter)}
        return render(request, "voting/voter/result.html", context)
    return redirect(reverse("show_ballot"))


def verify(request):
    return render(request, "voting/voter/verify.html", {"page_title": "OTP Verification"})


def resend_otp(request):
    user = request.user
    voter = user.voter
    error = False

    if settings.SEND_OTP:
        if voter.otp_sent >= 3:
            return JsonResponse({"data": "You have requested OTP three times. Enter the previous OTP.", "error": True})

        phone = voter.phone
        otp = voter.otp or generate_otp()
        voter.otp = otp
        voter.save()
        msg = f"Dear {user}, kindly use {otp} as your OTP"
        if send_sms(phone, msg):
            voter.otp_sent += 1
            voter.save()
            response = "OTP has been sent."
        else:
            error = True
            response = "OTP not sent. Try again."
    else:
        response = bypass_otp()

    return JsonResponse({"data": response, "error": error})


def bypass_otp():
    Voter.objects.filter(otp=None, verified=False).update(otp="0000", verified=True)
    return "Kindly cast your vote"


def send_sms(phone_number, msg):
    email = settings.SMS_EMAIL
    password = settings.SMS_PASSWORD
    if not email or not password:
        raise Exception("Email/Password cannot be Null")

    url = "https://app.multitexter.com/v2/app/sms"
    data = {"email": email, "password": password, "message": msg, "sender_name": "OTP", "recipients": phone_number, "forcednd": 1}
    headers = {"Content-type": "application/json"}
    r = requests.post(url, data=json.dumps(data), headers=headers)
    response = r.json()
    return str(response.get("status", 0)) == "1"


def verify_otp(request):
    if request.method != "POST":
        messages.error(request, "Access Denied")
        return redirect(reverse("voterVerify"))
    otp = request.POST.get("otp")
    voter = request.user.voter
    if otp != voter.otp:
        messages.error(request, "Invalid OTP")
        return redirect(reverse("voterVerify"))
    voter.verified = True
    voter.save()
    messages.success(request, "Verification successful.")
    return redirect(reverse("show_ballot"))


# ========================================
#           BALLOT SUBMISSION
# ========================================
def show_ballot(request):
    if request.user.voter.voted:
        messages.error(request, "You have voted already")
        return redirect(reverse("voterDashboard"))
    ballot = generate_ballot()
    return render(request, "voting/voter/ballot.html", {"ballot": ballot})


def preview_vote(request):
    if request.method != "POST":
        return JsonResponse({"error": True, "list": ""}, safe=False)

    output = ""
    form = dict(request.POST)
    form.pop("csrfmiddlewaretoken", None)

    error = False
    positions = Position.objects.all()

    for position in positions:
        pos = slugify(position.name)
        if position.max_vote > 1:
            this_key = pos + "[]"
            selected = form.get(this_key)
            if not selected:
                continue
            if len(selected) > position.max_vote:
                return JsonResponse({"error": True, "list": f"You can only choose {position.max_vote} for {position.name}"}, safe=False)

            block = f"""
            <div class='row votelist'>
                <span class='col-sm-4 pull-right'><b>{position.name}:</b></span>
                <span class='col-sm-8'>
                    <ul style='list-style-type:none; margin-left:-40px'>
            """
            for cid in selected:
                try:
                    c = Candidate.objects.get(id=cid, position=position)
                    block += f"<li><i class='fa fa-check-square-o'></i> {c.fullname}</li>"
                except:
                    return JsonResponse({"error": True, "list": "Invalid selection"}, safe=False)
            block += "</ul></span></div><hr/>"
            output += block
        else:
            selected = form.get(pos)
            if not selected:
                continue
            try:
                cid = selected[0]
                c = Candidate.objects.get(id=cid, position=position)
                output += f"""
                <div class='row votelist'>
                    <span class='col-sm-4 pull-right'><b>{position.name}:</b></span>
                    <span class='col-sm-8'><i class="fa fa-check-circle-o"></i> {c.fullname}</span>
                </div><hr/>
                """
            except:
                return JsonResponse({"error": True, "list": "Invalid selection"}, safe=False)

    return JsonResponse({"error": error, "list": output}, safe=False)


def submit_ballot(request):
    if request.method != "POST":
        messages.error(request, "Invalid submission")
        return redirect(reverse("show_ballot"))

    voter = request.user.voter
    if voter.voted:
        messages.error(request, "You have already voted")
        return redirect(reverse("voterDashboard"))

    form = dict(request.POST)
    form.pop("csrfmiddlewaretoken", None)
    form.pop("submit_vote", None)

    if len(form.keys()) < 1:
        messages.error(request, "Please select at least one candidate")
        return redirect(reverse("show_ballot"))

    positions = Position.objects.all()
    form_count = 0

    for position in positions:
        pos = slugify(position.name)
        if position.max_vote > 1:
            this_key = pos + "[]"
            selected = form.get(this_key)
            if not selected:
                continue
            if len(selected) > position.max_vote:
                messages.error(request, f"You can only choose {position.max_vote} for {position.name}")
                return redirect(reverse("show_ballot"))
            for cid in selected:
                try:
                    candidate = Candidate.objects.get(id=cid, position=position)
                    Votes.objects.create(candidate=candidate, voter=voter, position=position)
                    form_count += 1
                except:
                    messages.error(request, "Invalid candidate selection")
                    return redirect(reverse("show_ballot"))
        else:
            selected = form.get(pos)
            if not selected:
                continue
            cid = selected[0]
            try:
                candidate = Candidate.objects.get(id=cid, position=position)
                Votes.objects.create(candidate=candidate, voter=voter, position=position)
                form_count += 1
            except:
                messages.error(request, "Invalid candidate selection")
                return redirect(reverse("show_ballot"))

    inserted_votes = Votes.objects.filter(voter=voter)
    if inserted_votes.count() != form_count:
        inserted_votes.delete()
        messages.error(request, "Vote submission failed. Try again.")
        return redirect(reverse("show_ballot"))

    voter.voted = True
    voter.save()
    messages.success(request, "Thanks for voting!")
    return redirect(reverse("voterDashboard"))

def ballot_page(request):
    return render(request, "voting/voter/ballot.html")
