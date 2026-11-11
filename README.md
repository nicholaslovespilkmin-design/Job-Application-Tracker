# Job Application Tracker

A Flask + MySQL web app for tracking companies, job postings, applications and contacts, with a skill-based Job Match feature.

## Setup

### 1. Requirements
- Python 3.10+
- MySQL 8.0+ (MySQL Server or MySQL Workbench)

### 2. Install Python packages
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create the database
This drops and recreates the `job_tracker` database and loads sample data:
```bash
mysql -u root -p < schema.sql
```
(Or open `schema.sql` in MySQL Workbench and run the whole script.)

### 4. Configure the connection
```bash
cp .env.example .env
```
Edit `.env` and set `DB_PASSWORD` to your MySQL password.

### 5. Test the connection
```bash
python database.py
```
You should see row counts for all four tables.

### 6. Run the app
```bash
python app.py
```
Then open http://127.0.0.1:5000

## Database design

| Table | Purpose | Relationships |
|---|---|---|
| `companies` | Organizations you apply to | Parent of `jobs` and `contacts` |
| `jobs` | Job postings; `requirements` is a JSON array of skills | FK → `companies` |
| `applications` | Your application to a job; `interview_data` is a JSON object | FK → `jobs` |
| `contacts` | People at a company | FK → `companies` |

- All foreign keys use `ON DELETE CASCADE`: deleting a company also deletes its jobs, their applications, and its contacts.
- `CHECK` constraints keep `salary_min <= salary_max` and make sure the JSON columns have the right shape.
- The `application_overview` view joins applications → jobs → companies for list pages and the dashboard.
