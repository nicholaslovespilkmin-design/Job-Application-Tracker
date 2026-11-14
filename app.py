"""
app.py - Flask routes for the Job Application Tracker.

Run with:  python app.py   then open http://127.0.0.1:5000
"""

import os
from datetime import date

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import database as db

app = Flask(__name__)
# database.py has already loaded .env, so SECRET_KEY can live there too.
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")


# =====================================================================
# Template helpers
# =====================================================================

@app.template_filter("money")
def money(value):
    """45000 -> $45,000"""
    return f"${value:,}" if value is not None else ""


@app.context_processor
def inject_constants():
    return {
        "JOB_TYPES": db.JOB_TYPES,
        "APPLICATION_STATUSES": db.APPLICATION_STATUSES,
    }


# =====================================================================
# Shared form handling
# =====================================================================

def friendly_error(exc):
    """Turn a database/validation error into a message a user can act on."""
    if isinstance(exc, ValueError):
        return f"Interview data must be a JSON object, e.g. {{\"rounds\": []}}. ({exc})"
    msg = getattr(exc, "msg", None) or str(exc)
    errno = getattr(exc, "errno", None)
    if errno == 1062:
        return "That name already exists. Please use a different one."
    if errno == 1048:
        return "Please fill in all required fields."
    if "chk_salary_range" in msg:
        return "Minimum salary can't be greater than maximum salary."
    if "chk_salary_positive" in msg:
        return "Salaries can't be negative."
    return f"Could not save: {msg}"


def form_page(template, item, save, success_msg, list_endpoint, **context):
    """
    GET  -> show the form filled with `item`.
    POST -> call save(request.form); on success redirect to the list page,
            on error re-show the form with what the user typed.
    """
    if request.method == "POST":
        try:
            save(request.form)
        except (db.Error, ValueError) as exc:
            flash(friendly_error(exc), "error")
            return render_template(template, item=request.form, **context), 400
        flash(success_msg, "success")
        return redirect(url_for(list_endpoint))
    return render_template(template, item=item, **context)


def delete_record(delete, record_id, success_msg, list_endpoint):
    try:
        delete(record_id)
        flash(success_msg, "success")
    except db.Error as exc:
        flash(f"Could not delete: {exc}", "error")
    return redirect(url_for(list_endpoint))


def get_or_404(getter, record_id):
    record = getter(record_id)
    if record is None:
        abort(404)
    return record


# =====================================================================
# Dashboard
# =====================================================================

@app.route("/")
def dashboard():
    return render_template("dashboard.html", stats=db.get_dashboard_stats())


# =====================================================================
# Companies
# =====================================================================

@app.route("/companies")
def companies():
    return render_template("companies.html", companies=db.get_all_companies())


@app.route("/companies/new", methods=["GET", "POST"])
def companies_new():
    return form_page("company_form.html", {}, db.create_company,
                     "Company added.", "companies", is_edit=False)


@app.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
def companies_edit(company_id):
    company = get_or_404(db.get_company, company_id)
    return form_page("company_form.html", company,
                     lambda form: db.update_company(company_id, form),
                     "Company updated.", "companies", is_edit=True)


@app.route("/companies/<int:company_id>/delete", methods=["POST"])
def companies_delete(company_id):
    return delete_record(db.delete_company, company_id,
                         "Company and its jobs, applications and contacts deleted.", "companies")


# =====================================================================
# Jobs
# =====================================================================

@app.route("/jobs")
def jobs():
    return render_template("jobs.html", jobs=db.get_all_jobs())


@app.route("/jobs/new", methods=["GET", "POST"])
def jobs_new():
    # ?company_id=3 pre-selects the company (used by the Companies page).
    defaults = {"job_type": "Full-time", **request.args.to_dict()}
    return form_page("job_form.html", defaults, db.create_job,
                     "Job added.", "jobs",
                     is_edit=False, companies=db.get_company_options())


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def jobs_edit(job_id):
    job = get_or_404(db.get_job, job_id)
    return form_page("job_form.html", job,
                     lambda form: db.update_job(job_id, form),
                     "Job updated.", "jobs",
                     is_edit=True, companies=db.get_company_options())


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def jobs_delete(job_id):
    return delete_record(db.delete_job, job_id,
                         "Job and its applications deleted.", "jobs")


