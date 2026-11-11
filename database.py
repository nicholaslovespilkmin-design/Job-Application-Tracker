"""
database.py - all MySQL access for the Job Application Tracker.

app.py should never write SQL itself; it calls the functions in this file.

    from database import get_all_jobs, create_job
    jobs = get_all_jobs()
    new_id = create_job(request.form)

Connection settings come from a .env file (see .env.example), so your
password never ends up on GitHub.
"""

import json
import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error, IntegrityError  # re-exported for app.py
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "job_tracker"),
}

# Allowed values - keep in sync with the ENUMs in schema.sql.
# Use these to build <select> dropdowns in your templates.
JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship"]
APPLICATION_STATUSES = ["Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"]


# =====================================================================
# Connection + low-level helpers
# =====================================================================

def get_db():
    """Open a new connection to the job_tracker database."""
    return mysql.connector.connect(**DB_CONFIG)


@contextmanager
def db_cursor(commit=False):
    """
    Open a connection + dictionary cursor and always close them.

        with db_cursor() as cur:
            cur.execute("SELECT * FROM companies")
            rows = cur.fetchall()

    With commit=True the changes are committed at the end, or rolled
    back if anything inside the block raises an error.
    """
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def query_all(sql, params=None):
    """Run a SELECT and return a list of dicts."""
    with db_cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql, params=None):
    """Run a SELECT and return one dict, or None if no row matched."""
    with db_cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql, params=None):
    """Run INSERT/UPDATE/DELETE. Returns the new id for INSERTs, else rows affected."""
    with db_cursor(commit=True) as cur:
        cur.execute(sql, params or ())
        return cur.lastrowid or cur.rowcount


# =====================================================================
# Value cleaning - HTML forms send everything as strings, and an empty
# field arrives as "" which MySQL rejects for INT/DATE columns.
# =====================================================================

def _clean(value):
    """Strip strings and turn empty strings into None (SQL NULL)."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _to_bool(value):
    """Checkbox -> bool. A checked box sends 'on'; an unchecked one sends nothing."""
    if isinstance(value, str):
        return value.strip().lower() in ("on", "true", "1", "yes")
    return bool(value)


def parse_skills(value):
    """
    Turn user input into a clean list of skills.
    Accepts a list, or a comma-separated string like "Python, SQL ,flask".
    Duplicates (case-insensitive) are removed; order is kept.
    """
    if value is None:
        return []
    if isinstance(value, str):
        value = value.split(",")
    skills, seen = [], set()
    for skill in value:
        skill = str(skill).strip()
        if skill and skill.lower() not in seen:
            seen.add(skill.lower())
            skills.append(skill)
    return skills


def _to_json(value, expected_type):
    """
    Convert a Python object or a JSON string into a JSON string for MySQL.
    Raises ValueError if it's not valid JSON of the expected type
    (list for requirements, dict for interview_data).
    """
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc.msg}") from exc
    if not isinstance(value, expected_type):
        raise ValueError(f"Expected a JSON {expected_type.__name__}")
    return json.dumps(value)


def _from_json(value, default):
    """MySQL returns JSON columns as str (or bytes); turn them back into Python."""
    if value is None:
        return default
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value


def _build_values(data, columns):
    """Pick the allowed columns out of `data` (e.g. request.form) and clean them."""
    return [_clean(data.get(col)) for col in columns]


def _insert(table, columns, values):
    # Table/column names come from the constants in this file, never from
    # user input, so formatting them in is safe. Values always use %s.
    cols = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    return execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", values)


def _update(table, pk, record_id, columns, values):
    assignments = ", ".join(f"{col} = %s" for col in columns)
    return execute(f"UPDATE {table} SET {assignments} WHERE {pk} = %s", [*values, record_id])


# =====================================================================
# COMPANIES
# =====================================================================

COMPANY_COLUMNS = ["company_name", "industry", "website", "city", "state", "notes"]


def get_all_companies():
    """All companies with how many jobs/contacts each has."""
    return query_all("""
        SELECT c.*,
               (SELECT COUNT(*) FROM jobs     j  WHERE j.company_id  = c.company_id) AS job_count,
               (SELECT COUNT(*) FROM contacts ct WHERE ct.company_id = c.company_id) AS contact_count
        FROM companies c
        ORDER BY c.company_name
    """)


def get_company(company_id):
    return query_one("SELECT * FROM companies WHERE company_id = %s", (company_id,))


def create_company(data):
    """Raises IntegrityError if the company name already exists."""
    return _insert("companies", COMPANY_COLUMNS, _build_values(data, COMPANY_COLUMNS))


def update_company(company_id, data):
    return _update("companies", "company_id", company_id,
                   COMPANY_COLUMNS, _build_values(data, COMPANY_COLUMNS))


def delete_company(company_id):
    """WARNING: also deletes the company's jobs, applications and contacts (ON DELETE CASCADE)."""
    return execute("DELETE FROM companies WHERE company_id = %s", (company_id,))


