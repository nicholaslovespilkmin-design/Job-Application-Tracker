-- =====================================================================
-- Job Application Tracker - Database Schema
-- ---------------------------------------------------------------------
-- Recreates the whole database from scratch (drops it first!).
--
-- Run it from a terminal:
--     mysql -u root -p < schema.sql
-- or open it in MySQL Workbench and execute the whole script.
--
-- Tables (created in dependency order):
--     companies  <- jobs  <- applications
--     companies  <- contacts
-- =====================================================================

DROP DATABASE IF EXISTS job_tracker;
CREATE DATABASE job_tracker
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE job_tracker;

-- ---------------------------------------------------------------------
-- companies: organizations you are applying to
-- ---------------------------------------------------------------------
CREATE TABLE companies (
    company_id    INT           PRIMARY KEY AUTO_INCREMENT,
    company_name  VARCHAR(100)  NOT NULL,
    industry      VARCHAR(50),
    website       VARCHAR(200),
    city          VARCHAR(50),
    state         VARCHAR(50),
    notes         TEXT,

    CONSTRAINT uq_company_name UNIQUE (company_name)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- jobs: individual job postings at a company
--   requirements is a JSON array of skill strings, e.g.
--   ["Python", "SQL", "Flask"]  -> used by the Job Match feature
-- ---------------------------------------------------------------------
CREATE TABLE jobs (
    job_id        INT           PRIMARY KEY AUTO_INCREMENT,
    company_id    INT           NOT NULL,
    job_title     VARCHAR(100)  NOT NULL,
    job_type      ENUM('Full-time', 'Part-time', 'Contract', 'Internship')
                                NOT NULL DEFAULT 'Full-time',
    salary_min    INT,
    salary_max    INT,
    job_url       VARCHAR(300),
    date_posted   DATE,
    requirements  JSON,

    CONSTRAINT fk_jobs_company
        FOREIGN KEY (company_id) REFERENCES companies (company_id)
        ON DELETE CASCADE          -- deleting a company deletes its jobs
        ON UPDATE CASCADE,
    CONSTRAINT chk_salary_range
        CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max),
    CONSTRAINT chk_salary_positive
        CHECK ((salary_min IS NULL OR salary_min >= 0) AND (salary_max IS NULL OR salary_max >= 0)),
    CONSTRAINT chk_requirements_array
        CHECK (requirements IS NULL OR JSON_TYPE(requirements) = 'ARRAY')
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- applications: your application to a specific job
--   interview_data is a JSON object, e.g.
--   {"rounds": [{"date": "2026-10-02", "type": "Phone",
--                "interviewer": "Jane Doe", "notes": "Went well"}]}
-- ---------------------------------------------------------------------
CREATE TABLE applications (
    application_id     INT          PRIMARY KEY AUTO_INCREMENT,
    job_id             INT          NOT NULL,
    application_date   DATE         NOT NULL,
    status             ENUM('Applied', 'Screening', 'Interview',
                            'Offer', 'Rejected', 'Withdrawn')
                                    NOT NULL DEFAULT 'Applied',
    resume_version     VARCHAR(50),
    cover_letter_sent  BOOLEAN      NOT NULL DEFAULT FALSE,
    interview_data     JSON,

    CONSTRAINT fk_applications_job
        FOREIGN KEY (job_id) REFERENCES jobs (job_id)
        ON DELETE CASCADE          -- deleting a job deletes its applications
        ON UPDATE CASCADE,
    CONSTRAINT chk_interview_data_object
        CHECK (interview_data IS NULL OR JSON_TYPE(interview_data) = 'OBJECT')
) ENGINE = InnoDB;

CREATE INDEX idx_applications_status ON applications (status);
CREATE INDEX idx_applications_date   ON applications (application_date);

-- ---------------------------------------------------------------------
-- contacts: people you know at a company (recruiters, referrals, ...)
-- ---------------------------------------------------------------------
CREATE TABLE contacts (
    contact_id    INT           PRIMARY KEY AUTO_INCREMENT,
    company_id    INT           NOT NULL,
    contact_name  VARCHAR(100)  NOT NULL,
    title         VARCHAR(100),
    email         VARCHAR(100),
    phone         VARCHAR(20),
    linkedin_url  VARCHAR(200),
    notes         TEXT,

    CONSTRAINT fk_contacts_company
        FOREIGN KEY (company_id) REFERENCES companies (company_id)
        ON DELETE CASCADE          -- deleting a company deletes its contacts
        ON UPDATE CASCADE
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- View: one row per application with its job + company details.
-- Handy for the Applications list page and the Dashboard.
-- ---------------------------------------------------------------------
CREATE VIEW application_overview AS
SELECT  a.application_id,
        a.application_date,
        a.status,
        a.resume_version,
        a.cover_letter_sent,
        j.job_id,
        j.job_title,
        j.job_type,
        c.company_id,
        c.company_name
FROM    applications a
JOIN    jobs      j ON j.job_id     = a.job_id
JOIN    companies c ON c.company_id = j.company_id;


-- =====================================================================
-- SAMPLE DATA (fictional) - lets the app show something on first run.
-- Delete this section if you want to start with an empty database.
-- =====================================================================

INSERT INTO companies (company_name, industry, website, city, state, notes) VALUES
('TechCorp',        'Software',      'https://techcorp.example.com',   'Austin',    'TX', 'Fast-growing SaaS company. Great reviews on culture.'),
('DataCo',          'Analytics',     'https://dataco.example.com',     'Chicago',   'IL', 'Hybrid, 3 days in office.'),
('CloudNine Labs',  'Cloud Services','https://cloudnine.example.com',  'Seattle',   'WA', NULL),
('GreenLeaf Health','Healthcare',    'https://greenleaf.example.com',  'Denver',    'CO', 'Mission-driven; met them at the career fair.'),
('Pixel Forge',     'Gaming',        'https://pixelforge.example.com', 'Raleigh',   'NC', 'Small studio, remote-friendly.');

INSERT INTO jobs (company_id, job_title, job_type, salary_min, salary_max, job_url, date_posted, requirements) VALUES
(1, 'Software Developer',        'Full-time',  75000,  95000, 'https://techcorp.example.com/careers/101',  '2026-09-15', '["Python", "SQL", "Flask"]'),
(1, 'Junior QA Engineer',        'Full-time',  60000,  72000, 'https://techcorp.example.com/careers/102',  '2026-09-20', '["Python", "Selenium", "Git"]'),
(2, 'Data Analyst',              'Full-time',  65000,  80000, 'https://dataco.example.com/jobs/da-7',      '2026-09-10', '["Python", "SQL", "Tableau"]'),
(2, 'Data Engineering Intern',   'Internship', 20000,  25000, 'https://dataco.example.com/jobs/int-3',     '2026-10-01', '["SQL", "Python", "Airflow", "Git"]'),
(3, 'Cloud Support Associate',   'Contract',   55000,  70000, 'https://cloudnine.example.com/jobs/csa',    '2026-10-05', '["Linux", "AWS", "Networking"]'),
(4, 'Web Developer',             'Part-time',  30000,  40000, 'https://greenleaf.example.com/careers/web', '2026-10-12', '["HTML", "CSS", "JavaScript", "Flask"]'),
(5, 'Game Tools Programmer',     'Full-time',  70000,  90000, 'https://pixelforge.example.com/jobs/tools', '2026-10-20', '["C++", "Python", "Git"]');

INSERT INTO applications (job_id, application_date, status, resume_version, cover_letter_sent, interview_data) VALUES
(1, '2026-09-18', 'Interview', 'v2-backend', TRUE,
    '{"rounds": [{"date": "2026-10-01", "type": "Phone",     "interviewer": "Sam Rivera", "notes": "Asked about Flask projects"},
                 {"date": "2026-10-09", "type": "Technical", "interviewer": "Priya Shah", "notes": "SQL JOIN questions"}]}'),
(3, '2026-09-12', 'Screening', 'v1-data',    FALSE, NULL),
(4, '2026-10-03', 'Applied',   'v1-data',    TRUE,  NULL),
(5, '2026-10-07', 'Rejected',  'v1-general', FALSE, NULL),
(6, '2026-10-14', 'Offer',     'v2-web',     TRUE,
    '{"rounds": [{"date": "2026-10-21", "type": "Video", "interviewer": "Alex Kim", "notes": "Portfolio review"}],
      "offer": {"salary": 38000, "deadline": "2026-11-20"}}'),
(7, '2026-10-22', 'Withdrawn', 'v1-general', FALSE, NULL);

INSERT INTO contacts (company_id, contact_name, title, email, phone, linkedin_url, notes) VALUES
(1, 'Sam Rivera',  'Technical Recruiter',   'sam.rivera@techcorp.example.com', '512-555-0101', 'https://www.linkedin.com/in/example-sam',   'Very responsive over email.'),
(1, 'Priya Shah',  'Engineering Manager',   'priya.shah@techcorp.example.com', NULL,           NULL,                                      'Ran the technical interview.'),
(2, 'Jordan Lee',  'HR Coordinator',        'jordan.lee@dataco.example.com',   '312-555-0144', NULL,                                      NULL),
(4, 'Alex Kim',    'Lead Web Developer',    'alex.kim@greenleaf.example.com',  '303-555-0190', 'https://www.linkedin.com/in/example-alex',  'Met at the fall career fair.'),
(5, 'Morgan Chen', 'Studio Director',       NULL,                              NULL,           'https://www.linkedin.com/in/example-morgan','Referral from a classmate.');
