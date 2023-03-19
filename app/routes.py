import time
from flask import Response, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import login_user, current_user, login_required, logout_user
from app import app, db, bcrypt
from app.models import Answer, Question, Student, Group, Meeting, StudentMeeting, Teacher, GroupMeeting, User, StudentGroup
from datetime import datetime

from random import randint
from faker import Faker


@app.errorhandler(404)
def page_not_found(e):
    # return custom 404 page when 404 error occures
    return render_template('404.html'), 404


@app.route("/admin")
@login_required
def admin():
    groups = db.session.query(Group).all()
    group_list = []
    for group in groups:
        print(group.name)
        group_list.append({
            "name": group.name,
            "id": group.id
        })
    return render_template("admin.html", group_list=group_list)


@app.route("/admin/create-teacher", methods=['POST'])
def create_teacher_form():
    firstname = request.form["admin-teacher-firstname"]
    lastname = request.form["admin-teacher-lastname"]
    email = request.form["admin-teacher-email"]
    admin = False
    if request.form.getlist("admin-teacher-admin-true"):
        admin = True
    teacher = Teacher(first_name=firstname,
                      last_name=lastname, email=email, admin=admin)
    db.session.add(teacher)
    db.session.commit()
    return redirect(url_for("admin"))


@app.route("/admin/create-student", methods=['POST'])
def create_student_form():
    student_number = request.form["admin-student-number"]
    firstname = request.form["admin-student-firstname"]
    lastname = request.form["admin-student-lastname"]
    email = request.form["admin-student-email"]
    student = Student(student_number=student_number, first_name=firstname,
                      last_name=lastname, email=email)
    db.session.add(student)
    db.session.commit()
    group = request.form["admin-student-group"]
    student_group = StudentGroup(student_id=student.id, group_id=group)
    db.session.add(student_group)
    db.session.commit()
    return redirect(url_for("admin"))


@app.route("/admin/create-group", methods=['POST'])
def create_group_form():
    name_group = request.form["admin-group-id"]
    start_date = request.form["admin-group-start"]
    end_date = request.form["admin-group-end"]
    formatted_startdate = datetime.strptime(start_date, "%Y-%m-%d")
    formatted_enddate = datetime.strptime(end_date, "%Y-%m-%d")
    group = Group(name=name_group, start_date=formatted_startdate,
                  end_date=formatted_enddate)
    db.session.add(group)
    db.session.commit()
    return redirect(url_for("admin"))


@app.route("/home")
@login_required
def home():
    meetings = Meeting.query.filter(
        Meeting.date >= datetime.today().date()).order_by(Meeting.date).limit(5).all()
    return render_template('index.html', meetings=meetings)


@app.route("/timer/start")
@login_required
def start_timer():
    # UPDATE: set timer length through form where user can choose the length
    # UPDATE: set time of starting in db ( this time can later be used to check if a student can join a meeting or if they where to late)
    session['timer_length'] = 30
    session['start_time'] = time.time()
    return str(session['start_time'])


@app.route("/timer/update")
@login_required
def update_timer():
    print('start', session['start_time'])
    print('current', time.time())

    # calculate time left on timer
    session['time_left'] = round(
        session['timer_length'] - (time.time() - session['start_time']))
    mins, secs = divmod(session['time_left'], 60)
    # format time to mm:ss
    session['timer_text'] = '{:02d}:{:02d}'.format(mins, secs)

    # UPDATE: if timer == 0 update meeting status in db

    # check if time is less then 0, then set the timer to 0
    if (session['time_left'] < 0):
        session['time_left'] = 0
        mins, secs = divmod(session['time_left'], 60)
        session['timer_text'] = '{:02d}:{:02d}'.format(mins, secs)

    return jsonify({"result": {"timetext": session['timer_text'], "time": session['time_left']}})


@app.route("/rooster")
@login_required
def rooster():
    # current logged in student id
    # print(current_user.student[0].id)

    return render_template('rooster.html')


@app.route("/wachtwoord/nieuw/<code>", methods=("GET", "POST"))
def set_password(code=None):
    if request.method == "GET":

        # Check if password code exists
        exists = db.session.query(
            User.query.filter_by(password_code=code).exists()
        ).scalar()
        if exists:
            return render_template('set_password.html', code=code)
        else:
            abort(404)

    elif request.method == "POST":
        # form validation
        print(request.form)
        if (request.form.get('password') == request.form.get('password_confirm')):
            user = User.query.filter_by(password_code=code).first()
            # Update password in db
            user.update_password(request.form.get('password'))
            # Remove password code so password cant be changed again with the same code
            user.remove_password_code()
            login_user(user)
            flash("Je wachtwoord is aangepast!", 'success')
            return redirect(url_for('home'))
        else:
            flash("Wachtwoord velden komen niet overeen!", 'error')
            return render_template('set_password.html', code=code)


@app.route("/aanwezigheid/<code>")
@login_required
def presence(code=None):
    # check if code exists else throw 404 not found error
    exists = db.session.query(
        Meeting.query.filter_by(meeting_code=code).exists()
    ).scalar()
    if exists:
        return render_template('presence.html', code=code)
    else:
        abort(404)