def get_company_options():
    """(id, name) pairs for a <select> dropdown on the job/contact forms."""
    return query_all("SELECT company_id, company_name FROM companies ORDER BY company_name")


# =====================================================================
# JOBS
# =====================================================================

JOB_COLUMNS = ["company_id", "job_title", "job_type", "salary_min", "salary_max",
               "job_url", "date_posted", "requirements"]


def _job_values(data):
    values = _build_values(data, JOB_COLUMNS)
    skills = parse_skills(data.get("requirements"))
    values[JOB_COLUMNS.index("requirements")] = json.dumps(skills) if skills else None
    return values


def _decode_job(row):
    if row:
        row["requirements"] = _from_json(row.get("requirements"), [])
    return row


JOB_SELECT = """
    SELECT j.*, c.company_name
    FROM jobs j
    JOIN companies c ON c.company_id = j.company_id
"""


def get_all_jobs():
    rows = query_all(JOB_SELECT + " ORDER BY j.date_posted DESC, j.job_id DESC")
    return [_decode_job(r) for r in rows]


def get_job(job_id):
    return _decode_job(query_one(JOB_SELECT + " WHERE j.job_id = %s", (job_id,)))


def create_job(data):
    """`requirements` may be a list or a comma-separated string."""
    return _insert("jobs", JOB_COLUMNS, _job_values(data))


def update_job(job_id, data):
    return _update("jobs", "job_id", job_id, JOB_COLUMNS, _job_values(data))


def delete_job(job_id):
    """WARNING: also deletes applications for this job (ON DELETE CASCADE)."""
    return execute("DELETE FROM jobs WHERE job_id = %s", (job_id,))


def get_job_options():
    """Jobs labelled 'Title @ Company' for the application form dropdown."""
    return query_all("""
        SELECT j.job_id, CONCAT(j.job_title, ' @ ', c.company_name) AS label
        FROM jobs j JOIN companies c ON c.company_id = j.company_id
        ORDER BY c.company_name, j.job_title
    """)


def get_jobs_for_matching():
    """
    Every job with its requirements as a Python list - the input for your
    Job Match algorithm, e.g.
        {"job_id": 1, "job_title": "Software Developer",
         "company_name": "TechCorp", "requirements": ["Python", "SQL", "Flask"]}
    """
    rows = query_all("""
        SELECT j.job_id, j.job_title, j.job_type, j.salary_min, j.salary_max,
               j.requirements, c.company_name
        FROM jobs j JOIN companies c ON c.company_id = j.company_id
        WHERE j.requirements IS NOT NULL
    """)
    return [_decode_job(r) for r in rows]


# =====================================================================
# APPLICATIONS
# =====================================================================

APPLICATION_COLUMNS = ["job_id", "application_date", "status", "resume_version",
                       "cover_letter_sent", "interview_data"]


def _application_values(data):
    values = _build_values(data, APPLICATION_COLUMNS)
    values[APPLICATION_COLUMNS.index("cover_letter_sent")] = _to_bool(data.get("cover_letter_sent"))
    values[APPLICATION_COLUMNS.index("interview_data")] = _to_json(data.get("interview_data"), dict)
    return values


