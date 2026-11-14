-- =====================================================================
-- Job Application Tracker - Database Schema
-- ---------------------------------------------------------------------

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
-- contacts: people you know at a company 
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