# =====================================================================
# Applications
# =====================================================================

@app.route("/applications")
def applications():
    status = request.args.get("status")
    if status not in db.APPLICATION_STATUSES:
        status = None
    return render_template("applications.html",
                           applications=db.get_all_applications(status),
                           current_status=status)


@app.route("/applications/new", methods=["GET", "POST"])
def applications_new():
    # ?job_id=3 pre-selects the job (used by Jobs and Job Match pages).
    defaults = {"application_date": date.today().isoformat(), "status": "Applied",
                **request.args.to_dict()}
    return form_page("application_form.html", defaults, db.create_application,
                     "Application added.", "applications",
                     is_edit=False, jobs=db.get_job_options())


@app.route("/applications/<int:application_id>/edit", methods=["GET", "POST"])
def applications_edit(application_id):
    application = get_or_404(db.get_application, application_id)
    return form_page("application_form.html", application,
                     lambda form: db.update_application(application_id, form),
                     "Application updated.", "applications",
                     is_edit=True, jobs=db.get_job_options())


@app.route("/applications/<int:application_id>/delete", methods=["POST"])
def applications_delete(application_id):
    return delete_record(db.delete_application, application_id,
                         "Application deleted.", "applications")


# =====================================================================
# Contacts
# =====================================================================

@app.route("/contacts")
def contacts():
    return render_template("contacts.html", contacts=db.get_all_contacts())


@app.route("/contacts/new", methods=["GET", "POST"])
def contacts_new():
    return form_page("contact_form.html", request.args.to_dict(), db.create_contact,
                     "Contact added.", "contacts",
                     is_edit=False, companies=db.get_company_options())


@app.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
def contacts_edit(contact_id):
    contact = get_or_404(db.get_contact, contact_id)
    return form_page("contact_form.html", contact,
                     lambda form: db.update_contact(contact_id, form),
                     "Contact updated.", "contacts",
                     is_edit=True, companies=db.get_company_options())


@app.route("/contacts/<int:contact_id>/delete", methods=["POST"])
def contacts_delete(contact_id):
    return delete_record(db.delete_contact, contact_id, "Contact deleted.", "contacts")


# =====================================================================
# Job Match
# =====================================================================

def match_jobs(user_skills, jobs):
    """
    Rank jobs by how many of their required skills the user has.
    Comparison ignores case ("python" matches "Python").

    match % = matched requirements / total requirements of the job.
    Jobs with no matching skills are left out.
    """
    have = {skill.lower() for skill in user_skills}
    results = []
    for job in jobs:
        required = job["requirements"]
        if not required:
            continue
        matched = [s for s in required if s.lower() in have]
        if not matched:
            continue
        missing = [s for s in required if s.lower() not in have]
        results.append({
            **job,
            "matched": matched,
            "missing": missing,
            "percent": round(100 * len(matched) / len(required)),
        })
   
    results.sort(key=lambda r: (-r["percent"], -len(r["matched"]), r["job_title"]))
    return results


@app.route("/match")
def match():
    skills_text = request.args.get("skills", "")
    skills = db.parse_skills(skills_text)
    results = match_jobs(skills, db.get_jobs_for_matching()) if skills else []
    return render_template("match.html", skills_text=skills_text,
                           skills=skills, results=results)


# =====================================================================
# Errors
# =====================================================================

@app.errorhandler(404)
def not_found(_exc):
    return render_template("error.html", title="Not found",
                           message="That page or record doesn't exist."), 404


@app.errorhandler(db.Error)
def database_error(exc):
    return render_template("error.html", title="Database error",
                           message=f"Could not reach MySQL: {exc}. "
                                   "Check your .env file and that MySQL is running."), 500


if __name__ == "__main__":
    app.run(debug=True)