@app.route("/meeting/start/<code>")
@login_required
def start_presence(code=None):
    # check if code exists else throw 404 not found error
    exists = db.session.query(
        Meeting.query.filter_by(meeting_code=code).exists()
    ).scalar()
    if exists:
        session['timer_length'] = 30
        session['start_time'] = time.time()

        # update status in db
        meeting = Meeting.query.filter_by(meeting_code=code).first()
        meeting.status = 1
        meeting.checkin_date = datetime.now()
        meeting.present = False
        db.session.commit()

        # UDPATE: loop through all groups added to meeting
        # loop through all students in each group

        # UPDATE: insert all students with presence false
        # student = StudentMeeting(student_id=id, meeting_id=meeting.id, checkin_date=datetime.now(), present=False)

        return redirect(url_for('presence', code=code))
    else:
        abort(404)


@app.route('/aanmelden', methods=("GET", "POST"))
@login_required
def presence_code():
    if request.method == "GET":
        return render_template('code-input.html')
    elif request.method == "POST":
        code = request.form["meeting_code"]
        return redirect(url_for('question', code=code))
        # return redirect(url_for('setpresence', code=code))


@app.route('/aanmelden/<code>')
@login_required
def setpresence(code=None):
    # check if user is a student
    if (current_user.role == 1):
        # logged in student
        id = current_user.student[0].id
    else:
        flash("Je kunt niet meedoen aan deze bijeenkomst", 'error')
        return redirect(url_for("home"))

    exists = db.session.query(
        Meeting.query.filter_by(meeting_code=code).exists()
    ).scalar()
    if exists:
        meeting = Meeting.query.filter_by(meeting_code=code).first()
    else:
        flash("Deze les code bestaat niet", 'error')
        return redirect(url_for('presence_code'))

    # UPDATE: if user logs in then execute below

    student_present = db.session.query(
        StudentMeeting.query.filter_by(
            meeting_id=meeting.id, student_id=id).exists()
    ).scalar()

    print(student_present)
    if student_present:
        # student is already present return to home, with message
        flash("Je was al aangemeld voor deze les", 'error')
        return redirect('/')
    else:
        # add student to meeting
        student = StudentMeeting(
            student_id=id, meeting_id=meeting.id, checkin_date=datetime.now(), present=True)
        db.session.add(student)
        db.session.commit()
        # student is added so return to home, with a message
        flash("Je bent aangemeld in de les!", 'success')
        return redirect('/')


@app.route("/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        next_url = request.args.get("next")
        username = request.form["username"]
        password = request.form["password"]
        user = db.session.query(User).filter(
            User.email == username.lower()).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            if next_url:
               url = next_url[1:]
               return redirect(url_for(url))
            return redirect(url_for("home"))
        else:
            flash("Gebruikersnaam of wachtwoord onjuist. Probeer opnieuw.", 'error')
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/code-input")
@login_required
def code_input():
    return render_template("code-input.html")


@app.route("/les_overzicht/<meeting_code>")
@login_required
def les_overzicht(meeting_code):
    meeting = Meeting.query.filter_by(meeting_code=meeting_code).first()
    question = Question.query.filter_by(meeting_id=meeting.id).first()
    group_meetings = meeting.groups
    group_names = [group_meeting.group.name for group_meeting in group_meetings]
    return render_template("les_overzicht.html", meeting_code=meeting_code, meeting=meeting, question=question, groups=group_names)


@app.route("/overzicht/<id>")
@login_required
def overview_page(id=None):
    student = Student.query.filter_by(user_id=id).first()
    return render_template('overview.html', student=student)


@app.route("/vraag/<code>", methods=["GET", "POST"])
@login_required
def question(code=None):
    meeting = Meeting.query.filter_by(meeting_code=code).first()
    question = Question.query.filter_by(meeting_id=meeting.id).first()
    if request.method == "GET":
        return render_template('question.html', question=question, code=code)
    elif request.method == "POST":
        print(request.form["answer"])
        answer = Answer(text=request.form["answer"], question_id=question.id)
        db.session.add(answer)
        db.session.commit()
        return redirect(url_for('setpresence', code=code))


@app.route("/faker")
def faker():
    fake = Faker()
    for _ in range(5):
        student = Student(first_name=fake.first_name(),
                          last_name=fake.last_name(), email=fake.free_email())
        db.session.add(student)
        db.session.commit()

        teacher = Teacher(first_name=fake.first_name(), last_name=fake.last_name(
        ), email=fake.free_email(), admin=randint(0, 1))
        db.session.add(teacher)
        db.session.commit()

        group = Group(start_date=datetime.now(),
                      end_date=datetime.now(), name=fake.word())
        db.session.add(group)
        db.session.commit()

    return "Data toegevoegd aan de database"


@app.route("/meeting/delete/<id>")
def delete_meeting(id=None):
    Meeting.query.filter_by(id=id).delete()
    db.session.commit()
    flash("meeting verwijderd", "success")
    return redirect(url_for("rooster"))


@app.route("/lessen/zoeken")
def search_meetings():
    return render_template("meetings.html")


@app.route("/studenten/zoeken")
def search_students():
    return render_template("students.html")


@app.route("/klassen/zoeken")
def search_groups():
    return render_template("groups.html")


@app.route("/docenten/zoeken")
def search_teachers():
    return render_template("teachers.html")
