#importing libraries
from flask import Flask, render_template, request, jsonify, url_for, g, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import sqlite3
from flask_oidc import OpenIDConnect
from okta import UsersClient
from flask_mail import Message,Mail
from hashlib import md5

app = Flask(__name__)

#generating 7 days from now.
now = datetime.now()
dates=[]
for x in range(8):
    d = now + timedelta(days=x)
    dates.append(d.strftime("%Y-%m-%d"))

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
app.config["OIDC_CLIENT_SECRETS"] = "client_secrets.json"
app.config["OIDC_COOKIE_SECURE"] = False
app.config["OIDC_CALLBACK_ROUTE"] = "/oidc/callback"
app.config["OIDC_SCOPES"] = ["openid", "email", "profile"]
app.secret_key = "0averylongrandomstring"
app.config["OIDC_ID_TOKEN_COOKIE_NAME"] = "oidc_token"
oidc = OpenIDConnect(app)
okta_client = UsersClient("https://dev-02149256.okta.com","009hEG5Bb1c3hHbrhppgzCCaAefPINuNzQ4ckQRXwk")

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

#dashboard code
@app.route("/dashboard")
@oidc.require_login
def dashboard():
    created_date= str(g.user.created).split(" ")[0]
    today_date= str(datetime.utcnow()).split(" ")[0]
    created_time= str(g.user.created).split(" ")[1].split("+")[0]
    print(created_date)
    if created_date==today_date:
        with sqlite3.connect(DATABASE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            query="SELECT * from Patient where id='{}'".format(g.user.id)
            cur.execute(query)
            rows = cur.fetchall()
            print(len(rows))
            if len(rows)==0:
                query="INSERT INTO Patient(id,patient_name,patient_last_name,patient_mail,phone) values('{0}','{1}','{2}','{3}',{4})".format(g.user.id,g.user.profile.firstName,g.user.profile.lastName,g.user.profile.email,g.user.profile.mobilePhone)
                cur.execute(query)
    #extracting confirmed, cancelled, upcoming appointments for a patient
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        completed="with appt as (select start_time,doctor_id,date_created,canceled from  Appointments where patient_id='{}'),doc as ( select Doctor.first_name|| ' ' || Doctor.last_name as doctor_name, doctor_Specilization.specilization,Doctor.id from Doctor inner join doctor_Specilization on Doctor.specilization=doctor_Specilization.id) select doctor_name,specilization,start_time as appointment_time, date_created as booking_date from appt  inner join doc  on appt.doctor_id=doc.id where canceled=0 and appointment_time < (SELECT datetime());".format(g.user.id)
        cancelled="with appt as (select start_time,doctor_id,date_created,canceled,cancellation_reson  from  Appointments where patient_id='{}'),doc as ( select Doctor.first_name|| ' ' || Doctor.last_name as doctor_name, doctor_Specilization.specilization,Doctor.id from Doctor inner join doctor_Specilization on Doctor.specilization=doctor_Specilization.id) select doctor_name,specilization,start_time as appointment_time, date_created as booking_date,cancellation_reson as cancel_reason from appt  inner join doc on appt.doctor_id=doc.id where canceled=1;".format(g.user.id)
        upcoming="with appt as (select start_time,doctor_id,date_created,canceled from  Appointments where patient_id='{}'),doc as ( select Doctor.first_name|| ' ' || Doctor.last_name as doctor_name, doctor_Specilization.specilization,Doctor.id from Doctor inner join doctor_Specilization on Doctor.specilization=doctor_Specilization.id) select doctor_name,specilization,start_time as appointment_time, date_created as booking_date from appt  inner join doc  on appt.doctor_id=doc.id where canceled=0 and appointment_time > (SELECT datetime());".format(g.user.id)
        cur.execute(completed)
        rows = cur.fetchall()
        completed_appointments = rows
        cur.execute(cancelled)
        rows1 = cur.fetchall()
        cancelled_appointments = rows1
        cur.execute(upcoming)
        rows2 = cur.fetchall()
        upcoming_appointments = rows2
    return render_template("dashboard.html",completed_appointments=completed_appointments,cancelled_appointments=cancelled_appointments,upcoming_appointments=upcoming_appointments)

#login redirect
@app.route("/login")
@oidc.require_login
def login():
    return redirect(url_for("dashboard"))

#logout
@app.route("/logout")
@oidc.require_login
def logout():
    info = oidc.user_getinfo(['preferred_username','email','sub'])
    from oauth2client.client import OAuth2Credentials
    raw_id_token = OAuth2Credentials.from_json(oidc.credentials_store[info.get('sub')]).token_response['id_token']
    id_token = str(raw_id_token)
    logout_request = 'https://dev-02149256.okta.com/oauth2/default/v1/logout?id_token_hint={TOKEN}&post_logout_redirect_uri=https://127.0.0.1:5000'.format(TOKEN=id_token)
    oidc.logout()
    return redirect(logout_request)

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

#profile redirect
@app.route("/profile")
def profile():
    user_email= g.user.profile.email
    digest = md5(user_email.lower().encode('utf-8')).hexdigest()
    image_url='https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(digest, 256)
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="SELECT * from Patient where id='{}'".format(g.user.id)
        cur.execute(query)
        rows = cur.fetchall()
        for x in rows:
            first_name=x[1]
            last_name=x[2]
            email_id=x[3]
            phone=x[4]
            location=x[5]
            insurance=x[6]
            insurance_id=x[7]
            age=x[8]
    completed=''
    cancelled=''
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        completed_query="select count(id) from Appointments where patient_id='{patient_id}' and canceled=0".format(patient_id=g.user.id)
        cur.execute(completed_query)
        rows1 = cur.fetchall()
        for x in rows1:
            completed=x[0]
        cancelled_query="select count(id) from Appointments where patient_id='{patient_id}' and canceled=1".format(patient_id=g.user.id)
        cur.execute(cancelled_query)
        rows2 = cur.fetchall()
        for x in rows2:
            cancelled=x[0]

    return render_template('profile.html',first_name=first_name,last_name=last_name,phone=phone,email_id=email_id,location=location,insurance=insurance,insurance_id=insurance_id,completed=completed,cancelled=cancelled,image_url=image_url,age=age)

#appointments
@app.route('/appointments')
def appointments():
    spec = db.session.query(specilization).all()
    return render_template('booking.html',spec = [x['specilization'] for x in spec],dates=dates)

#select the doctor
@app.route('/doctor/<division>')
def test(division):
    final=[]
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="select Doctor.id,Doctor.first_name,Doctor.last_name from Doctor inner join doctor_Specilization on Doctor.specilization=doctor_Specilization.id where doctor_Specilization.specilization='{division}'".format(division=division)
        cur.execute(query)
        rows = cur.fetchall()
        for x in rows:
            docObj = {}
            docObj['id'] = str(x[0])
            docObj['name'] = str(x[1] +" "+ x[2])
            final.append(docObj)
        print(final)
        return jsonify({'doctorlist' : final})

#select timeslot
@app.route('/timeslot/<values>')
def timeslot(values):
    test=values.split(",")
    doctor=test[0]
    print(doctor)
    date_slot=test[1]
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="SELECT schedule.id, time(schedule.start_time) AS time_slot  FROM schedule WHERE date(schedule.start_time) = '{date_slot}' AND schedule.doctor_id = '{doct}' AND schedule.start_time > (SELECT datetime())  AND schedule.start_time NOT IN ( SELECT Appointments.start_time FROM Appointments WHERE Appointments.doctor_id ='{doct}'  AND date(Appointments.start_time)='{date_slot}')".format(doct=doctor,date_slot=date_slot)
        cur.execute(query)
        rows = cur.fetchall()
        time_slots = []
        for x in rows:
            docObj = {}
            docObj['id'] = str(x[0])
            docObj['time_slot'] = str(x[1])
            time_slots.append(docObj)
    return jsonify({'timeslot' : time_slots})

#saving appointment
@app.route('/saving_profile',methods=['GET','POST'])
def saving_appointment():
    date_created=str(datetime.now()).split(".")[0]
    patient_id=g.user.id
    doctor_id=request.form['doctor_select']
    patient_name=request.form['name']
    patient_contact=request.form['phone']
    appointment_date=request.form['appointment_date']
    appointment_time=request.form['time_slot']
    patient_message=request.form['message']
    patient_email=request.form['email']
    start_date_time = datetime.fromisoformat(appointment_date+" "+appointment_time)
    end_date_time = str(start_date_time+timedelta(hours=1))
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="insert into Appointments(date_created,patient_id,doctor_id,Patient_name,Patient_contact,start_time,end_time,canceled,patient_message,patient_email) values('{date_created}','{patient_id}','{doctor_id}','{patient_name}','{patient_contact}','{start_date_time}','{end_date_time}',0,'{patient_message}','{patient_email}')".format(date_created=date_created,patient_id=patient_id,doctor_id=str(doctor_id),patient_name=patient_name,patient_contact=patient_contact,start_date_time=str(start_date_time),end_date_time=end_date_time,patient_message=patient_message,patient_email=patient_email)
        cur.execute(query)

    #for sending email to patient
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="select first_name|| ' ' || last_name as doctor_name, doctor_Specilization.specilization as specilization from Doctor inner join doctor_Specilization on Doctor.specilization=doctor_Specilization.id where Doctor.id='{doctor_id}'".format(doctor_id=doctor_id)
        cur.execute(query)
        rows = cur.fetchall()
        for x in rows:
            doctor_name=x['doctor_name']
            doctor_specilization=x['specilization']
    msg = Message('Hurray,Booking Confirmed!', sender =("Avinash from PMS", 'avinashramesh2312@gmail.com'), recipients=[patient_email])
    msg.html = render_template('confirmation_email.html',patient_name=patient_name,start_date_time=start_date_time,appointment_date=appointment_date,appointment_time=appointment_time,doctor_name=doctor_name,doctor_specilization=doctor_specilization)
    mail.send(msg)
    return render_template('confirmation.html')

#update profile
@app.route('/update_profile',methods=['GET','POST'])
def update_profile():
        first_name=request.form['first_name']
        last_name=request.form['last_name']
        #email_id=request.form['email_id']
        phone=request.form['phone']
        insurance=request.form['insurance']
        location=request.form['location']
        insurance_id=request.form['insurance_id']
        age=request.form['age']
        with sqlite3.connect(DATABASE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            query="UPDATE Patient SET patient_name='{first_name}',patient_last_name='{last_name}',Phone='{phone}',Location='{location}',insurance_provider='{insurance}',insurance_id='{insurance_id}',Age='{age}' where id='{patient_id}'".format(patient_id=g.user.id,first_name=first_name,last_name=last_name,phone=phone,location=location,insurance=insurance,insurance_id=insurance_id,age=age)
            cur.execute(query)
        flash('Updates was successful')
        return redirect(url_for('profile'))

@app.route('/cancel_appointments',methods=['GET','POST'])
def cancel_appointments():
    date = request.form['get_date']
    reason=request.form['Cancel_Reason']
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="update Appointments set canceled=1,cancellation_reson='{reason}' where patient_id='{patient_id}' and start_time='{start_date}'".format(patient_id=g.user.id,start_date=date,reason=reason)
        cur.execute(query)
        patient_email="select patient_email,patient_name,start_time from Appointments where patient_id='{patient_id}' and start_time='{start_date}' and canceled=1".format(patient_id=g.user.id,start_date=date)
        cur.execute(patient_email)
        rows = cur.fetchall()
        for x in rows:
            patient_email = x['patient_email']
            patient_name = x['patient_name']
        doctor_details ="with temp as( select Appointments.doctor_id, Doctor.first_name|| ' ' || Doctor.last_name as doctor_name, Doctor.specilization  from Appointments  inner join Doctor on Appointments.doctor_id=Doctor.id  where  Appointments.patient_id='{patient_id}' and Appointments.start_time='{start_date}' and canceled=1) select doctor_name, doctor_Specilization.specilization from temp inner join doctor_Specilization where temp.specilization=doctor_Specilization.id;".format(patient_id=g.user.id,start_date=date)
        cur.execute(doctor_details)
        rows1 = cur.fetchall()
        for x in rows1:
            doctor_name = x['doctor_name']
            doctor_specilization=x['specilization']

    msg = Message('Ohh No,Your Booking has been Cancelled!', sender =("PMS Team", 'avinashramesh2312@gmail.com'), recipients=[patient_email])
    msg.html = render_template('cancellation_email.html',patient_name=patient_name,start_date_time=date, doctor_name=doctor_name, doctor_specilization=doctor_specilization, reason=reason)
    mail.send(msg)

    return redirect(url_for('dashboard'))

#doctor details
@app.route('/view_doctor')
def view_doctor():
    with sqlite3.connect(DATABASE) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        query="with temp as (SELECT doctor_id, avg(ratings) as average_ratings FROM doctor_ratings GROUP by doctor_id) select Doctor.first_name|| ' ' || Doctor.last_name as doctor_name,round(temp.average_ratings,2), doctor_Specilization.specilization from temp inner join doctor_Specilization on Doctor.specilization=doctor_Specilization.id inner join Doctor on temp.doctor_id=Doctor.id order by average_ratings desc;"
        cur.execute(query)
        rows = cur.fetchall()
    return render_template('view_doctor.html', value=rows)

#main function, run the app
if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=True, ssl_context='adhoc')
