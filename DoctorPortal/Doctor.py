#importing libraries
from flask import Flask, render_template, request, jsonify, url_for, g, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import sqlite3
from flask_oidc import OpenIDConnect
from okta import UsersClient
from flask_mail import Message,Mail
from hashlib import md5

#generating 7 days from now.
now = datetime.now()
dates=[]
for x in range(8):
    d = now + timedelta(days=x)
    dates.append(d.strftime("%Y-%m-%d"))
app = Flask(__name__)

#DB configurations
DATABASE = '/Users/avinash/Documents/testing.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////Users/avinash/Documents/testing.db'
app.config['SECRET_KEY'] = 'secret'
db = SQLAlchemy(app)
doctor= db.Table('Doctor', db.metadata, autoload=True, autoload_with=db.engine)
specilization = db.Table('doctor_Specilization', db.metadata, autoload=True, autoload_with=db.engine)
schedule = db.Table('schedule', db.metadata, autoload=True, autoload_with=db.engine)
Appointments = db.Table('Appointments', db.metadata, autoload=True, autoload_with=db.engine)

#okta config
app.config["OIDC_CLIENT_SECRETS"] = "doctor_secrets.json"
app.config["OIDC_COOKIE_SECURE"] = False
app.config["OIDC_CALLBACK_ROUTE"] = "/oidc/callback"
app.config["OIDC_SCOPES"] = ["openid", "email", "profile"]
app.secret_key = "0averylongrandomstring"
app.config["OIDC_ID_TOKEN_COOKIE_NAME"] = "oidc_token"
oidc = OpenIDConnect(app)
okta_client = UsersClient("https://dev-14170676.okta.com","00Td1LFpEQh8AgiAJRAaDVYQ71wjL31y8ZVhZXCqMB")

#gmail config
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
#have removed password replace email and id password with yours for testing, incase you face any issue enable smpt in gmail settings
app.config['MAIL_USERNAME'] = 'avinashramesh2312@gmail.com'
app.config['MAIL_PASSWORD'] = 'India@1234'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
#initialize mail server
mail = Mail(app)

@app.before_request
def before_request():
    if oidc.user_loggedin:
        g.user = okta_client.get_user(oidc.user_getfield("sub"))
    else:
        g.user = None

#index.html
@app.route("/")
def index():
    return render_template("index.html")

#login redirect
@app.route("/login")
@oidc.require_login
def login():
    return redirect(url_for("doctor_dashboard"))

#logout
@app.route("/logout")
@oidc.require_login
def logout():
    info = oidc.user_getinfo(['preferred_username','email','sub'])
    from oauth2client.client import OAuth2Credentials
    raw_id_token = OAuth2Credentials.from_json(oidc.credentials_store[info.get('sub')]).token_response['id_token']
    id_token = str(raw_id_token)
    logout_request = 'https://dev-14170676.okta.com/oauth2/default/v1/logout?id_token_hint={TOKEN}&post_logout_redirect_uri=https://127.0.0.1:8000'.format(TOKEN=id_token)
    oidc.logout()
    return redirect(logout_request)

#cancel appointments
@app.route('/cancel_appointments',methods=['GET','POST'])
def cancel_appointments():
    #cancel_reason = request.form.get['Cancel_Reason']
    date = request.form['get_date']
    reason=request.form['Cancel_Reason']
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="update Appointments set canceled=1,cancellation_reson='{reason}' where doctor_id='{doctor_id}' and start_time='{start_date}'".format(doctor_id=g.user.id,start_date=date,reason=reason)
        cur.execute(query)

        patient_email="select patient_email,patient_name,start_time from Appointments where doctor_id='{doctor_id}' and start_time='{start_date}' and canceled=1".format(doctor_id=g.user.id,start_date=date)
        cur.execute(patient_email)
        rows = cur.fetchall()
        for x in rows:
            patient_email = x['patient_email']
            patient_name = x['patient_name']
        doctor_details ="with temp as( select Appointments.doctor_id, Doctor.first_name|| ' ' || Doctor.last_name as doctor_name, Doctor.specilization  from Appointments  inner join Doctor on Appointments.doctor_id=Doctor.id  where  Appointments.doctor_id='{doctor_id}' and Appointments.start_time='{start_date}' and canceled=1) select doctor_name, doctor_Specilization.specilization from temp inner join doctor_Specilization where temp.specilization=doctor_Specilization.id;".format(doctor_id=g.user.id,start_date=date)
        cur.execute(doctor_details)
        rows1 = cur.fetchall()
        for x in rows1:
            doctor_name = x['doctor_name']
            doctor_specilization=x['specilization']

    msg = Message('Ohh No,Your Booking has been Cancelled!', sender =("PMS Team", 'avinashramesh2312@gmail.com'), recipients=[patient_email])
    msg.html = render_template('cancellation_email.html',patient_name=patient_name,start_date_time=date, doctor_name=doctor_name, doctor_specilization=doctor_specilization, reason=reason)
    mail.send(msg)
    return redirect(url_for('doctor_dashboard'))

