from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from datetime import date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'placepro_secret_2026'

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Karthik@09092005',
    'database': 'placement_db'
}

# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# =========================================================
# AUTH DECORATORS
# =========================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Access denied.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def recruiter_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'recruiter':
            flash('Access denied.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Access denied.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# =========================================================
# HOME
# =========================================================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['role'] == 'student':
        return redirect(url_for('student_dashboard'))

    if session['role'] == 'recruiter':
        return redirect(url_for('recruiter_dashboard'))

    if session['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))

    return redirect(url_for('login'))

# =========================================================
# LOGIN
# =========================================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        try:
            conn = get_db()
            cur = conn.cursor(dictionary=True)

            # ================= STUDENT LOGIN =================

            if role == 'student':

                cur.execute("""
                    SELECT * FROM Student
                    WHERE email=%s AND phone=%s
                """, (email, password))

                user = cur.fetchone()

                if user:
                    session['user_id'] = user['student_id']
                    session['name'] = user['name']
                    session['role'] = 'student'
                    session['dept'] = user['department']
                    session['cgpa'] = float(user['cgpa'])

                    flash('Login successful!', 'success')

                    cur.close()
                    conn.close()

                    return redirect(url_for('student_dashboard'))

            # ================= RECRUITER LOGIN =================

            elif role == 'recruiter':

                cur.execute("""
                    SELECT r.*, c.company_name
                    FROM Recruiter r
                    JOIN Company c ON r.company_id = c.company_id
                    WHERE r.email=%s AND r.phone=%s
                """, (email, password))

                user = cur.fetchone()

                if user:
                    session['user_id'] = user['recruiter_id']
                    session['name'] = user['recruiter_name']
                    session['role'] = 'recruiter'
                    session['company_id'] = user['company_id']
                    session['company_name'] = user['company_name']

                    flash('Recruiter login successful!', 'success')

                    cur.close()
                    conn.close()

                    return redirect(url_for('recruiter_dashboard'))

            # ================= ADMIN LOGIN =================

            elif role == 'admin':

                if email == 'admin@placepro.com' and password == 'admin123':

                    session['user_id'] = 0
                    session['name'] = 'Admin'
                    session['role'] = 'admin'

                    return redirect(url_for('admin_dashboard'))

            flash('Invalid credentials.', 'error')

            cur.close()
            conn.close()

        except Exception as e:
            print("LOGIN ERROR:", repr(e))
            flash(f'ERROR: {repr(e)}', 'error')

    return render_template('login.html')

# =========================================================
# STUDENT REGISTER
# =========================================================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form.get('name')
        dept = request.form.get('department')
        cgpa = request.form.get('cgpa')
        email = request.form.get('email')
        phone = request.form.get('phone')
        skills = request.form.getlist('skills')

        try:
            conn = get_db()
            cur = conn.cursor(dictionary=True)

            cur.execute("""
                SELECT * FROM Student
                WHERE email=%s
            """, (email,))

            existing = cur.fetchone()

            if existing:
                flash('Email already exists.', 'error')
                return redirect(url_for('register'))

            # ================= INSERT STUDENT =================

            cur.execute("""
                INSERT INTO Student
                (name, department, cgpa, email, phone)
                VALUES (%s,%s,%s,%s,%s)
            """, (name, dept, cgpa, email, phone))

            sid = cur.lastrowid

            # ================= INSERT SKILLS =================

            for skill_id in skills:

                cur.execute("""
                    INSERT INTO Student_Skill
                    (student_id, skill_id, proficiency_level)
                    VALUES (%s,%s,%s)
                """, (sid, skill_id, 'Intermediate'))

            conn.commit()

            flash('Registration successful!', 'success')

            session['user_id'] = sid
            session['name'] = name
            session['role'] = 'student'
            session['dept'] = dept
            session['cgpa'] = float(cgpa)

            cur.close()
            conn.close()

            return redirect(url_for('student_dashboard'))

        except Exception as e:
            conn.rollback()
            print("REGISTER ERROR:", repr(e))
            flash(f'ERROR: {repr(e)}', 'error')

    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM Skill")

        skills = cur.fetchall()

        cur.close()
        conn.close()

    except:
        skills = []

    return render_template('register.html', skills=skills)

# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route('/student/dashboard')
@login_required
@student_required
def student_dashboard():

    sid = session['user_id']
    search = request.args.get('q', '').strip()
    job_type = request.args.get('type', '').strip()
    company = request.args.get('company', '').strip()
    min_package = request.args.get('min_package', '').strip()
    sort = request.args.get('sort', 'deadline').strip()

    sort_map = {
        'deadline': 'j.deadline ASC',
        'package': 'j.package DESC',
        'match': 'matched_skills DESC, j.deadline ASC'
    }
    order_by = sort_map.get(sort, sort_map['deadline'])

    filter_clauses = []
    filter_params = []

    if search:
        filter_clauses.append("j.role LIKE %s")
        filter_params.append(f"%{search}%")

    if job_type:
        filter_clauses.append("j.job_type = %s")
        filter_params.append(job_type)

    if company:
        filter_clauses.append("c.company_name = %s")
        filter_params.append(company)

    min_pkg_val = None
    if min_package:
        try:
            min_pkg_val = float(min_package)
        except ValueError:
            min_pkg_val = None

    if min_pkg_val is not None:
        filter_clauses.append("j.package >= %s")
        filter_params.append(min_pkg_val)

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT COUNT(*) AS total
            FROM Application
            WHERE student_id=%s
        """, (sid,))

        total_applied = cur.fetchone()['total']

        filter_sql = ""
        if filter_clauses:
            filter_sql = " AND " + " AND ".join(filter_clauses)

        cur.execute(f"""
            SELECT j.*, c.company_name,
                   COUNT(DISTINCT js.skill_id) AS required_skills,
                   COUNT(DISTINCT CASE WHEN ss.skill_id IS NOT NULL THEN js.skill_id END) AS matched_skills,
                   GROUP_CONCAT(DISTINCT sk.skill_name ORDER BY sk.skill_name SEPARATOR ',') AS required_skill_names,
                   GROUP_CONCAT(DISTINCT CASE WHEN ss.skill_id IS NOT NULL THEN sk.skill_name END
                                ORDER BY sk.skill_name SEPARATOR ',') AS matched_skill_names,
                   COUNT(DISTINCT a.application_id) AS applicant_count,
                   (
                       SELECT COUNT(*)
                       FROM Application a2
                       JOIN Job j2 ON a2.job_id = j2.job_id
                       WHERE j2.company_id = j.company_id
                   ) AS company_app_count,
                   (
                       SELECT COUNT(*)
                       FROM Result r
                       JOIN Interview i ON r.interview_id = i.interview_id
                       JOIN Application a3 ON i.application_id = a3.application_id
                       JOIN Job j3 ON a3.job_id = j3.job_id
                       WHERE j3.company_id = j.company_id
                         AND r.result_status = 'Selected'
                   ) AS company_selected_count
            FROM Job j
            JOIN Company c ON j.company_id = c.company_id
            LEFT JOIN Job_Skill js ON j.job_id = js.job_id
            LEFT JOIN Skill sk ON js.skill_id = sk.skill_id
            LEFT JOIN Student_Skill ss
                   ON ss.skill_id = js.skill_id
                  AND ss.student_id = %s
            LEFT JOIN Application a ON j.job_id = a.job_id
            WHERE j.job_id NOT IN (
                SELECT job_id FROM Application
                WHERE student_id=%s
            )
            AND j.eligibility_cgpa <= %s
            {filter_sql}
            GROUP BY j.job_id
            ORDER BY {order_by}
        """, (sid, sid, session['cgpa'], *filter_params))

        available_jobs = cur.fetchall()

        if available_jobs:
            max_applicants = max((j.get('applicant_count') or 0) for j in available_jobs) or 1
        else:
            max_applicants = 1

        today_date = date.today()

        for j in available_jobs:
            required = j.get('required_skills') or 0
            matched = j.get('matched_skills') or 0
            skill_score = matched / required if required > 0 else 1.0

            elig_cgpa = float(j.get('eligibility_cgpa') or 0)
            cgpa_gap = (float(session['cgpa']) - elig_cgpa)
            cgpa_score = min(1.0, max(0.0, (cgpa_gap / 2.0) + 0.5))

            applicant_count = j.get('applicant_count') or 0
            competition_score = 1.0 - min(1.0, applicant_count / max_applicants)

            company_apps = j.get('company_app_count') or 0
            company_selected = j.get('company_selected_count') or 0
            company_rate = (company_selected / company_apps) if company_apps > 0 else 0.5

            deadline = j.get('deadline')
            if deadline:
                days_left = (deadline - today_date).days
            else:
                days_left = 0
            recency_score = min(1.0, max(0.0, days_left / 30.0))

            score = (
                0.35 * skill_score +
                0.20 * cgpa_score +
                0.15 * competition_score +
                0.20 * company_rate +
                0.10 * recency_score
            )

            j['placement_score'] = int(round(score * 100))

            required_list = [s for s in (j.get('required_skill_names') or '').split(',') if s]
            matched_list = [s for s in (j.get('matched_skill_names') or '').split(',') if s]
            missing = [s for s in required_list if s not in matched_list]
            j['missing_skills'] = missing

        cur.execute("""
            SELECT a.application_id,
                   a.application_date,
                   a.status,
                   j.role,
                   j.job_type,
                   j.package,
                   c.company_name,
                   r.result_status,
                                     r.offered_package,
                                     (
                                             SELECT COUNT(*)
                                             FROM Application_Message m
                                             WHERE m.application_id = a.application_id
                                                 AND m.sender_role = 'recruiter'
                                                 AND m.read_at IS NULL
                                     ) AS unread_count
            FROM Application a
            JOIN Job j ON a.job_id = j.job_id
            JOIN Company c ON j.company_id = c.company_id
            LEFT JOIN Interview i ON a.application_id = i.application_id
            LEFT JOIN Result r ON i.interview_id = r.interview_id
            WHERE a.student_id=%s
            ORDER BY a.application_date DESC
        """, (sid,))

        my_apps = cur.fetchall()

        cur.execute("""
            SELECT sk.skill_name
            FROM Student_Skill ss
            JOIN Skill sk ON ss.skill_id = sk.skill_id
            WHERE ss.student_id=%s
            ORDER BY sk.skill_name
        """, (sid,))

        my_skills = cur.fetchall()

        cur.execute("""
            SELECT DISTINCT c.company_name
            FROM Job j
            JOIN Company c ON j.company_id = c.company_id
            ORDER BY c.company_name
        """)

        company_options = [r['company_name'] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT job_type
            FROM Job
            WHERE job_type IS NOT NULL AND job_type <> ''
            ORDER BY job_type
        """)

        job_type_options = [r['job_type'] for r in cur.fetchall()]

        cur.execute("""
            SELECT COUNT(*) AS total
            FROM Result r
            JOIN Interview i ON r.interview_id = i.interview_id
            JOIN Application a ON i.application_id = a.application_id
            WHERE a.student_id=%s
              AND r.result_status='Selected'
        """, (sid,))

        total_selected = cur.fetchone()['total']

        cur.close()
        conn.close()

        return render_template(
            'student_dashboard.html',
            total_applied=total_applied,
            available_jobs=available_jobs,
            my_apps=my_apps,
            total_selected=total_selected,
            my_skills=my_skills,
            company_options=company_options,
            job_type_options=job_type_options,
            filters={
                'q': search,
                'type': job_type,
                'company': company,
                'min_package': min_package,
                'sort': sort
            },
            today=date.today().isoformat()
        )

    except Exception as e:
        print("DASHBOARD ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return render_template(
            'student_dashboard.html',
            total_applied=0,
            available_jobs=[],
            my_apps=[],
            total_selected=0,
            my_skills=[],
            company_options=[],
            job_type_options=[],
            filters={},
            today=date.today().isoformat()
        )

# =========================================================
# APPLY JOB
# =========================================================

@app.route('/student/apply/<int:job_id>', methods=['GET', 'POST'])
@login_required
@student_required
def student_apply(job_id):

    sid = session['user_id']

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT j.*, c.company_name
            FROM Job j
            JOIN Company c ON j.company_id = c.company_id
            WHERE j.job_id=%s
        """, (job_id,))

        job = cur.fetchone()

        if request.method == 'POST':

            application_date = request.form.get('application_date')

            cur.execute("""
                SELECT * FROM Application
                WHERE student_id=%s AND job_id=%s
            """, (sid, job_id))

            existing = cur.fetchone()

            if existing:
                flash('Already applied.', 'error')
                return redirect(url_for('student_dashboard'))

            cur.execute("""
                INSERT INTO Application
                (application_date, status, student_id, job_id)
                VALUES (%s,%s,%s,%s)
            """, (
                application_date or date.today(),
                'Applied',
                sid,
                job_id
            ))

            conn.commit()

            flash('Applied successfully!', 'success')

            cur.close()
            conn.close()

            return redirect(url_for('student_dashboard'))

        cur.execute("""
            SELECT sk.skill_name,
                   CASE WHEN ss.student_id IS NULL THEN 0 ELSE 1 END AS has_skill
            FROM Job_Skill js
            JOIN Skill sk ON js.skill_id = sk.skill_id
            LEFT JOIN Student_Skill ss
                   ON ss.skill_id = js.skill_id
                  AND ss.student_id = %s
            WHERE js.job_id=%s
            ORDER BY sk.skill_name
        """, (sid, job_id))

        skill_match = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'apply.html',
            job=job,
            today=date.today().isoformat(),
            skill_match=skill_match
        )

    except Exception as e:
        conn.rollback()
        print("APPLY ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return redirect(url_for('student_dashboard'))

# =========================================================
# RECRUITER DASHBOARD
# =========================================================

@app.route('/recruiter/dashboard')
@login_required
@recruiter_required
def recruiter_dashboard():

    cid = session['company_id']

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT j.*, COUNT(a.application_id) AS applicant_count
            FROM Job j
            LEFT JOIN Application a
            ON j.job_id = a.job_id
            WHERE j.company_id=%s
            GROUP BY j.job_id
        """, (cid,))

        jobs = cur.fetchall()

        cur.execute("""
            SELECT COUNT(a.application_id) AS total
            FROM Application a
            JOIN Job j ON a.job_id = j.job_id
            WHERE j.company_id=%s
        """, (cid,))

        total_applicants = cur.fetchone()['total']

        cur.close()
        conn.close()

        return render_template(
            'recruiter_dashboard.html',
            jobs=jobs,
            total_jobs=len(jobs),
            total_applicants=total_applicants
        )

    except Exception as e:
        print("RECRUITER ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return render_template(
            'recruiter_dashboard.html',
            jobs=[],
            total_jobs=0,
            total_applicants=0
        )