def _decode_application(row):
    if row:
        row["interview_data"] = _from_json(row.get("interview_data"), {})
        row["cover_letter_sent"] = bool(row.get("cover_letter_sent"))
    return row


APPLICATION_SELECT = """
    SELECT a.*, j.job_title, c.company_id, c.company_name
    FROM applications a
    JOIN jobs j      ON j.job_id     = a.job_id
    JOIN companies c ON c.company_id = j.company_id
"""


def get_all_applications(status=None):
    """All applications, newest first. Pass a status to filter (e.g. 'Interview')."""
    if status:
        rows = query_all(APPLICATION_SELECT + " WHERE a.status = %s ORDER BY a.application_date DESC",
                         (status,))
    else:
        rows = query_all(APPLICATION_SELECT + " ORDER BY a.application_date DESC")
    return [_decode_application(r) for r in rows]


def get_application(application_id):
    return _decode_application(
        query_one(APPLICATION_SELECT + " WHERE a.application_id = %s", (application_id,)))


def create_application(data):
    """Raises ValueError if interview_data isn't a valid JSON object."""
    return _insert("applications", APPLICATION_COLUMNS, _application_values(data))


def update_application(application_id, data):
    return _update("applications", "application_id", application_id,
                   APPLICATION_COLUMNS, _application_values(data))


def delete_application(application_id):
    return execute("DELETE FROM applications WHERE application_id = %s", (application_id,))


# =====================================================================
# CONTACTS
# =====================================================================

CONTACT_COLUMNS = ["company_id", "contact_name", "title", "email", "phone",
                   "linkedin_url", "notes"]

CONTACT_SELECT = """
    SELECT ct.*, c.company_name
    FROM contacts ct
    JOIN companies c ON c.company_id = ct.company_id
"""


def get_all_contacts():
    return query_all(CONTACT_SELECT + " ORDER BY c.company_name, ct.contact_name")


def get_contact(contact_id):
    return query_one(CONTACT_SELECT + " WHERE ct.contact_id = %s", (contact_id,))


def create_contact(data):
    return _insert("contacts", CONTACT_COLUMNS, _build_values(data, CONTACT_COLUMNS))


def update_contact(contact_id, data):
    return _update("contacts", "contact_id", contact_id,
                   CONTACT_COLUMNS, _build_values(data, CONTACT_COLUMNS))


def delete_contact(contact_id):
    return execute("DELETE FROM contacts WHERE contact_id = %s", (contact_id,))


# =====================================================================
# DASHBOARD
# =====================================================================

def get_dashboard_stats():
    """Everything the dashboard page needs in one dict."""
    counts = query_one("""
        SELECT (SELECT COUNT(*) FROM companies)    AS companies,
               (SELECT COUNT(*) FROM jobs)         AS jobs,
               (SELECT COUNT(*) FROM applications) AS applications,
               (SELECT COUNT(*) FROM contacts)     AS contacts
    """)

    # Start every status at 0 so the template can show all of them.
    by_status = {status: 0 for status in APPLICATION_STATUSES}
    for row in query_all("SELECT status, COUNT(*) AS n FROM applications GROUP BY status"):
        by_status[row["status"]] = row["n"]

    total = counts["applications"]
    responded = total - by_status["Applied"] - by_status["Withdrawn"]
    response_rate = round(100 * responded / total) if total else 0

    recent = query_all("""
        SELECT * FROM application_overview
        ORDER BY application_date DESC LIMIT 5
    """)

    return {
        "counts": counts,
        "by_status": by_status,
        "response_rate": response_rate,
        "recent_applications": recent,
    }


# =====================================================================
# Run `python database.py` to check that your connection works.
# =====================================================================

if __name__ == "__main__":
    try:
        stats = get_dashboard_stats()
    except Error as exc:
        print(f"Could not connect to MySQL: {exc}")
        print("Check your .env file and that you ran: mysql -u root -p < schema.sql")
        raise SystemExit(1)

    print(f"Connected to '{DB_CONFIG['database']}' on {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    for table, n in stats["counts"].items():
        print(f"  {table:<13} {n} rows")
    print("  applications by status:", stats["by_status"])