#schedule timings code
@app.route("/save_schedule", methods=['GET', 'POST'])
def save_schedule():
    sample_slots=['08:00','09:00','10:00','11:00','12:00','13:00','14:00','15:00','16:00','17:00']
    slots = request.form.getlist('slots')
    dat=request.form['Schedule']
    for start_time in slots:
        start_date_time = datetime.fromisoformat(dat+" "+start_time)
        end_date_time = str(start_date_time+timedelta(hours=1))
        with sqlite3.connect(DATABASE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            query="insert into schedule(doctor_id,start_time,end_time) values('{doctor_id}','{start_date_time}','{end_date_time}')".format(doctor_id=g.user.id,start_date_time=str(start_date_time),end_date_time=end_date_time)
            cur.execute(query)
    flash("Slots added successfully")
    return render_template("schedule_timings.html",dates=dates)

@app.route('/display_slots/<values>')
def display_slots(values):
    date_value = values
    print(date_value)
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="select distinct(time(start_time)) as start_time from schedule where doctor_id='{doctor_id}' and date(start_time)='{start_date}'".format(doctor_id=g.user.id,start_date=str(date_value))
        cur.execute(query)
        rows = cur.fetchall()
        time_slots = [x['start_time'] for x in rows]
    return jsonify( { 'slots': time_slots } )

@app.route("/delete_schedule", methods=['GET', 'POST'])
def delete_schedule():
    delete_slots=request.form.getlist('delete_slots')
    delete_date=request.form['date_drop']
    for start_times in delete_slots:
        start_date_time = datetime.fromisoformat(delete_date + start_times)
        with sqlite3.connect(DATABASE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            query="delete from schedule where doctor_id='{doctor_id}' and start_time='{start_date_time}'".format(doctor_id=g.user.id,start_date_time=str(start_date_time))
            cur.execute(query)
    flash("Delete was done successfully")
    return render_template("schedule_timings.html",dates=dates)

@app.route('/schedule_timings')
def schedule_timing():
    return render_template("schedule_timings.html",dates=dates)

#doctor dashboard code
@app.route("/doctor_dashboard")
@oidc.require_login
def doctor_dashboard():
    #extracting confirmed, cancelled, upcoming appointments for a doctor
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        completed="select Patient_name,patient_message, start_time,date_created from Appointments where doctor_id='{doctor_id}' and canceled=0 and start_time < (SELECT datetime())".format(doctor_id=g.user.id)
        cancelled="select Patient_name,patient_message,start_time,date_created from Appointments where doctor_id='{doctor_id}' and canceled=1".format(doctor_id=g.user.id)
        upcoming="select Patient_name,patient_message,start_time,date_created from Appointments where doctor_id='{doctor_id}' and canceled=0 and start_time > (SELECT datetime())".format(doctor_id=g.user.id)
        cur.execute(completed)
        rows = cur.fetchall()
        completed_appointments = rows
        cur.execute(cancelled)
        rows1 = cur.fetchall()
        cancelled_appointments = rows1
        cur.execute(upcoming)
        rows2 = cur.fetchall()
        upcoming_appointments = rows2
    return render_template("doctor_dashboard.html",completed_appointments=completed_appointments,cancelled_appointments=cancelled_appointments,upcoming_appointments=upcoming_appointments)

#contact us
@app.route("/contact")
def contact():
    return render_template("contact.html")

#contact us form
@app.route("/contact_form_submit", methods=['GET','POST'])
def contact_form_submit():
    name=request.form['name']
    email=request.form['email']
    subject=request.form['subject']
    phone=request.form['phone']
    message=request.form['message']
    msg = Message('Your query has been received!', sender =("PMS", 'avinashramesh2312@gmail.com'), recipients=[email])
    msg.body ="Thank You for contacting Us, Our Support Team is looking into your Query, We will get back to you within 3-5 working days"
    mail.send(msg)
    flash("Your Query has been Submitted")
    return render_template("contact.html")

@app.route("/doctor_profile")
def doctor_profile():
    user_email= g.user.profile.email
    digest = md5(user_email.lower().encode('utf-8')).hexdigest()
    image_url='https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(digest, 256)
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="SELECT * from Doctor where id='{}'".format(g.user.id)
        cur.execute(query)
        rows = cur.fetchall()
        for x in rows:
            first_name=x[1]
            last_name=x[2]
            specilization=x[3]
            age=x[4]
            phone_number=x[5]
            experience=x[6]
    completed=''
    cancelled=''
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        completed_query="select count(id) from Appointments where doctor_id='{doctor_id}' and canceled=0".format(doctor_id=g.user.id)
        cur.execute(completed_query)
        rows1 = cur.fetchall()
        for x in rows1:
            completed=x[0]
        cancelled_query="select count(id) from Appointments where doctor_id='{doctor_id}' and canceled=1".format(doctor_id=g.user.id)
        cur.execute(cancelled_query)
        rows2 = cur.fetchall()
        for x in rows2:
            cancelled=x[0]

        doctor_specilization="select specilization from doctor_Specilization where id='{specilization}'".format(specilization=specilization)
        cur.execute(doctor_specilization)
        rows3 = cur.fetchall()
        for x in rows3:
           doctor_specialization= x['specilization']

    return render_template('doctor_profile.html',first_name=first_name,last_name=last_name,completed=completed,cancelled=cancelled,image_url=image_url,age=age,doctor_specilization=doctor_specialization,experience=experience,phone_number=phone_number)

#update profile
@app.route('/update_profile',methods=['GET','POST'])
def update_profile():
        first_name=request.form['first_name']
        last_name=request.form['last_name']
        phone_number=request.form['phone']
        age=request.form['age']
        experience=request.form['experience']
        with sqlite3.connect(DATABASE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            query="UPDATE Doctor SET first_name='{first_name}',last_name='{last_name}',phone_number='{phone_number}',age='{age}',Experience={experience} where id='{doctor_id}'".format(doctor_id=g.user.id,first_name=first_name,last_name=last_name,phone_number=phone_number,age=age,experience=experience)
            cur.execute(query)
        return redirect(url_for('doctor_profile'))

#main function, run the app
if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=True, ssl_context='adhoc',port=8000)