# =========================================================
# STUDENT MESSAGES
# =========================================================

@app.route('/student/application/<int:app_id>/messages', methods=['GET', 'POST'])
@login_required
@student_required
def student_messages(app_id):

    sid = session['user_id']

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT a.application_id, j.role, c.company_name
            FROM Application a
            JOIN Job j ON a.job_id = j.job_id
            JOIN Company c ON j.company_id = c.company_id
            WHERE a.application_id=%s AND a.student_id=%s
        """, (app_id, sid))

        app_row = cur.fetchone()

        if not app_row:
            flash('Application not found.', 'error')
            return redirect(url_for('student_dashboard'))

        if request.method == 'POST':
            message = request.form.get('message', '').strip()

            if message:
                cur.execute("""
                    INSERT INTO Application_Message
                    (application_id, sender_role, sender_id, message)
                    VALUES (%s, %s, %s, %s)
                """, (app_id, 'student', sid, message))

                conn.commit()
                flash('Message sent.', 'success')

            return redirect(url_for('student_messages', app_id=app_id))

        cur.execute("""
            UPDATE Application_Message
            SET read_at = CURRENT_TIMESTAMP
            WHERE application_id=%s
              AND sender_role='recruiter'
              AND read_at IS NULL
        """, (app_id,))

        conn.commit()

        cur.execute("""
            SELECT sender_role, sender_id, message, sent_at
            FROM Application_Message
            WHERE application_id=%s
            ORDER BY sent_at ASC
        """, (app_id,))

        messages = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'messages.html',
            thread=app_row,
            messages=messages,
            role='student'
        )

    except Exception as e:
        print("STUDENT MESSAGES ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return redirect(url_for('student_dashboard'))

# =========================================================
# RECRUITER MESSAGES
# =========================================================

@app.route('/recruiter/application/<int:app_id>/messages', methods=['GET', 'POST'])
@login_required
@recruiter_required
def recruiter_messages(app_id):

    cid = session['company_id']
    rid = session['user_id']

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT a.application_id, j.role, c.company_name, s.name AS student_name
            FROM Application a
            JOIN Job j ON a.job_id = j.job_id
            JOIN Company c ON j.company_id = c.company_id
            JOIN Student s ON a.student_id = s.student_id
            WHERE a.application_id=%s AND j.company_id=%s
        """, (app_id, cid))

        app_row = cur.fetchone()

        if not app_row:
            flash('Application not found.', 'error')
            return redirect(url_for('recruiter_dashboard'))

        if request.method == 'POST':
            message = request.form.get('message', '').strip()

            if message:
                cur.execute("""
                    INSERT INTO Application_Message
                    (application_id, sender_role, sender_id, message)
                    VALUES (%s, %s, %s, %s)
                """, (app_id, 'recruiter', rid, message))

                conn.commit()
                flash('Message sent.', 'success')

            return redirect(url_for('recruiter_messages', app_id=app_id))

        cur.execute("""
            UPDATE Application_Message
            SET read_at = CURRENT_TIMESTAMP
            WHERE application_id=%s
              AND sender_role='student'
              AND read_at IS NULL
        """, (app_id,))

        conn.commit()

        cur.execute("""
            SELECT sender_role, sender_id, message, sent_at
            FROM Application_Message
            WHERE application_id=%s
            ORDER BY sent_at ASC
        """, (app_id,))

        messages = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'messages.html',
            thread=app_row,
            messages=messages,
            role='recruiter'
        )

    except Exception as e:
        print("RECRUITER MESSAGES ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return redirect(url_for('recruiter_dashboard'))

# =========================================================
# RECRUITER APPLICANTS
# =========================================================

@app.route('/recruiter/job/<int:job_id>/applicants')
@login_required
@recruiter_required
def view_applicants(job_id):

    cid = session['company_id']
    status_filter = request.args.get('status', '').strip()

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT j.*, c.company_name
            FROM Job j
            JOIN Company c ON j.company_id = c.company_id
            WHERE j.job_id=%s AND j.company_id=%s
        """, (job_id, cid))

        job = cur.fetchone()

        if not job:
            flash('Job not found.', 'error')
            return redirect(url_for('recruiter_dashboard'))

        query = """
            SELECT a.application_id,
                   a.application_date,
                   a.status,
                   s.name,
                   s.department,
                   s.cgpa,
                   s.email,
                   r.result_status,
                   (
                       SELECT COUNT(*)
                       FROM Application_Message m
                       WHERE m.application_id = a.application_id
                         AND m.sender_role = 'student'
                         AND m.read_at IS NULL
                   ) AS unread_count
            FROM Application a
            JOIN Student s ON a.student_id = s.student_id
            LEFT JOIN Interview i ON a.application_id = i.application_id
            LEFT JOIN Result r ON i.interview_id = r.interview_id
            WHERE a.job_id=%s
        """

        params = [job_id]

        if status_filter:
            query += " AND a.status=%s"
            params.append(status_filter)

        query += " ORDER BY a.application_date DESC"

        cur.execute(query, params)

        applicants = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'applicants.html',
            job=job,
            applicants=applicants,
            status_filter=status_filter,
            job_id=job_id
        )

    except Exception as e:
        print("APPLICANTS ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return redirect(url_for('recruiter_dashboard'))

# =========================================================
# UPDATE APPLICATION STATUS
# =========================================================

@app.route('/recruiter/application/<int:app_id>/status', methods=['POST'])
@login_required
@recruiter_required
def update_application(app_id):

    cid = session['company_id']
    job_id = request.form.get('job_id', type=int)
    status = request.form.get('status', '').strip()

    allowed = ['Applied', 'Under Review', 'Shortlisted', 'On Hold', 'Selected', 'Rejected']
    if status not in allowed:
        flash('Invalid status.', 'error')
        return redirect(url_for('view_applicants', job_id=job_id))

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT a.application_id
            FROM Application a
            JOIN Job j ON a.job_id = j.job_id
            WHERE a.application_id=%s AND a.job_id=%s AND j.company_id=%s
        """, (app_id, job_id, cid))

        if not cur.fetchone():
            flash('Application not found.', 'error')
            return redirect(url_for('recruiter_dashboard'))

        cur.execute("""
            UPDATE Application
            SET status=%s
            WHERE application_id=%s
        """, (status, app_id))

        conn.commit()

        flash('Application updated.', 'success')

        cur.close()
        conn.close()

        return redirect(url_for('view_applicants', job_id=job_id))

    except Exception as e:
        conn.rollback()
        print("UPDATE APPLICATION ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return redirect(url_for('view_applicants', job_id=job_id))

# =========================================================
# DELETE JOB
# =========================================================

@app.route('/recruiter/job/<int:job_id>/delete')
@login_required
@recruiter_required
def delete_job(job_id):

    cid = session['company_id']

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM Job
            WHERE job_id=%s AND company_id=%s
        """, (job_id, cid))

        if cur.rowcount == 0:
            flash('Job not found.', 'error')
        else:
            flash('Job deleted.', 'success')

        conn.commit()

        cur.close()
        conn.close()

        return redirect(url_for('recruiter_dashboard'))

    except Exception as e:
        conn.rollback()
        print("DELETE JOB ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return redirect(url_for('recruiter_dashboard'))

# =========================================================
# ADD JOB
# =========================================================

@app.route('/recruiter/job/add', methods=['GET', 'POST'])
@login_required
@recruiter_required
def add_job():

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        if request.method == 'POST':

            role = request.form.get('role')
            package = request.form.get('package')
            egpa = request.form.get('eligibility_cgpa')
            jtype = request.form.get('job_type')
            deadline = request.form.get('deadline')
            skills = request.form.getlist('skills')

            cur.execute("""
                INSERT INTO Job
                (role, package, eligibility_cgpa, job_type, deadline, company_id)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                role,
                package,
                egpa,
                jtype,
                deadline,
                session['company_id']
            ))

            jid = cur.lastrowid

            for skill_id in skills:

                cur.execute("""
                    INSERT INTO Job_Skill
                    (job_id, skill_id, required_level)
                    VALUES (%s,%s,%s)
                """, (
                    jid,
                    skill_id,
                    'Intermediate'
                ))

            conn.commit()

            flash('Job posted successfully!', 'success')

            cur.close()
            conn.close()

            return redirect(url_for('recruiter_dashboard'))

        cur.execute("SELECT * FROM Skill")

        skills = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'add_job.html',
            skills=skills
        )

    except Exception as e:
        conn.rollback()
        print("ADD JOB ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return redirect(url_for('recruiter_dashboard'))

# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT COUNT(*) AS t FROM Student")
        total_students = cur.fetchone()['t']

        cur.execute("SELECT COUNT(*) AS t FROM Job")
        total_jobs = cur.fetchone()['t']

        cur.execute("SELECT COUNT(*) AS t FROM Application")
        total_apps = cur.fetchone()['t']

        cur.execute("SELECT COUNT(*) AS t FROM Company")
        total_companies = cur.fetchone()['t']

        cur.execute("""
            SELECT DATE_FORMAT(application_date, '%Y-%m') AS ym, COUNT(*) AS cnt
            FROM Application
            WHERE application_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY ym
            ORDER BY ym
        """)

        monthly_apps = cur.fetchall()

        cur.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM Application
            GROUP BY status
            ORDER BY cnt DESC
        """)

        status_dist = cur.fetchall()

        cur.execute("""
            SELECT j.role, c.company_name, COUNT(a.application_id) AS app_count
            FROM Job j
            JOIN Company c ON j.company_id = c.company_id
            LEFT JOIN Application a ON j.job_id = a.job_id
            GROUP BY j.job_id
            ORDER BY app_count DESC, j.job_id DESC
            LIMIT 5
        """)

        top_jobs = cur.fetchall()

        cur.execute("""
            SELECT s.department,
                   COUNT(DISTINCT s.student_id) AS students,
                   COUNT(a.application_id) AS applications
            FROM Student s
            LEFT JOIN Application a ON s.student_id = a.student_id
            GROUP BY s.department
            ORDER BY students DESC
        """)

        dept_stats = cur.fetchall()

        cur.execute("""
            SELECT c.company_name,
                   COUNT(DISTINCT j.job_id) AS jobs,
                   COUNT(a.application_id) AS applicants
            FROM Company c
            LEFT JOIN Job j ON c.company_id = j.company_id
            LEFT JOIN Application a ON j.job_id = a.job_id
            GROUP BY c.company_id
            ORDER BY applicants DESC
        """)

        company_stats = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'admin_dashboard.html',
            total_students=total_students,
            total_jobs=total_jobs,
            total_apps=total_apps,
            total_companies=total_companies,
            top_jobs=top_jobs,
            status_dist=status_dist,
            dept_stats=dept_stats,
            company_stats=company_stats,
            monthly_apps=monthly_apps
        )

    except Exception as e:
        print("ADMIN ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return render_template(
            'admin_dashboard.html',
            total_students=0,
            total_jobs=0,
            total_apps=0,
            total_companies=0,
            top_jobs=[],
            status_dist=[],
            dept_stats=[],
            company_stats=[],
            monthly_apps=[]
        )

# =========================================================
# ADMIN STUDENTS
# =========================================================

@app.route('/admin/students')
@login_required
@admin_required
def admin_students():

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT s.*, COUNT(a.application_id) AS app_count
            FROM Student s
            LEFT JOIN Application a
                ON s.student_id = a.student_id
            GROUP BY s.student_id
            ORDER BY s.student_id
        """)

        students = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'admin_students.html',
            students=students
        )

    except Exception as e:
        print("ADMIN STUDENTS ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return render_template(
            'admin_students.html',
            students=[]
        )

