from flask import Flask, render_template, url_for, request, redirect, flash, session
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import datetime
import hashlib
import requests
import random
import os


load_dotenv()
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
WEATHER_API_URL = os.getenv('WEATHER_API_URL')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

app.secret_key = "3ad82aa45292bf5c0a038ffc0c29b469dd71d73db45d047727c078b26c4b5127"

    
class account(db.Model):
    account_username = db.Column(db.String(20), primary_key=True)
    account_pwd = db.Column(db.String(256), nullable=False)
    score_table = db.relationship('score_table', back_populates='user')

class questions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(256))
    correct_answer = db.Column(db.String(256))
    options = db.relationship('question_options', back_populates='question')

class question_options(db.Model):
    question_id = db.Column(db.Integer, db.ForeignKey(questions.id) ,primary_key=True)
    option = db.Column(db.String(256), primary_key = True)
    question = db.relationship('questions', back_populates='options')

class score_table(db.Model):
    account_username = db.Column(db.String(20), db.ForeignKey(account.account_username, primary_key=True))
    score_time = db.Column(db.DateTime, primary_key=True, default=datetime.datetime.utcnow)
    score = db.Column(db.Integer, nullable=False)
    user = db.relationship('account', back_populates='score_table')

@app.route('/', methods=['POST', 'GET'])
def home():
    weather_info = {}
    city = ''
    date = datetime.date.today()
    day = date.strftime("%A")

    if request.method == 'POST':
        city = request.form['kota']
        print(city)

        try:
            res = requests.get(WEATHER_API_URL, params={'key' : WEATHER_API_KEY,'q': city, 'days':3})
            data = res.json()
            print(data['forecast']['forecastday'][1]['day']['condition'])
            city = data['location']['name']
            weather_info['current'] = data['current']['condition']
            weather_info['day_temp'] = data['forecast']['forecastday'][0]['hour'][12]['temp_c']
            weather_info['night_temp'] = data['forecast']['forecastday'][0]['hour'][20]['temp_c']
            weather_info['day_1'] = data['forecast']['forecastday'][0]['day']['condition']
            weather_info['day_2'] = data['forecast']['forecastday'][1]['day']['condition']
            weather_info['day_3'] = data['forecast']['forecastday'][2]['day']['condition']

            # weather_info = res['forecast'][0]['hour'][12]['condition']['text']
        except:
            return "Failed to get weather info"

    return render_template('beranda.html', weather_info = weather_info, city = city, date=date, day=day)

@app.route('/signin/', methods=['POST', 'GET'])
def signin():
    errorMessage = None
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        new_account = account(account_username = username, account_pwd=password)

        if account.query.filter_by(account_username=username).first() :
            errorMessage = "Username telah digunakan. Silakan gunakan username lain"
            return render_template('signin.html', errorMessage=errorMessage)

        try:
            db.session.add(new_account)
            db.session.commit()
            return redirect('/')
        except:
            return "Pendaftaran Gagal"

    return render_template('signin.html', errorMessage=errorMessage)

@app.route('/login/', methods=['POST', 'GET'])
def login():
    errorMessage = None
    if request.method == "POST":
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        if account.query.filter_by(account_username=username).first():
            if password == account.query.filter_by(account_username=username).first().account_pwd:
                session['username'] = username
                return redirect('/')
            else:
                return render_template('login.html', errorMessage="Password salah. Silakan coba lagi.")
        else:
            errorMessage = "Akun tidak ditemukan"
    return render_template('login.html', errorMessage=errorMessage)

@app.route('/logout/', methods=['POST', 'GET'])
def logout():
    try:
        session.pop("username", None)
    except:
        return "Gagal keluar"
    return redirect("/")

@app.route('/quiz/', methods=['POST', 'GET'])
def quiz():
    quiz = {}
    score = 0
    total_questions = 0
    qs = db.session.query(questions.id, questions.question_text, questions.correct_answer)
    quiz['questions'] = [row._asdict() for row in qs]
    random.shuffle(quiz['questions'])
    for q in quiz['questions']:
        opts = db.session.query(question_options.option).filter_by(question_id=q['id']).all()
        q['options'] = [opt.option for opt in opts]

    if request.method == 'POST':
        user_answers = {key: value for key, value in request.form.items()}
        score, total_questions = calculate_score(user_answers, quiz)

        new_score = score_table()
        new_score.account_username = session['username']
        new_score.score = score
        db.session.add(new_score)
        db.session.commit()


    return render_template('quiz.html', session=session, quiz=quiz['questions'], score=score, total_questions=total_questions)

def calculate_score(user_answers, quiz):
    score = 0
    total_questions = len(quiz['questions'])

    for question in quiz['questions']:
        question_id = question['id']
        user_answer = user_answers.get(str(question_id))
        if user_answer and user_answer == question['correct_answer']:
            score += 1

    return score, total_questions

@app.route('/leaderboard/')
def leaderboard():
    score_tables = []
    scores = db.session.query(score_table.account_username, score_table.score).order_by(score_table.score.desc()).all()
    score_tables = [row._asdict() for row in scores]
    return render_template('leaderboard.html', score_tables=score_tables)

@app.route('/add_question/', methods=['POST', 'GET'])
def add_question():
    new_question = questions()
    options = []
    if request.method == "POST":
        new_question.question_text = request.form['question']
        new_question.correct_answer = request.form['correct']
        options.append(request.form['option1'])
        options.append(request.form['option2'])
        options.append(request.form['option3'])
        options.append(request.form['option4'])
        try:
            db.session.add(new_question)
            db.session.commit()

            for option in options:
                new_option = question_options()
                new_option.option = option
                new_option.question_id = new_question.id

                db.session.add(new_option)
            
            db.session.commit()
                
        except:
            return "Gagal menambahkan pertanyaan"



    return render_template('addQuestion.html')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)