# =========================================================
# ADMIN JOBS
# =========================================================

@app.route('/admin/jobs')
@login_required
@admin_required
def admin_jobs():

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT j.*, c.company_name, COUNT(a.application_id) AS app_count
            FROM Job j
            JOIN Company c ON j.company_id = c.company_id
            LEFT JOIN Application a ON j.job_id = a.job_id
            GROUP BY j.job_id
            ORDER BY j.job_id DESC
        """)

        jobs = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'admin_jobs.html',
            jobs=jobs
        )

    except Exception as e:
        print("ADMIN JOBS ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return render_template(
            'admin_jobs.html',
            jobs=[]
        )

# =========================================================
# ADMIN APPLICATIONS
# =========================================================

@app.route('/admin/applications')
@login_required
@admin_required
def admin_applications():

    try:

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT a.application_id,
                   a.application_date,
                   a.status,
                   s.name AS student_name,
                   s.department,
                   s.cgpa,
                   j.role,
                   j.package,
                   c.company_name
            FROM Application a
            JOIN Student s ON a.student_id = s.student_id
            JOIN Job j ON a.job_id = j.job_id
            JOIN Company c ON j.company_id = c.company_id
            ORDER BY a.application_date DESC, a.application_id DESC
        """)

        applications = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'admin_applications.html',
            applications=applications
        )

    except Exception as e:
        print("ADMIN APPLICATIONS ERROR:", repr(e))
        flash(f'ERROR: {repr(e)}', 'error')

        return render_template(
            'admin_applications.html',
            applications=[]
        )

# =========================================================
# LOGOUT
# =========================================================

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('login'))

# =========================================================
# RUN
# =========================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)